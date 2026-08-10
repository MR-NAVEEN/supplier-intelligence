from rest_framework.permissions import BasePermission


class IsWorkspaceMember(BasePermission):
    def has_permission(self, request, view):
        return bool(getattr(request, 'workspace', None) and getattr(request, 'workspace_role', None))


class IsWorkspaceAdmin(BasePermission):
    def has_permission(self, request, view):
        return getattr(request, 'workspace_role', None) == 'admin'
