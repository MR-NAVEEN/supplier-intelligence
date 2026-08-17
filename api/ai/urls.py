from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AIBulkUploadView,
    AIBusinessCardViewSet,
    AICatalogueProductViewSet,
    AICatalogueViewSet,
    AIChatView,
    AIExtractionRunViewSet,
)

router = DefaultRouter()
router.register('extract', AIExtractionRunViewSet, basename='ai-extract')
router.register('catalogues', AICatalogueViewSet, basename='ai-catalogues')
router.register('cards', AIBusinessCardViewSet, basename='ai-cards')

urlpatterns = router.urls + [
    path(
        'catalogues/<int:catalogue_pk>/products/',
        AICatalogueProductViewSet.as_view({'get': 'list'}),
        name='ai-catalogue-products',
    ),
    path('chat/', AIChatView.as_view(), name='ai-chat'),
    path('bulk-upload/', AIBulkUploadView.as_view(), name='ai-bulk-upload'),
]
