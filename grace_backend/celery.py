# grace_backend/celery.py

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'grace_backend.settings')

app = Celery('grace_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule.update({
    'auto-close-past-appointments-daily': {
        'task': 'apps.appointments.tasks.auto_close_past_appointments',
        'schedule': crontab(hour=0, minute=5),  # Runs daily at 00:05
    },
})
