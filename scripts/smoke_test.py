"""Smoke test for supplier-intelligence API."""
import os
import sys
import uuid
from io import BytesIO

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from api.workspaces.models import Workspace, WorkspaceMembership

User = get_user_model()


def run():
    client = APIClient()
    email = 'smoke@example.com'
    password = 'SmokeTest123!'
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={'username': 'smoke', 'first_name': 'Smoke', 'last_name': 'Test'},
    )
    user.set_password(password)
    user.save()

    workspace, _ = Workspace.objects.get_or_create(
        slug='smoke-workspace',
        defaults={'name': 'Smoke Workspace', 'created_by': user},
    )
    WorkspaceMembership.objects.get_or_create(workspace=workspace, user=user, defaults={'role': 'admin'})

    login = client.post('/api/auth/token/', {'email': email, 'password': password}, format='json')
    assert login.status_code == 200, login.content
    access = login.json()['data']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}', HTTP_X_WORKSPACE_ID=str(workspace.id))

    me = client.get('/api/auth/me/')
    assert me.status_code == 200 and me.json()['success'], me.content

    supplier = client.post(
        '/api/suppliers/',
        {'name': 'Acme Supplies', 'status': 'prospect', 'country': 'India'},
        format='json',
    )
    assert supplier.status_code == 201, supplier.content
    supplier_id = supplier.json()['data']['id']

    product = client.post(
        '/api/products/',
        {'name': 'Widget A', 'supplier': supplier_id, 'status': 'active'},
        format='json',
    )
    assert product.status_code == 201, product.content

    slug = f'hardware-{uuid.uuid4().hex[:8]}'
    category = client.post('/api/categories/', {'name': 'Hardware', 'slug': slug}, format='json')
    assert category.status_code in (201, 200), category.content

    tree = client.get('/api/categories/tree/')
    assert tree.status_code == 200, tree.content

    search = client.get('/api/search/?q=Widget')
    assert search.status_code == 200, search.content

    dashboard = client.get('/api/dashboard/summary/')
    assert dashboard.status_code == 200 and 'supplierCount' in dashboard.json()['data'], dashboard.content

    notifications = client.get('/api/notifications/')
    assert notifications.status_code == 200, notifications.content

    settings_resp = client.get('/api/settings/profile/')
    assert settings_resp.status_code == 200, settings_resp.content

    activity = client.get('/api/activity/')
    assert activity.status_code == 200, activity.content

    analytics = client.get('/api/analytics/products/')
    assert analytics.status_code == 200, analytics.content

    card_image = SimpleUploadedFile('card.jpg', b'fake-image-bytes', content_type='image/jpeg')
    extract = client.post('/api/business-cards/extract/', {'file': card_image}, format='multipart')
    assert extract.status_code == 201, extract.content
    card_id = extract.json()['data']['business_card']['id']

    commit = client.post(
        '/api/business-cards/commit/',
        {'business_card_id': card_id},
        format='json',
    )
    assert commit.status_code == 201, commit.content

    catalogue = client.post(
        '/api/catalogues/',
        {'title': '2026 Catalogue', 'supplier': supplier_id},
        format='json',
    )
    assert catalogue.status_code == 201, catalogue.content
    catalogue_id = catalogue.json()['data']['id']

    session = client.post('/api/catalogues/upload-sessions/', {'files': []}, format='json')
    assert session.status_code == 201, session.content
    session_id = session.json()['data']['id']

    committed = client.post(
        f'/api/catalogues/upload-sessions/{session_id}/commit/',
        {'title': 'Uploaded Catalogue', 'supplier_id': supplier_id},
        format='json',
    )
    assert committed.status_code == 201, committed.content

    jobs = client.get('/api/jobs/')
    assert jobs.status_code == 200, jobs.content

    print('SMOKE TEST PASSED')
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
