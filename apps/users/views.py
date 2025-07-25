from django.conf import settings
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import LoginAudit
from rest_framework import viewsets, status
from django.utils.timezone import now
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from apps.users.serializers import FCMTokenUpdateSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework.decorators import action
from apps.users.models import CustomUser
from apps.users.serializers import LoginSerializer, RegisterSerializer, UserSerializer
from apps.therapists.models import TherapistProfile
from apps.core.utils import api_response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
User = get_user_model()


# -------------------------------
# Register a New User
# -------------------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        therapist_profile_id = serializer.validated_data.get('therapist_profile_id')

        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "user_type": user.user_type,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "therapist_profile_id": therapist_profile_id  # ✅ الجديد
            }
        }, status=status.HTTP_200_OK)
# View User Profile
# -------------------------------
class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return api_response(True, data=serializer.data, message="User profile fetched successfully")


# -------------------------------
# Update User Profile
# -------------------------------
class UserUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return api_response(True, data=serializer.data, message="Profile updated successfully")
        return api_response(False, serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -------------------------------
# Password Reset OTP Throttling
# -------------------------------
class PasswordResetRequestThrottle(UserRateThrottle):
    rate = '3/hour'


# -------------------------------
# Request Password Reset OTP
# -------------------------------
@method_decorator(csrf_exempt, name='dispatch')
class PasswordResetRequestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PasswordResetRequestThrottle]

    def post(self, request):
        user = request.user
        otp = get_random_string(length=6, allowed_chars='0123456789')
        cache.set(f"otp_{user.email}", otp, timeout=300)

        try:
            send_mail(
                subject="Your Password Reset OTP",
                message=f"Your OTP for password reset is: {otp}",
                from_email="no-reply@graceapp.local",
                recipient_list=[user.email],
            )
            return api_response(True, message="OTP sent successfully")
        except Exception as e:
            return api_response(False, f"Failed to send OTP: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# -------------------------------
# Confirm Password Reset with OTP
# -------------------------------
class PasswordResetConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')

        cached_otp = cache.get(f"otp_{user.email}")
        if not cached_otp or otp != cached_otp:
            return api_response(False, "Invalid OTP provided. Please try again.", status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user)
            user.set_password(new_password)
            user.save()
            cache.delete(f"otp_{user.email}")
            return api_response(True, message="Password updated successfully")
        except Exception as e:
            return api_response(False, str(e), status=status.HTTP_400_BAD_REQUEST)


# -------------------------------
# User Logout (JWT Token Blacklist)
# -------------------------------
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return api_response(False, "Refresh token is required.", status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return api_response(True, message="Logout successful")
        except Exception as e:
            return api_response(False, f"Logout failed: {str(e)}", status=status.HTTP_400_BAD_REQUEST)


# -------------------------------
# Resend OTP for Password Reset
# -------------------------------
class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()
        if not user:
            return api_response(False, "User not found", status=status.HTTP_404_NOT_FOUND)

        otp = get_random_string(length=6, allowed_chars='1234567890')
        cache.set(f"otp_{user.email}", otp, timeout=300)

        try:
            send_mail(
                subject="Your OTP",
                message=f"Your new OTP is {otp}",
                from_email="noreply@graceapp.com",
                recipient_list=[user.email]
            )
            return api_response(True, message="OTP resent to your email")
        except Exception as e:
            return api_response(False, f"Failed to resend OTP: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# -------------------------------
# Verify Email View
# -------------------------------
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = []  #  Disable throttling

    def get(self, request):
        uidb64 = request.query_params.get('uid')
        token = request.query_params.get('token')

        if not uidb64 or not token:
            return api_response(False, "Missing UID or token", status=400)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)

            if user.is_verified:
                return api_response(True, message="Email is already verified.")

            if default_token_generator.check_token(user, token):
                user.is_verified = True
                user.save()
                return api_response(True, message="Email verified successfully.")
            else:
                return api_response(False, "Invalid or expired token.", status=400)

        except (User.DoesNotExist, ValueError, TypeError):
            return api_response(False, "Invalid verification link.", status=400)


# -------------------------------
# Resend Verification Email
# -------------------------------
class ResendVerificationEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return api_response(False, "Email is required.", status=400)

        try:
            user = User.objects.get(email=email)

            if user.is_verified:
                return api_response(True, message="Email is already verified.")

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email/?uid={uid}&token={token}"

            send_mail(
                subject="Verify your email",
                message=f"Hi {user.first_name},\n\nPlease verify your email by clicking the link below:\n{verify_url}\n\nThank you,\nGRACE Team",
                from_email="no-reply@graceapp.local",
                recipient_list=[user.email],
            )

            return api_response(True, message="Verification email resent successfully.")
        except User.DoesNotExist:
            return api_response(False, "User with this email does not exist.", status=404)


def log_event(request, user, event):
    ip = get_client_ip(request)
    LoginAudit.objects.create(user=user, event=event, ip_address=ip)

def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0]
    return request.META.get('REMOTE_ADDR')



class UpdateFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        if 'fcm_token' not in request.data:
            return Response(
                {"detail": "fcm_token is required in the request body."},
                status=400
            )

        serializer = FCMTokenUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "FCM token updated successfully!"}, status=200)



@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])  # 👈 يمكن تعديلها لو تريد السماح لأنواع مستخدمين أخرى
def connect_patient_to_therapist(request):
    patient_id = request.data.get('patient_id')
    therapist_id = request.data.get('therapist_id')

    if not patient_id or not therapist_id:
        return Response({"detail": "patient_id and therapist_id are required."},
                        status=status.HTTP_400_BAD_REQUEST)

    # تحقق من وجود المريض
    try:
        patient = User.objects.get(id=patient_id, user_type='patient')
    except User.DoesNotExist:
        return Response({"detail": "Patient not found or not a patient."},
                        status=status.HTTP_404_NOT_FOUND)

    # تحقق من وجود المعالج
    try:
        therapist = User.objects.get(id=therapist_id, user_type='therapist')
    except User.DoesNotExist:
        return Response({"detail": "Therapist not found or not a therapist."},
                        status=status.HTTP_404_NOT_FOUND)

    # تحديث الربط
    patient.connected_user_id = therapist.id
    patient.save()

    return Response({
        "detail": "Patient connected to therapist successfully.",
        "patient_id": patient.id,
        "therapist_id": therapist.id
    }, status=status.HTTP_200_OK)