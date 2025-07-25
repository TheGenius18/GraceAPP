from django.db import models
from .models import AppointmentLog
from apps.therapists.models import TherapistProfile
from .models import AppointmentFeedback
def log_action(appointment, user, action, notes=''):
    AppointmentLog.objects.create(
        appointment=appointment,
        performed_by=user,
        action=action,
        notes=notes
    )
def update_therapist_average_rating(therapist):
    feedbacks = AppointmentFeedback.objects.filter(appointment__therapist=therapist)
    if feedbacks.exists():
        average = feedbacks.aggregate(avg=models.Avg('rating'))['avg']
        therapist.average_rating = round(average, 2)
    else:
        therapist.average_rating = 0
    therapist.save()