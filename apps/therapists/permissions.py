from rest_framework.permissions import BasePermission


class IsTherapist(BasePermission):
    """
    Allows access only to authenticated users who have an active TherapistProfile.
    Optional: add therapistprofile.verified if needed.
    """

    def has_permission(self, request, view):
        return (
            hasattr(request.user, 'therapistprofile') and
            request.user.therapistprofile.is_active
            # and request.user.therapistprofile.verified  # Uncomment if needed
        )
