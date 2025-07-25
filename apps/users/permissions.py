from rest_framework.permissions import BasePermission

class IsAdminUserType(BasePermission):
    """
    Allows access only to users with user_type = 'admin'
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.user_type == 'admin')
