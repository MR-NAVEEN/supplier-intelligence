from django.conf import settings
from django.db import models

from api.common.models import TimeStampedModel, WorkspaceScopedModel


class Product(WorkspaceScopedModel):
    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'
    STATUS_NEEDS_REVIEW = 'needs_review'
    STATUS_VERIFIED = 'verified'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ARCHIVED, 'Archived'),
        (STATUS_NEEDS_REVIEW, 'Needs Review'),
        (STATUS_VERIFIED, 'Verified'),
    ]
    SOURCE_MANUAL = 'manual'
    SOURCE_AI = 'ai_extraction'
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, 'Manual'),
        (SOURCE_AI, 'AI Extraction'),
    ]

    supplier = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
    )
    category = models.ForeignKey(
        'categories.Category',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=128, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=8, default='INR')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    extraction_status = models.CharField(max_length=32, blank=True)
    tags = models.JSONField(default=list, blank=True)
    ai_summary = models.TextField(blank=True)
    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='products_created',
    )

    class Meta:
        ordering = ['-created_at']


class ProductImage(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    file = models.ImageField(upload_to='product_images/')
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)


class ProductNote(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='product_notes',
    )
