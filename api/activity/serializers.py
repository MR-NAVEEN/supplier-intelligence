from rest_framework import serializers

from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = ('id', 'action', 'entity_type', 'entity_id', 'metadata', 'user', 'created_at')
        read_only_fields = fields
