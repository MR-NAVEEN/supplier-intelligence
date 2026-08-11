"""Live smoke for POST /api/ai/extract/ — not imported by manage.py test."""
import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
django.setup()

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from api.workspaces.models import Workspace, WorkspaceMembership

User = get_user_model()


def main():
    pdf_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'JBL.pdf')
    if not os.path.exists(pdf_path):
        print('MISSING_PDF', pdf_path)
        return 2

    client = APIClient()
    user, _ = User.objects.get_or_create(
        email='ai-live@example.com',
        defaults={'username': 'ailive'},
    )
    user.set_password('AiLive123!')
    user.save()
    workspace, _ = Workspace.objects.get_or_create(
        slug='ai-live-ws',
        defaults={'name': 'AI Live', 'created_by': user},
    )
    WorkspaceMembership.objects.get_or_create(
        workspace=workspace, user=user, defaults={'role': 'admin'}
    )

    login = client.post('/api/auth/token/', {'email': user.email, 'password': 'AiLive123!'}, format='json')
    print('LOGIN', login.status_code)
    if login.status_code != 200:
        print(login.content)
        return 1
    access = login.json()['data']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}', HTTP_X_WORKSPACE_ID=str(workspace.id))

    with open(pdf_path, 'rb') as handle:
        upload = SimpleUploadedFile('JBL.pdf', handle.read(), content_type='application/pdf')
    resp = client.post(
        '/api/ai/extract/',
        {'file': upload, 'page_mode': 'first_n', 'page_count': 1, 'model_tier': 'high_accuracy'},
        format='multipart',
    )
    print('EXTRACT', resp.status_code)
    body = resp.json()
    print('success', body.get('success'), 'message', body.get('message'))
    data = body.get('data') or {}
    if resp.status_code >= 400:
        print('error_preview', str(body)[:800])
        return 1
    print('run_id', data.get('id'))
    print('status', data.get('status'))
    print('pages_requested', data.get('pages_requested'))
    print('summary', data.get('summary'))
    print('timing', data.get('timing'))
    costing = data.get('costing') or {}
    print('cost_usd', costing.get('estimated_cost_usd'), 'tokens', costing.get('total_tokens'))
    pages = (data.get('result') or {}).get('pages') or []
    print('kept_pages', len(pages))
    if pages:
        prods = pages[0].get('products') or []
        print('first_page_products', len(prods))
        if prods:
            print('first_product', prods[0].get('product_name'), prods[0].get('price'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
