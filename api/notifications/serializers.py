from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            'id', 'notification_type', 'title', 'message', 'is_read',
            'metadata', 'created_at', 'updated_at',
        )
        read_only_fields = fields
