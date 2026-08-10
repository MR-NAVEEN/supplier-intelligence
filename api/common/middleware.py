from django.utils.functional import SimpleLazyObject

from api.workspaces.models import WorkspaceMembership


def _resolve_workspace_context(request):
    workspace_id = request.headers.get('X-Workspace-Id') or request.META.get('HTTP_X_WORKSPACE_ID')
    if not workspace_id or not request.user.is_authenticated:
        return None, None
    try:
        membership = WorkspaceMembership.objects.select_related('workspace').get(
            workspace_id=workspace_id,
            user=request.user,
        )
    except (WorkspaceMembership.DoesNotExist, ValueError):
        return None, None
    return membership.workspace, membership.role


class WorkspaceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ctx = SimpleLazyObject(lambda: _resolve_workspace_context(request))
        request.workspace = SimpleLazyObject(lambda: ctx[0])
        request.workspace_role = SimpleLazyObject(lambda: ctx[1])
        return self.get_response(request)
