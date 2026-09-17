from groq import Groq
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from apps.accounts.models import User
from apps.services.models import Service
from apps.schedules.models import Schedule
from apps.appointments.models import Appointment
from apps.appointments.utils import get_available_slots
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
            if slot_start < now + timedelta(hours=1):
                current += timedelta(minutes=30)
                continue

            # Verificar conflictos
            conflict = Appointment.objects.filter(
                barber=barber,
                status='scheduled',
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
        model="openai/gpt-oss-120b",
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


# ==========================================================
# Gestión de citas: sugerencia de HORARIOS para un barbero y
# servicio que el cliente ya eligió (no vuelve a decidir qué
# corte pedir). La disponibilidad SIEMPRE se calcula de forma
# determinista contra la base de datos; la IA solo redacta el
# mensaje y el tip para el cliente.
# ==========================================================

def _slots_for_date(barber, service, date, min_advance_hours=0):
    """Convierte los slots de una fecha puntual a strings ISO,
    filtrando los que no cumplen la anticipación mínima."""
    now = timezone.now()
    result = []

    for slot in get_available_slots(barber, date, service):
        hour, minute = map(int, slot['start'].split(':'))
        start_dt = timezone.make_aware(
            datetime.combine(date, datetime.min.time()).replace(hour=hour, minute=minute)
        )
        if min_advance_hours and start_dt < now + timedelta(hours=min_advance_hours):
            continue
        result.append(start_dt.strftime('%Y-%m-%dT%H:%M:%S'))

    return result


def day_status(barber, service, date, today=None):
    """
    Estado de un día para el calendario del cliente:
    - 'closed': el barbero no trabaja ese día (sin horario configurado).
    - 'available': trabaja y le queda al menos un horario libre.
    - 'full': trabaja pero no le queda ningún horario libre ese día
      (ya sea por citas ya tomadas o porque el día ya casi termina).
    """
    if today is None:
        today = timezone.now().date()

    has_schedule = Schedule.objects.filter(
        barber=barber, day=date.weekday(), is_active=True
    ).exists()
    if not has_schedule:
        return 'closed'

    min_advance_hours = 1 if date == today else 0
    slots = _slots_for_date(barber, service, date, min_advance_hours=min_advance_hours)
    return 'available' if slots else 'full'


def month_availability(barber, service, year, month):
    """
    Estado de cada día del mes (desde hoy en adelante, hasta 30 días)
    para pintar el calendario. Los días pasados o fuera del rango
    permitido para agendar simplemente no se incluyen.
    """
    import calendar as calendar_module

    today = timezone.now().date()
    max_date = today + timedelta(days=30)
    _, days_in_month = calendar_module.monthrange(year, month)

    days = {}
    for day in range(1, days_in_month + 1):
        date = datetime(year, month, day).date()
        if date < today or date > max_date:
            continue
        days[date.isoformat()] = day_status(barber, service, date, today)

    return days


def _describe_slots_with_ai(barber, service, slots, context, personalization_note=None):
    """Le pide al modelo SOLO redactar un mensaje amigable con los
    horarios ya calculados; nunca decide disponibilidad.

    `personalization_note`: dato ya verificado del perfil de preferencias
    del cliente (ver apps/appointments/preferences.py), que la IA puede
    mencionar en el mensaje para que la personalización sea explícita y
    no un ordenamiento silencioso que el cliente nunca nota (Tintarev &
    Masthoff, 2015, sobre transparencia en recomendaciones). La IA solo
    puede repetir este hecho, nunca inventar uno nuevo.
    """
    barber_name = barber.get_full_name() or barber.username

    slots_text = ", ".join(
        datetime.strptime(s, '%Y-%m-%dT%H:%M:%S').strftime('%A %d de %B a las %H:%M')
        for s in slots
    ) if slots else "ninguno"

    personalization_line = (
        f'\nDato real sobre este cliente (puedes mencionarlo brevemente si es natural, '
        f'nunca inventes otro): {personalization_note}.'
        if personalization_note else ""
    )

    prompt = f"""Eres el asistente de agendamiento de una barbería.
El cliente ya eligió el servicio "{service.name}" con el barbero {barber_name}.
Está buscando disponibilidad para: {context}.
Horarios disponibles encontrados: {slots_text}.{personalization_line}

Responde SOLO en formato JSON con esta estructura exacta:
{{
    "message": "<mensaje breve y amigable resumiendo lo que encontraste, máximo 2 frases>",
    "tips": "<un consejo corto y amigable, como sugerir llegar unos minutos antes de la cita. No inventes razones sobre lo que hará el barbero (como "preparar todo"); solo invita a llegar con anticipación de forma simple>"
}}

Si no hay horarios disponibles, el mensaje debe explicarlo con amabilidad y
sugerir intentar otro día o con otro barbero. No agregues texto fuera del JSON."""

    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=200,
        )
        content = response.choices[0].message.content.strip()
        result = json.loads(content)
        return result.get("message", ""), result.get("tips", "")
    except Exception:
        # Si la IA falla, la funcionalidad sigue funcionando con un
        # mensaje genérico: la disponibilidad ya se calculó antes.
        if slots:
            return (
                f"Encontramos {len(slots)} horario(s) disponible(s) para "
                f"{service.name} con {barber_name}.",
                "Intenta llegar unos minutos antes de tu cita.",
            )
        return (
            f"No encontramos disponibilidad para {service.name} con "
            f"{barber_name} en ese rango. Intenta con otra fecha.",
            "Prueba consultando otro día u otro barbero disponible.",
        )


def _diversify_slots(slots, max_count=4, preferred_band=None):
    """
    De una lista de horarios disponibles (ordenada), elige una muestra
    repartida entre mañana / tarde / tarde-noche, en vez de varios
    horarios seguidos del mismo bloque (ej: 4 opciones todas a las
    6:00, 6:30, 7:00, 7:30).

    `preferred_band` (opcional): 'mañana' | 'tarde' | 'noche', tomado del
    perfil de preferencias del cliente (preferences.py). Cuando se pasa,
    ese bloque se prioriza dentro de la muestra sin dejar de mostrar
    variedad: sigue siendo el mismo cálculo determinista de siempre,
    solo cambia el ORDEN, nunca inventa disponibilidad que no exista.
    """
    if len(slots) <= max_count:
        return slots

    def hour_of(slot):
        return int(slot.split('T')[1][:2])

    segments = {
        "mañana": [s for s in slots if hour_of(s) < 12],
        "tarde": [s for s in slots if 12 <= hour_of(s) < 17],
        "noche": [s for s in slots if hour_of(s) >= 17],
    }

    # El bloque preferido del cliente se recorre primero para que, ante
    # empates de espacio, quede representado en la muestra final.
    order = list(segments.keys())
    if preferred_band in segments:
        order.remove(preferred_band)
        order.insert(0, preferred_band)

    picked = []
    for band in order:
        segment = segments[band]
        if segment and len(picked) < max_count:
            picked.append(segment[len(segment) // 2])

    remaining = [s for s in slots if s not in picked]
    while len(picked) < max_count and remaining:
        picked.append(remaining.pop(len(remaining) // 2))

    return sorted(picked)


def suggest_slots_for_selection(barber, service, when, description=None, client=None):
    """
    Sugiere horarios para un barbero y servicio ya elegidos.
    `when`: 'hoy' | 'manana' | 'fin_de_semana' | 'custom'
    `description`: texto libre del cliente, solo se usa si when='custom'.
    `client`: usuario que está agendando (opcional). Si se pasa y tiene
    suficiente historial, su perfil de preferencias (preferences.py)
    prioriza el bloque horario que suele elegir y se lo mencionamos en
    el mensaje, cerrando el ciclo "perfil personalizado -> IA".
    """
    today = timezone.now().date()
    MAX_SLOTS = 4

    preferred_band = None
    personalization_note = None
    if client is not None:
        from apps.appointments.preferences import get_client_preferences

        profile = get_client_preferences(client)
        if profile["has_enough_data"]:
            preferred_band = profile["preferred_time_band"]
            if preferred_band:
                personalization_note = (
                    f"Este cliente suele preferir citas en la {preferred_band}"
                )

    if when == 'hoy':
        raw_slots = _slots_for_date(barber, service, today, min_advance_hours=1)
        context = "hoy"
    elif when == 'manana':
        raw_slots = _slots_for_date(barber, service, today + timedelta(days=1))
        context = "mañana"
    elif when == 'fin_de_semana':
        raw_slots = []
        days_found = 0
        for offset in range(0, 8):
            check_date = today + timedelta(days=offset)
            if check_date.weekday() in (5, 6):  # sábado, domingo
                raw_slots += _slots_for_date(
                    barber, service, check_date,
                    min_advance_hours=1 if check_date == today else 0,
                )
                days_found += 1
            if days_found >= 2:
                break
        context = "el próximo fin de semana"
    else:
        preferred_days = parse_day_preference(description or "")
        time_range = parse_time_preference(description or "")
        raw_slots = get_available_slots_for_barber(
            barber, service, preferred_days, time_range, limit=12
        )
        context = description or "el horario que prefieres"

    slots = _diversify_slots(raw_slots, MAX_SLOTS, preferred_band=preferred_band)

    message, tips = _describe_slots_with_ai(
        barber, service, slots, context, personalization_note=personalization_note
    )

    return {
        "barber": {
            "id": barber.id,
            "name": barber.get_full_name() or barber.username,
        },
        "service": {
            "id": service.id,
            "name": service.name,
            "price": str(service.price),
            "duration": service.duration,
        },
        "personalized": personalization_note is not None,
        "suggested_slots": slots,
        "available": len(slots) > 0,
        "message": message,
        "tips": tips,
    }