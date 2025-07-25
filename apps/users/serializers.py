from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q

from apps.therapists.models import TherapistProfile
from apps.users.models import CustomUser

User = get_user_model()


# -------------------------------
# Register Serializer
# -------------------------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    user_type = serializers.ChoiceField(choices=User.USER_TYPE_CHOICES, required=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'password', 'user_type', 'first_name', 'last_name']
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user_type = validated_data.get('user_type', 'patient')

        # Create and save the user
        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # Create therapist profile if applicable
        if user_type == 'therapist' and not TherapistProfile.objects.filter(user=user).exists():
            TherapistProfile.objects.create(user=user)

        # Send email verification link
        if not user.is_verified:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email/?uid={uid}&token={token}"

            send_mail(
                subject="Verify your email",
                message=f"Hi {user.first_name},\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nThank you,\nGRACE Team",
                from_email="no-reply@graceapp.local",
                recipient_list=[user.email],
            )

        return user


# -------------------------------
# User Serializer
# -------------------------------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'user_type']
        read_only_fields = ['id', 'email', 'user_type']


# -------------------------------
# Login Serializer
# -------------------------------
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # Can be email or username
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        identifier = attrs.get('identifier')
        password = attrs.get('password')
    
        if not identifier or not password:
            raise serializers.ValidationError({"detail": "Both identifier and password are required."})
    
        # Try to fetch user by email or username
        try:
            user = User.objects.get(Q(email__iexact=identifier) | Q(username__iexact=identifier))
        except User.DoesNotExist:
            raise serializers.ValidationError({"detail": "Invalid credentials."})
    
        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError({"detail": "Invalid credentials."})
    
        # Check verification status
        if not user.is_verified and not user.is_superuser:
            raise serializers.ValidationError({"detail": "Email not verified. Please check your inbox."})
    
        attrs['user'] = user
    
        # ✅ Include therapist_profile_id if therapist
        if user.user_type == 'therapist':
            try:
                therapist_profile = TherapistProfile.objects.get(user=user)
                attrs['therapist_profile_id'] = therapist_profile.id
            except TherapistProfile.DoesNotExist:
                attrs['therapist_profile_id'] = None
    
        return attrs


class ConnectedPatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'is_verified']
        

class FCMTokenUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['fcm_token']