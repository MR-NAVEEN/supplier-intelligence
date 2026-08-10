from django.conf import settings
from django.db import models

from api.common.models import TimeStampedModel, WorkspaceScopedModel


class SavedSearch(WorkspaceScopedModel):
    name = models.CharField(max_length=255)
    query = models.CharField(max_length=512)
    filters = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_searches')


class RecentSearch(TimeStampedModel):
    workspace = models.ForeignKey('workspaces.Workspace', on_delete=models.CASCADE, related_name='recent_searches')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recent_searches')
    query = models.CharField(max_length=512)
    result_count = models.PositiveIntegerField(default=0)


class SearchHistory(WorkspaceScopedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='search_history')
    query = models.CharField(max_length=512)
    filters = models.JSONField(default=dict, blank=True)
    result_count = models.PositiveIntegerField(default=0)
    search_type = models.CharField(max_length=32, default='global')

    class Meta:
        ordering = ['-created_at']
