from rest_framework import viewsets, permissions
from apps.schedules.models import Schedule
from apps.schedules.serializers import ScheduleSerializer
from apps.accounts.permissions import IsAdmin, IsAdminOrBarber
from drf_spectacular.utils import extend_schema_view, extend_schema


@extend_schema_view(
    list=extend_schema(summary='Listar horarios'),
    retrieve=extend_schema(summary='Ver horario'),
    create=extend_schema(summary='Crear horario'),
    update=extend_schema(summary='Actualizar horario'),
    destroy=extend_schema(summary='Eliminar horario'),
)
class ScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = ScheduleSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_barber:
            return Schedule.objects.filter(barber=user)
        return Schedule.objects.filter(is_active=True)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        elif self.action in ['update', 'partial_update']:
            return [IsAdminOrBarber()]
        return [IsAdmin()]