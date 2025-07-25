from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count

from .models import TrainingExercise, AssignedTraining
from .serializers import (
    TrainingExerciseSerializer,
    AssignedTrainingSerializer,
    CreateAndAssignTrainingSerializer
)
from .permissions import IsTherapist, IsPatient


class TrainingExerciseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for TrainingExercise.
    Therapists can create new exercises.
    Patients can only list public exercises.
    Supports filters, search, and ordering.
    """
    queryset = TrainingExercise.objects.all()
    serializer_class = TrainingExerciseSerializer
    permission_classes = [IsAuthenticated]

    # Enable filtering, searching, and ordering
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'importance', 'is_public']
    search_fields = ['title', 'description']
    ordering_fields = ['importance', 'created_at']

    def get_permissions(self):
        # Per-action permission logic
        if self.action in ['create', 'assign_existing', 'create_and_assign']:
            return [IsAuthenticated(), IsTherapist()]
        elif self.action == 'self_assign':
            return [IsAuthenticated(), IsPatient()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'therapist' or user.is_staff:
            # Therapists see all trainings
            return TrainingExercise.objects.all()
        # Patients see only public trainings
        return TrainingExercise.objects.filter(is_public=True)

    def perform_create(self, serializer):
        # Therapist creates a training
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['post'], url_path='assign')
    def assign_existing(self, request):
        """
        Assign an existing training to a patient.
        Input: { "training_id": 5, "patient_id": 12 }
        """
        training_id = request.data.get('training_id')
        patient_id = request.data.get('patient_id')

        if not training_id or not patient_id:
            return Response(
                {"detail": "training_id and patient_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        training = TrainingExercise.objects.filter(id=training_id).first()
        if not training:
            return Response({"detail": "Training not found."}, status=status.HTTP_404_NOT_FOUND)

        assigned = AssignedTraining.objects.create(
            training=training,
            patient_id=patient_id,
            assigned_by=request.user
        )
        return Response(
            AssignedTrainingSerializer(assigned).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'], url_path='create-and-assign')
    def create_and_assign(self, request):
        """
        Create a new training AND assign it to a patient in one go.
        """
        serializer = CreateAndAssignTrainingSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save()
        return Response(
            serializer.to_representation(assignment),
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['post'], url_path='self-assign')
    def self_assign(self, request):
        """
        Patient self-assigns a public training.
        Input: { "training_id": 7 }
        """
        training_id = request.data.get('training_id')
        training = TrainingExercise.objects.filter(id=training_id, is_public=True).first()
        if not training:
            return Response(
                {"detail": "Training not found or not public."},
                status=status.HTTP_404_NOT_FOUND
            )

        assigned = AssignedTraining.objects.create(
            training=training,
            patient=request.user,
            assigned_by=None
        )
        return Response(
            AssignedTrainingSerializer(assigned).data,
            status=status.HTTP_201_CREATED
        )


class AssignedTrainingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing assigned trainings.
    Therapists see only the trainings they assigned.
    Patients see only their own assigned trainings.
    """
    serializer_class = AssignedTrainingSerializer
    permission_classes = [IsAuthenticated]

    # Enable filtering by patient (therapist only) or status
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'patient']
    ordering_fields = ['updated_at', 'status']

    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'therapist' or user.is_staff:
            # Therapists see only assignments they assigned
            return AssignedTraining.objects.filter(assigned_by=user)
        # Patients see only their own assigned trainings
        return AssignedTraining.objects.filter(patient=user)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Only the patient who owns it OR the therapist who assigned it can update
        if not (
            (getattr(request.user, 'is_therapist', False) and instance.assigned_by == request.user)
            or instance.patient == request.user
        ):
            return Response(
                {"detail": "You do not have permission to modify this record."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=['get'], url_path='progress-stats')
    def progress_stats(self, request):
        """
        Return a count of assignments by status for the current user (therapist or patient).
        """
        user = request.user
        if user.user_type == 'therapist':
            qs = AssignedTraining.objects.filter(assigned_by=user)
        else:
            qs = AssignedTraining.objects.filter(patient=user)

        stats = qs.values('status').annotate(count=Count('id'))
        return Response(stats)
