from groq import Groq
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from apps.accounts.models import User
from apps.services.models import Service
from apps.schedules.models import Schedule
from apps.appointments.models import Appointment
import json


def parse_day_preference(description: str) -> list:
    """
    Detecta preferencia de día en la descripción del cliente.
    Retorna lista de días de la semana (0=lunes, 6=domingo)
    """
    description = description.lower()
    day_map = {
        'lunes': [0], 'martes': [1], 'miércoles': [2], 'miercoles': [2],
        'jueves': [3], 'viernes': [4], 'sábado': [5], 'sabado': [5],
        'domingo': [6], 'fin de semana': [5, 6], 'entre semana': [0, 1, 2, 3, 4]
    }
    for key, days in day_map.items():
        if key in description:
            return days
    return list(range(7))


def parse_time_preference(description: str) -> tuple:
    """
    Detecta preferencia de hora en la descripción.
    Retorna (hora_inicio, hora_fin)
    """
    description = description.lower()
    if any(w in description for w in ['mañana', 'manana', 'temprano']):
        return (8, 12)
    elif any(w in description for w in ['tarde', 'después del mediodía']):
        return (12, 18)
    elif any(w in description for w in ['noche', 'después de las 6']):
        return (18, 22)
    return (8, 18)


def get_available_slots_for_barber(barber, service, preferred_days, time_range, limit=3):
    """
    Busca slots disponibles para un barbero específico
    dentro de los próximos 7 días.
    """
    now = timezone.now()
    slots = []
    days_checked = 0

    while len(slots) < limit and days_checked < 14:
        check_date = (now + timedelta(days=days_checked + 1)).date()
        day_of_week = check_date.weekday()

        if day_of_week not in preferred_days:
            days_checked += 1
            continue

        try:
            schedule = Schedule.objects.get(
                barber=barber,
                day=day_of_week,
                is_active=True
            )
        except Schedule.DoesNotExist:
            days_checked += 1
            continue

        start_hour, end_hour = time_range
        current = datetime.combine(check_date, schedule.start_time)
        end = datetime.combine(check_date, schedule.end_time)
        duration = timedelta(minutes=service.duration)

        # Ajustar al rango de preferencia horaria
        if current.hour < start_hour:
            current = current.replace(hour=start_hour, minute=0)
        if end.hour > end_hour:
            end = end.replace(hour=end_hour, minute=0)

        while current + duration <= end and len(slots) < limit:
            slot_start = timezone.make_aware(current)
            slot_end = slot_start + duration

            # Verificar anticipación mínima
            if slot_start < now + timedelta(hours=2):
                current += timedelta(minutes=30)
                continue

            # Verificar conflictos
            conflict = Appointment.objects.filter(
                barber=barber,
                status__in=['pending', 'confirmed'],
                start_datetime__lt=slot_end,
                end_datetime__gt=slot_start
            ).exists()

            if not conflict:
                slots.append(slot_start.strftime('%Y-%m-%dT%H:%M:%S'))

            current += timedelta(minutes=30)

        days_checked += 1

    return slots


def get_smart_appointment_recommendation(description: str) -> dict:
    """
    Recibe descripción del cliente y recomienda
    servicio, barbero y horarios disponibles.
    """
    # Obtener catálogo de servicios
    services = Service.objects.filter(is_active=True).select_related('category')
    catalog = "\n".join([
        f"- ID:{s.id} {s.name} (Categoría: {s.category.name}, "
        f"Duración: {s.duration} min, Precio: ${s.price})"
        for s in services
    ])

    # Obtener barberos disponibles
    barbers = User.objects.filter(role='barber')
    barbers_text = "\n".join([
        f"- ID:{b.id} {b.get_full_name() or b.username}"
        for b in barbers
    ])

    prompt = f"""Eres un asistente inteligente de una barbería. 
Analiza la descripción del cliente y recomienda el servicio y barbero más adecuados.

Servicios disponibles:
{catalog}

Barberos disponibles:
{barbers_text}

Descripción del cliente: "{description}"

Responde SOLO en formato JSON con esta estructura exacta:
{{
    "service_id": <id del servicio recomendado>,
    "service_name": "<nombre exacto del servicio>",
    "barber_id": <id del barbero recomendado>,
    "reason": "<explicación de por qué este servicio y barbero son ideales>",
    "tips": "<consejo útil para el cliente>"
}}

No agregues texto fuera del JSON."""

    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500
    )

    content = response.choices[0].message.content.strip()
    result = json.loads(content)

    # Obtener datos reales del servicio y barbero
    service = Service.objects.select_related('category').get(
        id=result['service_id'], is_active=True
    )
    barber = User.objects.get(id=result['barber_id'], role='barber')

    # Detectar preferencias de día y hora
    preferred_days = parse_day_preference(description)
    time_range = parse_time_preference(description)

    # Buscar slots disponibles
    slots = get_available_slots_for_barber(
        barber, service, preferred_days, time_range, limit=3
    )

    # Verificar si hay slots disponibles
    if not slots:
        # Intentar con todos los días sin preferencia
        slots_fallback = get_available_slots_for_barber(
            barber, service, list(range(7)), (8, 18), limit=3
        )

        if not slots_fallback:
            return {
                "service": {
                    "id": service.id,
                    "name": service.name,
                    "category": service.category.name,
                    "duration": service.duration,
                    "price": str(service.price),
                    "image_url": service.image_url,
                },
                "barber": {
                    "id": barber.id,
                    "name": barber.get_full_name() or barber.username,
                    "image_url": barber.image_url,
                },
                "suggested_slots": [],
                "available": False,
                "message": (
                    f"Lo sentimos, {barber.get_full_name() or barber.username} "
                    f"no tiene disponibilidad en los próximos 14 días. "
                    f"Te recomendamos intentar con otro barbero o consultar "
                    f"la disponibilidad directamente en /api/appointments/availability/."
                ),
                "reason": result['reason'],
                "tips": result['tips'],
            }

        # Hay slots pero no en el horario preferido
        return {
            "service": {
                "id": service.id,
                "name": service.name,
                "category": service.category.name,
                "duration": service.duration,
                "price": str(service.price),
                "image_url": service.image_url,
            },
            "barber": {
                "id": barber.id,
                "name": barber.get_full_name() or barber.username,
                "image_url": barber.image_url,
            },
            "suggested_slots": slots_fallback,
            "available": True,
            "message": (
                f"No hay disponibilidad en el horario que prefieres, "
                f"pero encontramos {len(slots_fallback)} horario(s) alternativo(s) "
                f"para {service.name} con {barber.get_full_name() or barber.username}."
            ),
            "reason": result['reason'],
            "tips": result['tips'],
        }

    return {
        "service": {
            "id": service.id,
            "name": service.name,
            "category": service.category.name,
            "duration": service.duration,
            "price": str(service.price),
            "image_url": service.image_url,
        },
        "barber": {
            "id": barber.id,
            "name": barber.get_full_name() or barber.username,
            "image_url": barber.image_url,
        },
        "suggested_slots": slots,
        "available": True,
        "message": (
            f"Encontramos {len(slots)} horario(s) disponible(s) "
            f"para {service.name} con {barber.get_full_name() or barber.username}."
        ),
        "reason": result['reason'],
        "tips": result['tips'],
    }