from rest_framework import serializers

from .models import Product, ProductImage, ProductNote


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = '__all__'
        read_only_fields = ('id', 'product', 'created_at', 'updated_at')


class ProductNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductNote
        fields = '__all__'
        read_only_fields = ('id', 'product', 'created_by', 'created_at', 'updated_at')


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = (
            'id', 'supplier', 'category', 'name', 'sku', 'description', 'price', 'currency',
            'status', 'extraction_status', 'tags', 'ai_summary', 'source', 'metadata',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'ai_summary', 'created_at', 'updated_at')
