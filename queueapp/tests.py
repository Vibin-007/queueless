from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token as AuthToken
from rest_framework.test import APITestCase

from .models import Token

STAFF_PASSWORD = 'counter-pass-123'
CUSTOMER_PASSWORD = 'customer-pass-123'


def make_staff(username='staff'):
    user = User.objects.create_user(username=username, password=STAFF_PASSWORD)
    user.is_staff = True
    user.save(update_fields=['is_staff'])
    return user


def make_customer(username='customer'):
    return User.objects.create_user(
        username=username,
        password=CUSTOMER_PASSWORD,
    )


class StaffAuthTests(APITestCase):
    def setUp(self):
        self.staff = make_staff()
        self.customer = make_customer()

    def test_login_returns_token_for_staff(self):
        response = self.client.post(
            '/api/auth/login/',
            {'username': 'staff', 'password': STAFF_PASSWORD},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['token'])
        self.assertEqual(response.data['user']['username'], 'staff')
        self.assertTrue(response.data['user']['is_staff'])

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            '/api/auth/login/',
            {'username': 'staff', 'password': 'wrong'},
            format='json',
        )

        self.assertEqual(response.status_code, 400)

    def test_login_rejects_non_staff_account(self):
        response = self.client.post(
            '/api/auth/login/',
            {'username': 'customer', 'password': CUSTOMER_PASSWORD},
            format='json',
        )

        self.assertEqual(response.status_code, 403)

    def test_login_requires_credentials(self):
        response = self.client.post('/api/auth/login/', {}, format='json')

        self.assertEqual(response.status_code, 400)

    def test_me_requires_authentication(self):
        response = self.client.get('/api/auth/me/')

        self.assertEqual(response.status_code, 401)

    def test_me_returns_staff_profile(self):
        token = AuthToken.objects.create(user=self.staff)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get('/api/auth/me/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['username'], 'staff')

    def test_logout_invalidates_token(self):
        token = AuthToken.objects.create(user=self.staff)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post('/api/auth/logout/')

        self.assertEqual(response.status_code, 204)
        self.assertFalse(AuthToken.objects.filter(key=token.key).exists())


class StaffEndpointTests(APITestCase):
    def setUp(self):
        self.staff = make_staff()
        self.customer = make_customer()
        self.staff_token = AuthToken.objects.create(user=self.staff)

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def test_public_endpoints_work_without_auth(self):
        status_response = self.client.get('/api/status/')
        book_response = self.client.post(
            '/api/book/',
            {'customer_name': 'Alex'},
            format='json',
        )

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(book_response.status_code, 201)

    def test_call_next_requires_authentication(self):
        response = self.client.post('/api/next/')

        self.assertEqual(response.status_code, 401)

    def test_call_next_rejects_non_staff_token(self):
        customer_token = AuthToken.objects.create(user=self.customer)
        self.authenticate(customer_token)

        response = self.client.post('/api/next/')

        self.assertEqual(response.status_code, 403)

    def test_call_next_works_for_staff(self):
        Token.objects.create(token_number=101, customer_name='Alex')
        self.authenticate(self.staff_token)

        response = self.client.post('/api/next/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['called']['token_number'], 101)
        self.assertEqual(response.data['total_waiting'], 0)

    def test_reset_requires_authentication(self):
        response = self.client.post('/api/reset/')

        self.assertEqual(response.status_code, 401)

    def test_skip_requires_authentication(self):
        Token.objects.create(token_number=101, customer_name='Alex')

        response = self.client.post('/api/skip/101/')

        self.assertEqual(response.status_code, 401)

    def test_skip_works_for_staff(self):
        Token.objects.create(token_number=101, customer_name='Alex')
        self.authenticate(self.staff_token)

        response = self.client.post('/api/skip/101/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['token']['status'], Token.STATUS_CANCELLED)

    def test_reset_works_for_staff(self):
        Token.objects.create(token_number=101, customer_name='Alex')
        self.authenticate(self.staff_token)

        response = self.client.post('/api/reset/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Token.objects.count(), 0)

    def test_customer_can_still_cancel_own_token(self):
        Token.objects.create(token_number=101, customer_name='Alex')

        response = self.client.post('/api/cancel/101/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['token']['status'], 'CANCELLED')
