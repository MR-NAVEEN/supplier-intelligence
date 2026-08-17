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
                'brands': 'Columbia',
                'extras': 'not-a-dict',
            }
        )
        self.assertEqual(data['full_name'], 'Ravi')
        self.assertEqual(data['emails'], ['ravi@test.com'])
        self.assertEqual(data['phones'], [])
        self.assertEqual(data['brands'], ['Columbia'])
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
                'brands': ['Acme'],
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
        self.assertEqual(data['brands'], ['Acme'])
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

    @patch('api.ai.views.extract_business_card')
    def test_accepts_pdf_and_two_sides(self, extract_mock):
        extract_mock.return_value = {
            'result': {
                'full_name': 'JAYENDER SINGH',
                'job_title': 'Business Development Manager',
                'company': 'Corporate Gifts House',
                'emails': ['woodland.b2b@gmail.com'],
                'phones': ['+91-8510009660'],
                'website': 'www.corporategiftshouse.com',
                'address': 'C-14, RK Metro Mall, Delhi-110007',
                'linkedin': '',
                'brands': ['Columbia', 'Rico', 'Woodland', 'TRIPLE DOT'],
                'extras': {},
                'extra_text': 'Exclusive B2B Pan India Distributor',
            },
            'usage': {'prompt_tokens': 500, 'completion_tokens': 120, 'total_tokens': 620},
            'sides': 2,
        }
        resp = self.client.post(
            '/api/ai/cards/',
            {
                'file': [
                    self._png('front.png'),
                    self._png('back.png'),
                ]
            },
            format='multipart',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()['data']
        self.assertEqual(data['full_name'], 'JAYENDER SINGH')
        self.assertEqual(data['company'], 'Corporate Gifts House')
        self.assertIn('Woodland', data['brands'])
        self.assertEqual(len(data['source_files']), 2)
        self.assertEqual(extract_mock.call_count, 1)
        paths = extract_mock.call_args[0][0]
        self.assertEqual(len(paths), 2)

        pdf_resp = self.client.post(
            '/api/ai/cards/',
            {'file': SimpleUploadedFile('card.pdf', _tiny_pdf_bytes(), content_type='application/pdf')},
            format='multipart',
        )
        self.assertEqual(pdf_resp.status_code, 201, pdf_resp.content)


FINGER_PRODUCTS = [
    (1, 'SOUNDKING-5W', '1499'),
    (1, 'MINIMOT-5W', '1999'),
    (1, 'SOUNDNUGGET-8W', '1995'),
    (2, 'MUSILICIOUS 3', '1175'),
    (2, 'SWAG5-10W', '2999'),
    (2, 'KARAOKESTAR-K4-12W', '2999'),
    (3, 'ROCK-N-ROLL H6', '1999'),
    (4, 'KICKSTAR-C11', '1645'),
    (4, 'MAGPOWER-P10', '3445'),
    (4, 'FUEL K3', '2199'),
    (5, 'BT-FREEDOM', '1199'),
    (5, 'HOLD-ME-UP3', '499'),
]

JBL_PRODUCTS = [
    (1, 'WAVE BUDS 2', '6999', 'JBL BUDS'),
    (1, 'WAVE BEAM 2', '7499', 'JBL BUDS'),
    (1, 'LIVE BUDS 3', '24999', 'JBL BUDS'),
    (1, 'LIVE BEAM 3', '24999', 'JBL BUDS'),
]


def _seed_extracted_catalogues():
    from api.ai.models import AICatalogue, AICatalogueUpload, AIExtractedProduct, AIExtractionRun
    from api.ai.services.persist import _parse_price, _search_text
    from api.workspaces.models import Workspace

    workspace, _ = Workspace.objects.get_or_create(slug='ai-demo', defaults={'name': 'AI Demo'})
    finger = AICatalogue.objects.create(
        workspace=workspace,
        title='FINGER 2026',
        brand='FINGER',
        source_filename='FINGER 2026.pdf',
        total_pages=5,
    )
    jbl = AICatalogue.objects.create(
        workspace=workspace,
        title='JBL',
        brand='JBL',
        source_filename='JBL.pdf',
        total_pages=8,
    )
    upload = AICatalogueUpload.objects.create(
        workspace=workspace,
        catalogue=finger,
        file=SimpleUploadedFile('seed.pdf', _tiny_pdf_bytes(), content_type='application/pdf'),
        original_filename='seed.pdf',
    )
    run = AIExtractionRun.objects.create(
        workspace=workspace,
        catalogue=finger,
        upload=upload,
        status=AIExtractionRun.STATUS_SUCCEEDED,
        page_mode=AIExtractionRun.MODE_FIRST_N,
        page_count=5,
    )
    for page, name, price in FINGER_PRODUCTS:
        AIExtractedProduct.objects.create(
            catalogue=finger,
            run=run,
            page_number=page,
            product_name=name,
            price=_parse_price(price),
            price_raw=price,
            search_text=_search_text(name, '', '', '', {}),
            is_current=True,
        )
    for page, name, price, series in JBL_PRODUCTS:
        AIExtractedProduct.objects.create(
            catalogue=jbl,
            run=run,
            page_number=page,
            product_name=name,
            price=_parse_price(price),
            price_raw=price,
            series=series,
            search_text=_search_text(name, '', series, '', {}),
            is_current=True,
        )
    return workspace


class AIChatAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        _seed_extracted_catalogues()

    def test_requires_message(self):
        resp = self.client.post('/api/ai/chat/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_gold_cases_return_catalogue_facts(self):
        from api.ai.gold_chat import GOLD_CASES
        from api.ai.services.chat import answer_question

        failures = []
        for case in GOLD_CASES:
            result = answer_question(case['q'])
            answer = result['answer']
            missing = [token for token in case['must'] if token.lower() not in answer.lower()]
            banned = [token for token in case.get('must_not', []) if token.lower() in answer.lower()]
            if missing or banned:
                failures.append(f"{case['id']}: answer={answer!r} missing={missing} banned={banned}")
        self.assertFalse(failures, '\n'.join(failures))

    def test_chat_endpoint_soundking_price(self):
        resp = self.client.post(
            '/api/ai/chat/',
            {'message': 'What is the MRP of SOUNDKING-5W?'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()['data']
        self.assertIn('1499', data['answer'])
        self.assertEqual(data['sources'][0]['product_name'], 'SOUNDKING-5W')
        self.assertTrue(data['session_id'])

    def test_chat_followup_uses_session(self):
        first = self.client.post(
            '/api/ai/chat/',
            {'message': 'Cheapest product in Finger catalogue?'},
            format='json',
        )
        self.assertEqual(first.status_code, 200, first.content)
        session_id = first.json()['data']['session_id']
        second = self.client.post(
            '/api/ai/chat/',
            {'message': 'What about the most expensive?', 'session_id': session_id},
            format='json',
        )
        self.assertEqual(second.status_code, 200, second.content)
        self.assertIn('MAGPOWER-P10', second.json()['data']['answer'])
        self.assertIn('3445', second.json()['data']['answer'])