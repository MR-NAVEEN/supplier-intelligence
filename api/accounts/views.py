from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from api.common.responses import success_envelope
from api.workspaces.models import WorkspaceMembership

from .serializers import SignupSerializer, UserSerializer

User = get_user_model()


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.EMAIL_FIELD

    def _get_workspace_membership(self, user, request_data):
        workspace_id = request_data.get('workspace_id') or request_data.get('workspaceId')
        if workspace_id:
            membership = WorkspaceMembership.objects.select_related('workspace').filter(
                user=user,
                workspace_id=workspace_id,
            ).first()
            if membership:
                return membership

        return (
            WorkspaceMembership.objects.select_related('workspace')
            .filter(user=user)
            .order_by('workspace__name')
            .first()
        )

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        membership = WorkspaceMembership.objects.filter(user=user).order_by('workspace__name').first()
        if membership:
            token['workspace_id'] = str(membership.workspace_id)
            token['workspace_role'] = membership.role
            token['workspace_name'] = membership.workspace.name
            token['workspace_slug'] = membership.workspace.slug
            token['workspace'] = str(membership.workspace_id)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        membership = self._get_workspace_membership(user, self.context['request'].data)

        if membership:
            access_token = AccessToken(data['access'])
            refresh_token = RefreshToken(data['refresh'])

            access_token['workspace_id'] = str(membership.workspace_id)
            access_token['workspace_role'] = membership.role
            access_token['workspace_name'] = membership.workspace.name
            access_token['workspace_slug'] = membership.workspace.slug

            refresh_token['workspace_id'] = str(membership.workspace_id)
            refresh_token['workspace_role'] = membership.role
            refresh_token['workspace_name'] = membership.workspace.name
            refresh_token['workspace_slug'] = membership.workspace.slug

            data['access'] = str(access_token)
            data['refresh'] = str(refresh_token)
            data['workspace'] = {
                'id': str(membership.workspace_id),
                'name': membership.workspace.name,
                'slug': membership.workspace.slug,
                'role': membership.role,
            }
        else:
            data['workspace'] = None

        data['user'] = UserSerializer(user).data
        return data


class SignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        workspace = user._signup_workspace
        refresh = RefreshToken.for_user(user)
        return success_envelope(
            {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data,
                'workspace': {
                    'id': str(workspace.id),
                    'name': workspace.name,
                    'slug': workspace.slug,
                    'role': WorkspaceMembership.ROLE_ADMIN,
                },
            },
            'Signup successful',
            status.HTTP_201_CREATED,
        )


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]


class TokenRefreshEnvelopeView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            return success_envelope(response.data, 'Token refreshed')
        return response


class TokenBlacklistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh = request.data.get('refresh')
        if not refresh:
            return Response({'detail': 'refresh token required'}, status=status.HTTP_400_BAD_REQUEST)
        token = RefreshToken(refresh)
        token.blacklist()
        return success_envelope(None, 'Logged out successfully')


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        memberships = WorkspaceMembership.objects.filter(user=user).select_related('workspace')
        workspace_id = request.headers.get('X-Workspace-Id')
        current = None
        role = None
        permissions_list = []
        workspaces = []
        for m in memberships:
            ws_data = {
                'id': str(m.workspace_id),
                'name': m.workspace.name,
                'slug': m.workspace.slug,
                'role': m.role,
            }
            workspaces.append(ws_data)
            if workspace_id and str(m.workspace_id) == str(workspace_id):
                current = ws_data
                role = m.role
        if current is None and workspaces:
            current = workspaces[0]
            role = workspaces[0]['role']
        if role == 'admin':
            permissions_list = ['*']
        else:
            permissions_list = ['read', 'write']
        data = {
            'user': {
                'id': user.id,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'timezone': user.timezone,
            },
            'workspace': current,
            'role': role,
            'permissions': permissions_list,
            'workspaces': workspaces,
        }
        return success_envelope(data)


class PasswordResetView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'detail': 'email required'}, status=status.HTTP_400_BAD_REQUEST)
        return success_envelope({'email': email}, 'If the account exists, reset instructions were sent.')
