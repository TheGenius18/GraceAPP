from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import ChatMessage

channel_layer = get_channel_layer()

# ✅ إرسال عند إنشاء أو تعديل رسالة
@receiver(post_save, sender=ChatMessage)
def broadcast_message_save(sender, instance, created, **kwargs):
    thread_id = instance.thread.id
    if created:
        # رسالة جديدة
        async_to_sync(channel_layer.group_send)(
            f"chat_{thread_id}",
            {
                "type": "chat_message",
                "message": instance.content,
                "sender": instance.sender.username if instance.sender else "",
                "timestamp": instance.sent_at.isoformat(),
                "attachment_url": instance.file.url if instance.file else None,
            }
        )
    else:
        # تعديل رسالة موجودة
        async_to_sync(channel_layer.group_send)(
            f"chat_{thread_id}",
            {
                "type": "message_update",
                "message_id": instance.id,
                "new_content": instance.content,
                "is_read": instance.is_read,
                "timestamp": instance.sent_at.isoformat(),
            }
        )


@receiver(post_delete, sender=ChatMessage)
def broadcast_message_delete(sender, instance, **kwargs):
    thread_id = instance.thread.id
    async_to_sync(channel_layer.group_send)(
        f"chat_{thread_id}",
        {
            "type": "message_delete",
            "message_id": instance.id,
        }
    )
