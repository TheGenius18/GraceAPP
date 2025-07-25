from datetime import time
from django.db import models
from django.conf import settings

from apps.users.models import CustomUser
DAY_CHOICES = [
    ('Mon', 'Monday'),
    ('Tue', 'Tuesday'),
    ('Wed', 'Wednesday'),
    ('Thu', 'Thursday'),
    ('Fri', 'Friday'),
    ('Sat', 'Saturday'),
    ('Sun', 'Sunday'),
]
class TherapistProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='therapistprofile'
    )

    # Personal & professional info
    bio = models.TextField(blank=True)
    specialties = models.CharField(max_length=255, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female')],
        blank=True
    )
    session_fee = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    rating = models.FloatField(default=0.0)  # optional static field
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    experience = models.PositiveIntegerField(default=0, help_text="Years of experience")

    # Profile media & preferences
    profile_photo = models.ImageField(
        upload_to='therapists/photos/',
        null=True,
        blank=True
    )
    
    languages = models.JSONField(default=list, blank=True)
    timezone = models.CharField(max_length=50, default='Asia/Riyadh')
    available_from = models.TimeField(default=time(9, 0))
    available_to = models.TimeField(default=time(17, 0))

    # System flags
    is_active = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    notify_on_booking = models.BooleanField(default=True)
    notify_on_cancellation = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} ({self.user.email})"


class TherapistAvailability(models.Model):
    therapist = models.ForeignKey('therapists.TherapistProfile', on_delete=models.CASCADE, related_name='availabilities')
    day = models.CharField(max_length=10, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.therapist.user.username} - {self.day} {self.start_time} to {self.end_time}"


class TherapistRequest(models.Model):
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='therapist_requests')
    therapist = models.ForeignKey(TherapistProfile, on_delete=models.CASCADE, related_name='incoming_requests')
    status = models.CharField(
        max_length=10,
        choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('patient', 'therapist')  # Prevent duplicate requests

    def __str__(self):
        return f"{self.patient.email} → {self.therapist.user.email} ({self.status})"
