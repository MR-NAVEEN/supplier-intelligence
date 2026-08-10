from django.db import models

from api.common.models import TimeStampedModel


class Workspace(TimeStampedModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='owned_workspaces',
    )
    settings = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.name


class WorkspaceMembership(TimeStampedModel):
    ROLE_ADMIN = 'admin'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_MEMBER, 'Member'),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='workspace_memberships')
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER)

    class Meta:
        unique_together = ('workspace', 'user')

    def __str__(self):
        return f'{self.user.email} @ {self.workspace.name} ({self.role})'
