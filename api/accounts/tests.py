from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from api.workspaces.models import WorkspaceMembership

User = get_user_model()


class SignupAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_creates_user_workspace_and_tokens(self):
        resp = self.client.post(
            '/api/auth/signup/',
            {
                'email': 'naveen@example.com',
                'password': 'StrongPass123!',
                'first_name': 'Naveen',
                'last_name': 'Kumar',
                'phone': '+91-9000000000',
                'workspace_name': 'Pezala',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        body = resp.json()
        self.assertTrue(body['success'])
        data = body['data']
        self.assertTrue(data['access'])
        self.assertTrue(data['refresh'])
        self.assertEqual(data['user']['email'], 'naveen@example.com')
        self.assertEqual(data['workspace']['name'], 'Pezala')
        self.assertEqual(data['workspace']['role'], 'admin')
        user = User.objects.get(email='naveen@example.com')
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                user=user,
                workspace_id=data['workspace']['id'],
                role='admin',
            ).exists()
        )

    def test_duplicate_email_rejected(self):
        User.objects.create_user(
            username='existing',
            email='naveen@example.com',
            password='StrongPass123!',
        )
        resp = self.client.post(
            '/api/auth/signup/',
            {'email': 'naveen@example.com', 'password': 'StrongPass123!'},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_signup_then_me_and_extract_headers(self):
        signup = self.client.post(
            '/api/auth/signup/',
            {'email': 'ws@example.com', 'password': 'StrongPass123!', 'workspace_name': 'WS'},
            format='json',
        )
        self.assertEqual(signup.status_code, 201, signup.content)
        access = signup.json()['data']['access']
        workspace_id = signup.json()['data']['workspace']['id']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        me = self.client.get('/api/auth/me/')
        self.assertEqual(me.status_code, 200, me.content)
        self.assertEqual(me.json()['data']['workspaces'][0]['id'], workspace_id)
