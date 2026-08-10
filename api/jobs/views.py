from api.common.views import WorkspaceViewSet

from .models import Job
from .serializers import JobSerializer


class JobViewSet(WorkspaceViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    filterset_fields = ('job_type', 'status', 'entity_type')
    http_method_names = ['get', 'head', 'options']
