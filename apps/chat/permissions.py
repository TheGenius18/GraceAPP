from rest_framework.permissions import BasePermission

class IsParticipantInThread(BasePermission):
    """
    يسمح فقط للمستخدمين المشاركين في الـ Thread (patient أو therapist)
    بالوصول أو التعديل على الرسائل.
    """
    def has_object_permission(self, request, view, obj):
        return (
            obj.thread.patient == request.user or
            obj.thread.therapist == request.user
        )
