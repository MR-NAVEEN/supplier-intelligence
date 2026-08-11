from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/auth/', include('api.accounts.urls')),
    path('api/suppliers/', include('api.suppliers.urls')),
    path('api/products/', include('api.products.urls')),
    path('api/categories/', include('api.categories.urls')),
    path('api/catalogues/', include('api.catalogues.urls')),
    path('api/business-cards/', include('api.business_cards.urls')),
    path('api/jobs/', include('api.jobs.urls')),
    path('api/search/', include('api.search.urls')),
    path('api/notifications/', include('api.notifications.urls')),
    path('api/dashboard/', include('api.dashboard.urls')),
    path('api/settings/', include('api.settings_app.urls')),
    path('api/activity/', include('api.activity.urls')),
    path('api/analytics/', include('api.analytics.urls')),
    path('api/ai/', include('api.ai.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
