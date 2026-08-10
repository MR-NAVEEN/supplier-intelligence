from api.activity.models import ActivityLog


def log_activity(workspace, user, action, entity_type, entity_id, metadata=None):
    ActivityLog.objects.create(
        workspace=workspace,
        user=user,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        metadata=metadata or {},
    )
