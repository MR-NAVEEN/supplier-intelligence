from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from api.ai.services.card_extract import normalize_card_data


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

    def test_allows_anonymous(self):
        resp = self.client.post(
            '/api/ai/extract/',
            {'file': self._pdf(), 'page_mode': 'first_n'},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertNotEqual(resp.status_code, 401)

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

        catalogues = self.client.get('/api/ai/catalogues/')
        self.assertEqual(catalogues.status_code, 200, catalogues.content)
        rows = catalogues.json()['data']['results']
        self.assertEqual(len(rows), 1)
        cat_id = rows[0]['id']
        schema = self.client.get(f'/api/ai/catalogues/{cat_id}/')
        self.assertEqual(schema.status_code, 200)
        schema_data = schema.json()['data']
        self.assertEqual(schema_data['products'][0]['product_name'], 'WAVE BUDS 2')
        self.assertEqual(schema_data['products'][0]['price_raw'], '6999')
        products = self.client.get(f'/api/ai/catalogues/{cat_id}/products/')
        self.assertEqual(products.status_code, 200)
        self.assertEqual(products.json()['data']['results'][0]['product_name'], 'WAVE BUDS 2')


def _tiny_png_bytes():
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0'
        b'\x00\x00\x00\x03\x00\x01\x00\x05\xfe\xd4\xef\x00\x00\x00\x00IEND\xaeB`\x82'
    )


class AIBusinessCardNormalizeTest(TestCase):
    def test_normalize_nulls_and_scalars(self):
        data = normalize_card_data(
            {
                'full_name': '  Ravi  ',
                'emails': 'ravi@test.com',
                'phones': None,
                'extras': 'not-a-dict',
            }
        )
        self.assertEqual(data['full_name'], 'Ravi')
        self.assertEqual(data['emails'], ['ravi@test.com'])
        self.assertEqual(data['phones'], [])
        self.assertEqual(data['extras'], {})


class AIBusinessCardAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _png(self, name='card.png'):
        return SimpleUploadedFile(name, _tiny_png_bytes(), content_type='image/png')

    def test_rejects_non_image(self):
        resp = self.client.post(
            '/api/ai/cards/',
            {'file': SimpleUploadedFile('note.txt', b'hi', content_type='text/plain')},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 400)

    def test_allows_anonymous(self):
        resp = self.client.post(
            '/api/ai/cards/',
            {'file': SimpleUploadedFile('note.txt', b'hi', content_type='text/plain')},
            format='multipart',
        )
        self.assertNotEqual(resp.status_code, 401)

    @patch('api.ai.views.extract_business_card')
    def test_upload_saves_structured_json(self, extract_mock):
        extract_mock.return_value = {
            'result': {
                'full_name': 'Priya Sharma',
                'job_title': 'Sales Manager',
                'company': 'Acme Traders',
                'emails': ['priya@acme.test'],
                'phones': ['+91 98765 43210'],
                'website': 'www.acme.test',
                'address': 'Pune, India',
                'linkedin': 'linkedin.com/in/priya',
                'extras': {'gst': '27AAAAA0000A1Z5'},
                'extra_text': '',
            },
            'usage': {'prompt_tokens': 400, 'completion_tokens': 80, 'total_tokens': 480},
        }
        resp = self.client.post(
            '/api/ai/cards/',
            {'file': self._png('priya-card.png')},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertTrue(body['success'])
        data = body['data']
        self.assertEqual(data['status'], 'succeeded')
        self.assertEqual(data['full_name'], 'Priya Sharma')
        self.assertEqual(data['company'], 'Acme Traders')
        self.assertEqual(data['emails'], ['priya@acme.test'])
        self.assertEqual(data['phones'], ['+91 98765 43210'])
        self.assertEqual(data['result_json']['job_title'], 'Sales Manager')
        self.assertIn('duration_ms', data['timing'])
        self.assertIn('estimated_cost_usd', data['costing'])

        card_id = data['id']
        detail = self.client.get(f'/api/ai/cards/{card_id}/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['data']['website'], 'www.acme.test')

        listing = self.client.get('/api/ai/cards/')
        self.assertEqual(listing.status_code, 200)
        rows = listing.json()['data']['results']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['full_name'], 'Priya Sharma')

        filtered = self.client.get('/api/ai/cards/', {'company': 'Acme'})
        self.assertEqual(filtered.json()['data']['count'], 1)
        missing = self.client.get('/api/ai/cards/', {'company': 'NoSuchCo'})
        self.assertEqual(missing.json()['data']['count'], 0)

    @patch('api.ai.views.extract_business_card', side_effect=RuntimeError('OPENAI_API_KEY is not set.'))
    def test_failed_extract_is_saved(self, _extract_mock):
        resp = self.client.post(
            '/api/ai/cards/',
            {'file': self._png()},
            format='multipart',
        )
        self.assertEqual(resp.status_code, 500, resp.content)
        data = resp.json()['data']
        self.assertEqual(data['status'], 'failed')
        self.assertTrue(data['error_message'])
        listing = self.client.get('/api/ai/cards/')
        self.assertEqual(listing.json()['data']['count'], 1)