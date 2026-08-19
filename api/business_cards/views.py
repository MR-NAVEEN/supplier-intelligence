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


class BusinessCardExtractView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        try:
            if not request.workspace:
                raise WorkspaceRequired()
            image = request.FILES.get('file') or request.FILES.get('image')
            if not image:
                return success_envelope(None, 'image required', 400)
            job = Job.objects.create(
                workspace=request.workspace,
                job_type=Job.TYPE_BUSINESS_CARD_OCR,
                entity_type='business_card',
                created_by=request.user,
            )
            card = BusinessCard.objects.create(
                workspace=request.workspace,
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

    def post(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        card_id = request.data.get('business_card_id')
        card = BusinessCard.objects.get(pk=card_id, workspace=request.workspace)
        data = request.data.get('extracted_data') or card.extracted_data or {}
        supplier = Supplier.objects.create(
            workspace=request.workspace,
            name=data.get('name') or data.get('company_name') or 'New Supplier',
            company_name=data.get('company_name', ''),
            email=data.get('email', ''),
            phone=data.get('phone', ''),
            created_by=request.user,
        )
        card.supplier = supplier
        card.status = BusinessCard.STATUS_COMMITTED
        card.save(update_fields=['supplier', 'status', 'updated_at'])
        return success_envelope(
            {'supplier_id': supplier.id, 'business_card_id': card.id},
            'Business card committed',
            201,
        )
