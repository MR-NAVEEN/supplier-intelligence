from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser

from api.common.responses import success_envelope
from api.common.services.ai_stub import generate_ai_summary
from api.common.views import WorkspaceViewSet

from .models import Product, ProductImage, ProductNote
from .serializers import ProductImageSerializer, ProductNoteSerializer, ProductSerializer


class ProductViewSet(WorkspaceViewSet):
    queryset = Product.objects.select_related('supplier', 'category').all()
    serializer_class = ProductSerializer
    search_fields = ('name', 'sku', 'description')
    filterset_fields = ('status', 'supplier', 'category', 'source')

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        product = self.get_object()
        product.status = Product.STATUS_ARCHIVED
        product.save(update_fields=['status', 'updated_at'])
        return success_envelope(ProductSerializer(product).data)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        product = self.get_object()
        product.status = Product.STATUS_ACTIVE
        product.save(update_fields=['status', 'updated_at'])
        return success_envelope(ProductSerializer(product).data)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        product = self.get_object()
        clone = Product.objects.create(
            workspace=product.workspace,
            supplier=product.supplier,
            category=product.category,
            name=f'{product.name} (Copy)',
            sku='',
            description=product.description,
            price=product.price,
            currency=product.currency,
            status=Product.STATUS_ACTIVE,
            tags=list(product.tags or []),
            source=product.source,
            metadata=dict(product.metadata or {}),
            created_by=request.user,
        )
        return success_envelope(ProductSerializer(clone).data, 'Product duplicated', 201)

    @action(detail=True, methods=['post'])
    def ai_summary(self, request, pk=None):
        product = self.get_object()
        product.ai_summary = generate_ai_summary('product', product)
        product.save(update_fields=['ai_summary', 'updated_at'])
        return success_envelope({'ai_summary': product.ai_summary})

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        action_name = request.data.get('action')
        ids = request.data.get('ids', [])
        qs = self.get_queryset().filter(id__in=ids)
        updated = 0
        if action_name == 'archive':
            updated = qs.update(status=Product.STATUS_ARCHIVED)
        elif action_name == 'restore':
            updated = qs.update(status=Product.STATUS_ACTIVE)
        elif action_name == 'category':
            category_id = request.data.get('category_id')
            updated = qs.update(category_id=category_id)
        elif action_name == 'tag':
            tag = request.data.get('tag')
            for product in qs:
                tags = list(product.tags or [])
                if tag and tag not in tags:
                    tags.append(tag)
                    product.tags = tags
                    product.save(update_fields=['tags', 'updated_at'])
                    updated += 1
        return success_envelope({'updated': updated})

    @action(detail=True, methods=['get', 'post'], url_path='images', parser_classes=[MultiPartParser, FormParser])
    def images(self, request, pk=None):
        product = self.get_object()
        if request.method == 'GET':
            return success_envelope(ProductImageSerializer(product.images.all(), many=True).data)
        file = request.FILES.get('file') or request.FILES.get('image')
        if not file:
            return success_envelope(None, 'file required', status.HTTP_400_BAD_REQUEST)
        image = ProductImage.objects.create(
            product=product,
            file=file,
            is_primary=request.data.get('is_primary', False),
        )
        return success_envelope(ProductImageSerializer(image).data, 'Image uploaded', 201)

    @action(detail=True, methods=['get', 'post'], url_path='notes')
    def notes(self, request, pk=None):
        product = self.get_object()
        if request.method == 'GET':
            return success_envelope(ProductNoteSerializer(product.notes.all(), many=True).data)
        serializer = ProductNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product, created_by=request.user)
        return success_envelope(serializer.data, 'Note created', 201)
