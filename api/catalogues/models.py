from django.conf import settings
from django.db import models

from api.common.models import TimeStampedModel, WorkspaceScopedModel


class Catalogue(WorkspaceScopedModel):
    STATUS_DRAFT = 'draft'
    STATUS_QUEUED = 'queued'
    STATUS_PROCESSING = 'processing'
    STATUS_REVIEW = 'review'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_REVIEW, 'Review'),
        (STATUS_READY, 'Ready'),
        (STATUS_FAILED, 'Failed'),
    ]

    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='catalogues',
    )
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    current_version = models.PositiveIntegerField(default=1)
    ai_insights = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='catalogues_created',
    )


class CatalogueVersion(TimeStampedModel):
    catalogue = models.ForeignKey(Catalogue, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    notes = models.TextField(blank=True)


class CatalogueFile(TimeStampedModel):
    catalogue_version = models.ForeignKey(
        CatalogueVersion,
        on_delete=models.CASCADE,
        related_name='files',
    )
    file = models.FileField(upload_to='catalogue_files/')
    filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=128, blank=True)
    page_count = models.PositiveIntegerField(default=0)


class UploadSession(TimeStampedModel):
    STATUS_OPEN = 'open'
    STATUS_COMMITTED = 'committed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_COMMITTED, 'Committed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    workspace = models.ForeignKey('workspaces.Workspace', on_delete=models.CASCADE, related_name='upload_sessions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_OPEN)
    catalogue = models.ForeignKey(Catalogue, on_delete=models.SET_NULL, null=True, blank=True)
    files_meta = models.JSONField(default=list, blank=True)


class ExtractionCandidate(TimeStampedModel):
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    catalogue = models.ForeignKey(Catalogue, on_delete=models.CASCADE, related_name='extractions')
    page_number = models.PositiveIntegerField(default=1)
    raw_data = models.JSONField(default=dict, blank=True)
    normalized_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    confidence = models.FloatField(default=0.0)
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extraction_candidates',
    )


class OcrPage(TimeStampedModel):
    catalogue_file = models.ForeignKey(CatalogueFile, on_delete=models.CASCADE, related_name='ocr_pages')
    page_number = models.PositiveIntegerField()
    text = models.TextField(blank=True)
    blocks = models.JSONField(default=list, blank=True)
