from rest_framework import serializers
from apps.therapists.models import TherapistAvailability, TherapistProfile  # ✅ Corrected import
from apps.appointments.models import AppointmentFeedback
from apps.appointments.serializers import AppointmentFeedbackSerializer
from apps.users.models import CustomUser
from .models import TherapistRequest
class TherapistProfileSerializer(serializers.ModelSerializer):
    profile_photo = serializers.ImageField(required=False)
    languages = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    user = serializers.SerializerMethodField()  # ✅ Include user info as nested dict

    class Meta:
        model = TherapistProfile
        fields = [
            'user',
            'bio',
            'specialties',
            'rating',
            'is_active',
            'session_fee',
            'gender',
            'languages',
            'timezone',
            'verified',
            'profile_photo',
            'notify_on_booking',
            'notify_on_cancellation',
            'available_from',
            'available_to',
            'experience'
        ]
        read_only_fields = ['rating', 'verified']

    def get_user(self, obj):
        if obj.user:
            return {
                "id": obj.user.id,
                "name": obj.user.get_full_name() or obj.user.username,
                "email": obj.user.email
            }
        return None



class TherapistAvailabilitySerializer(serializers.ModelSerializer):
    average_rating = serializers.DecimalField(max_digits=3, decimal_places=2, read_only=True)
    latest_feedbacks = serializers.SerializerMethodField()
    class Meta:
        model = TherapistProfile
        fields = [
            'id', 'user', 'bio', 'specialties', 'gender', 'session_fee',
            'average_rating', 'latest_feedbacks', 'languages', 'timezone',
            'profile_photo', 'is_active', 'verified',
            'notify_on_booking', 'notify_on_cancellation','available_from', 'available_to' 
        ]
        read_only_fields = ['average_rating', 'latest_feedbacks']
    def get_latest_feedbacks(self, obj):
        feedbacks = AppointmentFeedback.objects.filter(appointment__therapist=obj).order_by('-submitted_at')[:5]
        return AppointmentFeedbackSerializer(feedbacks, many=True).data    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['therapist'] = user.therapistprofile
        return super().create(validated_data)
    
class TherapistFilterSerializer(serializers.Serializer):
    gender = serializers.ChoiceField(choices=[('male', 'Male'), ('female', 'Female')], required=False)
    language = serializers.CharField(required=False)
    specialization = serializers.CharField(required=False)
    min_experience = serializers.IntegerField(required=False, min_value=0)



# 1. Create Therapist Request (Patient sends it)
class TherapistRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TherapistRequest
        fields = ['therapist']

    def validate(self, data):
        user = self.context['request'].user
        if user.user_type != 'patient':
            raise serializers.ValidationError("Only patients can send therapist requests.")

        # Prevent duplicate requests
        if TherapistRequest.objects.filter(patient=user, therapist=data['therapist']).exists():
            raise serializers.ValidationError("You have already requested this therapist.")
        return data

    def create(self, validated_data):
        validated_data['patient'] = self.context['request'].user
        return TherapistRequest.objects.create(**validated_data)

# 2. Accept/Reject Therapist Request (Therapist responds)
class TherapistRequestResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TherapistRequest
        fields = ['status']

    def validate_status(self, value):
        if value not in ['accepted', 'rejected']:
            raise serializers.ValidationError("Status must be 'accepted' or 'rejected'.")
        return value
    


class TherapistRequestListSerializer(serializers.ModelSerializer):
    patient = serializers.SerializerMethodField()

    class Meta:
        model = TherapistRequest
        fields = ['id', 'patient', 'status', 'created_at']

    def get_patient(self, obj):
        profile = getattr(obj.patient, 'patientprofile', None)
        return {
            "id": obj.patient.id,
            "name": obj.patient.get_full_name() or obj.patient.username,
            "email": obj.patient.email,
            "phone": getattr(profile, 'phone_number', None),
            "age": getattr(profile, 'age', None),
            "gender": getattr(profile, 'gender', None),
            "timezone": getattr(profile, 'timezone', None),
            "bio": getattr(profile, 'bio', None),
        }


