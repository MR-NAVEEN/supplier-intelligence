from django.db.models import Count
from rest_framework.decorators import action

from api.common.responses import success_envelope
from api.common.views import WorkspaceViewSet

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(WorkspaceViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ('name', 'slug')

    @action(detail=False, methods=['get'])
    def tree(self, request):
        categories = list(self.get_queryset())
        by_parent = {}
        for cat in categories:
            by_parent.setdefault(cat.parent_id, []).append(cat)

        def build_node(cat):
            return {
                'id': cat.id,
                'name': cat.name,
                'slug': cat.slug,
                'children': [build_node(c) for c in by_parent.get(cat.id, [])],
            }

        roots = [build_node(c) for c in categories if c.parent_id is None]
        return success_envelope(roots)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        stats = (
            self.get_queryset()
            .annotate(product_count=Count('products'))
            .values('id', 'name', 'slug', 'product_count')
        )
        return success_envelope(list(stats))
