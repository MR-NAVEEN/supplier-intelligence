from rest_framework import serializers

from .models import (
    AIAttachment,
    AIBusinessCard,
    AICatalogue,
    AICatalogueUpload,
    AIExtractedPage,
    AIExtractedProduct,
    AIExtractionRun,
    Note,
)
from .services.files import (
    MAX_UPLOAD_BYTES,
    classify_upload,
    upload_too_large,
)


class AIExtractRequestSerializer(serializers.Serializer):
    card = serializers.CharField(required=True)
    files = serializers.ListField(child=serializers.FileField(), allow_empty=False)
    page_mode = serializers.ChoiceField(
        choices=AIExtractionRun.PAGE_MODE_CHOICES,
        required=False,
        allow_null=True,
    )
    page_count = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    page_range = serializers.CharField(required=False, allow_blank=True, max_length=128)
    model_tier = serializers.ChoiceField(
        choices=AIExtractionRun.MODEL_TIER_CHOICES,
        required=False,
        default=AIExtractionRun.TIER_HIGH,
    )
    dpi = serializers.IntegerField(required=False, default=200, min_value=72, max_value=300)

    def validate_files(self, value):
        kinds = []
        for item in value:
            if upload_too_large(item):
                raise serializers.ValidationError('Each file must be 50 MB or smaller.')
            kind = classify_upload(item)
            if kind in {'spreadsheet', 'xls'}:
                raise serializers.ValidationError(
                    'Excel/CSV files must be sent to POST /api/ai/bulk-upload/, not /api/ai/extract/.'
                )
            if kind == 'unknown':
                raise serializers.ValidationError(
                    f'{item.name}: upload a PDF or photo (jpg, png, webp, gif, tiff).'
                )
            kinds.append(kind)
        unique = set(kinds)
        if 'pdf' in unique and 'image' in unique:
            raise serializers.ValidationError('Send either one PDF or photo files, not both in the same request.')
        if kinds.count('pdf') > 1:
            raise serializers.ValidationError('Upload one PDF per request.')
        return value

    def validate(self, attrs):
        files = attrs.get('files') or []
        kinds = {classify_upload(item) for item in files}
        mode = attrs.get('page_mode')
        card_id = attrs.get('card')
        if not AIBusinessCard.objects.filter(id=card_id).exists():
            raise serializers.ValidationError({'card': 'No business card found for that id.'})
        if 'pdf' in kinds and not mode:
            raise serializers.ValidationError({'page_mode': 'Required for PDF uploads (full, first_n, or range).'})
        if not mode:
            attrs['page_mode'] = AIExtractionRun.MODE_FULL
            mode = attrs['page_mode']
        if mode == AIExtractionRun.MODE_FIRST_N and not attrs.get('page_count'):
            raise serializers.ValidationError({'page_count': 'Required when page_mode is first_n.'})
        if mode == AIExtractionRun.MODE_RANGE and not (attrs.get('page_range') or '').strip():
            raise serializers.ValidationError({'page_range': 'Required when page_mode is range.'})
        return attrs


class AIBulkUploadRequestSerializer(serializers.Serializer):
    file = serializers.FileField()
    supplier = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    sheet = serializers.CharField(required=False, allow_blank=True, max_length=128)
    header_row = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    column_map = serializers.CharField(required=False, allow_blank=True)
    max_rows = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=20000)

    def validate_file(self, value):
        if upload_too_large(value):
            raise serializers.ValidationError('File is larger than 50 MB.')
        kind = classify_upload(value)
        if kind == 'xls':
            raise serializers.ValidationError('Legacy .xls is not supported. Save as .xlsx or CSV.')
        if kind != 'spreadsheet':
            raise serializers.ValidationError('Upload a .xlsx, .xlsm, .csv, or .tsv file.')
        return value


class AICardBulkUploadRequestSerializer(serializers.Serializer):
    file = serializers.FileField()
    supplier = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    sheet = serializers.CharField(required=False, allow_blank=True, max_length=128)
    header_row = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    column_map = serializers.CharField(required=False, allow_blank=True)
    max_rows = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=20000)

    def validate_file(self, value):
        if upload_too_large(value):
            raise serializers.ValidationError('File is larger than 50 MB.')
        kind = classify_upload(value)
        if kind == 'xls':
            raise serializers.ValidationError('Legacy .xls is not supported. Save as .xlsx or CSV.')
        if kind != 'spreadsheet':
            raise serializers.ValidationError('Upload a .xlsx, .xlsm, .csv, or .tsv file.')
        return value


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
            'supplier',
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
    'image/bmp',
    'image/tiff',
    'application/pdf',
    'application/x-pdf',
}
CARD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.pdf'}
MAX_CARD_FILES = 6


def _validate_card_upload(value):
    name = (getattr(value, 'name', '') or '').lower()
    content_type = (getattr(value, 'content_type', '') or '').lower()
    ext = ''
    if '.' in name:
        ext = '.' + name.rsplit('.', 1)[-1]
    if ext not in CARD_EXTENSIONS and content_type not in CARD_CONTENT_TYPES:
        raise serializers.ValidationError('Upload card files as jpg, png, webp, gif, or pdf.')
    size = getattr(value, 'size', 0) or 0
    if size > MAX_UPLOAD_BYTES:
        raise serializers.ValidationError('File is larger than 50 MB.')
    return value


class AICardExtractRequestSerializer(serializers.Serializer):
    supplier = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    files = serializers.ListField(child=serializers.FileField(), allow_empty=False)
    model_tier = serializers.ChoiceField(
        choices=AIExtractionRun.MODEL_TIER_CHOICES,
        required=False,
        default=AIExtractionRun.TIER_HIGH,
    )

    def validate_files(self, value):
        if len(value) > MAX_CARD_FILES:
            raise serializers.ValidationError(f'Upload at most {MAX_CARD_FILES} card files (front, back, extra sides).')
        return [_validate_card_upload(item) for item in value]


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
            'brands',
            'extras',
            'extra_text',
            'source_files',
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


class AIChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2000)
    session_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    catalogue_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class AIAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIAttachment
        fields = (
            'id',
            'note',
            'file',
            'original_filename',
            'attachment_type',
            'document_type',
            'image_type',
            'mime_type',
            'file_size',
            'uploaded_by',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'mime_type', 'file_size', 'uploaded_by', 'created_at', 'updated_at')

    def validate(self, attrs):
        attachment_type = attrs.get('attachment_type') or getattr(self.instance, 'attachment_type', None)
        if attachment_type == AIAttachment.AttachmentType.DOCUMENT and not (
            attrs.get('document_type') or getattr(self.instance, 'document_type', None)
        ):
            raise serializers.ValidationError({'document_type': 'Required when attachment_type is document.'})
        if attachment_type == AIAttachment.AttachmentType.IMAGE and not (
            attrs.get('image_type') or getattr(self.instance, 'image_type', None)
        ):
            raise serializers.ValidationError({'image_type': 'Required when attachment_type is image.'})
        return attrs


class NoteSerializer(serializers.ModelSerializer):
    attachments = AIAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Note
        fields = (
            'id',
            'business_card',
            'catalogue',
            'title',
            'description',
            'created_by',
            'attachments',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'attachments', 'created_at', 'updated_at')


class NoteListSerializer(serializers.ModelSerializer):
    attachments_count = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = (
            'id',
            'business_card',
            'catalogue',
            'title',
            'description',
            'created_by',
            'attachments_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_attachments_count(self, obj):
        return obj.attachments.count()


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
            'brands',
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