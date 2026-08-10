from rest_framework.routers import DefaultRouter

from .views import CatalogueViewSet

router = DefaultRouter()
router.register('', CatalogueViewSet, basename='catalogues')

urlpatterns = router.urls
