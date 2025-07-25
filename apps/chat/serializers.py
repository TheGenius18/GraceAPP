from rest_framework import serializers
from .models import ChatMessage, ChatThread

class ChatThreadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatThread
        fields = ['id', 'patient', 'therapist', 'appointment', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

class ChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)

    class Meta:
        model = ChatMessage
        fields = ['id', 'thread', 'sender', 'sender_name', 'content', 'file', 'is_read', 'sent_at']
        read_only_fields = ['id', 'sender', 'sender_name', 'is_read', 'sent_at']  
