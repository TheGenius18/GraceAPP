from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.mood.tasks import notify_after_delay
from apps.notifications.utils import notify_user  # adjust path to your file
from .utils import message_for_mood
from .models import MoodLog
from .serializers import MoodLogSerializer
from apps.training.models import AssignedTraining
from datetime import timedelta
from django.utils import timezone
from apps.mood import serializers  # to check therapist–patient relation if needed
from rest_framework.exceptions import ValidationError
class MoodLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for MoodLog:
    - Patients can create logs and view their own history.
    - Therapists can view logs of patients they are assigned to.
    """
    serializer_class = MoodLogSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # If therapist → show only logs for patients assigned by this therapist
        if user.user_type == 'therapist':
            patient_ids = AssignedTraining.objects.filter(assigned_by=user).values_list('patient_id', flat=True)
            return MoodLog.objects.filter(patient_id__in=patient_ids)
        # Else (patient) → show only their own mood logs
        return MoodLog.objects.filter(patient=user)

    def perform_create(self, serializer):
        user = self.request.user
    
        # Only patients can create
        if user.user_type != 'patient':
            raise ValidationError("Only patients can log moods.")
    
        # ✅ Check last mood log within 12 hours
        twelve_hours_ago = timezone.now() - timedelta(hours=12)
        recent_log = user.mood_logs.filter(created_at__gte=twelve_hours_ago).order_by('-created_at').first()
    
        if recent_log:
            raise ValidationError(
                {"detail": f"You can only log your mood once every 12 hours. Last log was at {recent_log.created_at}."}
            )
    
        # ✅ Save new mood log
        mood_log = serializer.save(patient=user)
    
        # ✅ Immediate notification
        message = message_for_mood(mood_log.mood)
        notify_user(user, message, title="Mood Logged ✅")
    
        # ✅ Schedule follow-up if needed
        if mood_log.mood == 'sad':
            notify_after_delay.apply_async(args=[mood_log.id], countdown=12 * 3600)  