import re
from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _snake_to_camel(name: str) -> str:
    parts = name.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def camelize(data: Any) -> Any:
    if isinstance(data, list):
        return [camelize(item) for item in data]
    if isinstance(data, dict):
        return {_snake_to_camel(k): camelize(v) for k, v in data.items()}
    return data


def success_envelope(data=None, message='Success', status_code=status.HTTP_200_OK):
    return Response(
        {
            'success': True,
            'status': str(status_code),
            'message': message,
            'data': data,
        },
        status=status_code,
    )


def error_envelope(message='Error', status_code=status.HTTP_400_BAD_REQUEST, data=None):
    return Response(
        {
            'success': False,
            'status': str(status_code),
            'message': message,
            'data': data,
        },
        status=status_code,
    )


def camel_envelope(data=None, message='Success', status_code=status.HTTP_200_OK):
    return success_envelope(camelize(data), message, status_code)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        detail = response.data
        if isinstance(detail, dict) and 'detail' in detail:
            message = str(detail['detail'])
        else:
            message = 'Request failed'
        response.data = {
            'success': False,
            'status': str(response.status_code),
            'message': message,
            'data': detail if not isinstance(detail, dict) or 'detail' not in detail else None,
        }
    return response


class WorkspaceRequired(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'X-Workspace-Id header is required.'


class PermissionDenied(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have permission for this action.'
