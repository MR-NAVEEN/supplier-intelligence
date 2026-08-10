from django.urls import path

from .views import ProductAnalyticsView, SearchAnalyticsView

urlpatterns = [
    path('products/', ProductAnalyticsView.as_view()),
    path('search/', SearchAnalyticsView.as_view()),
]
