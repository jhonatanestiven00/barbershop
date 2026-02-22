from datetime import datetime, timedelta
from django.utils import timezone
from apps.schedules.models import Schedule
from apps.appointments.models import Appointment


def get_available_slots(barber, date, service):
    """
    Retorna lista de horarios disponibles para un barbero
    en una fecha específica dado un servicio.
    """
    # Obtener el día de la semana (0=lunes, 6=domingo)
    day_of_week = date.weekday()

    # Verificar si el barbero trabaja ese día
    try:
        schedule = Schedule.objects.get(
            barber=barber,
            day=day_of_week,
            is_active=True
        )
    except Schedule.DoesNotExist:
        return []

    # Generar slots cada 30 minutos dentro del horario del barbero
    slots = []
    current = datetime.combine(date, schedule.start_time)
    end = datetime.combine(date, schedule.end_time)
    duration = timedelta(minutes=service.duration)

    while current + duration <= end:
        slot_start = timezone.make_aware(current)
        slot_end = slot_start + duration

        # Verificar que no haya cita en ese slot
        conflict = Appointment.objects.filter(
            barber=barber,
            status__in=['pending', 'confirmed'],
            start_datetime__lt=slot_end,
            end_datetime__gt=slot_start
        ).exists()

        if not conflict:
            slots.append({
                'start': slot_start.strftime('%H:%M'),
                'end': slot_end.strftime('%H:%M'),
            })

        current += timedelta(minutes=30)

    return slots