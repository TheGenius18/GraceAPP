import os
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# Absolute path to firebase_credentials.json
FIREBASE_CRED_PATH = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'firebase_credentials.json')
)

FIREBASE_AVAILABLE = False
if os.path.exists(FIREBASE_CRED_PATH):
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_CRED_PATH)
            firebase_admin.initialize_app(cred)
            FIREBASE_AVAILABLE = True
            logger.info("[Firebase] Initialized successfully.")
    except Exception as e:
        logger.error(f"[Firebase Init Error] {e}")
else:
    logger.warning(f"[Firebase] Credentials not found at {FIREBASE_CRED_PATH}")

def notify_user(user, message, title="GRACE App", data=None):
    """
    Send a push notification via Firebase or fallback to email.
    :param user: User instance
    :param message: Body of the notification
    :param title: Title of the notification
    :param data: Optional dict of extra data to send (string keys/values)
    """
    # Ensure data is string:string for FCM
    data = {str(k): str(v) for k, v in (data or {}).items()}

    # Firebase Push
    if FIREBASE_AVAILABLE and hasattr(user, 'fcm_token') and user.fcm_token:
        try:
            msg = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=message,
                ),
                token=user.fcm_token,
                data=data
            )
            messaging.send(msg)
            logger.info(f"[Firebase] Push sent to {user.username}")
            return
        except Exception as e:
            logger.error(f"[Firebase Error] {e}")

    # Fallback Email
    if user.email:
        try:
            send_mail(
                subject=title,
                message=message,
                from_email=None,
                recipient_list=[user.email],
                fail_silently=False,
            )
            logger.info(f"[Email] Sent to {user.email}")
        except Exception as e:
            logger.error(f"[Email Error] {e}")
