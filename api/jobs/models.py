from django.conf import settings
from django.db import models

from api.common.models import TimeStampedModel, WorkspaceScopedModel


class Job(WorkspaceScopedModel):
    TYPE_CATALOGUE_OCR = 'catalogue_ocr'
    TYPE_CATALOGUE_EXTRACTION = 'catalogue_extraction'
    TYPE_BUSINESS_CARD_OCR = 'business_card_ocr'
    TYPE_REPROCESS = 'reprocess'
    TYPE_CHOICES = [
        (TYPE_CATALOGUE_OCR, 'Catalogue OCR'),
        (TYPE_CATALOGUE_EXTRACTION, 'Catalogue Extraction'),
        (TYPE_BUSINESS_CARD_OCR, 'Business Card OCR'),
        (TYPE_REPROCESS, 'Reprocess'),
    ]
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    job_type = models.CharField(max_length=64, choices=TYPE_CHOICES)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    progress = models.PositiveSmallIntegerField(default=0)
    entity_type = models.CharField(max_length=64, blank=True)
    entity_id = models.CharField(max_length=64, blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='jobs_created',
    )

    class Meta:
        ordering = ['-created_at']
