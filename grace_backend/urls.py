
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
urlpatterns = [
    path('', lambda request: JsonResponse({'status': 'Grace Backend is running'})),
    path('admin/', admin.site.urls),
    path('api/users/', include('apps.users.urls')),
    path('api/therapists/', include('apps.therapists.urls')),
    path('api/appointments/', include('apps.appointments.urls')),
    path('api/chat/', include('apps.chat.urls')),
    path('api/training/', include('apps.training.urls')),
    path('api/mood/', include('apps.mood.urls')),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)