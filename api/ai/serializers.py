from rest_framework import serializers

from .models import (
    AIBusinessCard,
    AICatalogue,
    AICatalogueUpload,
    AIExtractedPage,
    AIExtractedProduct,
    AIExtractionRun,
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class AIExtractRequestSerializer(serializers.Serializer):
    file = serializers.FileField()
    card = serializers.CharField(required=True)
    page_mode = serializers.ChoiceField(choices=AIExtractionRun.PAGE_MODE_CHOICES)
    page_count = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    page_range = serializers.CharField(required=False, allow_blank=True, max_length=128)
    model_tier = serializers.ChoiceField(
        choices=AIExtractionRun.MODEL_TIER_CHOICES,
        required=False,
        default=AIExtractionRun.TIER_HIGH,
    )
    dpi = serializers.IntegerField(required=False, default=200, min_value=72, max_value=300)

    def validate_file(self, value):
        name = (getattr(value, 'name', '') or '').lower()
        content_type = (getattr(value, 'content_type', '') or '').lower()
        if not name.endswith('.pdf') and content_type not in ('application/pdf', 'application/x-pdf'):
            raise serializers.ValidationError('Only PDF files are accepted.')
        size = getattr(value, 'size', 0) or 0
        if size > MAX_UPLOAD_BYTES:
            raise serializers.ValidationError('PDF is larger than 50 MB.')
        return value

    def validate(self, attrs):
        mode = attrs.get('page_mode')
        card = AIBusinessCard.objects.filter(id = attrs.get('card')).first()
        if not card:
            raise serializers.ValidationError("give me the valid card id")
        if mode == AIExtractionRun.MODE_FIRST_N and not attrs.get('page_count'):
            raise serializers.ValidationError({'page_count': 'Required when page_mode is first_n.'})
        if mode == AIExtractionRun.MODE_RANGE and not (attrs.get('page_range') or '').strip():
            raise serializers.ValidationError({'page_range': 'Required when page_mode is range.'})
        return attrs


class AICatalogueUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = AICatalogueUpload
        fields = (
            'id',
            'original_filename',
            'file_size_bytes',
            'total_pages',
            'content_type',
            'created_at',
        )
        read_only_fields = fields


class AIExtractionRunSerializer(serializers.ModelSerializer):
    upload = AICatalogueUploadSerializer(read_only=True)
    timing = serializers.SerializerMethodField()
    costing = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    result = serializers.SerializerMethodField()

    class Meta:
        model = AIExtractionRun
        fields = (
            'id',
            'upload',
            'status',
            'page_mode',
            'page_count',
            'page_range',
            'pages_requested',
            'model_tier',
            'model_name',
            'dpi',
            'result',
            'summary',
            'timing',
            'costing',
            'error_message',
            'created_at',
        )
        read_only_fields = fields

    def get_result(self, obj):
        return obj.result_json or {}

    def get_summary(self, obj):
        return {
            'pages_kept': obj.pages_kept,
            'products_count': obj.products_count,
            'advertisement_pages_skipped': obj.advertisement_pages_skipped,
        }

    def get_timing(self, obj):
        seconds = round((obj.duration_ms or 0) / 1000, 2)
        return {
            'started_at': obj.started_at,
            'finished_at': obj.finished_at,
            'duration_ms': obj.duration_ms,
            'duration_seconds': seconds,
        }

    def get_costing(self, obj):
        return {
            'currency': 'USD',
            'estimated_cost_usd': str(obj.estimated_cost_usd),
            'prompt_tokens': obj.prompt_tokens,
            'completion_tokens': obj.completion_tokens,
            'total_tokens': obj.total_tokens,
            'model_name': obj.model_name,
            'breakdown': obj.cost_breakdown or {},
        }


class AIExtractedProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIExtractedProduct
        fields = (
            'id',
            'page_number',
            'product_name',
            'code_or_sku',
            'price',
            'price_raw',
            'currency',
            'description',
            'series',
            'attributes',
            'is_current',
            'created_at',
        )
        read_only_fields = fields


class AIExtractedProductWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIExtractedProduct
        fields = (
            'id',
            'business_card',
            'catalogue',
            'run',
            'page',
            'page_number',
            'product_name',
            'code_or_sku',
            'price',
            'price_raw',
            'currency',
            'description',
            'series',
            'attributes',
            'is_current',
            'created_at',
        )
        read_only_fields = ('id', 'created_at')


class AIExtractedPageSerializer(serializers.ModelSerializer):
    products = serializers.SerializerMethodField()

    class Meta:
        model = AIExtractedPage
        fields = (
            'id',
            'page_number',
            'page_type',
            'series_or_section_title',
            'raw_text_summary',
            'page_notes',
            'is_current',
            'products',
        )
        read_only_fields = fields

    def get_products(self, obj):
        qs = obj.products.filter(is_current=True)
        return AIExtractedProductSerializer(qs, many=True).data


class AICatalogueListSerializer(serializers.ModelSerializer):
    products_count = serializers.SerializerMethodField()
    pages_count = serializers.SerializerMethodField()

    class Meta:
        model = AICatalogue
        fields = (
            'id',
            'title',
            'brand',
            'source_filename',
            'total_pages',
            'current_run',
            'products_count',
            'pages_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_products_count(self, obj):
        return obj.products.filter(is_current=True).count()

    def get_pages_count(self, obj):
        return obj.pages.filter(is_current=True).count()


class AICatalogueSchemaSerializer(serializers.ModelSerializer):
    pages = serializers.SerializerMethodField()
    products = serializers.SerializerMethodField()

    class Meta:
        model = AICatalogue
        fields = (
            'id',
            'title',
            'brand',
            'source_filename',
            'total_pages',
            'current_run',
            'pages',
            'products',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_pages(self, obj):
        qs = obj.pages.filter(is_current=True).prefetch_related('products')
        return AIExtractedPageSerializer(qs, many=True).data

    def get_products(self, obj):
        qs = obj.products.filter(is_current=True)
        return AIExtractedProductSerializer(qs, many=True).data


class AIExtractionRunListSerializer(serializers.ModelSerializer):
    source_file = serializers.CharField(source='upload.original_filename', read_only=True)

    class Meta:
        model = AIExtractionRun
        fields = (
            'id',
            'source_file',
            'status',
            'page_mode',
            'pages_requested',
            'pages_kept',
            'products_count',
            'duration_ms',
            'estimated_cost_usd',
            'created_at',
        )
        read_only_fields = fields


CARD_CONTENT_TYPES = {
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/webp',
    'image/gif',
}
CARD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


class AICardExtractRequestSerializer(serializers.Serializer):
    file = serializers.FileField()
    model_tier = serializers.ChoiceField(
        choices=AIExtractionRun.MODEL_TIER_CHOICES,
        required=False,
        default=AIExtractionRun.TIER_HIGH,
    )

    def validate_file(self, value):
        name = (getattr(value, 'name', '') or '').lower()
        content_type = (getattr(value, 'content_type', '') or '').lower()
        ext = ''
        if '.' in name:
            ext = '.' + name.rsplit('.', 1)[-1]
        if ext not in CARD_EXTENSIONS and content_type not in CARD_CONTENT_TYPES:
            raise serializers.ValidationError('Upload a card image (jpg, png, webp).')
        size = getattr(value, 'size', 0) or 0
        if size > MAX_UPLOAD_BYTES:
            raise serializers.ValidationError('File is larger than 50 MB.')
        return value


class AIBusinessCardSerializer(serializers.ModelSerializer):
    timing = serializers.SerializerMethodField()
    costing = serializers.SerializerMethodField()

    class Meta:
        model = AIBusinessCard
        fields = (
            'id',
            'original_filename',
            'status',
            'full_name',
            'job_title',
            'company',
            'emails',
            'phones',
            'website',
            'address',
            'linkedin',
            'extras',
            'extra_text',
            'result_json',
            'model_name',
            'timing',
            'costing',
            'error_message',
            'created_at',
        )
        read_only_fields = fields

    def get_timing(self, obj):
        return {
            'started_at': obj.started_at,
            'finished_at': obj.finished_at,
            'duration_ms': obj.duration_ms,
            'duration_seconds': round((obj.duration_ms or 0) / 1000, 2),
        }

    def get_costing(self, obj):
        return {
            'currency': 'USD',
            'estimated_cost_usd': str(obj.estimated_cost_usd),
            'prompt_tokens': obj.prompt_tokens,
            'completion_tokens': obj.completion_tokens,
            'total_tokens': obj.total_tokens,
            'model_name': obj.model_name,
            'breakdown': obj.cost_breakdown or {},
        }


class AIBusinessCardListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIBusinessCard
        fields = (
            'id',
            'original_filename',
            'status',
            'full_name',
            'job_title',
            'company',
            'emails',
            'phones',
            'duration_ms',
            'website',
            'address',
            'linkedin',
            'extras',
            'extra_text',
            'estimated_cost_usd',
            'created_at',
        )
        read_only_fields = fields