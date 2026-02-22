from django.db import models
from apps.accounts.models import User


class Schedule(models.Model):
    class Day(models.IntegerChoices):
        MONDAY = 0, 'Lunes'
        TUESDAY = 1, 'Martes'
        WEDNESDAY = 2, 'Miércoles'
        THURSDAY = 3, 'Jueves'
        FRIDAY = 4, 'Viernes'
        SATURDAY = 5, 'Sábado'
        SUNDAY = 6, 'Domingo'

    barber = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='schedules',
        limit_choices_to={'role': 'barber'}
    )
    day = models.IntegerField(choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['barber', 'day']
        ordering = ['day', 'start_time']

    def __str__(self):
        return f"{self.barber} - {self.get_day_display()} {self.start_time}-{self.end_time}"