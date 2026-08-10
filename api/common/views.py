from rest_framework import viewsets

from .permissions import IsWorkspaceMember
from .responses import WorkspaceRequired, success_envelope


class WorkspaceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsWorkspaceMember]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method != 'OPTIONS' and not getattr(request, 'workspace', None):
            raise WorkspaceRequired()

    def get_queryset(self):
        qs = super().get_queryset()
        workspace = getattr(self.request, 'workspace', None)
        if workspace is not None and hasattr(qs.model, 'workspace_id'):
            return qs.filter(workspace=workspace)
        return qs

    def perform_create(self, serializer):
        extra = {}
        if hasattr(serializer.Meta.model, 'workspace'):
            extra['workspace'] = self.request.workspace
        if hasattr(serializer.Meta.model, 'created_by'):
            extra['created_by'] = self.request.user
        serializer.save(**extra)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return success_envelope(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_envelope(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return success_envelope(serializer.data, 'Created successfully', 201)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_envelope(serializer.data, 'Updated successfully')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return success_envelope(None, 'Deleted successfully')
