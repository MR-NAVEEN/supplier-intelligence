from django.urls import path

from .views import NotificationPreferencesView, ProfileSettingsView

urlpatterns = [
    path('profile/', ProfileSettingsView.as_view()),
    path('notification-preferences/', NotificationPreferencesView.as_view()),
]
