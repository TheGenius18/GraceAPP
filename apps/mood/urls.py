from rest_framework.routers import DefaultRouter
from .views import MoodLogViewSet

router = DefaultRouter()
router.register('mood', MoodLogViewSet, basename='mood')

urlpatterns = router.urls
