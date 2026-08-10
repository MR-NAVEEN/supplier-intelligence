from rest_framework.views import APIView

from api.accounts.serializers import UserSerializer
from api.common.permissions import IsWorkspaceMember
from api.common.responses import success_envelope


class ProfileSettingsView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        return success_envelope(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_envelope(serializer.data, 'Profile updated')


class NotificationPreferencesView(APIView):
    permission_classes = [IsWorkspaceMember]

    def get(self, request):
        return success_envelope(request.user.notification_preferences or {})

    def patch(self, request):
        prefs = dict(request.user.notification_preferences or {})
        prefs.update(request.data)
        request.user.notification_preferences = prefs
        request.user.save(update_fields=['notification_preferences'])
        return success_envelope(prefs, 'Notification preferences updated')
