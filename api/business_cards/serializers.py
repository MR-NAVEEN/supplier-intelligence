from rest_framework import serializers

from .models import BusinessCard


class BusinessCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessCard
        fields = (
            'id', 'image', 'extracted_data', 'status', 'supplier', 'job',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'extracted_data', 'status', 'supplier', 'job', 'created_at', 'updated_at')
