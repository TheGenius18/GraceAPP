# apps/chat/middleware.py
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async

User = get_user_model()

@database_sync_to_async
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    """
    Middleware to authenticate WebSocket connections using JWT token.
    Expected URL format:
    ws://host/ws/chat/<thread_id>/?token=<JWT_ACCESS_TOKEN>
    """
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = None

        # Extract token from query string
        if "token=" in query_string:
            parts = query_string.split("token=")
            if len(parts) > 1:
                token = parts[1].split("&")[0]

        if token:
            try:
                access = AccessToken(token)
                scope["user"] = await get_user(access["user_id"])
            except Exception:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
