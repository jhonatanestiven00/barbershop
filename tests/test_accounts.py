import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def create_user():
    def make_user(username, role='client', password='Test1234!'):
        return User.objects.create_user(
            username=username,
            password=password,
            role=role,
            email=f'{username}@test.com'
        )
    return make_user


@pytest.fixture
def auth_client(api_client, create_user):
    user = create_user('testclient', role='client')
    url = reverse('login')
    response = api_client.post(url, {'username': 'testclient', 'password': 'Test1234!'})
    token = response.data['access']
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api_client, user


@pytest.mark.django_db
class TestRegister:
    def test_register_success(self, api_client):
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'Test1234!',
            'password2': 'Test1234!',
            'role': 'client'
        }
        response = api_client.post(url, data)
        assert response.status_code == 201
        assert User.objects.filter(username='newuser').exists()

    def test_register_passwords_dont_match(self, api_client):
        url = reverse('register')
        data = {
            'username': 'newuser',
            'email': 'newuser@test.com',
            'password': 'Test1234!',
            'password2': 'Different1234!',
            'role': 'client'
        }
        response = api_client.post(url, data)
        assert response.status_code == 400

    def test_register_duplicate_username(self, api_client, create_user):
        create_user('existinguser')
        url = reverse('register')
        data = {
            'username': 'existinguser',
            'email': 'other@test.com',
            'password': 'Test1234!',
            'password2': 'Test1234!',
            'role': 'client'
        }
        response = api_client.post(url, data)
        assert response.status_code == 400


@pytest.mark.django_db
class TestLogin:
    def test_login_success(self, api_client, create_user):
        create_user('loginuser')
        url = reverse('login')
        response = api_client.post(url, {'username': 'loginuser', 'password': 'Test1234!'})
        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_login_wrong_password(self, api_client, create_user):
        create_user('loginuser')
        url = reverse('login')
        response = api_client.post(url, {'username': 'loginuser', 'password': 'wrong'})
        assert response.status_code == 401

    def test_login_nonexistent_user(self, api_client):
        url = reverse('login')
        response = api_client.post(url, {'username': 'noexiste', 'password': 'Test1234!'})
        assert response.status_code == 401


@pytest.mark.django_db
class TestProfile:
    def test_get_profile_authenticated(self, auth_client):
        client, user = auth_client
        url = reverse('profile')
        response = client.get(url)
        assert response.status_code == 200
        assert response.data['username'] == user.username

    def test_get_profile_unauthenticated(self, api_client):
        url = reverse('profile')
        response = api_client.get(url)
        assert response.status_code == 401