from django.contrib import admin
from .models import Appointment
from .models import ReminderLog
# @admin.register(AvailabilitySlot)
# class AvailabilitySlotAdmin(admin.ModelAdmin):
#    list_display = ('therapist', 'start_time', 'end_time', 'is_booked')
#    list_filter = ('therapist', 'is_booked')
#    search_fields = ('therapist__user__first_name', 'therapist__user__last_name')
#    ordering = ('start_time',) 

# @admin.register(Appointment)
# class AppointmentAdmin(admin.ModelAdmin):
#    list_display = ('patient', 'slot', 'status', 'created_at')
#    list_filter = ('status', 'created_at')
#    search_fields = ('patient__first_name', 'patient__last_name', 'slot__therapist__user__first_name')
#    ordering = ('-created_at',)


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = ['appointment', 'reminder_type', 'sent_to', 'sent_at']
    list_filter = ['reminder_type', 'sent_at']
    search_fields = ['sent_to', 'appointment__id']


