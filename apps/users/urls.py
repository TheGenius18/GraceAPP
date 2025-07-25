from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import LoginView, LogoutView, RegisterView, ResendVerificationEmailView, UpdateFCMTokenView, UserProfileView,UserUpdateView,PasswordResetRequestView, PasswordResetConfirmView, VerifyEmailView, connect_patient_to_therapist

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='custom-login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', UserProfileView.as_view()),
    path('profile/update/', UserUpdateView.as_view()),
    path('password-reset/request/', PasswordResetRequestView.as_view()),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view()),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('update-fcm-token/', UpdateFCMTokenView.as_view(), name='update-fcm-token'),
    path('connect-patient/', connect_patient_to_therapist, name='connect-patient'),
]
    