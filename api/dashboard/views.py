from django.db.models import Count
from rest_framework.views import APIView

from api.activity.models import ActivityLog
from api.catalogues.models import Catalogue
from api.common.permissions import IsWorkspaceMember
from api.common.responses import WorkspaceRequired, camel_envelope
from api.jobs.models import Job
from api.jobs.serializers import JobSerializer
from api.notifications.models import Notification
from api.products.models import Product
from api.products.serializers import ProductSerializer
from api.search.models import SearchHistory
from api.suppliers.models import Supplier
from api.suppliers.serializers import SupplierSerializer


class DashboardBaseView(APIView):
    permission_classes = [IsWorkspaceMember]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.workspace:
            raise WorkspaceRequired()


class DashboardSummaryView(DashboardBaseView):
    def get(self, request):
        ws = request.workspace
        supplier_count = Supplier.objects.filter(workspace=ws).count()
        product_count = Product.objects.filter(workspace=ws).count()
        catalogue_count = Catalogue.objects.filter(workspace=ws).count()
        pending_jobs = Job.objects.filter(workspace=ws, status__in=[Job.STATUS_PENDING, Job.STATUS_RUNNING]).count()
        show_onboarding = supplier_count == 0 and product_count == 0
        return camel_envelope({
            'supplier_count': supplier_count,
            'product_count': product_count,
            'catalogue_count': catalogue_count,
            'pending_jobs': pending_jobs,
            'show_onboarding': show_onboarding,
        })


class DashboardKpisView(DashboardBaseView):
    def get(self, request):
        ws = request.workspace
        return camel_envelope({
            'active_suppliers': Supplier.objects.filter(workspace=ws, status=Supplier.STATUS_ACTIVE).count(),
            'verified_products': Product.objects.filter(workspace=ws, status=Product.STATUS_VERIFIED).count(),
            'catalogues_in_review': Catalogue.objects.filter(workspace=ws, status=Catalogue.STATUS_REVIEW).count(),
            'failed_jobs': Job.objects.filter(workspace=ws, status=Job.STATUS_FAILED).count(),
        })


class DashboardJobsView(DashboardBaseView):
    def get(self, request):
        qs = Job.objects.filter(workspace=request.workspace).order_by('-created_at')[:10]
        return camel_envelope({'items': JobSerializer(qs, many=True).data})


class DashboardRecentSuppliersView(DashboardBaseView):
    def get(self, request):
        qs = Supplier.objects.filter(workspace=request.workspace).order_by('-created_at')[:5]
        return camel_envelope({'items': SupplierSerializer(qs, many=True).data})


class DashboardRecentProductsView(DashboardBaseView):
    def get(self, request):
        qs = Product.objects.filter(workspace=request.workspace).order_by('-created_at')[:5]
        return camel_envelope({'items': ProductSerializer(qs, many=True).data})


class DashboardRecentCataloguesView(DashboardBaseView):
    def get(self, request):
        qs = Catalogue.objects.filter(workspace=request.workspace).order_by('-created_at')[:5]
        items = [{'id': c.id, 'title': c.title, 'status': c.status} for c in qs]
        return camel_envelope({'items': items})


class DashboardRecentActivityView(DashboardBaseView):
    def get(self, request):
        qs = ActivityLog.objects.filter(workspace=request.workspace).order_by('-created_at')[:10]
        items = [
            {
                'id': a.id,
                'action': a.action,
                'entity_type': a.entity_type,
                'entity_id': a.entity_id,
                'created_at': a.created_at.isoformat(),
            }
            for a in qs
        ]
        return camel_envelope({'items': items})


class DashboardExtractionQueueView(DashboardBaseView):
    def get(self, request):
        qs = Catalogue.objects.filter(workspace=request.workspace, status=Catalogue.STATUS_REVIEW)
        items = [{'id': c.id, 'title': c.title, 'status': c.status} for c in qs[:10]]
        return camel_envelope({'items': items})


class DashboardSuppliersByStatusChartView(DashboardBaseView):
    def get(self, request):
        rows = (
            Supplier.objects.filter(workspace=request.workspace)
            .values('status')
            .annotate(count=Count('id'))
        )
        return camel_envelope({'series': list(rows)})


class DashboardProductsByCategoryChartView(DashboardBaseView):
    def get(self, request):
        rows = (
            Product.objects.filter(workspace=request.workspace)
            .values('category__name')
            .annotate(count=Count('id'))
        )
        return camel_envelope({'series': [{'category': r['category__name'] or 'Uncategorized', 'count': r['count']} for r in rows]})


class DashboardCataloguePipelineChartView(DashboardBaseView):
    def get(self, request):
        rows = (
            Catalogue.objects.filter(workspace=request.workspace)
            .values('status')
            .annotate(count=Count('id'))
        )
        return camel_envelope({'series': list(rows)})


class DashboardSearchVolumeChartView(DashboardBaseView):
    def get(self, request):
        rows = (
            SearchHistory.objects.filter(workspace=request.workspace)
            .values('search_type')
            .annotate(count=Count('id'))
        )
        return camel_envelope({'series': list(rows)})


class DashboardFollowUpsView(DashboardBaseView):
    def get(self, request):
        suppliers = Supplier.objects.filter(workspace=request.workspace, status=Supplier.STATUS_PROSPECT)[:5]
        items = [{'id': s.id, 'name': s.name, 'reason': 'prospect_follow_up'} for s in suppliers]
        return camel_envelope({'items': items})


class DashboardOnboardingView(DashboardBaseView):
    def get(self, request):
        ws = request.workspace
        steps = [
            {'key': 'create_supplier', 'done': Supplier.objects.filter(workspace=ws).exists()},
            {'key': 'upload_catalogue', 'done': Catalogue.objects.filter(workspace=ws).exists()},
            {'key': 'add_product', 'done': Product.objects.filter(workspace=ws).exists()},
        ]
        return camel_envelope({'steps': steps, 'completed': all(s['done'] for s in steps)})


class DashboardNotificationsSummaryView(DashboardBaseView):
    def get(self, request):
        qs = Notification.objects.filter(workspace=request.workspace, user=request.user)
        return camel_envelope({
            'unread_count': qs.filter(is_read=False).count(),
            'recent': [
                {'id': n.id, 'title': n.title, 'is_read': n.is_read}
                for n in qs.order_by('-created_at')[:5]
            ],
        })
