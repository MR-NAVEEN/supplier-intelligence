from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from api.common.permissions import IsWorkspaceMember, IsWorkspaceAdmin
from rest_framework.permissions import IsAuthenticated
from api.common.responses import WorkspaceRequired, success_envelope, error_envelope
from api.jobs.models import Job
from api.suppliers.models import Supplier

from .models import BusinessCard
from .serializers import BusinessCardSerializer
from .tasks import process_business_card_ocr


def resolve_optional_supplier(request, url_kwargs):
    """supplier is optional here (unlike the ai app) — a scanned card often represents
    a brand-new supplier that doesn't exist yet; that's what commit() is for. If an id
    IS given (via URL or body), it must resolve to a real supplier in this workspace."""
    supplier_id = url_kwargs.get('supplier_id') or request.data.get('supplier')
    if not supplier_id:
        return None, None
    supplier = Supplier.objects.filter(id=supplier_id, workspace=request.workspace).first()
    if supplier is None:
        return None, error_envelope('No supplier found for that id in this workspace.', 400)
    return supplier, None


class BusinessCardExtractView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        try:
            if not request.workspace:
                raise WorkspaceRequired()
            image = request.FILES.get('file') or request.FILES.get('image')
            if not image:
                return success_envelope(None, 'image required', 400)
            supplier, err = resolve_optional_supplier(request, self.kwargs)
            if err:
                return err
            job = Job.objects.create(
                workspace=request.workspace,
                job_type=Job.TYPE_BUSINESS_CARD_OCR,
                entity_type='business_card',
                created_by=request.user,
            )
            card = BusinessCard.objects.create(
                workspace=request.workspace,
                supplier=supplier,
                image=image,
                job=job,
                created_by=request.user,
            )
            job.entity_id = str(card.id)
            job.save(update_fields=['entity_id', 'updated_at'])
            process_business_card_ocr.delay(job.id, card.id)
            return success_envelope(
                {'job_id': job.id, 'business_card': BusinessCardSerializer(card).data},
                'Extraction started',
                201,
            )
        except Exception as e:
            return error_envelope(str(e), 400)


class BusinessCardCommitView(APIView):
    permission_classes = [IsWorkspaceMember, IsWorkspaceAdmin]

    def post(self, request, *args, **kwargs):
        if not request.workspace:
            raise WorkspaceRequired()
        card_id = request.data.get('business_card_id')
        card = BusinessCard.objects.get(pk=card_id, workspace=request.workspace)
        data = request.data.get('extracted_data') or card.extracted_data or {}

        supplier, err = resolve_optional_supplier(request, self.kwargs)
        if err:
            return err
        created_supplier = False
        if supplier is None:
            supplier = Supplier.objects.create(
                workspace=request.workspace,
                name=data.get('name') or data.get('company_name') or 'New Supplier',
                company_name=data.get('company_name', ''),
                email=data.get('email', ''),
                phone=data.get('phone', ''),
                created_by=request.user,
            )
            created_supplier = True

        card.supplier = supplier
        card.status = BusinessCard.STATUS_COMMITTED
        card.save(update_fields=['supplier', 'status', 'updated_at'])
        return success_envelope(
            {'supplier_id': supplier.id, 'business_card_id': card.id, 'supplier_created': created_supplier},
            'Business card committed',
            201,
        )


class BusinessCardListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if not request.workspace:
            raise WorkspaceRequired()
        qs = BusinessCard.objects.filter(workspace=request.workspace).order_by('-created_at')
        supplier_id = self.kwargs.get('supplier_id') or request.query_params.get('supplier')
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return success_envelope(BusinessCardSerializer(qs, many=True).data)


class BusinessCardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        if not request.workspace:
            raise WorkspaceRequired()
        card = BusinessCard.objects.filter(pk=pk, workspace=request.workspace).first()
        if card is None:
            return error_envelope('Business card not found.', 404)
        return success_envelope(BusinessCardSerializer(card).data)
