from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser

from api.common.responses import success_envelope
from api.common.services.ai_stub import generate_ai_insights
from api.common.views import WorkspaceViewSet
from api.jobs.models import Job
from api.products.models import Product

from .models import (
    Catalogue,
    CatalogueFile,
    CatalogueVersion,
    ExtractionCandidate,
    OcrPage,
    UploadSession,
)
from .serializers import (
    CatalogueFileSerializer,
    CatalogueSerializer,
    CatalogueVersionSerializer,
    ExtractionCandidateSerializer,
    OcrPageSerializer,
    UploadSessionSerializer,
)
from .tasks import process_catalogue_ocr


class CatalogueViewSet(WorkspaceViewSet):
    queryset = Catalogue.objects.all()
    serializer_class = CatalogueSerializer
    search_fields = ('title',)
    filterset_fields = ('status', 'supplier')

    def _start_job(self, request, catalogue, job_type):
        job = Job.objects.create(
            workspace=request.workspace,
            job_type=job_type,
            entity_type='catalogue',
            entity_id=str(catalogue.id),
            created_by=request.user,
        )
        process_catalogue_ocr.delay(job.id)
        catalogue.status = Catalogue.STATUS_QUEUED
        catalogue.save(update_fields=['status', 'updated_at'])
        return job

    @action(detail=True, methods=['get', 'post'], url_path='versions')
    def versions(self, request, pk=None):
        catalogue = self.get_object()
        if request.method == 'GET':
            return success_envelope(CatalogueVersionSerializer(catalogue.versions.all(), many=True).data)
        version_number = catalogue.current_version + 1
        version = CatalogueVersion.objects.create(
            catalogue=catalogue,
            version_number=version_number,
            notes=request.data.get('notes', ''),
        )
        catalogue.current_version = version_number
        catalogue.save(update_fields=['current_version', 'updated_at'])
        return success_envelope(CatalogueVersionSerializer(version).data, 'Version created', 201)

    @action(detail=True, methods=['get', 'post'], url_path=r'versions/(?P<version_id>[^/.]+)/files', parser_classes=[MultiPartParser, FormParser])
    def version_files(self, request, pk=None, version_id=None):
        catalogue = self.get_object()
        version = get_object_or_404(CatalogueVersion, pk=version_id, catalogue=catalogue)
        if request.method == 'GET':
            return success_envelope(CatalogueFileSerializer(version.files.all(), many=True).data)
        file = request.FILES.get('file')
        if not file:
            return success_envelope(None, 'file required', status.HTTP_400_BAD_REQUEST)
        cf = CatalogueFile.objects.create(
            catalogue_version=version,
            file=file,
            filename=file.name,
            mime_type=getattr(file, 'content_type', ''),
            page_count=int(request.data.get('page_count', 1)),
        )
        return success_envelope(CatalogueFileSerializer(cf).data, 'File uploaded', 201)

    @action(detail=False, methods=['post'], url_path='upload-sessions')
    def upload_sessions(self, request):
        session = UploadSession.objects.create(
            workspace=request.workspace,
            user=request.user,
            files_meta=request.data.get('files', []),
        )
        return success_envelope(UploadSessionSerializer(session).data, 'Upload session created', 201)

    @action(detail=False, methods=['post'], url_path=r'upload-sessions/(?P<session_id>[^/.]+)/commit')
    def commit_upload_session(self, request, session_id=None):
        session = get_object_or_404(UploadSession, pk=session_id, workspace=request.workspace)
        catalogue = Catalogue.objects.create(
            workspace=request.workspace,
            supplier_id=request.data.get('supplier_id'),
            title=request.data.get('title') or f'Catalogue {session.id}',
            created_by=request.user,
        )
        version = CatalogueVersion.objects.create(catalogue=catalogue, version_number=1)
        session.catalogue = catalogue
        session.status = UploadSession.STATUS_COMMITTED
        session.save(update_fields=['catalogue', 'status', 'updated_at'])
        job = self._start_job(request, catalogue, Job.TYPE_CATALOGUE_OCR)
        return success_envelope(
            {'catalogue': CatalogueSerializer(catalogue).data, 'job_id': job.id},
            'Upload session committed',
            201,
        )

    @action(detail=True, methods=['get'], url_path='jobs')
    def jobs(self, request, pk=None):
        catalogue = self.get_object()
        qs = Job.objects.filter(workspace=request.workspace, entity_type='catalogue', entity_id=str(catalogue.id))
        from api.jobs.serializers import JobSerializer
        return success_envelope(JobSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='extractions')
    def extractions(self, request, pk=None):
        catalogue = self.get_object()
        return success_envelope(ExtractionCandidateSerializer(catalogue.extractions.all(), many=True).data)

    @action(detail=True, methods=['post'], url_path=r'extractions/(?P<extraction_id>[^/.]+)/accept')
    def accept_extraction(self, request, pk=None, extraction_id=None):
        catalogue = self.get_object()
        extraction = get_object_or_404(ExtractionCandidate, pk=extraction_id, catalogue=catalogue)
        data = extraction.normalized_data or {}
        product = Product.objects.create(
            workspace=request.workspace,
            supplier=catalogue.supplier,
            name=data.get('name', 'Extracted Product'),
            sku=data.get('sku', ''),
            price=data.get('price'),
            status=Product.STATUS_NEEDS_REVIEW,
            source=Product.SOURCE_AI,
            created_by=request.user,
        )
        extraction.status = ExtractionCandidate.STATUS_ACCEPTED
        extraction.product = product
        extraction.save(update_fields=['status', 'product', 'updated_at'])
        return success_envelope({'product_id': product.id, 'extraction': ExtractionCandidateSerializer(extraction).data})

    @action(detail=True, methods=['post'], url_path=r'extractions/(?P<extraction_id>[^/.]+)/reject')
    def reject_extraction(self, request, pk=None, extraction_id=None):
        catalogue = self.get_object()
        extraction = get_object_or_404(ExtractionCandidate, pk=extraction_id, catalogue=catalogue)
        extraction.status = ExtractionCandidate.STATUS_REJECTED
        extraction.save(update_fields=['status', 'updated_at'])
        return success_envelope(ExtractionCandidateSerializer(extraction).data)

    @action(detail=True, methods=['patch'], url_path=r'extractions/(?P<extraction_id>[^/.]+)')
    def patch_extraction(self, request, pk=None, extraction_id=None):
        catalogue = self.get_object()
        extraction = get_object_or_404(ExtractionCandidate, pk=extraction_id, catalogue=catalogue)
        normalized = dict(extraction.normalized_data or {})
        normalized.update(request.data.get('normalized_data', request.data))
        extraction.normalized_data = normalized
        extraction.save(update_fields=['normalized_data', 'updated_at'])
        return success_envelope(ExtractionCandidateSerializer(extraction).data)

    @action(detail=True, methods=['get'], url_path='ocr-pages')
    def ocr_pages(self, request, pk=None):
        catalogue = self.get_object()
        version = catalogue.versions.order_by('-version_number').first()
        pages = OcrPage.objects.filter(catalogue_file__catalogue_version=version) if version else OcrPage.objects.none()
        return success_envelope(OcrPageSerializer(pages, many=True).data)

    @action(detail=True, methods=['get', 'post'], url_path='ai-insights')
    def ai_insights(self, request, pk=None):
        catalogue = self.get_object()
        if request.method == 'GET':
            return success_envelope(catalogue.ai_insights or {})
        catalogue.ai_insights = generate_ai_insights(catalogue)
        catalogue.save(update_fields=['ai_insights', 'updated_at'])
        return success_envelope(catalogue.ai_insights)

    @action(detail=True, methods=['post'])
    def reprocess(self, request, pk=None):
        catalogue = self.get_object()
        job = self._start_job(request, catalogue, Job.TYPE_REPROCESS)
        return success_envelope({'job_id': job.id}, 'Reprocess queued')

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        action_name = request.data.get('action')
        ids = request.data.get('ids', [])
        qs = self.get_queryset().filter(id__in=ids)
        updated = 0
        if action_name == 'archive':
            updated = qs.update(status=Catalogue.STATUS_READY)
        elif action_name == 'reprocess':
            for catalogue in qs:
                self._start_job(request, catalogue, Job.TYPE_REPROCESS)
                updated += 1
        return success_envelope({'updated': updated})
