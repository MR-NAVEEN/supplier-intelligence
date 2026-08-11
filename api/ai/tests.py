from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from api.workspaces.models import Workspace, WorkspaceMembership

User = get_user_model()


def _tiny_pdf_bytes():
    # Minimal one-page PDF (valid enough for most parsers; tests mock page count).
    return (
        b'%PDF-1.1\n'
        b'1 0 obj<<>>endobj\n'
        b'trailer<<>>\n'
        b'%%EOF\n'
    )


class AIExtractAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='aiuser',
            email='aiuser@example.com',
            password='AiTest123!',
        )
        self.workspace = Workspace.objects.create(name='AI WS', slug='ai-ws', created_by=self.user)
        WorkspaceMembership.objects.create(workspace=self.workspace, user=self.user, role='admin')
        login = self.client.post(
            '/api/auth/token/',
            {'email': 'aiuser@example.com', 'password': 'AiTest123!'},
            format='json',
        )
        self.assertEqual(login.status_code, 200, login.content)
        access = login.json()['data']['access']
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {access}',
            HTTP_X_WORKSPACE_ID=str(self.workspace.id),
        )

    def _pdf(self, name='sample.pdf'):
        return SimpleUploadedFile(name, _tiny_pdf_bytes(), content_type='application/pdf')

    def test_rejects_non_pdf(self):
        resp = self.client.post(
            '/api/ai/extract/',
            {'file': SimpleUploadedFile('note.txt', b'hi', content_type='text/plain'), 'page_mode': 'first_n', 'page_count': 1},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 400)

    def test_requires_page_count_for_first_n(self):
        resp = self.client.post(
            '/api/ai/extract/',
            {'file': self._pdf(), 'page_mode': 'first_n'},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 400)

    def test_requires_auth(self):
        anon = APIClient()
        resp = anon.post('/api/ai/extract/', {'page_mode': 'full'}, format='multipart')
        self.assertEqual(resp.status_code, 401)

    @patch('api.ai.views.extract_catalogue')
    @patch('api.ai.views.pdf_page_count', return_value=8)
    def test_create_first_n_returns_json_time_and_cost(self, _pages, extract_mock):
        extract_mock.return_value = {
            'result': {
                'source_file': 'sample.pdf',
                'total_pages_in_pdf': 8,
                'pages_processed': [1],
                'pages': [
                    {
                        'page_number': 1,
                        'page_type': 'product_listing',
                        'products': [{'product_name': 'WAVE BUDS 2', 'price': '6999', 'code_or_sku': None}],
                    }
                ],
            },
            'usage': {'prompt_tokens': 1000, 'completion_tokens': 200, 'total_tokens': 1200},
            'advertisement_pages_skipped': 0,
        }
        resp = self.client.post(
            '/api/ai/extract/',
            {'file': self._pdf('JBL.pdf'), 'page_mode': 'first_n', 'page_count': 1},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertTrue(body['success'])
        data = body['data']
        self.assertEqual(data['status'], 'succeeded')
        self.assertEqual(data['page_mode'], 'first_n')
        self.assertEqual(data['pages_requested'], [1])
        self.assertEqual(data['summary']['products_count'], 1)
        self.assertIn('duration_ms', data['timing'])
        self.assertIn('estimated_cost_usd', data['costing'])
        self.assertEqual(data['result']['pages'][0]['products'][0]['product_name'], 'WAVE BUDS 2')

        run_id = data['id']
        detail = self.client.get(f'/api/ai/extract/{run_id}/')
        self.assertEqual(detail.status_code, 200)
        listing = self.client.get('/api/ai/extract/')
        self.assertEqual(listing.status_code, 200)