from django.db.models import Q
from rest_framework.views import APIView

from api.catalogues.models import Catalogue
from api.common.permissions import IsWorkspaceMember
from api.common.responses import WorkspaceRequired, success_envelope
from api.common.services.ai_stub import semantic_search
from api.products.models import Product
from api.products.serializers import ProductSerializer
from api.suppliers.models import Supplier
from api.suppliers.serializers import SupplierSerializer

from .models import RecentSearch, SavedSearch, SearchHistory
from .serializers import RecentSearchSerializer, SavedSearchSerializer, SearchHistorySerializer


def _global_search(workspace, query, limit=20):
    suppliers = Supplier.objects.filter(workspace=workspace).filter(
        Q(name__icontains=query) | Q(company_name__icontains=query)
    )[:limit]
    products = Product.objects.filter(workspace=workspace).filter(
        Q(name__icontains=query) | Q(sku__icontains=query)
    )[:limit]
    catalogues = Catalogue.objects.filter(workspace=workspace, title__icontains=query)[:limit]
    return {
        'suppliers': SupplierSerializer(suppliers, many=True).data,
        'products': ProductSerializer(products, many=True).data,
        'catalogues': [{'id': c.id, 'title': c.title, 'status': c.status} for c in catalogues],
        'total': suppliers.count() + products.count() + catalogues.count(),
    }


class GlobalSearchView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        query = request.query_params.get('q', '')
        data = _global_search(request.workspace, query)
        SearchHistory.objects.create(
            workspace=request.workspace,
            user=request.user,
            query=query,
            result_count=data['total'],
            search_type='global',
        )
        return success_envelope(data)


class QuickSearchView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        query = request.query_params.get('q', '')
        results = []
        for s in Supplier.objects.filter(workspace=request.workspace, name__icontains=query)[:5]:
            results.append({'type': 'supplier', 'id': s.id, 'label': s.name})
        for p in Product.objects.filter(workspace=request.workspace, name__icontains=query)[:5]:
            results.append({'type': 'product', 'id': p.id, 'label': p.name})
        return success_envelope({'results': results})


class RecentSearchView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        qs = RecentSearch.objects.filter(workspace=request.workspace, user=request.user)[:20]
        return success_envelope(RecentSearchSerializer(qs, many=True).data)

    def post(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        obj = RecentSearch.objects.create(
            workspace=request.workspace,
            user=request.user,
            query=request.data.get('query', ''),
            result_count=request.data.get('result_count', 0),
        )
        return success_envelope(RecentSearchSerializer(obj).data, 'Recent search saved', 201)

    def delete(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        RecentSearch.objects.filter(workspace=request.workspace, user=request.user).delete()
        return success_envelope(None, 'Recent searches cleared')


class SavedSearchView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        qs = SavedSearch.objects.filter(workspace=request.workspace, user=request.user)
        return success_envelope(SavedSearchSerializer(qs, many=True).data)

    def post(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        obj = SavedSearch.objects.create(
            workspace=request.workspace,
            user=request.user,
            name=request.data.get('name'),
            query=request.data.get('query', ''),
            filters=request.data.get('filters', {}),
        )
        return success_envelope(SavedSearchSerializer(obj).data, 'Saved search created', 201)


class SavedSearchDetailView(APIView):
    permission_classes = [IsWorkspaceMember]

    def delete(self, request, pk):
        if not request.workspace:
            raise WorkspaceRequired()
        SavedSearch.objects.filter(pk=pk, workspace=request.workspace, user=request.user).delete()
        return success_envelope(None, 'Saved search deleted')


class SearchHistoryView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        qs = SearchHistory.objects.filter(workspace=request.workspace, user=request.user)[:50]
        return success_envelope(SearchHistorySerializer(qs, many=True).data)


class AISearchView(APIView):
    permission_classes = [IsWorkspaceMember]

    def post(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        query = request.data.get('query', '')
        results = semantic_search(query, request.workspace)
        return success_envelope({'query': query, 'results': results})
