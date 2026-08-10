from django.urls import path

from .views import (
    DashboardCataloguePipelineChartView,
    DashboardExtractionQueueView,
    DashboardFollowUpsView,
    DashboardJobsView,
    DashboardKpisView,
    DashboardNotificationsSummaryView,
    DashboardOnboardingView,
    DashboardProductsByCategoryChartView,
    DashboardRecentActivityView,
    DashboardRecentCataloguesView,
    DashboardRecentProductsView,
    DashboardRecentSuppliersView,
    DashboardSearchVolumeChartView,
    DashboardSummaryView,
    DashboardSuppliersByStatusChartView,
)

urlpatterns = [
    path('summary/', DashboardSummaryView.as_view()),
    path('kpis/', DashboardKpisView.as_view()),
    path('jobs/', DashboardJobsView.as_view()),
    path('recent-suppliers/', DashboardRecentSuppliersView.as_view()),
    path('recent-products/', DashboardRecentProductsView.as_view()),
    path('recent-catalogues/', DashboardRecentCataloguesView.as_view()),
    path('recent-activity/', DashboardRecentActivityView.as_view()),
    path('extraction-queue/', DashboardExtractionQueueView.as_view()),
    path('charts/suppliers-by-status/', DashboardSuppliersByStatusChartView.as_view()),
    path('charts/products-by-category/', DashboardProductsByCategoryChartView.as_view()),
    path('charts/catalogue-pipeline/', DashboardCataloguePipelineChartView.as_view()),
    path('charts/search-volume/', DashboardSearchVolumeChartView.as_view()),
    path('follow-ups/', DashboardFollowUpsView.as_view()),
    path('onboarding/', DashboardOnboardingView.as_view()),
    path('notifications-summary/', DashboardNotificationsSummaryView.as_view()),
]
