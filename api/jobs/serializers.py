from rest_framework import serializers

from .models import Job


class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = (
            'id', 'job_type', 'status', 'progress', 'entity_type', 'entity_id',
            'result', 'error', 'created_by', 'created_at', 'updated_at',
        )
        read_only_fields = fields
