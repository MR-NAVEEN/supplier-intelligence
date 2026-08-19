from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AIAttachmentViewSet,
    AIBulkUploadView,
    AICardBulkUploadView,
    AIBusinessCardViewSet,
    AICatalogueProductViewSet,
    AICatalogueViewSet,
    AIChatView,
    AIExtractionRunViewSet,
    NoteViewSet,
)

router = DefaultRouter()
router.register('extract', AIExtractionRunViewSet, basename='ai-extract')
router.register('catalogues', AICatalogueViewSet, basename='ai-catalogues')
router.register('cards', AIBusinessCardViewSet, basename='ai-cards')
router.register('products', AICatalogueProductViewSet, basename='ai-products')
router.register('notes', NoteViewSet, basename='ai-notes')
router.register('attachments', AIAttachmentViewSet, basename='ai-attachments')

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

    # Supplier-scoped routes: same views, supplier_id read from the URL instead of
    # (or in addition to) the request body. Writes still require a valid supplier_id
    # either way; these just let it live in the path.
    path(
        'suppliers/<int:supplier_id>/extract/',
        AIExtractionRunViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='ai-supplier-extract',
    ),
    path(
        'suppliers/<int:supplier_id>/extract/<int:pk>/',
        AIExtractionRunViewSet.as_view({'get': 'retrieve'}),
        name='ai-supplier-extract-detail',
    ),
    path(
        'suppliers/<int:supplier_id>/catalogues/',
        AICatalogueViewSet.as_view({'get': 'list'}),
        name='ai-supplier-catalogues',
    ),
    path(
        'suppliers/<int:supplier_id>/catalogues/<int:pk>/',
        AICatalogueViewSet.as_view({'get': 'retrieve'}),
        name='ai-supplier-catalogue-detail',
    ),
    path(
        'suppliers/<int:supplier_id>/products/',
        AICatalogueProductViewSet.as_view({'get': 'list'}),
        name='ai-supplier-products',
    ),
    path(
        'suppliers/<int:supplier_id>/cards/',
        AIBusinessCardViewSet.as_view({'get': 'list', 'post': 'create'}),
        name='ai-supplier-cards',
    ),
    path(
        'suppliers/<int:supplier_id>/cards/<int:pk>/',
        AIBusinessCardViewSet.as_view({'get': 'retrieve'}),
        name='ai-supplier-card-detail',
    ),
    path(
        'suppliers/<int:supplier_id>/bulk-upload/',
        AIBulkUploadView.as_view(),
        name='ai-supplier-bulk-upload',
    ),
    path(
        'suppliers/<int:supplier_id>/cards/bulk-upload/',
        AICardBulkUploadView.as_view(),
        name='ai-supplier-cards-bulk-upload',
    ),
] + router.urls
