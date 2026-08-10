from django.urls import path

from .views import (
    EmailTokenObtainPairView,
    MeView,
    PasswordResetView,
    TokenBlacklistView,
    TokenRefreshEnvelopeView,
)

urlpatterns = [
    path('token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshEnvelopeView.as_view(), name='token_refresh'),
    path('token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('me/', MeView.as_view(), name='auth_me'),
    path('password-reset/', PasswordResetView.as_view(), name='password_reset'),
]
