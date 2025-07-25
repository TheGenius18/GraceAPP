from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db import models
from django.contrib.auth import get_user_model
# apps.users.models.py

from django.conf import settings


class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('patient', 'Patient'),
        ('therapist', 'Therapist'),
        ('admin', 'Admin'),
    )

    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='patient')
    is_verified = models.BooleanField(default=False)

    #  Add this field to represent a match/connection
    connected_user = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='connected_clients'
    )
    fcm_token = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Firebase Cloud Messaging device token"
    )
    # in your CustomUser model (models.py)
    @property
    def is_therapist(self):
        return self.user_type == 'therapist'
    
    @property
    def is_patient(self):
        return self.user_type == 'patient'
    
    @property
    def is_admin(self):
        return self.user_type == 'admin'

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

User = get_user_model()
class LoginAudit(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    event = models.CharField(max_length=20, choices=[('login', 'Login'), ('logout', 'Logout'), ('fail', 'Failed Login')])
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} - {self.event} at {self.timestamp}"