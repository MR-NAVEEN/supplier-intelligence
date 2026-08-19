import os
from decimal import Decimal

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from api.common.pagination import StandardPagination
from api.common.responses import error_envelope, success_envelope

from .models import (
    AIAttachment,
    AIBusinessCard,
    AICatalogue,
    AICatalogueUpload,
    AIChatSession,
    AIChatTurn,
    AIExtractedProduct,
    AIExtractionRun,
    Note,
)
from .workspace import get_default_workspace, optional_user
from .serializers import (
    AIAttachmentSerializer,
    AIBulkUploadRequestSerializer,
    AIBusinessCardListSerializer,
    AIBusinessCardSerializer,
    AICardBulkUploadRequestSerializer,
    AICardExtractRequestSerializer,
    AICatalogueListSerializer,
    AICatalogueSchemaSerializer,
    AIChatRequestSerializer,
    AIExtractedProductSerializer,
    AIExtractedProductWriteSerializer,
    AIExtractRequestSerializer,
    AIExtractionRunListSerializer,
    AIExtractionRunSerializer,
    NoteListSerializer,
    NoteSerializer,
)
from .services.card_extract import extract_business_card
from .services.card_import import import_card_spreadsheet
from .services.card_import import parse_user_column_map as parse_user_card_column_map
from .services.chat import answer_question
from .services.costing import estimate_cost
from .services.excel_import import import_spreadsheet, parse_user_column_map
from .services.extraction import MODEL_TIERS, extract_catalogue, extract_catalogue_from_images, pdf_page_count
from .services.files import classify_upload
from .services.page_selection import resolve_pages
from .services.persist import persist_run_to_schema


def collect_uploads(request, keys=('file', 'files', 'files[]')):
    uploads = []
    seen = set()
    for key in keys:
        for item in request.FILES.getlist(key):
            marker = id(item)
            if marker in seen:
                continue
            seen.add(marker)
            uploads.append(item)
    return uploads


def _fail_run(run, exc):
    run.status = AIExtractionRun.STATUS_FAILED
    run.finished_at = timezone.now()
    if run.started_at:
        run.duration_ms = int((run.finished_at - run.started_at).total_seconds() * 1000)
    run.error_message = str(exc)
    run.save(
        update_fields=['status', 'finished_at', 'duration_ms', 'error_message', 'updated_at']
    )
    message = str(exc)
    status_code = 502
    lowered = message.lower()
    if 'openai_api_key' in lowered:
        status_code = 500
    if any(token in lowered for token in ('insufficient_quota', 'credit_balance_exhausted')):
        status_code = 402
    if isinstance(exc, ValueError):
        status_code = 400
    return error_envelope(message, status_code, data=AIExtractionRunSerializer(run).data)


def _succeed_run(run, extracted, pages_billed, card=None):
    finished = timezone.now()
    duration_ms = int((finished - run.started_at).total_seconds() * 1000)
    result = extracted['result']
    usage = extracted['usage']
    costing = estimate_cost(run.model_name, usage['prompt_tokens'], usage['completion_tokens'])
    pages_kept = len(result.get('pages') or [])
    products_count = sum(len(page.get('products') or []) for page in (result.get('pages') or []))
    costing['breakdown']['pages_billed'] = pages_billed
    if pages_billed and costing['estimated_cost_usd']:
        avg = (costing['estimated_cost_usd'] / Decimal(pages_billed)).quantize(Decimal('0.000001'))
        costing['breakdown']['avg_cost_per_page_usd'] = str(avg)
    run.status = AIExtractionRun.STATUS_SUCCEEDED
    run.result_json = result
    run.pages_kept = pages_kept
    run.products_count = products_count
    run.advertisement_pages_skipped = extracted.get('advertisement_pages_skipped') or 0
    run.finished_at = finished
    run.duration_ms = duration_ms
    run.prompt_tokens = usage['prompt_tokens']
    run.completion_tokens = usage['completion_tokens']
    run.total_tokens = usage['total_tokens']
    run.estimated_cost_usd = costing['estimated_cost_usd']
    run.cost_breakdown = costing['breakdown']
    run.save()
    persist_run_to_schema(run, result, card)
    return success_envelope(AIExtractionRunSerializer(run).data, 'Extraction completed', 201)


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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return success_envelope(self.get_serializer(instance).data, 'Created', 201)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return success_envelope(self.get_serializer(instance).data, 'Updated')

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_current = False
        instance.save(update_fields=['is_current'])
        return success_envelope(None, 'Deleted', 204)


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
        uploads = collect_uploads(request)
        if not uploads:
            return error_envelope('Upload a PDF or catalogue photos (jpg, png, webp).', 400)
        serializer = AIExtractRequestSerializer(
            data={
                'files': uploads,
                'card': request.data.get('card') or None,
                'page_mode': request.data.get('page_mode') or None,
                'page_count': request.data.get('page_count') or None,
                'page_range': request.data.get('page_range') or '',
                'model_tier': request.data.get('model_tier') or AIExtractionRun.TIER_HIGH,
                'dpi': request.data.get('dpi') or 200,
            }
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        card = None
        if data.get('card'):
            card = AIBusinessCard.objects.filter(id=data['card']).first()
            if card is None:
                return error_envelope('No business card found for that card id.', 400)
        uploads = data['files']
        kind = classify_upload(uploads[0])

        max_pages = int(os.environ.get('AI_MAX_PAGES_PER_REQUEST', '100'))
        model_tier = data.get('model_tier') or AIExtractionRun.TIER_HIGH
        model_name = MODEL_TIERS.get(model_tier, MODEL_TIERS['high_accuracy'])
        dpi = data.get('dpi') or 200
        workspace = get_default_workspace()
        user = optional_user(request)
        first = uploads[0]
        upload = AICatalogueUpload.objects.create(
            business_card = card,
            workspace=workspace,
            file=first,
            original_filename=', '.join(item.name for item in uploads),
            file_size_bytes=sum(getattr(item, 'size', 0) or 0 for item in uploads),
            content_type=getattr(first, 'content_type', '') or '',
            uploaded_by=user,
        )

        if kind == 'pdf':
            try:
                total_pages = pdf_page_count(upload.file.path)
            except Exception as exc:  # noqa: BLE001
                upload.delete()
                return error_envelope(f'Could not read PDF: {exc}', 400)
        else:
            total_pages = len(uploads)

        upload.total_pages = total_pages
        upload.save(update_fields=['total_pages', 'updated_at'])

        try:
            pages = resolve_pages(
                page_mode=data['page_mode'],
                total_pages=total_pages,
                page_count=data.get('page_count'),
                page_range=data.get('page_range'),
                max_pages=max_pages,
            )
        except Exception as exc:  # noqa: BLE001
            upload.delete()
            raise exc

        run = AIExtractionRun.objects.create(
            business_card = card,
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
            if kind == 'pdf':
                extracted = extract_catalogue(upload.file.path, pages, model_name, dpi=dpi)
            else:
                image_paths = [upload.file.path]
                for index, extra in enumerate(uploads[1:], start=2):
                    stored = default_storage.save(
                        f'ai/catalogues/{workspace.id}/page{index}_{extra.name}',
                        extra,
                    )
                    image_paths.append(default_storage.path(stored))
                extracted = extract_catalogue_from_images(image_paths, pages, model_name)
            return _succeed_run(run, extracted, len(pages), card=card)
        except Exception as exc:  # noqa: BLE001
            return _fail_run(run, exc)


class AICatalogueViewSet(AIOpenViewSetMixin, viewsets.ReadOnlyModelViewSet):
    queryset = AICatalogue.objects.all()
    serializer_class = AICatalogueSchemaSerializer
    http_method_names = ['get', 'head', 'options']
    search_fields = ('title', 'brand', 'source_filename')

    def get_queryset(self):
        qs = AICatalogue.objects.all()
        business_card = self.request.query_params.get('business_card')
        if business_card:
            qs = qs.filter(business_card_id=business_card)
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AICatalogueSchemaSerializer
        return AICatalogueSchemaSerializer


class AICatalogueProductViewSet(AIOpenViewSetMixin, viewsets.GenericViewSet, mixins.ListModelMixin,
                                 mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
                                 mixins.DestroyModelMixin):
    queryset = AIExtractedProduct.objects.select_related('catalogue').all()
    serializer_class = AIExtractedProductSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']
    search_fields = ('product_name', 'code_or_sku', 'series', 'search_text')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'delete', 'partial_update'):
            return AIExtractedProductWriteSerializer
        return AIExtractedProductSerializer

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


class NoteViewSet(AIOpenViewSetMixin, viewsets.ModelViewSet):
    queryset = Note.objects.select_related('business_card', 'catalogue', 'created_by').prefetch_related('attachments').all()
    serializer_class = NoteSerializer
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return NoteListSerializer
        return NoteSerializer

    def get_queryset(self):
        qs = Note.objects.select_related('business_card', 'catalogue', 'created_by').prefetch_related('attachments')
        business_card = self.request.query_params.get('business_card')
        if business_card:
            qs = qs.filter(business_card_id=business_card)
        catalogue = self.request.query_params.get('catalogue')
        if catalogue:
            qs = qs.filter(catalogue_id=catalogue)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=optional_user(self.request))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return success_envelope(None, 'Deleted', 204)


class AIAttachmentViewSet(AIOpenViewSetMixin, viewsets.ModelViewSet):
    queryset = AIAttachment.objects.select_related('note', 'uploaded_by').all()
    serializer_class = AIAttachmentSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = AIAttachment.objects.select_related('note', 'uploaded_by')
        note = self.request.query_params.get('note')
        if note:
            qs = qs.filter(note_id=note)
        return qs

    def perform_create(self, serializer):
        file_obj = serializer.validated_data.get('file')
        serializer.save(
            uploaded_by=optional_user(self.request),
            mime_type=getattr(file_obj, 'content_type', '') or '',
            file_size=getattr(file_obj, 'size', 0) or 0,
        )

    def perform_update(self, serializer):
        file_obj = serializer.validated_data.get('file')
        if file_obj is not None:
            serializer.save(
                mime_type=getattr(file_obj, 'content_type', '') or '',
                file_size=getattr(file_obj, 'size', 0) or 0,
            )
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return success_envelope(None, 'Deleted', 204)


class AIBusinessCardViewSet(AIOpenViewSetMixin, viewsets.GenericViewSet):
    queryset = AIBusinessCard.objects.all()
    serializer_class = AIBusinessCardSerializer
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['get', 'post', 'head', 'options']
    pagination_class = StandardPagination

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


class AIBulkUploadView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        uploads = collect_uploads(request)
        if not uploads:
            return error_envelope('Upload one .xlsx, .xlsm, .csv, or .tsv file.', 400)
        if len(uploads) > 1:
            return error_envelope('Upload one spreadsheet per request.', 400)
        serializer = AIBulkUploadRequestSerializer(
            data={
                'file': uploads[0],
                'sheet': request.data.get('sheet') or '',
                'header_row': request.data.get('header_row') or None,
                'column_map': request.data.get('column_map') or '',
                'max_rows': request.data.get('max_rows') or None,
            }
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        uploaded = data['file']
        try:
            column_map = parse_user_column_map(data.get('column_map'))
        except ValueError as exc:
            return error_envelope(str(exc), 400)

        workspace = get_default_workspace()
        user = optional_user(request)
        max_rows = data.get('max_rows') or int(os.environ.get('AI_MAX_EXCEL_ROWS', '5000'))
        upload = AICatalogueUpload.objects.create(
            workspace=workspace,
            file=uploaded,
            original_filename=uploaded.name,
            file_size_bytes=getattr(uploaded, 'size', 0) or 0,
            content_type=getattr(uploaded, 'content_type', '') or '',
            uploaded_by=user,
        )
        run = AIExtractionRun.objects.create(
            workspace=workspace,
            upload=upload,
            status=AIExtractionRun.STATUS_RUNNING,
            page_mode=AIExtractionRun.MODE_FULL,
            pages_requested=[],
            model_tier=AIExtractionRun.TIER_BUDGET,
            model_name='spreadsheet-import',
            started_at=timezone.now(),
            created_by=user,
        )
        try:
            extracted = import_spreadsheet(
                upload.file.path,
                sheet=data.get('sheet') or None,
                column_map=column_map,
                header_row=data.get('header_row'),
                max_rows=max_rows,
            )
            pages = extracted['result'].get('pages_processed') or [1]
            run.pages_requested = pages
            upload.total_pages = extracted['result'].get('total_pages_in_pdf') or 1
            upload.save(update_fields=['total_pages', 'updated_at'])
            return _succeed_run(run, extracted, 0)
        except Exception as exc:  # noqa: BLE001
            return _fail_run(run, exc)


class AICardBulkUploadView(APIView):
    """Bulk-import business card contacts from a spreadsheet — no OCR, no AI cost
    for the import itself (only used as a fallback if column headers are unrecognized)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        uploads = collect_uploads(request)
        if not uploads:
            return error_envelope('Upload one .xlsx, .xlsm, .csv, or .tsv file.', 400)
        if len(uploads) > 1:
            return error_envelope('Upload one spreadsheet per request.', 400)
        serializer = AICardBulkUploadRequestSerializer(
            data={
                'file': uploads[0],
                'sheet': request.data.get('sheet') or '',
                'header_row': request.data.get('header_row') or None,
                'column_map': request.data.get('column_map') or '',
                'max_rows': request.data.get('max_rows') or None,
            }
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        uploaded = data['file']
        try:
            column_map = parse_user_card_column_map(data.get('column_map'))
        except ValueError as exc:
            return error_envelope(str(exc), 400)

        workspace = get_default_workspace()
        user = optional_user(request)
        max_rows = data.get('max_rows') or int(os.environ.get('AI_MAX_EXCEL_ROWS', '5000'))

        stored_name = default_storage.save(
            f'ai/cards_bulk/{workspace.id}/{uploaded.name}', uploaded
        )
        stored_path = default_storage.path(stored_name)

        try:
            parsed = import_card_spreadsheet(
                stored_path,
                sheet=data.get('sheet') or None,
                column_map=column_map,
                header_row=data.get('header_row'),
                max_rows=max_rows,
            )
        except ValueError as exc:
            return error_envelope(str(exc), 400)
        except Exception as exc:  # noqa: BLE001
            return error_envelope(f'Could not read spreadsheet: {exc}', 400)

        now = timezone.now()
        created = []
        try:
            with transaction.atomic():
                for row in parsed['cards']:
                    card = AIBusinessCard.objects.create(
                        workspace=workspace,
                        image=None,
                        original_filename=uploaded.name,
                        content_type=getattr(uploaded, 'content_type', '') or '',
                        file_size_bytes=0,
                        status=AIBusinessCard.STATUS_SUCCEEDED,
                        full_name=row['full_name'],
                        job_title=row['job_title'],
                        company=row['company'],
                        emails=row['emails'],
                        phones=row['phones'],
                        website=row['website'],
                        address=row['address'],
                        linkedin=row['linkedin'],
                        extras=row['extras'],
                        source_files=[],
                        result_json=row,
                        model_tier=AIExtractionRun.TIER_BUDGET,
                        model_name='excel-import',
                        started_at=now,
                        finished_at=now,
                        duration_ms=0,
                        estimated_cost_usd=0,
                        created_by=user,
                    )
                    created.append(card)
        except Exception as exc:  # noqa: BLE001
            return error_envelope(f'Could not save imported cards: {exc}', 400)

        return success_envelope(
            {
                'source_file': parsed['source_file'],
                'sheet': parsed['sheet'],
                'header_row': parsed['header_row'],
                'column_map': parsed['column_map'],
                'column_map_source': parsed['column_map_source'],
                'rows_imported': parsed['rows_imported'],
                'rows_skipped': parsed['rows_skipped'],
                'cards': AIBusinessCardListSerializer(created, many=True).data,
            },
            'Bulk cards imported',
            201,
        )
