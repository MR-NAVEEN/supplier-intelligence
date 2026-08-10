from rest_framework.views import APIView

from api.common.permissions import IsWorkspaceMember
from api.common.responses import WorkspaceRequired, success_envelope

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityListView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        qs = ActivityLog.objects.filter(workspace=request.workspace)
        entity_type = request.query_params.get('entity_type')
        entity_id = request.query_params.get('entity_id')
        action = request.query_params.get('action')
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        if action:
            qs = qs.filter(action=action)
        return success_envelope(ActivityLogSerializer(qs[:100], many=True).data)
