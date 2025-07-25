from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.therapists.views import (
    ConnectedPatientsView,
    TherapistListView,
    TherapistDetailView,
    TherapistProfileUpdateView,
    TherapistDashboardView,
    TherapistRequestCreateView,
    TherapistRequestListView,
    TherapistRequestResponseView,
    VerifyTherapistView,
    TherapistAvailabilityViewSet,
    TherapistProfileViewSet,  
    FindMyTherapistView
)

router = DefaultRouter()
router.register(r'availability', TherapistAvailabilityViewSet, basename='availability')
router.register(r'', TherapistProfileViewSet, basename='therapists')  

urlpatterns = [
    # Public endpoints
    path('', TherapistListView.as_view(), name='therapist-list'),
    path('<int:pk>/', TherapistDetailView.as_view(), name='therapist-detail'),
    path('find-my-therapist/', FindMyTherapistView.as_view(), name='find-my-therapist'),
    path('connected-patients/', ConnectedPatientsView.as_view(), name='connected-patients'),
    # Therapist self-management
    path('me/update/', TherapistProfileUpdateView.as_view(), name='therapist-profile-update'),
    path('dashboard/', TherapistDashboardView.as_view(), name='therapist-dashboard'),
    # Therapist interaction endpoints
    path('request/', TherapistRequestCreateView.as_view(), name='send-therapist-request'),
    path('requests/', TherapistRequestListView.as_view(), name='list-therapist-requests'),
    path('requests/<int:request_id>/respond/', TherapistRequestResponseView.as_view(), name='respond-therapist-request'),
    # Admin action
    path('verify/<int:user_id>/', VerifyTherapistView.as_view(), name='verify-therapist'),

    # Router endpoints (availability + top-rated)
    path('', include(router.urls)),
]
