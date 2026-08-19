from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AIBulkUploadView,
    AICardBulkUploadView,
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
router.register('products', AICatalogueProductViewSet, basename='ai-products')

# Explicit paths must come before router.urls: the router's cards/<pk>/ pattern
# would otherwise swallow "bulk-upload" as if it were a business card id.
urlpatterns = [
    path(
        'catalogues/<int:catalogue_pk>/products/',
        AICatalogueProductViewSet.as_view({'get': 'list'}),
        name='ai-catalogue-products',
    ),
    path('chat/', AIChatView.as_view(), name='ai-chat'),
    path('bulk-upload/', AIBulkUploadView.as_view(), name='ai-bulk-upload'),
    path('cards/bulk-upload/', AICardBulkUploadView.as_view(), name='ai-cards-bulk-upload'),
] + router.urls
