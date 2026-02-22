from django.utils import timezone
from django.db.models import Count, Sum
from apps.appointments.models import Appointment
from apps.accounts.models import User


def get_dashboard_data():
    today = timezone.now().date()

    # Citas de hoy
    today_appointments = Appointment.objects.filter(
        start_datetime__date=today
    ).select_related('client', 'barber', 'service')

    # Resumen por estado
    status_summary = today_appointments.values('status').annotate(
        total=Count('id')
    )

    # Ingreso estimado del día (citas completadas)
    daily_revenue = today_appointments.filter(
        status='completed'
    ).aggregate(
        total=Sum('service__price')
    )['total'] or 0

    # Barbero más ocupado hoy
    busiest_barber = today_appointments.values(
        'barber__first_name', 'barber__last_name', 'barber__username'
    ).annotate(
        total=Count('id')
    ).order_by('-total').first()

    # Citas por estado general
    general_summary = Appointment.objects.values('status').annotate(
        total=Count('id')
    )

    # Total usuarios por rol
    users_by_role = User.objects.values('role').annotate(
        total=Count('id')
    )

    # Próximas citas del día
    upcoming = today_appointments.filter(
        status__in=['pending', 'confirmed'],
        start_datetime__gte=timezone.now()
    ).order_by('start_datetime')[:5]

    return {
        'date': str(today),
        'today': {
            'total_appointments': today_appointments.count(),
            'revenue': float(daily_revenue),
            'by_status': list(status_summary),
            'busiest_barber': busiest_barber,
            'upcoming_appointments': [
                {
                    'id': a.id,
                    'client': a.client.get_full_name() or a.client.username,
                    'barber': a.barber.get_full_name() or a.barber.username,
                    'service': a.service.name,
                    'start': a.start_datetime.strftime('%H:%M'),
                    'status': a.status,
                }
                for a in upcoming
            ]
        },
        'general': {
            'appointments_by_status': list(general_summary),
            'users_by_role': list(users_by_role),
            'total_appointments': Appointment.objects.count(),
        }
    }