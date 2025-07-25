from django.urls import path
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from .views import (
    ChatThreadViewSet,
    ChatMessageViewSet,
    UnreadMessageCountView,
    MarkMessagesAsReadView,
    end_call,
)

router = DefaultRouter()
router.register(r'threads', ChatThreadViewSet, basename='chat-threads')
router.register(r'messages', ChatMessageViewSet, basename='chat-messages')

urlpatterns = [
    # Custom endpoints
    path('messages/unread-count/', UnreadMessageCountView.as_view(), name='unread-count'),
    path('messages/mark-as-read/<int:thread_id>/', MarkMessagesAsReadView.as_view(), name='mark-as-read'),
    path('end-call/', end_call, name='end-call'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += router.urls
