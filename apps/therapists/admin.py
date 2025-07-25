from django.contrib import admin
from .models import TherapistProfile, TherapistAvailability

@admin.register(TherapistProfile)
class TherapistProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'verified', 'session_fee', 'average_rating', 'is_active', 'available_from', 'available_to')
    list_editable = ('available_from', 'available_to')
    fields = ('user', 'verified', 'session_fee', 'average_rating', 'is_active', 'available_from', 'available_to')

@admin.register(TherapistAvailability)
class TherapistAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('therapist', 'day', 'start_time', 'end_time')
