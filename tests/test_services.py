import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.services.models import Category, Service


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def category():
    return Category.objects.create(name='Cortes de cabello')


@pytest.fixture
def service(category):
    return Service.objects.create(
        category=category,
        name='Diesel',
        duration=30,
        price=25000
    )


@pytest.fixture
def auth_client(api_client):
    user = User.objects.create_user(
        username='cliente', password='Test1234!', role='client'
    )
    url = reverse('login')
    response = api_client.post(url, {'username': 'cliente', 'password': 'Test1234!'})
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
    return api_client


@pytest.fixture
def admin_client(api_client):
    user = User.objects.create_superuser(
        username='admin', password='Test1234!', role='admin'
    )
    url = reverse('login')
    response = api_client.post(url, {'username': 'admin', 'password': 'Test1234!'})
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
    return api_client


@pytest.mark.django_db
class TestCategories:
    def test_list_categories_authenticated(self, auth_client, category):
        url = reverse('category-list')
        response = auth_client.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_list_categories_unauthenticated(self, api_client, category):
        url = reverse('category-list')
        response = api_client.get(url)
        assert response.status_code == 401

    def test_create_category_as_admin(self, admin_client):
        url = reverse('category-list')
        response = admin_client.post(url, {'name': 'Tintes'})
        assert response.status_code == 201

    def test_create_category_as_client(self, auth_client):
        url = reverse('category-list')
        response = auth_client.post(url, {'name': 'Tintes'})
        assert response.status_code == 403


@pytest.mark.django_db
class TestServices:
    def test_list_services_authenticated(self, auth_client, service):
        url = reverse('service-list')
        response = auth_client.get(url)
        assert response.status_code == 200

    def test_filter_services_by_category(self, auth_client, service, category):
        url = reverse('service-list')
        response = auth_client.get(url, {'category': category.id})
        assert response.status_code == 200
        assert len(response.data) == 1