from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

from apps.notifications.tasks import send_notification_task
from apps.notifications.utils import notify_user
from .models import ChatThread, ChatMessage, CallLog

logger = logging.getLogger(__name__)
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.thread_id = self.scope['url_route']['kwargs']['thread_id']
        self.room_group_name = f"chat_{self.thread_id}"
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        is_authorized = await self.user_in_thread(self.user.id, self.thread_id)
        if not is_authorized:
            logger.warning(f"Unauthorized WebSocket access attempt by User[{self.user.id}] on Thread[{self.thread_id}]")
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user_id': self.user.id,
                'username': self.user.username,
                'status': 'online'
            }
        )

    @database_sync_to_async
    def user_in_thread(self, user_id, thread_id):
        try:
            thread = ChatThread.objects.get(id=thread_id)
            return thread.patient_id == user_id or thread.therapist_id == user_id
        except ChatThread.DoesNotExist:
            return False

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
       
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user_id': self.user.id,
                'username': self.user.username,
                'status': 'offline'
            }
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get("action")

        if action == "send-message":
            await self.handle_send_message(data)
        elif action == "start-call":
            await self.handle_start_call(data)
        elif action == "signal":
            await self.handle_signal(data)
        elif action == "end-call":
            await self.handle_end_call(data)
        elif action == "typing":
            await self.handle_typing(data)

    # ================================
    
    # ================================
    async def handle_send_message(self, data):
        message = data.get('message')
        thread_id = data.get('thread_id')
        if not message or not thread_id:
            return

        thread = await self.get_thread(thread_id)
        if not thread:
            return

        msg_obj = await self.create_message(thread, self.user, message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': msg_obj.content,
                'sender': self.user.username,
                'timestamp': msg_obj.sent_at.isoformat(),
                'attachment_url': msg_obj.file.url if msg_obj.file else None
            }
        )
    async def message_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_update",
            "message_id": event["message_id"],
            "new_content": event["new_content"],
            "is_read": event["is_read"],
            "timestamp": event["timestamp"],
        }))

    async def message_delete(self, event):
        await self.send(text_data=json.dumps({
            "type": "message_delete",
            "message_id": event["message_id"],
        }))
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'sender': event['sender'],
            'timestamp': event['timestamp'],
            'attachment_url': event.get('attachment_url')
        }))

    # ================================
    
    # ================================


    async def handle_start_call(self, data):
        thread_id = data.get('thread_id')
        callee_id = data.get('callee_id')
        call_type = data.get('call_type')

        if not thread_id or not callee_id or not call_type:
            return

        thread = await self.get_thread(thread_id)
        callee = await self.get_user(callee_id)
        if not thread or not callee:
            return

        call_log = await self.create_call_log(thread, self.user, callee, call_type)

        
        send_notification_task.delay(
            callee.id,
            f"{self.user.username} is calling you",
            "Incoming Call",
            {
                "thread_id": str(thread.id),
                "log_id": str(call_log.id),
                "call_type": call_type
            }
        )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'call_event',
                'event': 'incoming_call',
                'caller_id': self.user.id,
                'caller': self.user.username,
                'call_type': call_type,
                'thread_id': thread.id,
                'log_id': call_log.id
            }
        )


    async def call_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call',
            'event': event['event'],
            'caller_id': event['caller_id'],
            'caller': event['caller'],
            'call_type': event['call_type'],
            'thread_id': event['thread_id'],
            'log_id': event['log_id']
        }))

    async def handle_end_call(self, data):
        log_id = data.get('log_id')
        status_value = data.get('status', 'completed')
        callee_id = data.get('callee_id')
    
        if log_id:
            await self.update_call_status(log_id, status_value)
    
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'call_event',
                    'event': 'call_ended',
                    'caller': self.user.username,
                    'log_id': log_id,
                    'status': status_value
                }
            )
    
            if callee_id:
                send_notification_task.delay(
                    callee_id,
                    f"Missed call from {self.user.username}" if status_value == 'missed'
                    else f"Call ended with {self.user.username}",
                    "Call Update",
                    {
                        "thread_id": str(self.thread_id),
                        "log_id": str(log_id),
                        "status": status_value
                    }
                )

    async def messages_seen(self, event):
        await self.send(text_data=json.dumps({
            'type': 'seen',
            'reader_id': event['reader_id'],
            'reader_username': event['reader_username'],
            'message_ids': event['message_ids']
        }))

    # ================================
    
    # ================================
    async def handle_typing(self, data):
        is_typing = data.get('is_typing', False)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_event',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_typing': is_typing
            }
        )

    async def typing_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_typing': event['is_typing']
        }))

    # ================================
    
    # ================================
    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status',
            'user_id': event['user_id'],
            'username': event['username'],
            'status': event['status']  # online/offline
        }))

    # ================================
    
    # ================================
    @database_sync_to_async
    def get_thread(self, thread_id):
        try:
            return ChatThread.objects.get(id=thread_id)
        except ChatThread.DoesNotExist:
            return None

    @database_sync_to_async
    def create_message(self, thread, sender, message):
        return ChatMessage.objects.create(
            thread=thread,
            sender=sender,
            content=message,
            sent_at=timezone.now()
        )

    @database_sync_to_async
    def create_call_log(self, thread, caller, callee, call_type):
        return CallLog.objects.create(
            thread=thread,
            caller=caller,
            callee=callee,
            call_type=call_type,
            started_at=timezone.now(),
            status='ongoing'
        )

    @database_sync_to_async
    def update_call_status(self, log_id, status_value):
        try:
            call = CallLog.objects.get(id=log_id)
            call.ended_at = timezone.now()
            call.status = status_value
            call.save()
        except CallLog.DoesNotExist:
            pass

    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
