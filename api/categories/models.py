from django.db import models

from api.common.models import WorkspaceScopedModel


class Category(WorkspaceScopedModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ('workspace', 'slug')
        ordering = ['name']

    def __str__(self):
        return self.name
