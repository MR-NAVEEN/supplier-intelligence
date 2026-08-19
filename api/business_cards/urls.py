from django.urls import path

from .views import (
    BusinessCardCommitView,
    BusinessCardDetailView,
    BusinessCardExtractView,
    BusinessCardListView,
)

urlpatterns = [
    path('', BusinessCardListView.as_view(), name='business-card-list'),
    path('<int:pk>/', BusinessCardDetailView.as_view(), name='business-card-detail'),
    path('extract/', BusinessCardExtractView.as_view(), name='business-card-extract'),
    path('commit/', BusinessCardCommitView.as_view(), name='business-card-commit'),

    # Supplier-scoped: same views, supplier_id read from the URL instead of (or in
    # addition to) the request body.
    path(
        'suppliers/<int:supplier_id>/',
        BusinessCardListView.as_view(),
        name='business-card-supplier-list',
    ),
    path(
        'suppliers/<int:supplier_id>/extract/',
        BusinessCardExtractView.as_view(),
        name='business-card-supplier-extract',
    ),
    path(
        'suppliers/<int:supplier_id>/commit/',
        BusinessCardCommitView.as_view(),
        name='business-card-supplier-commit',
    ),
]
