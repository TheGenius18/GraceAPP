from django.contrib.auth import get_user_model
from celery import shared_task

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def send_notification_task(self, user_id, message, title="GRACE App", data=None):
    User = get_user_model()  # ✅ يتم استدعاؤه فقط عند تنفيذ المهمة
    try:
        user = User.objects.get(id=user_id)
        # استدعاء notify_user هنا
        from apps.notifications.utils import notify_user
        notify_user(user, message, title, data)
        return f"[✅ Notification Sent] to {user.username}"
    except User.DoesNotExist:
        return "[⚠️ Notification Failed] User not found."
    except Exception as e:
        raise self.retry(exc=e)
