from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AppointmentViewSet, AdminAnalyticsViewSet, TherapistRatingAnalytics

router = DefaultRouter()
router.register(r'', AppointmentViewSet, basename='appointments')
router.register(r'admin-analytics', AdminAnalyticsViewSet, basename='admin-analytics')

urlpatterns = [
    path('admin/analytics/therapist-ratings/', TherapistRatingAnalytics.as_view(), name='therapist-ratings'),
]

urlpatterns += router.urls  
