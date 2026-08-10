from rest_framework.views import APIView

from api.common.permissions import IsWorkspaceMember
from api.common.responses import WorkspaceRequired, camel_envelope, success_envelope

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        qs = Notification.objects.filter(workspace=request.workspace, user=request.user)
        unread = qs.filter(is_read=False).count()
        data = {
            'items': NotificationSerializer(qs[:50], many=True).data,
            'unread_count': unread,
        }
        return camel_envelope(data, 'Notifications fetched')


class NotificationMarkReadView(APIView):
    permission_classes = [IsWorkspaceMember]

    def post(self, request, pk):
        if not request.workspace:
            raise WorkspaceRequired()
        Notification.objects.filter(pk=pk, workspace=request.workspace, user=request.user).update(is_read=True)
        return camel_envelope(None, 'Notification marked read')


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsWorkspaceMember]

    def post(self, request):
        if not request.workspace:
            raise WorkspaceRequired()
        updated = Notification.objects.filter(
            workspace=request.workspace, user=request.user, is_read=False,
        ).update(is_read=True)
        return camel_envelope({'updated': updated}, 'All notifications marked read')
