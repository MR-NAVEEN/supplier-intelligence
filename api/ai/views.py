import os
from decimal import Decimal

from django.utils import timezone
from rest_framework.parsers import FormParser, MultiPartParser

from api.common.responses import error_envelope, success_envelope
from api.common.views import WorkspaceViewSet

from .models import AICatalogueUpload, AIExtractionRun
from .serializers import (
    AIExtractRequestSerializer,
    AIExtractionRunListSerializer,
    AIExtractionRunSerializer,
)
from .services.costing import estimate_cost
from .services.extraction import MODEL_TIERS, extract_catalogue, pdf_page_count
from .services.page_selection import resolve_pages


class AIExtractionRunViewSet(WorkspaceViewSet):
    queryset = AIExtractionRun.objects.select_related('upload').all()
    serializer_class = AIExtractionRunSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return AIExtractionRunListSerializer
        return AIExtractionRunSerializer

    def create(self, request, *args, **kwargs):
        serializer = AIExtractRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        uploaded = data['file']

        max_pages = int(os.environ.get('AI_MAX_PAGES_PER_REQUEST', '30'))
        model_tier = data.get('model_tier') or AIExtractionRun.TIER_HIGH
        model_name = MODEL_TIERS.get(model_tier, MODEL_TIERS['high_accuracy'])
        dpi = data.get('dpi') or 200

        upload = AICatalogueUpload.objects.create(
            workspace=request.workspace,
            file=uploaded,
            original_filename=uploaded.name,
            file_size_bytes=getattr(uploaded, 'size', 0) or 0,
            content_type=getattr(uploaded, 'content_type', '') or 'application/pdf',
            uploaded_by=request.user,
        )
        try:
            total_pages = pdf_page_count(upload.file.path)
        except Exception as exc:  # noqa: BLE001
            upload.delete()
            return error_envelope(f'Could not read PDF: {exc}', 400)

        upload.total_pages = total_pages
        upload.save(update_fields=['total_pages', 'updated_at'])

        pages = resolve_pages(
            page_mode=data['page_mode'],
            total_pages=total_pages,
            page_count=data.get('page_count'),
            page_range=data.get('page_range'),
            max_pages=max_pages,
        )

        run = AIExtractionRun.objects.create(
            workspace=request.workspace,
            upload=upload,
            status=AIExtractionRun.STATUS_RUNNING,
            page_mode=data['page_mode'],
            page_count=data.get('page_count'),
            page_range=(data.get('page_range') or '').strip(),
            pages_requested=pages,
            model_tier=model_tier,
            model_name=model_name,
            dpi=dpi,
            started_at=timezone.now(),
            created_by=request.user,
        )

        try:
            extracted = extract_catalogue(upload.file.path, pages, model_name, dpi=dpi)
            finished = timezone.now()
            duration_ms = int((finished - run.started_at).total_seconds() * 1000)
            result = extracted['result']
            usage = extracted['usage']
            costing = estimate_cost(model_name, usage['prompt_tokens'], usage['completion_tokens'])
            pages_kept = len(result.get('pages') or [])
            products_count = sum(len(page.get('products') or []) for page in (result.get('pages') or []))
            pages_billed = len(pages)
            costing['breakdown']['pages_billed'] = pages_billed
            if pages_billed:
                avg = (costing['estimated_cost_usd'] / Decimal(pages_billed)).quantize(Decimal('0.000001'))
                costing['breakdown']['avg_cost_per_page_usd'] = str(avg)

            run.status = AIExtractionRun.STATUS_SUCCEEDED
            run.result_json = result
            run.pages_kept = pages_kept
            run.products_count = products_count
            run.advertisement_pages_skipped = extracted['advertisement_pages_skipped']
            run.finished_at = finished
            run.duration_ms = duration_ms
            run.prompt_tokens = usage['prompt_tokens']
            run.completion_tokens = usage['completion_tokens']
            run.total_tokens = usage['total_tokens']
            run.estimated_cost_usd = costing['estimated_cost_usd']
            run.cost_breakdown = costing['breakdown']
            run.save()
        except Exception as exc:  # noqa: BLE001
            run.status = AIExtractionRun.STATUS_FAILED
            run.finished_at = timezone.now()
            if run.started_at:
                run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
            run.error_message = str(exc)
            run.save(
                update_fields=[
                    'status',
                    'finished_at',
                    'duration_ms',
                    'error_message',
                    'updated_at',
                ]
            )
            message = str(exc)
            status_code = 502
            lowered = message.lower()
            if 'openai_api_key' in lowered:
                status_code = 500
            if any(token in lowered for token in ('insufficient_quota', 'credit_balance_exhausted')):
                status_code = 402
            return error_envelope(message, status_code, data=AIExtractionRunSerializer(run).data)

        return success_envelope(AIExtractionRunSerializer(run).data, 'Extraction completed', 201)