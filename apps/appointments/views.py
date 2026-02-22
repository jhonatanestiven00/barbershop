from rest_framework import viewsets, permissions, views, response, status
from apps.appointments.models import Appointment
from apps.appointments.serializers import AppointmentSerializer
from apps.accounts.permissions import IsAdminOrBarber, IsClient, IsOwnerOrAdmin
from apps.accounts.models import User
from apps.services.models import Service
from apps.appointments.utils import get_available_slots
from datetime import datetime
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from apps.appointments.dashboard import get_dashboard_data
from apps.accounts.permissions import IsAdminOrBarber, IsClient, IsOwnerOrAdmin, IsAdmin



@extend_schema_view(
    list=extend_schema(summary='Listar citas'),
    retrieve=extend_schema(summary='Ver cita'),
    create=extend_schema(summary='Crear cita'),
    update=extend_schema(summary='Actualizar cita'),
    destroy=extend_schema(summary='Cancelar cita'),
)
class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Appointment.objects.select_related('client', 'barber', 'service').all()
        elif user.is_barber:
            return Appointment.objects.select_related('client', 'barber', 'service').filter(barber=user)
        return Appointment.objects.select_related('client', 'barber', 'service').filter(client=user)

    def get_permissions(self):
        if self.action == 'create':
            return [IsClient()]
        elif self.action in ['update', 'partial_update']:
            return [IsAdminOrBarber()]
        elif self.action == 'destroy':
            return [IsOwnerOrAdmin()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)


class AvailabilityView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary='Consultar disponibilidad',
        parameters=[
            OpenApiParameter('barber_id', int, description='ID del barbero'),
            OpenApiParameter('service_id', int, description='ID del servicio'),
            OpenApiParameter('date', str, description='Fecha en formato YYYY-MM-DD'),
        ]
    )
    def get(self, request):
        barber_id = request.query_params.get('barber_id')
        service_id = request.query_params.get('service_id')
        date_str = request.query_params.get('date')

        if not all([barber_id, service_id, date_str]):
            return response.Response(
                {'error': 'barber_id, service_id y date son requeridos.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            barber = User.objects.get(id=barber_id, role='barber')
            service = Service.objects.get(id=service_id, is_active=True)
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except User.DoesNotExist:
            return response.Response({'error': 'Barbero no encontrado.'}, status=404)
        except Service.DoesNotExist:
            return response.Response({'error': 'Servicio no encontrado.'}, status=404)
        except ValueError:
            return response.Response({'error': 'Formato de fecha inválido. Use YYYY-MM-DD.'}, status=400)

        slots = get_available_slots(barber, date, service)

        return response.Response({
            'barber': barber.get_full_name(),
            'service': service.name,
            'date': date_str,
            'available_slots': slots
        })


class AppointmentStatusView(views.APIView):
    permission_classes = [IsAdminOrBarber]

    @extend_schema(summary='Cambiar estado de una cita')
    def patch(self, request, pk):
        try:
            appointment = Appointment.objects.get(pk=pk)
        except Appointment.DoesNotExist:
            return response.Response({'error': 'Cita no encontrada.'}, status=404)

        new_status = request.data.get('status')
        valid_statuses = ['pending', 'confirmed', 'cancelled', 'completed']

        if new_status not in valid_statuses:
            return response.Response(
                {'error': f'Estado inválido. Opciones: {valid_statuses}'},
                status=400
            )

        # Barbero solo puede cambiar sus propias citas
        if request.user.is_barber and appointment.barber != request.user:
            return response.Response(
                {'error': 'No puedes modificar citas de otro barbero.'},
                status=403
            )

        appointment.status = new_status
        appointment.save()

        return response.Response({
            'message': f'Estado actualizado a {new_status}',
            'appointment_id': appointment.id,
            'status': appointment.status
        })

class DashboardView(views.APIView):
    permission_classes = [IsAdmin]

    @extend_schema(summary='Dashboard administrativo')
    def get(self, request):
        data = get_dashboard_data()
        return response.Response(data)