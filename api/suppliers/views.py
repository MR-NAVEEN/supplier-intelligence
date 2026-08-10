from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser

from api.catalogues.models import Catalogue
from api.catalogues.serializers import CatalogueSerializer
from api.common.responses import success_envelope
from api.common.services.activity_service import log_activity
from api.common.services.ai_stub import generate_ai_summary
from api.common.views import WorkspaceViewSet

from .models import Supplier, SupplierAttachment, SupplierContact, SupplierNote
from .serializers import (
    SupplierAttachmentSerializer,
    SupplierContactSerializer,
    SupplierNoteSerializer,
    SupplierSerializer,
)


class SupplierViewSet(WorkspaceViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    search_fields = ('name', 'company_name', 'email', 'city')
    filterset_fields = ('status', 'country')

    def perform_create(self, serializer):
        super().perform_create(serializer)
        log_activity(
            self.request.workspace, self.request.user, 'supplier.created',
            'supplier', serializer.instance.id,
        )

    @action(detail=True, methods=['get'])
    def context(self, request, pk=None):
        supplier = self.get_object()
        data = {
            'supplier': SupplierSerializer(supplier).data,
            'contacts': SupplierContactSerializer(supplier.contacts.all(), many=True).data,
            'notes_count': supplier.notes.count(),
            'attachments_count': supplier.attachments.count(),
            'products_count': supplier.products.count(),
            'catalogues_count': supplier.catalogues.count(),
        }
        return success_envelope(data)

    @action(detail=True, methods=['post'])
    def ai_summary(self, request, pk=None):
        supplier = self.get_object()
        supplier.ai_summary = generate_ai_summary('supplier', supplier)
        supplier.save(update_fields=['ai_summary', 'updated_at'])
        return success_envelope({'ai_summary': supplier.ai_summary})

    @action(detail=True, methods=['get'])
    def catalogues(self, request, pk=None):
        supplier = self.get_object()
        qs = Catalogue.objects.filter(workspace=request.workspace, supplier=supplier)
        return success_envelope(CatalogueSerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def business_card(self, request, pk=None):
        supplier = self.get_object()
        file = request.FILES.get('file') or request.FILES.get('image')
        if not file:
            return success_envelope(None, 'file required', status.HTTP_400_BAD_REQUEST)
        attachment = SupplierAttachment.objects.create(
            supplier=supplier,
            file=file,
            name=file.name,
            uploaded_by=request.user,
        )
        return success_envelope(SupplierAttachmentSerializer(attachment).data, 'Business card uploaded', 201)

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        action_name = request.data.get('action')
        ids = request.data.get('ids', [])
        qs = self.get_queryset().filter(id__in=ids)
        updated = 0
        if action_name == 'archive':
            updated = qs.update(status=Supplier.STATUS_INACTIVE)
        elif action_name == 'activate':
            updated = qs.update(status=Supplier.STATUS_ACTIVE)
        elif action_name == 'tag':
            tag = request.data.get('tag')
            for supplier in qs:
                tags = list(supplier.tags or [])
                if tag and tag not in tags:
                    tags.append(tag)
                    supplier.tags = tags
                    supplier.save(update_fields=['tags', 'updated_at'])
                    updated += 1
        return success_envelope({'updated': updated})

    @action(detail=True, methods=['get', 'post'], url_path='contacts')
    def contacts_list(self, request, pk=None):
        supplier = self.get_object()
        if request.method == 'GET':
            return success_envelope(SupplierContactSerializer(supplier.contacts.all(), many=True).data)
        serializer = SupplierContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(supplier=supplier)
        return success_envelope(serializer.data, 'Contact created', 201)

    @action(detail=True, methods=['get', 'patch', 'delete'], url_path=r'contacts/(?P<contact_id>[^/.]+)')
    def contact_detail(self, request, pk=None, contact_id=None):
        supplier = self.get_object()
        contact = get_object_or_404(SupplierContact, pk=contact_id, supplier=supplier)
        if request.method == 'GET':
            return success_envelope(SupplierContactSerializer(contact).data)
        if request.method == 'DELETE':
            contact.delete()
            return success_envelope(None, 'Contact deleted')
        serializer = SupplierContactSerializer(contact, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_envelope(serializer.data)

    @action(detail=True, methods=['get', 'post'], url_path='notes')
    def notes_list(self, request, pk=None):
        supplier = self.get_object()
        if request.method == 'GET':
            return success_envelope(SupplierNoteSerializer(supplier.notes.all(), many=True).data)
        serializer = SupplierNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(supplier=supplier, created_by=request.user)
        return success_envelope(serializer.data, 'Note created', 201)

    @action(detail=True, methods=['get', 'post'], url_path='attachments')
    def attachments_list(self, request, pk=None):
        supplier = self.get_object()
        if request.method == 'GET':
            return success_envelope(SupplierAttachmentSerializer(supplier.attachments.all(), many=True).data)
        file = request.FILES.get('file')
        if not file:
            return success_envelope(None, 'file required', status.HTTP_400_BAD_REQUEST)
        attachment = SupplierAttachment.objects.create(
            supplier=supplier,
            file=file,
            name=request.data.get('name') or file.name,
            uploaded_by=request.user,
        )
        return success_envelope(SupplierAttachmentSerializer(attachment).data, 'Attachment uploaded', 201)
