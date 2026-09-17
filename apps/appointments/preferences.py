"""
Módulo de perfiles personalizados (Objetivo específico 2: "...que permita la
integración de módulos para agendamiento, recordatorios automáticos y
perfiles personalizados gestionados con IA").

Principio de diseño (mismo que el resto de apps/appointments/ai.py): el
perfil se infiere con cálculo determinista sobre datos reales del cliente
(sin encuestas ni intervención del usuario); la IA nunca inventa el perfil,
solo se le puede dar como contexto para que redacte un mensaje natural.

Fundamento académico:
- Adomavicius, G., & Tuzhilin, A. (2005). Toward the next generation of
  recommender systems: A survey of the state-of-the-art and possible
  extensions. IEEE Transactions on Knowledge and Data Engineering, 17(6),
  734-749. Distingue perfiles EXPLÍCITOS (cuestionarios) de perfiles
  IMPLÍCITOS, aprendidos del comportamiento transaccional del usuario.
  Este módulo implementa un perfil implícito.
- Hu, Y., Koren, Y., & Volinsky, C. (2008). Collaborative filtering for
  implicit feedback datasets. Proceedings of the 8th IEEE International
  Conference on Data Mining, 263-272. Formaliza el uso de señales de
  comportamiento pasivo (aquí: historial real de citas) para modelar
  preferencias, en vez de pedirle al usuario que las declare.
- Tintarev, N., & Masthoff, J. (2015). Explaining recommendations: Design
  and evaluation. En Recommender Systems Handbook (pp. 353-382). Springer.
  Sustenta por qué el perfil inferido se le explica al cliente en lenguaje
  simple en vez de aplicarse "a ciegas": la transparencia aumenta la
  confianza y la satisfacción del usuario con el sistema.
"""

from django.utils import timezone
from django.db.models import Count
from apps.appointments.models import Appointment

# Con menos citas que este umbral no hay suficiente señal de
# comportamiento para inferir un patrón real (evita "perfiles" con una
# sola cita, que serían ruido, no una preferencia).
MIN_APPOINTMENTS_FOR_PROFILE = 2

TIME_BANDS = (
    ("mañana", 6, 12),
    ("tarde", 12, 18),
    ("noche", 18, 24),
)


def _time_band_label(hour: int) -> str:
    for label, start, end in TIME_BANDS:
        if start <= hour < end:
            return label
    return "mañana"


def get_client_preferences(client) -> dict:
    """
    Infiere el perfil de preferencias de un cliente a partir de su
    historial real de citas. Solo se consideran citas 'scheduled' o
    'completed': las canceladas no reflejan una preferencia real del
    cliente (pudo cancelar por cualquier motivo ajeno a su gusto).
    """
    history = (
        Appointment.objects.filter(client=client, status__in=["scheduled", "completed"])
        .select_related("service", "barber")
    )

    total = history.count()
    if total < MIN_APPOINTMENTS_FOR_PROFILE:
        return {
            "has_enough_data": False,
            "total_appointments": total,
            "favorite_service": None,
            "favorite_barber": None,
            "preferred_time_band": None,
        }

    favorite_service_row = (
        history.values("service__id", "service__name")
        .annotate(total=Count("id"))
        .order_by("-total", "-service__id")
        .first()
    )
    favorite_barber_row = (
        history.values(
            "barber__id", "barber__first_name", "barber__last_name", "barber__username"
        )
        .annotate(total=Count("id"))
        .order_by("-total", "-barber__id")
        .first()
    )

    band_counts: dict[str, int] = {}
    for appt in history:
        band = _time_band_label(timezone.localtime(appt.start_datetime).hour)
        band_counts[band] = band_counts.get(band, 0) + 1
    preferred_band = max(band_counts, key=band_counts.get) if band_counts else None

    barber_name = None
    if favorite_barber_row:
        full_name = (
            f"{favorite_barber_row['barber__first_name']} "
            f"{favorite_barber_row['barber__last_name']}"
        ).strip()
        barber_name = full_name or favorite_barber_row["barber__username"]

    return {
        "has_enough_data": True,
        "total_appointments": total,
        "favorite_service": (
            {
                "id": favorite_service_row["service__id"],
                "name": favorite_service_row["service__name"],
            }
            if favorite_service_row
            else None
        ),
        "favorite_barber": (
            {"id": favorite_barber_row["barber__id"], "name": barber_name}
            if favorite_barber_row
            else None
        ),
        "preferred_time_band": preferred_band,
    }
