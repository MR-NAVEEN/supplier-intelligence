from django.conf import settings
from django.db import models

from api.common.models import TimeStampedModel, WorkspaceScopedModel


def ai_catalogue_upload_path(instance, filename):
    return f'ai/catalogues/{instance.workspace_id}/{filename}'


class AICatalogueUpload(WorkspaceScopedModel):
    file = models.FileField(upload_to=ai_catalogue_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size_bytes = models.BigIntegerField(default=0)
    total_pages = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=128, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ai_catalogue_uploads',
    )

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.original_filename


class AIExtractionRun(TimeStampedModel):
    MODE_FULL = 'full'
    MODE_FIRST_N = 'first_n'
    MODE_RANGE = 'range'
    PAGE_MODE_CHOICES = [
        (MODE_FULL, 'Full PDF'),
        (MODE_FIRST_N, 'First N pages'),
        (MODE_RANGE, 'Selected page range'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
    ]

    TIER_BUDGET = 'budget'
    TIER_BALANCED = 'balanced'
    TIER_HIGH = 'high_accuracy'
    MODEL_TIER_CHOICES = [
        (TIER_BUDGET, 'Budget'),
        (TIER_BALANCED, 'Balanced'),
        (TIER_HIGH, 'High accuracy'),
    ]

    workspace = models.ForeignKey(
        'workspaces.Workspace',
        on_delete=models.CASCADE,
        related_name='ai_extraction_runs',
    )
    upload = models.ForeignKey(
        AICatalogueUpload,
        on_delete=models.CASCADE,
        related_name='runs',
    )
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    page_mode = models.CharField(max_length=16, choices=PAGE_MODE_CHOICES)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    page_range = models.CharField(max_length=128, blank=True)
    pages_requested = models.JSONField(default=list, blank=True)
    model_tier = models.CharField(max_length=32, choices=MODEL_TIER_CHOICES, default=TIER_HIGH)
    model_name = models.CharField(max_length=128, blank=True)
    dpi = models.PositiveIntegerField(default=200)
    result_json = models.JSONField(default=dict, blank=True)
    pages_kept = models.PositiveIntegerField(default=0)
    products_count = models.PositiveIntegerField(default=0)
    advertisement_pages_skipped = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    cost_breakdown = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ai_extraction_runs',
    )

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Run {self.pk} ({self.status})'