from django.urls import path

from .views import (
    AISearchView,
    GlobalSearchView,
    QuickSearchView,
    RecentSearchView,
    SavedSearchDetailView,
    SavedSearchView,
    SearchHistoryView,
)

urlpatterns = [
    path('', GlobalSearchView.as_view(), name='search-global'),
    path('quick/', QuickSearchView.as_view(), name='search-quick'),
    path('recent/', RecentSearchView.as_view(), name='search-recent'),
    path('saved/', SavedSearchView.as_view(), name='search-saved'),
    path('saved/<int:pk>/', SavedSearchDetailView.as_view(), name='search-saved-detail'),
    path('history/', SearchHistoryView.as_view(), name='search-history'),
    path('ai/', AISearchView.as_view(), name='search-ai'),
]
