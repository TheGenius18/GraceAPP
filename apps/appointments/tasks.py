from celery import shared_task
from django.utils.timezone import now, timedelta
from apps.appointments.models import Appointment, ReminderLog
from apps.notifications.utils import notify_user
import logging

from celery.exceptions import Retry
logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_upcoming_session_reminders(self):
    current_time = now()

    # 1-hour reminder window
    one_hour_target = current_time + timedelta(hours=1)
    one_hour_window_start = one_hour_target - timedelta(minutes=1)

    # 15-minute reminder window
    fifteen_min_target = current_time + timedelta(minutes=15)
    fifteen_min_window_start = fifteen_min_target - timedelta(minutes=1)

    # ===== 1-HOUR REMINDERS =====
    appts_1h = Appointment.objects.filter(
        scheduled_at__range=(one_hour_window_start, one_hour_target),
        status='confirmed',
        reminder_sent=False
    )

    for appt in appts_1h:
            try:
                message = f"Reminder: You have a session at {appt.scheduled_at.strftime('%H:%M')} (in 1 hour)."
                notify_user(appt.patient, f"[Patient Reminder] {message}")
                notify_user(appt.therapist.user, f"[Therapist Reminder] {message}")

                ReminderLog.objects.create(appointment=appt, reminder_type='1h', sent_to=appt.patient.email)
                ReminderLog.objects.create(appointment=appt, reminder_type='1h', sent_to=appt.therapist.user.email)

                appt.reminder_sent = True
                appt.save()
                logger.info(f"[1h Reminder] Sent for appointment #{appt.id}")
            except Exception as e:
                logger.error(f"Retrying reminder for appointment #{appt.id} due to error: {str(e)}")
                raise self.retry(exc=e)

    # ===== 15-MINUTE REMINDERS =====
    appts_15m = Appointment.objects.filter(
        scheduled_at__range=(fifteen_min_window_start, fifteen_min_target),
        status='confirmed',
        reminder_15_sent=False
    )

    for appt in appts_15m:
        message = f"Reminder: Your session starts in 15 minutes at {appt.scheduled_at.strftime('%H:%M')}."
        
        # Notify both users
        notify_user(appt.patient, f"[Patient Reminder] {message}")
        notify_user(appt.therapist.user, f"[Therapist Reminder] {message}")

        # Log reminder
        ReminderLog.objects.create(appointment=appt, reminder_type='15m', sent_to=appt.patient.email)
        ReminderLog.objects.create(appointment=appt, reminder_type='15m', sent_to=appt.therapist.user.email)

        appt.reminder_15_sent = True
        appt.save()
        logger.info(f"[15m Reminder] Sent for appointment #{appt.id}")






@shared_task
def auto_close_past_appointments():
    now_time = now()

    # All confirmed appointments in the past
    past_appts = Appointment.objects.filter(
        scheduled_at__lt=now_time,
        status='confirmed'
    )

    missed = 0
    completed = 0

    for appt in past_appts:
        if appt.checked_in:
            appt.status = 'completed'
            completed += 1
        else:
            appt.status = 'missed'
            missed += 1
        appt.save()

    logger.info(f"[Auto-Close] Updated {completed} completed and {missed} missed appointments.")
