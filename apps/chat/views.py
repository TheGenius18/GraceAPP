from datetime import timezone
from rest_framework import viewsets, permissions, generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from apps.chat.permissions import IsParticipantInThread
from apps.notifications.tasks import send_notification_task
from .models import ChatThread, ChatMessage
from .serializers import ChatThreadSerializer, ChatMessageSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from .models import CallLog
from apps.notifications.utils import notify_user
from rest_framework.pagination import PageNumberPagination
def is_valid_match(patient_user, therapist_user):
    return (
        patient_user.user_type == 'patient' and
        therapist_user.user_type == 'therapist' and
        patient_user.connected_user_id == therapist_user.id
    )

class ChatThreadViewSet(viewsets.ModelViewSet):
    serializer_class = ChatThreadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return ChatThread.objects.filter(
            Q(patient=user) | Q(therapist=user)
        )

    def perform_create(self, serializer):
        patient = serializer.validated_data['patient']
        therapist = serializer.validated_data['therapist']

        if not is_valid_match(patient, therapist):
            raise PermissionDenied("No valid match between patient and therapist.")

        serializer.save()

class ChatMessagePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class ChatMessageViewSet(viewsets.ModelViewSet):
    serializer_class = ChatMessageSerializer
    permission_classes = [permissions.IsAuthenticated, IsParticipantInThread]
    pagination_class = ChatMessagePagination

    def get_queryset(self):
        user = self.request.user
        queryset = ChatMessage.objects.filter(
            Q(thread__patient=user) | Q(thread__therapist=user)
        ).order_by('-sent_at')

        unread_only = self.request.query_params.get('unread_only')
        if unread_only and unread_only.lower() == 'true':
            queryset = queryset.filter(is_read=False).exclude(sender=user)

        return queryset

    def perform_create(self, serializer):
        thread = serializer.validated_data['thread']
        user = self.request.user
        if thread.patient != user and thread.therapist != user:
            raise PermissionDenied("You are not part of this chat thread.")

        msg_obj = serializer.save(sender=user)

        # Send notification to other participant
        recipient = thread.patient if thread.therapist == user else thread.therapist

        send_notification_task.delay(
            recipient.id,
            " New attachment received" if msg_obj.file else f"You have a new message from {user.username}",
            "New Message",
            {
                "thread_id": str(thread.id),
                "message_id": str(msg_obj.id),
                "has_attachment": str(bool(msg_obj.file))
            }
        )


class UnreadMessageCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        count = ChatMessage.objects.filter(
            Q(thread__patient=user) | Q(thread__therapist=user),
            ~Q(sender=user),
            is_read=False
        ).count()
        return Response({'unread_count': count})


class MarkMessagesAsReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, thread_id):
        user = request.user
        try:
            thread = ChatThread.objects.get(id=thread_id)
            if user != thread.patient and user != thread.therapist:
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

            
            unread_messages = ChatMessage.objects.filter(thread=thread, is_read=False).exclude(sender=user)
            updated_ids = list(unread_messages.values_list('id', flat=True))
            unread_messages.update(is_read=True)

            
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"chat_{thread_id}",
                {
                    'type': 'messages_seen',
                    'reader_id': user.id,
                    'reader_username': user.username,
                    'message_ids': updated_ids
                }
            )

            return Response({'detail': 'Messages marked as read', 'message_ids': updated_ids})

        except ChatThread.DoesNotExist:
            return Response({'detail': 'Thread not found'}, status=status.HTTP_404_NOT_FOUND)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_call(request):
    call_id = request.data.get('call_id')
    status = request.data.get('status', 'completed')

    try:
        call = CallLog.objects.get(id=call_id)
        call.ended_at = timezone.now()
        call.status = status
        call.save()
        return Response({'success': True})
    except CallLog.DoesNotExist:
        return Response({'error': 'Call not found'}, status=404)