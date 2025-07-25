from django.db import models
from django.conf import settings
from apps.users.models import CustomUser  # make sure this import is at the top
from django.db import models
from django.utils.timezone import now
class Appointment(models.Model):
    SESSION_TYPE_CHOICES = [
        ('chat', 'Chat'),
        ('video', 'Video Call'),
        ('in_person', 'In-Person'),
        ('online', 'Online Session'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('no_show', 'No-show'),
        ('missed', 'Missed'),
    ]

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='appointments')
    therapist = models.ForeignKey('therapists.TherapistProfile', on_delete=models.CASCADE, related_name='appointments')
    session_type = models.CharField(max_length=20, choices=SESSION_TYPE_CHOICES, default='chat')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    scheduled_at = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)  # for therapist notes after session
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    duration_minutes = models.PositiveIntegerField(default=60)
    is_recurring = models.BooleanField(default=False)
    recurring_group = models.UUIDField(default=None, null=True, blank=True)
    reminder_sent = models.BooleanField(default=False)
    reminder_15_sent = models.BooleanField(default=False)
    checked_in = models.BooleanField(default=False)
    class Meta:
        unique_together = ('therapist', 'scheduled_at')  # prevent double-booking

    def __str__(self):
        return f"{self.patient.username} with {self.therapist.user.username} on {self.scheduled_at}"



    


class AppointmentLog(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='logs')
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.performed_by} - {self.action} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class AppointmentFeedback(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    rating = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])  # 1 to 5
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='feedbacks')
    def __str__(self):
        return f"Rating: {self.rating} by {self.appointment.patient.username} for {self.appointment.therapist.user.username}"



class ReminderLog(models.Model):
    appointment = models.ForeignKey('Appointment', on_delete=models.CASCADE)
    reminder_type = models.CharField(max_length=10, choices=[('1h', '1 Hour'), ('15m', '15 Minutes')])
    sent_to = models.EmailField()
    sent_at = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.reminder_type} reminder to {self.sent_to} for appointment #{self.appointment_id}"