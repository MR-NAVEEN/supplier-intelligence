import os
from decimal import Decimal

from django.core.files.storage import default_storage
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from api.common.pagination import StandardPagination
from api.common.responses import error_envelope, success_envelope

from .models import (
    AIBusinessCard,
    AICatalogue,
    AICatalogueUpload,
    AIChatSession,
    AIChatTurn,
    AIExtractedProduct,
    AIExtractionRun,
)
from .workspace import get_default_workspace, optional_user
from .serializers import (
    AIBusinessCardListSerializer,
    AIBusinessCardSerializer,
    AICardExtractRequestSerializer,
    AICatalogueListSerializer,
    AICatalogueSchemaSerializer,
    AIChatRequestSerializer,
    AIExtractedProductSerializer,
    AIExtractRequestSerializer,
    AIExtractionRunListSerializer,
    AIExtractionRunSerializer,
)
from .services.card_extract import extract_business_card
from .services.chat import answer_question
from .services.costing import estimate_cost
from .services.extraction import MODEL_TIERS, extract_catalogue, pdf_page_count
from .services.page_selection import resolve_pages
from .services.persist import persist_run_to_schema


class AIOpenViewSetMixin:
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = StandardPagination

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return success_envelope(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_envelope(serializer.data)


class AIExtractionRunViewSet(AIOpenViewSetMixin, viewsets.GenericViewSet):
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

        workspace = get_default_workspace()
        user = optional_user(request)
        upload = AICatalogueUpload.objects.create(
            workspace=workspace,
            file=uploaded,
            original_filename=uploaded.name,
            file_size_bytes=getattr(uploaded, 'size', 0) or 0,
            content_type=getattr(uploaded, 'content_type', '') or 'application/pdf',
            uploaded_by=user,
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
            workspace=workspace,
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
            created_by=user,
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
            persist_run_to_schema(run, result)
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


class AICatalogueViewSet(AIOpenViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AICatalogue.objects.all()
    serializer_class = AICatalogueListSerializer
    http_method_names = ['get', 'head', 'options']
    search_fields = ('title', 'brand', 'source_filename')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AICatalogueSchemaSerializer
        return AICatalogueListSerializer


class AICatalogueProductViewSet(AIOpenViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AIExtractedProduct.objects.select_related('catalogue').all()
    serializer_class = AIExtractedProductSerializer
    http_method_names = ['get', 'head', 'options']
    search_fields = ('product_name', 'code_or_sku', 'series', 'search_text')

    def get_queryset(self):
        qs = AIExtractedProduct.objects.filter(is_current=True).select_related('catalogue')
        catalogue_id = self.kwargs.get('catalogue_pk')
        if catalogue_id:
            qs = qs.filter(catalogue_id=catalogue_id)
        page_number = self.request.query_params.get('page_number')
        if page_number:
            qs = qs.filter(page_number=page_number)
        sku = self.request.query_params.get('sku')
        if sku:
            qs = qs.filter(code_or_sku__icontains=sku)
        return qs


class AIBusinessCardViewSet(AIOpenViewSetMixin, viewsets.GenericViewSet):
    queryset = AIBusinessCard.objects.all()
    serializer_class = AIBusinessCardSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return AIBusinessCardListSerializer
        return AIBusinessCardSerializer

    def get_queryset(self):
        qs = AIBusinessCard.objects.all()
        company = self.request.query_params.get('company')
        if company:
            qs = qs.filter(company__icontains=company)
        name = self.request.query_params.get('name')
        if name:
            qs = qs.filter(full_name__icontains=name)
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(
                Q(full_name__icontains=q)
                | Q(company__icontains=q)
                | Q(job_title__icontains=q)
            )
        return qs

    def _collect_uploads(self, request):
        uploads = []
        seen = set()
        for key in ('file', 'files', 'files[]'):
            for item in request.FILES.getlist(key):
                marker = id(item)
                if marker in seen:
                    continue
                seen.add(marker)
                uploads.append(item)
        return uploads

    def create(self, request, *args, **kwargs):
        uploads = self._collect_uploads(request)
        if not uploads:
            return error_envelope('Upload at least one card file (jpg, png, webp, pdf). Repeat key "file" for front and back.', 400)
        serializer = AICardExtractRequestSerializer(
            data={
                'files': uploads,
                'model_tier': request.data.get('model_tier') or AIExtractionRun.TIER_HIGH,
            }
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        uploads = data['files']
        model_tier = data.get('model_tier') or AIExtractionRun.TIER_HIGH
        model_name = MODEL_TIERS.get(model_tier, MODEL_TIERS['high_accuracy'])
        workspace = get_default_workspace()
        user = optional_user(request)
        first = uploads[0]
        source_files = [
            {
                'filename': item.name,
                'content_type': getattr(item, 'content_type', '') or '',
                'size_bytes': getattr(item, 'size', 0) or 0,
            }
            for item in uploads
        ]

        card = AIBusinessCard.objects.create(
            workspace=workspace,
            image=first,
            original_filename=', '.join(item.name for item in uploads),
            content_type=getattr(first, 'content_type', '') or '',
            file_size_bytes=sum(getattr(item, 'size', 0) or 0 for item in uploads),
            source_files=source_files,
            status=AIBusinessCard.STATUS_PENDING,
            model_tier=model_tier,
            model_name=model_name,
            started_at=timezone.now(),
            created_by=user,
        )
        saved_paths = [card.image.path]
        try:
            for index, uploaded in enumerate(uploads[1:], start=2):
                stored_name = default_storage.save(
                    f'ai/cards/{workspace.id}/side{index}_{uploaded.name}',
                    uploaded,
                )
                saved_paths.append(default_storage.path(stored_name))
            extracted = extract_business_card(saved_paths, model_name)
            finished = timezone.now()
            result = extracted['result']
            usage = extracted['usage']
            costing = estimate_cost(model_name, usage['prompt_tokens'], usage['completion_tokens'])
            card.status = AIBusinessCard.STATUS_SUCCEEDED
            card.full_name = result.get('full_name') or ''
            card.job_title = result.get('job_title') or ''
            card.company = result.get('company') or ''
            card.emails = result.get('emails') or []
            card.phones = result.get('phones') or []
            card.website = result.get('website') or ''
            card.address = result.get('address') or ''
            card.linkedin = result.get('linkedin') or ''
            card.brands = result.get('brands') or []
            card.extras = result.get('extras') or {}
            card.extra_text = result.get('extra_text') or ''
            card.result_json = result
            card.finished_at = finished
            card.duration_ms = int((finished - card.started_at).total_seconds() * 1000)
            card.prompt_tokens = usage['prompt_tokens']
            card.completion_tokens = usage['completion_tokens']
            card.total_tokens = usage['total_tokens']
            card.estimated_cost_usd = costing['estimated_cost_usd']
            card.cost_breakdown = costing['breakdown']
            card.save()
        except Exception as exc:  # noqa: BLE001
            card.status = AIBusinessCard.STATUS_FAILED
            card.finished_at = timezone.now()
            if card.started_at:
                card.duration_ms = int((card.finished_at - card.started_at).total_seconds() * 1000)
            card.error_message = str(exc)
            card.save()
            status_code = 502
            lowered = str(exc).lower()
            if 'openai_api_key' in lowered:
                status_code = 500
            if any(token in lowered for token in ('insufficient_quota', 'credit_balance_exhausted')):
                status_code = 402
            return error_envelope(str(exc), status_code, data=AIBusinessCardSerializer(card).data)

        return success_envelope(AIBusinessCardSerializer(card).data, 'Card extracted', 201)


class AIChatView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [JSONParser, FormParser]

    def post(self, request, *args, **kwargs):
        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        message = data['message'].strip()
        if not message:
            return error_envelope('message is required', 400)

        workspace = get_default_workspace()
        session = None
        session_id = data.get('session_id')
        if session_id:
            session = AIChatSession.objects.filter(pk=session_id, workspace=workspace).first()
            if session is None:
                return error_envelope('Unknown session_id', 404)
        else:
            session = AIChatSession.objects.create(workspace=workspace)

        result = answer_question(
            message,
            catalogue_id=data.get('catalogue_id'),
            last_context=session.last_context or {},
        )
        session.last_context = result['context']
        session.save(update_fields=['last_context', 'updated_at'])
        AIChatTurn.objects.create(
            session=session,
            question=message,
            answer=result['answer'],
            intent=result['intent'],
            sources=result['sources'],
        )
        return success_envelope(
            {
                'session_id': session.id,
                'answer': result['answer'],
                'intent': result['intent'],
                'sources': result['sources'],
            },
            'Answered',
        )