from rest_framework.routers import DefaultRouter
from .views import TrainingExerciseViewSet, AssignedTrainingViewSet

router = DefaultRouter()
router.register('training', TrainingExerciseViewSet, basename='training')
router.register('assigned-training', AssignedTrainingViewSet, basename='assigned-training')

urlpatterns = router.urls
