from rest_framework import generics, permissions, status, filters, viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.conf import settings

from apps.therapists.models import TherapistProfile, TherapistAvailability, TherapistRequest
from apps.therapists.serializers import (
    TherapistProfileSerializer,
    TherapistAvailabilitySerializer,
    TherapistRequestCreateSerializer,
    TherapistRequestListSerializer,
    TherapistRequestResponseSerializer,
    TherapistFilterSerializer
)
from apps.therapists.permissions import IsTherapist
from apps.core.utils import api_response
from apps.users.serializers import ConnectedPatientSerializer


# ✅ Public list of therapists (search, filter, sort)
class TherapistListView(generics.ListAPIView):
    queryset = TherapistProfile.objects.filter(is_active=True)
    serializer_class = TherapistProfileSerializer
    permission_classes = [permissions.AllowAny]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['specialties']
    search_fields = ['user__username', 'bio']
    ordering_fields = ['average_rating', 'session_fee']
    ordering = ['-average_rating']


# ✅ Public details of a specific therapist
class TherapistDetailView(generics.RetrieveAPIView):
    queryset = TherapistProfile.objects.filter(is_active=True)
    serializer_class = TherapistProfileSerializer
    permission_classes = [permissions.AllowAny]


# ✅ Therapist can view/update own profile
class TherapistProfileUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = TherapistProfileSerializer
    permission_classes = [IsTherapist]
    queryset = TherapistProfile.objects.all()

    def get_object(self):
        return TherapistProfile.objects.get(user=self.request.user)


# ✅ Therapist dashboard greeting (optional auth check)
class TherapistDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsTherapist]

    def get(self, request):
        return api_response(True, message="Welcome to your therapist dashboard.")


# ✅ Admin: manually verify therapist account
class VerifyTherapistView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        try:
            profile = TherapistProfile.objects.get(user_id=user_id)
            profile.verified = True
            profile.save()
            return api_response(True, message="Therapist verified successfully.")
        except TherapistProfile.DoesNotExist:
            return api_response(False, "Therapist not found.", status=status.HTTP_404_NOT_FOUND)


# ✅ Therapist manages availability slots
class TherapistAvailabilityViewSet(viewsets.ModelViewSet):
    serializer_class = TherapistAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TherapistAvailability.objects.filter(therapist=self.request.user.therapistprofile)

    def perform_create(self, serializer):
        serializer.save(therapist=self.request.user.therapistprofile)


# ✅ API to return top-rated therapists
class TherapistProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TherapistProfile.objects.filter(is_active=True, verified=True)
    serializer_class = TherapistProfileSerializer
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['get'], url_path='top-rated')
    def top_rated(self, request):
        limit = int(request.query_params.get('limit', 5))
        top_therapists = self.queryset.order_by('-average_rating')[:limit]
        serializer = self.get_serializer(top_therapists, many=True)
        return Response(serializer.data)


# ✅ Intelligent match-making
class FindMyTherapistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TherapistFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        filters = serializer.validated_data

        exact_qs = TherapistProfile.objects.filter(is_active=True)

        if 'gender' in filters:
            exact_qs = exact_qs.filter(gender=filters['gender'])

        if 'language' in filters:
            exact_qs = exact_qs.filter(languages__icontains=filters['language'])

        if 'specialization' in filters:
            exact_qs = exact_qs.filter(specialties__icontains=filters['specialization'])

        if 'min_experience' in filters:
            exact_qs = exact_qs.filter(experience__gte=filters['min_experience'])

        exact_matches = exact_qs.distinct()

        if not exact_matches.exists():
            suggestions = TherapistProfile.objects.filter(is_active=True).exclude(
                user=request.user
            )[:5]
            return Response({
                "matches": [],
                "suggested": TherapistProfileSerializer(suggestions, many=True).data
            })

        return Response({
            "matches": TherapistProfileSerializer(exact_matches, many=True).data,
            "suggested": []
        })


# ✅ Patient sends therapist request
class TherapistRequestCreateView(generics.CreateAPIView):
    serializer_class = TherapistRequestCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return TherapistRequest.objects.all()

    def perform_create(self, serializer):
        patient = self.request.user
        therapist = serializer.validated_data['therapist']

        if TherapistRequest.objects.filter(
            patient=patient,
            therapist=therapist,
            status='pending'
        ).exists():
            raise PermissionDenied("You already have a pending request with this therapist.")

        serializer.save(patient=patient)
        self.notify_therapist(therapist, patient)

    def notify_therapist(self, therapist_profile, patient_user):
        therapist_user = therapist_profile.user
        subject = "New Patient Request"
        message = (
            f"Dear {therapist_user.username},\n\n"
            f"You have a new connection request from {patient_user.username} ({patient_user.email}).\n"
            f"Please log in to your GRACE account to respond."
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [therapist_user.email],
            fail_silently=False,
        )


# ✅ Therapist views incoming requests
class TherapistRequestListView(generics.ListAPIView):
    serializer_class = TherapistRequestListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.user_type != 'therapist':
            return TherapistRequest.objects.none()

        return TherapistRequest.objects.filter(
            therapist__user=user
        ).order_by('-created_at')


# ✅ Therapist responds (accept/reject) to request
class TherapistRequestResponseView(generics.UpdateAPIView):
    serializer_class = TherapistRequestResponseSerializer
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = 'request_id'

    def get_queryset(self):
        user = self.request.user
        return TherapistRequest.objects.filter(therapist__user=user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data

        if request.user.user_type != 'therapist':
            raise PermissionDenied("Only therapists can respond to requests.")

        status_value = data.get('status')
        if status_value not in ['accepted', 'rejected']:
            return Response({'error': 'Invalid status value.'}, status=status.HTTP_400_BAD_REQUEST)

        instance.status = status_value
        instance.save()

        if status_value == 'accepted':
            patient_user = instance.patient
            therapist_user = instance.therapist.user

            if patient_user.connected_user_id:
                return Response({'error': 'Patient is already connected to a therapist.'}, status=400)

            patient_user.connected_user = therapist_user
            patient_user.save()
            self.notify_patient(patient_user, therapist_user)

        return Response({'detail': f'Request {status_value}.'}, status=200)

    def notify_patient(self, patient, therapist):
        subject = "Request Accepted"
        message = (
            f"Dear {patient.username},\n\n"
            f"Your request was accepted by therapist {therapist.username} ({therapist.email}).\n"
            f"You are now connected on GRACE and can begin chatting or booking sessions."
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [patient.email],
            fail_silently=False,
        )


# ✅ Therapist sees connected patients
class ConnectedPatientsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.user_type != 'therapist':
            raise PermissionDenied("Only therapists can view connected patients.")

        connected_patients = user.connected_clients.all()
        serializer = ConnectedPatientSerializer(connected_patients, many=True)
        return Response(serializer.data)
