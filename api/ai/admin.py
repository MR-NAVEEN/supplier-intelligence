from django.contrib import admin

from .models import (
    AIBusinessCard,
    AICatalogue,
    AICatalogueUpload,
    AIChatSession,
    AIChatTurn,
    AIExtractedPage,
    AIExtractedProduct,
    AIExtractionRun,
)


@admin.register(AICatalogue)
class AICatalogueAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'source_filename', 'workspace', 'current_run', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AICatalogueUpload)
class AICatalogueUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'original_filename', 'total_pages', 'workspace', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(AIExtractionRun)
class AIExtractionRunAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'upload',
        'status',
        'page_mode',
        'products_count',
        'duration_ms',
        'estimated_cost_usd',
        'created_at',
    )
    readonly_fields = ('created_at', 'updated_at', 'result_json', 'cost_breakdown')


@admin.register(AIExtractedPage)
class AIExtractedPageAdmin(admin.ModelAdmin):
    list_display = ('id', 'catalogue', 'page_number', 'series_or_section_title', 'is_current')


@admin.register(AIExtractedProduct)
class AIExtractedProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'product_name', 'code_or_sku', 'price_raw', 'page_number', 'is_current')


@admin.register(AIBusinessCard)
class AIBusinessCardAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'company', 'status', 'created_at')
    readonly_fields = ('created_at', 'updated_at', 'result_json', 'source_files', 'cost_breakdown')


@admin.register(AIChatSession)
class AIChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'workspace', 'updated_at')
    readonly_fields = ('created_at', 'updated_at', 'last_context')


@admin.register(AIChatTurn)
class AIChatTurnAdmin(admin.ModelAdmin):
    list_display = ('id', 'session', 'intent', 'created_at')
    readonly_fields = ('created_at', 'updated_at', 'sources')