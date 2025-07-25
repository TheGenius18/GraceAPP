
import uuid
from rest_framework import viewsets, permissions, status, mixins
from rest_framework.decorators import action,api_view,permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from apps.users.models import CustomUser
from .models import Appointment, AppointmentFeedback, AppointmentLog
from .serializers import AppointmentSerializer, AppointmentLogSerializer, AppointmentFeedbackSerializer
from .utils import log_action
from apps.therapists.models import TherapistProfile, TherapistAvailability
from django.utils.timezone import now
from datetime import datetime, timedelta, time
from rest_framework.permissions import IsAdminUser
from apps.appointments.models import Appointment, ReminderLog
from apps.notifications.utils import notify_user
from django.utils.timezone import now
from django.utils.timezone import make_aware
CANCELLATION_WINDOW_HOURS = 6

class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [IsAuthenticated]


    def get_queryset(self):
        user = self.request.user
        filter_type = self.request.query_params.get('filter')

        # Role-based visibility
        if user.user_type == 'admin':
            queryset = Appointment.objects.all()
        elif user.user_type == 'therapist':
            queryset = Appointment.objects.filter(therapist=user.therapistprofile)
        else:
            queryset = Appointment.objects.filter(patient=user)

        # Filters
        if filter_type == 'cancelled':
            queryset = queryset.filter(status='cancelled')
        elif filter_type == 'upcoming':
            queryset = queryset.exclude(status='cancelled').filter(scheduled_at__gte=now())
        elif filter_type == 'past':
            queryset = queryset.filter(scheduled_at__lt=now())
        else:
            queryset = queryset.exclude(status='cancelled')
        filter_recurring = self.request.query_params.get('recurring')
        if filter_recurring == 'true':
            queryset = queryset.filter(is_recurring=True)
        elif filter_recurring == 'false':
            queryset = queryset.filter(is_recurring=False)

        # Optional: filter by recurring group
        recurring_group = self.request.query_params.get('group')
        if recurring_group:
            queryset = queryset.filter(recurring_group=recurring_group)

        return queryset.order_by('scheduled_at')



    def perform_create(self, serializer):
        appointment = serializer.save(patient=self.request.user)
        
        notify_user(
            appointment.therapist.user,
            f"[New Request] {appointment.patient.username} has requested a session scheduled at {appointment.scheduled_at.strftime('%Y-%m-%d %H:%M')}."
        )
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reschedule(self, request, pk=None):
        appointment = self.get_object()

        if appointment.patient != request.user:
            return Response({"detail": "You cannot reschedule this appointment."}, status=403)

        new_time_raw = request.data.get('scheduled_at')
        if not new_time_raw or not isinstance(new_time_raw, str):
            return Response({"detail": "scheduled_at must be provided as an ISO string."}, status=400)

        new_time = parse_datetime(new_time_raw)
        if new_time is None:
            return Response({"detail": "Invalid datetime format."}, status=400)

        appointment.scheduled_time = new_time
        appointment.status = 'rescheduled'
        appointment.save()

        log_action(appointment, request.user, "Rescheduled")
        notify_user(
            appointment.therapist.user,
            f"[Rescheduled] {appointment.patient.username} has rescheduled the session to {appointment.scheduled_time.strftime('%Y-%m-%d %H:%M')}."
        )
        notify_user(
            appointment.patient,
            f"[Rescheduled] Your session has been updated to {appointment.scheduled_time.strftime('%Y-%m-%d %H:%M')}."
        )

        return Response({"detail": "Appointment rescheduled successfully."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_status(self, request, pk=None):
        user = request.user
        new_status = request.data.get('status')
        allowed_statuses = ['completed', 'cancelled', 'no_show']

        if new_status not in allowed_statuses:
            return Response({'error': 'Invalid status'}, status=400)

        if user.user_type == 'therapist':
            queryset = Appointment.objects.filter(therapist__user=user)
        else:
            queryset = Appointment.objects.filter(patient=user)

        appointment = get_object_or_404(queryset, id=pk)
        appointment.status = new_status
        appointment.save()

        log_action(appointment, user, f"Status changed to {new_status}")
        return Response({'detail': f'Appointment marked as {new_status}'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='logs')
    def get_logs(self, request, pk=None):
        user = request.user

        if user.user_type == 'therapist':
            queryset = Appointment.objects.filter(therapist__user=user)
        else:
            queryset = Appointment.objects.filter(patient=user)

        appointment = get_object_or_404(queryset, id=pk)
        logs = AppointmentLog.objects.filter(appointment=appointment).order_by('-timestamp')
        serializer = AppointmentLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], url_path='confirm')
    def confirm_appointment(self, request, pk=None):
        user = request.user

        if user.user_type != 'therapist':
            return Response({"error": "Only therapists can confirm appointments."}, status=403)

        therapist_profile = get_object_or_404(TherapistProfile, user=user)
        appointment = get_object_or_404(Appointment, therapist=therapist_profile, id=pk)

        if appointment.status != 'pending':
            return Response({"error": "Only pending appointments can be confirmed."}, status=400)

        appointment.status = 'confirmed'
        appointment.save()

        log_action(appointment, user, "Appointment confirmed")
        notify_user(
            appointment.patient,
            f"[Confirmed] Your session with {appointment.therapist.user.username} is confirmed for {appointment.scheduled_at.strftime('%Y-%m-%d %H:%M')}."
        )
        return Response({"detail": "Appointment confirmed successfully."}, status=status.HTTP_200_OK)
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        user = request.user
        queryset = self.get_queryset()
        appointment = get_object_or_404(queryset, id=pk)

        if appointment.status == 'cancelled':
            return Response({"detail": "Appointment already cancelled."}, status=400)

        if user != appointment.patient and user != appointment.therapist:
            return Response({"detail": "You are not allowed to cancel this appointment."}, status=403)

        time_diff = appointment.scheduled_at - now()
        if time_diff < timedelta(hours=CANCELLATION_WINDOW_HOURS):
            return Response({"detail": f"Cannot cancel within {CANCELLATION_WINDOW_HOURS} hours of appointment."}, status=400)

        appointment.status = 'cancelled'
        appointment.save()

        log_action(appointment, user, "Cancelled appointment")
        notify_user(
            appointment.patient,
            f"[Cancelled] Your session scheduled at {appointment.scheduled_at.strftime('%Y-%m-%d %H:%M')} has been cancelled by {user.username}."
        )
        notify_user(
            appointment.therapist.user,
            f"[Cancelled] Your session with {appointment.patient.username} at {appointment.scheduled_at.strftime('%Y-%m-%d %H:%M')} has been cancelled."
        )
        return Response({"detail": "Appointment cancelled successfully."}, status=status.HTTP_200_OK)
    @action(detail=True, methods=['get'], url_path='status', permission_classes=[IsAuthenticated])
    def get_status(self, request, pk=None):
        # Don't filter cancelled appointments here
        try:
            appointment = Appointment.objects.get(pk=pk)
        except Appointment.DoesNotExist:
            return Response({"detail": "Appointment not found."}, status=404)
    
        # Only allow patient or therapist to view
        user = request.user
        if appointment.patient != user and appointment.therapist != getattr(user, 'therapistprofile', None):
            return Response({"detail": "You do not have permission to view this appointment."}, status=403)
    
        return Response({
            "id": appointment.id,
            "status": appointment.status,
            "scheduled_at": appointment.scheduled_at,
            "therapist": appointment.therapist.user.username,
            "patient": appointment.patient.username
        })

    @action(detail=True, methods=['get', 'post'], permission_classes=[IsAuthenticated])
    def feedback(self, request, pk=None):
        appointment = self.get_object()

        if request.method == 'GET':
            feedback = AppointmentFeedback.objects.filter(appointment=appointment).first()
            if not feedback:
                return Response({"detail": "No feedback submitted."}, status=404)
            serializer = AppointmentFeedbackSerializer(feedback)
            return Response(serializer.data)

        # POST feedback logic
        if appointment.patient != request.user:
            return Response({"detail": "Only the patient can submit feedback."}, status=403)

        if appointment.status != 'completed':
            return Response({"detail": "You can only rate completed appointments you attended."}, status=400)

        if hasattr(appointment, 'feedback'):
            return Response({"detail": "Feedback already submitted."}, status=400)

        serializer = AppointmentFeedbackSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(appointment=appointment, patient=request.user)
            log_action(appointment, request.user, "Feedback submitted")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    @action(detail=False, methods=["post"], url_path="recurring", permission_classes=[IsAuthenticated])
    def create_recurring(self, request):
        user = request.user
        data = request.data

        patient_id = data.get("patient_id")
        therapist_id = data.get("therapist_id") or (user.therapistprofile.id if user.user_type == "therapist" else None)
        start_date_str = data.get("start_date")
        repeat = data.get("repeat", "weekly").lower()
        occurrences = int(data.get("occurrences", 1))
        duration = int(data.get("duration_minutes", 60))

        if not all([patient_id, therapist_id, start_date_str]):
            return Response({"error": "Missing required fields."}, status=400)

        try:
            start_datetime = parse_datetime(start_date_str)
            if not start_datetime:
                raise ValueError("Invalid date format.")
        except Exception:
            return Response({"error": "Invalid start_date format. Use ISO 8601 format."}, status=400)

        try:
            therapist = TherapistProfile.objects.get(id=therapist_id)
        except TherapistProfile.DoesNotExist:
            return Response({"error": "Therapist not found."}, status=404)

        try:
            patient = CustomUser.objects.get(id=patient_id, user_type="patient")
        except CustomUser.DoesNotExist:
            return Response({"error": "Patient not found."}, status=404)

        if user.user_type == "therapist" and therapist.user != user:
            return Response({"error": "You can't create sessions for another therapist."}, status=403)

        delta = timedelta(weeks=1) if repeat == "weekly" else timedelta(days=1)

        group_id = uuid.uuid4()  # 🔁 assign same group to all
    
        created_ids = []
        for i in range(occurrences):
            scheduled_at = start_datetime + i * delta
            appointment = Appointment.objects.create(
                patient=patient,
                therapist=therapist,
                scheduled_at=scheduled_at,
                duration_minutes=duration,
                status="pending",
                is_recurring=True,
                recurring_group=group_id
            )
            created_ids.append(appointment.id)
        notify_user(
            therapist.user,
            f"[Recurring Session] New session scheduled with {patient.username} on {scheduled_at.strftime('%Y-%m-%d %H:%M')}."
        )
        return Response({
            "message": f"{len(created_ids)} recurring appointments created.",
            "appointments": created_ids,
            "group_id": str(group_id)
        }, status=201)
    @action(detail=False, methods=["delete"], url_path="recurring/(?P<group_id>[0-9a-f-]+)")
    def cancel_recurring_group(self, request, group_id):
        user = request.user
    
        try:
            group_uuid = uuid.UUID(group_id)
        except ValueError:
            return Response({"error": "Invalid group_id format."}, status=status.HTTP_400_BAD_REQUEST)
    
        # Filter all appointments in this group
        appointments = Appointment.objects.filter(recurring_group=group_uuid)
    
        if not appointments.exists():
            return Response({"error": "No appointments found for this group."}, status=status.HTTP_404_NOT_FOUND)
    
        # Access control:
        if user.user_type == "therapist":
            appointments = appointments.filter(therapist=user.therapistprofile)
        elif user.user_type == "admin":
            pass  # admin can access all
        else:
            return Response({"error": "Only therapists or admin can cancel recurring appointments."},
                            status=status.HTTP_403_FORBIDDEN)
    
        count = appointments.update(status="cancelled")
    
        return Response({"message": f"{count} appointments cancelled."}, status=status.HTTP_200_OK)
    


    @action(detail=False, methods=["get"], url_path=r"therapists/(?P<therapist_id>\d+)/available-slots")
    def available_slots(self, request, therapist_id):
        date_str = request.query_params.get("date")
        if not date_str:
            return Response({"error": "Missing ?date=YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            therapist_user = CustomUser.objects.get(id=therapist_id, user_type="therapist")
            profile = therapist_user.therapistprofile
        except CustomUser.DoesNotExist:
            return Response({"error": "Therapist not found."}, status=status.HTTP_404_NOT_FOUND)
        except TherapistProfile.DoesNotExist:
            return Response({"error": "Therapist profile not found."}, status=status.HTTP_404_NOT_FOUND)

        work_start = profile.available_from
        work_end = profile.available_to
        slot_duration = 60  # minutes

        start_datetime = make_aware(datetime.combine(date_obj, work_start))
        end_datetime = make_aware(datetime.combine(date_obj, work_end))

        appointments = Appointment.objects.filter(
            therapist=profile,
            scheduled_at__range=(start_datetime, end_datetime)
        )

        booked_times = set(appt.scheduled_at.time() for appt in appointments)

        available_slots = []
        current_time = start_datetime
        while current_time + timedelta(minutes=slot_duration) <= end_datetime:
            if current_time.time() not in booked_times:
                available_slots.append({
                    "start": current_time.strftime("%H:%M"),
                    "end": (current_time + timedelta(minutes=slot_duration)).strftime("%H:%M")
                })
            current_time += timedelta(minutes=slot_duration)

        return Response({
            "date": date_str,
            "therapist_id": therapist_id,
            "available_slots": available_slots
        })
    
    @action(detail=True, methods=["post"], url_path=r"trigger-reminder", permission_classes=[IsAdminUser])
    def trigger_reminder(self, request, pk=None):
        try:
            appt = self.get_object()
        except Appointment.DoesNotExist:
            return Response({"error": "Appointment not found."}, status=status.HTTP_404_NOT_FOUND)

        reminder_type = request.data.get('type', '1h')
        if reminder_type not in ['1h', '15m']:
            return Response({"error": "Reminder type must be '1h' or '15m'."}, status=status.HTTP_400_BAD_REQUEST)

        message = f"Reminder: Your session is scheduled at {appt.scheduled_at.strftime('%H:%M')}."
        if reminder_type == '15m':
            message = f"Reminder: Your session starts in 15 minutes at {appt.scheduled_at.strftime('%H:%M')}."

        notify_user(appt.patient, f"[Patient Reminder] {message}")
        notify_user(appt.therapist.user, f"[Therapist Reminder] {message}")

        ReminderLog.objects.create(appointment=appt, reminder_type=reminder_type, sent_to=appt.patient.email)
        ReminderLog.objects.create(appointment=appt, reminder_type=reminder_type, sent_to=appt.therapist.user.email)

        return Response({"message": f"{reminder_type} reminder sent for appointment #{appt.id}"}, status=200)

    @action(detail=True, methods=["post"], url_path="check-in", permission_classes=[IsAuthenticated])
    def check_in(self, request, pk=None):
        appointment = self.get_object()

        if request.user != appointment.patient:
            return Response({"error": "Only the patient can check in."}, status=403)

        appointment.checked_in = True
        appointment.save()

        return Response({"message": f"Patient checked in for appointment #{appointment.id}."}, status=200)
    
    @action(detail=True, methods=["post"], url_path="resend-confirmation", permission_classes=[IsAuthenticated])
    def resend_confirmation(self, request, pk=None):
        appointment = self.get_object()

        # Optional: restrict to patient or admin only
        if request.user != appointment.patient and not request.user.is_staff:
            return Response({"error": "Not authorized."}, status=403)

        message = f"Your session is confirmed at {appointment.scheduled_at.strftime('%H:%M')} on {appointment.scheduled_at.date()}."

        notify_user(appointment.patient, f"[Confirmation] {message}")
        notify_user(appointment.therapist.user, f"[Confirmation] {message}")

        # Log this action
        ReminderLog.objects.create(appointment=appointment, reminder_type='confirm', sent_to=appointment.patient.email)
        ReminderLog.objects.create(appointment=appointment, reminder_type='confirm', sent_to=appointment.therapist.user.email)

        return Response({"message": f"Confirmation resent for appointment #{appointment.id}"}, status=200)
class AdminAnalyticsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        total_appointments = Appointment.objects.count()
        status_counts = Appointment.objects.values('status').annotate(count=Count('id'))
        therapists = TherapistProfile.objects.all()

        therapist_data = []
        for therapist in therapists:
            total_sessions = Appointment.objects.filter(therapist=therapist).count()
            completed_sessions = Appointment.objects.filter(therapist=therapist, status='completed').count()
            available_slots = TherapistAvailability.objects.filter(therapist=therapist).count()
            utilization = (total_sessions / available_slots) * 100 if available_slots else 0

            therapist_data.append({
                'therapist_id': therapist.id,
                'name': therapist.user.username,
                'sessions': total_sessions,
                'completed': completed_sessions,
                'availability_slots': available_slots,
                'utilization_percent': round(utilization, 2),
            })

        return Response({
            'total_appointments': total_appointments,
            'status_breakdown': status_counts,
            'therapist_summary': therapist_data
        })

class TherapistRatingAnalytics(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        ratings = AppointmentFeedback.objects.values('appointment__therapist')\
            .annotate(avg_rating=Avg('rating'))

        return Response(ratings)








