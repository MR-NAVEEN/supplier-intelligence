from rest_framework import serializers

from .models import (
    Catalogue,
    CatalogueFile,
    CatalogueVersion,
    ExtractionCandidate,
    OcrPage,
    UploadSession,
)


class CatalogueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Catalogue
        fields = (
            'id', 'supplier', 'title', 'status', 'current_version', 'ai_insights',
            'metadata', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'ai_insights', 'created_at', 'updated_at')


class CatalogueVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogueVersion
        fields = '__all__'
        read_only_fields = ('id', 'catalogue', 'created_at', 'updated_at')


class CatalogueFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogueFile
        fields = '__all__'
        read_only_fields = ('id', 'catalogue_version', 'created_at', 'updated_at')


class UploadSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadSession
        fields = '__all__'
        read_only_fields = ('id', 'workspace', 'user', 'catalogue', 'created_at', 'updated_at')


class ExtractionCandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExtractionCandidate
        fields = '__all__'
        read_only_fields = ('id', 'catalogue', 'product', 'created_at', 'updated_at')


class OcrPageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OcrPage
        fields = '__all__'
        read_only_fields = ('id', 'catalogue_file', 'created_at', 'updated_at')
