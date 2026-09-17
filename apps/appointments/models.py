from django.db import models
from apps.accounts.models import User
from apps.services.models import Service


class Appointment(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', 'Agendada'
        CANCELLED_BY_CLIENT = 'cancelled_client', 'Cancelada por cliente'
        CANCELLED_BY_BARBER = 'cancelled_barber', 'Cancelada por barbero'
        COMPLETED = 'completed', 'Completada'

    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='client_appointments',
        limit_choices_to={'role': 'client'}
    )
    barber = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='barber_appointments',
        limit_choices_to={'role': 'barber'}
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='appointments'
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_datetime']

    def __str__(self):
        return f"{self.client} con {self.barber} - {self.start_datetime}"