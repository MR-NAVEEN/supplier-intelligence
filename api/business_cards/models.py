from django.conf import settings
from django.db import models

from api.common.models import TimeStampedModel, WorkspaceScopedModel


class BusinessCard(WorkspaceScopedModel):
    STATUS_EXTRACTED = 'extracted'
    STATUS_COMMITTED = 'committed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_EXTRACTED, 'Extracted'),
        (STATUS_COMMITTED, 'Committed'),
        (STATUS_FAILED, 'Failed'),
    ]

    image = models.ImageField(upload_to='business_cards/')
    extracted_data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_EXTRACTED)
    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='business_cards',
    )
    job = models.ForeignKey(
        'jobs.Job',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='business_cards',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='business_cards',
    )
