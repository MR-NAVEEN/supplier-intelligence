from django.urls import path

from .views import BusinessCardCommitView, BusinessCardExtractView

urlpatterns = [
    path('extract/', BusinessCardExtractView.as_view(), name='business-card-extract'),
    path('commit/', BusinessCardCommitView.as_view(), name='business-card-commit'),
]
