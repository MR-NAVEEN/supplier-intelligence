from rest_framework.routers import DefaultRouter

from .views import AIExtractionRunViewSet

router = DefaultRouter()
router.register('extract', AIExtractionRunViewSet, basename='ai-extract')

urlpatterns = router.urls