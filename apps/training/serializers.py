from rest_framework import serializers
from .models import TrainingExercise, AssignedTraining

class TrainingExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingExercise
        fields = [
            'id',
            'title',
            'description',
            'category',
            'importance',
            'created_by',
            'is_public',
            'created_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at']


class AssignedTrainingSerializer(serializers.ModelSerializer):
    training = TrainingExerciseSerializer(read_only=True)
    training_id = serializers.PrimaryKeyRelatedField(
        queryset=TrainingExercise.objects.all(), source='training', write_only=True
    )

    class Meta:
        model = AssignedTraining
        fields = [
            'id',
            'training',
            'training_id',
            'patient',
            'assigned_by',
            'status',
            'progress_notes',
            'updated_at',
        ]
        read_only_fields = ['id', 'assigned_by', 'updated_at']
class CreateAndAssignTrainingSerializer(serializers.Serializer):
    # Training fields
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    category = serializers.CharField(required=False, allow_blank=True)
    importance = serializers.IntegerField(default=0)
    is_public = serializers.BooleanField(default=False)
    # Patient to assign to
    patient_id = serializers.IntegerField()

    def create(self, validated_data):
        therapist = self.context['request'].user
        patient_id = validated_data.pop('patient_id')

        # Create training
        training = TrainingExercise.objects.create(
            created_by=therapist,
            **validated_data
        )

        # Assign to patient
        assignment = AssignedTraining.objects.create(
            training=training,
            patient_id=patient_id,
            assigned_by=therapist,
            status='assigned'
        )
        return assignment

    def to_representation(self, instance):
        return AssignedTrainingSerializer(instance).data
