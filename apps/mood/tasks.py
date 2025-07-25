from celery import shared_task
from apps.notifications.utils import notify_user
from .models import MoodLog
from .utils import message_for_mood

@shared_task
def notify_after_delay(mood_log_id):
    try:
        mood_log = MoodLog.objects.get(id=mood_log_id)
    except MoodLog.DoesNotExist:
        return

    patient = mood_log.patient

    # Check for a newer mood
    newer_log = MoodLog.objects.filter(
        patient=patient,
        created_at__gt=mood_log.created_at
    ).order_by('-created_at').first()

    if newer_log:
        # ✅ Newer mood: notify for that mood
        message = message_for_mood(newer_log.mood)
        notify_user(patient, message, title="Mood Update ✨")
    else:
        # ✅ No newer mood: follow up on original mood
        follow_up_msg = "Are you still feeling sad? Let us help you! ❤️"
        notify_user(patient, follow_up_msg, title="Mood Check-In 🤗")
