"""Demo workspace so AI APIs can run without login / X-Workspace-Id."""
from api.workspaces.models import Workspace


def get_default_workspace():
    workspace, _ = Workspace.objects.get_or_create(
        slug='ai-demo',
        defaults={'name': 'AI Demo'},
    )
    return workspace


def optional_user(request):
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user
    return None