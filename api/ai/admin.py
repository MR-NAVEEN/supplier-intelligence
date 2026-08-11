from django.contrib import admin

from .models import AICatalogueUpload, AIExtractionRun


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