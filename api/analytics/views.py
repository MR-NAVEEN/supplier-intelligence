from django.db.models import Count
from rest_framework.views import APIView

from api.common.permissions import IsWorkspaceMember
from api.common.responses import WorkspaceRequired, success_envelope
from api.products.models import Product
from api.search.models import SearchHistory


class ProductAnalyticsView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        by_status = list(
            Product.objects.filter(workspace=request.workspace)
            .values('status')
            .annotate(count=Count('id'))
        )
        by_source = list(
            Product.objects.filter(workspace=request.workspace)
            .values('source')
            .annotate(count=Count('id'))
        )
        return success_envelope({'by_status': by_status, 'by_source': by_source})


class SearchAnalyticsView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        by_type = list(
            SearchHistory.objects.filter(workspace=request.workspace)
            .values('search_type')
            .annotate(count=Count('id'))
        )
        top_queries = list(
            SearchHistory.objects.filter(workspace=request.workspace)
            .values('query')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        return success_envelope({'by_type': by_type, 'top_queries': top_queries})
