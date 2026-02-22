import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.services.models import Category, Service
from apps.appointments.models import Appointment
from django.utils import timezone


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def client_user():
    return User.objects.create_user(
        username='cliente', password='Test1234!', role='client'
    )


@pytest.fixture
def barber_user():
    return User.objects.create_user(
        username='barbero', password='Test1234!', role='barber'
    )


@pytest.fixture
def service():
    category = Category.objects.create(name='Cortes')
    return Service.objects.create(
        category=category, name='Diesel', duration=30, price=25000
    )


@pytest.fixture
def auth_client_user(api_client, client_user):
    url = reverse('login')
    response = api_client.post(url, {'username': 'cliente', 'password': 'Test1234!'})
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
    return api_client


@pytest.fixture
def auth_barber_user(api_client, barber_user):
    url = reverse('login')
    response = api_client.post(url, {'username': 'barbero', 'password': 'Test1234!'})
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
    return api_client


@pytest.mark.django_db
class TestAppointments:
    def test_create_appointment_as_client(self, auth_client_user, barber_user, service):
        url = reverse('appointment-list')
        data = {
            'barber': barber_user.id,
            'service': service.id,
            'start_datetime': '2026-03-01T10:00:00',
        }
        response = auth_client_user.post(url, data)
        assert response.status_code == 201
        assert Appointment.objects.count() == 1

    def test_create_appointment_as_barber_forbidden(self, auth_barber_user, barber_user, service):
        url = reverse('appointment-list')
        data = {
            'barber': barber_user.id,
            'service': service.id,
            'start_datetime': '2026-03-01T10:00:00',
        }
        response = auth_barber_user.post(url, data)
        assert response.status_code == 403

    def test_no_double_booking(self, auth_client_user, client_user, barber_user, service):
        url = reverse('appointment-list')
        data = {
            'barber': barber_user.id,
            'service': service.id,
            'start_datetime': '2026-03-01T10:00:00',
        }
        # Primera cita
        auth_client_user.post(url, data)
        # Segunda cita en el mismo horario
        response = auth_client_user.post(url, data)
        assert response.status_code == 400


    def test_client_only_sees_own_appointments(self, auth_client_user, client_user, barber_user, service):
        Appointment.objects.create(
            client=client_user,
            barber=barber_user,
            service=service,
            start_datetime=timezone.make_aware(timezone.datetime(2026, 3, 1, 10, 0)),
            end_datetime=timezone.make_aware(timezone.datetime(2026, 3, 1, 10, 30)),
            status='pending'
        )
        url = reverse('appointment-list')
        response = auth_client_user.get(url)
        assert response.status_code == 200
        assert len(response.data) == 1