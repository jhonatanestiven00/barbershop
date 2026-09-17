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
from apps.appointments.ai import (
    get_smart_appointment_recommendation,
    suggest_slots_for_selection,
    month_availability,
)
from apps.appointments.preferences import get_client_preferences
from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter, inline_serializer
from rest_framework import serializers as drf_serializers
from apps.services.models import Service
from apps.accounts.models import User



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


class MonthAvailabilityView(views.APIView):
    """
    Estado (disponible / ocupado / sin servicio) de cada día de un mes,
    para pintar el calendario de agendamiento con colores.
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary='Disponibilidad de un mes completo, día por día',
        parameters=[
            OpenApiParameter('barber_id', int, description='ID del barbero'),
            OpenApiParameter('service_id', int, description='ID del servicio'),
            OpenApiParameter('year', int, description='Año, ej. 2026'),
            OpenApiParameter('month', int, description='Mes (1-12)'),
        ]
    )
    def get(self, request):
        barber_id = request.query_params.get('barber_id')
        service_id = request.query_params.get('service_id')
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        if not all([barber_id, service_id, year, month]):
            return response.Response(
                {'error': 'barber_id, service_id, year y month son requeridos.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            barber = User.objects.get(id=barber_id, role='barber')
            service = Service.objects.get(id=service_id, is_active=True)
            year = int(year)
            month = int(month)
        except User.DoesNotExist:
            return response.Response({'error': 'Barbero no encontrado.'}, status=404)
        except Service.DoesNotExist:
            return response.Response({'error': 'Servicio no encontrado.'}, status=404)
        except ValueError:
            return response.Response({'error': 'year y month deben ser numéricos.'}, status=400)

        if not (1 <= month <= 12):
            return response.Response({'error': 'month debe estar entre 1 y 12.'}, status=400)

        days = month_availability(barber, service, year, month)
        return response.Response({'days': days})


class AppointmentStatusView(views.APIView):
    permission_classes = [IsAdminOrBarber]

    @extend_schema(summary='Cambiar estado de una cita')
    def patch(self, request, pk):
        try:
            appointment = Appointment.objects.get(pk=pk)
        except Appointment.DoesNotExist:
            return response.Response({'error': 'Cita no encontrada.'}, status=404)

        new_status = request.data.get('status')
        valid_statuses = ['scheduled', 'cancelled_client', 'cancelled_barber', 'completed']

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


class SmartAppointmentView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary='Recomendación inteligente de cita',
        request=inline_serializer(
            name='SmartAppointmentRequest',
            fields={'description': drf_serializers.CharField()}
        ),
        responses={200: inline_serializer(
            name='SmartAppointmentResponse',
            fields={
                'service': drf_serializers.DictField(),
                'barber': drf_serializers.DictField(),
                'suggested_slots': drf_serializers.ListField(),
                'available': drf_serializers.BooleanField(),
                'message': drf_serializers.CharField(),
                'reason': drf_serializers.CharField(),
                'tips': drf_serializers.CharField(),
            }
        )}
    )
    def post(self, request):
        description = request.data.get('description')

        if not description:
            return response.Response(
                {'error': 'El campo description es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(description) < 5:
            return response.Response(
                {'error': 'La descripción es muy corta, sé más específico.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            recommendation = get_smart_appointment_recommendation(description)

            # Si no hay disponibilidad devolvemos 200 pero con available=False
            # para que el frontend pueda manejarlo sin romper el flujo
            return response.Response(recommendation)

        except Service.DoesNotExist:
            return response.Response(
                {'error': 'No se encontró un servicio adecuado para tu descripción.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except User.DoesNotExist:
            return response.Response(
                {'error': 'No hay barberos disponibles en este momento.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return response.Response(
                {'error': 'No se pudo generar la recomendación. Intenta de nuevo.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SuggestSlotsView(views.APIView):
    """
    Sugiere horarios para un barbero y servicio que el cliente ya
    eligió en el flujo de agendamiento. La disponibilidad se calcula
    siempre de forma determinista; la IA solo redacta el mensaje.
    """
    permission_classes = [permissions.IsAuthenticated]

    VALID_WHEN = ['hoy', 'manana', 'fin_de_semana', 'custom']

    @extend_schema(
        summary='Sugerir horarios para un barbero y servicio ya elegidos',
        request=inline_serializer(
            name='SuggestSlotsRequest',
            fields={
                'barber_id': drf_serializers.IntegerField(),
                'service_id': drf_serializers.IntegerField(),
                'when': drf_serializers.ChoiceField(choices=VALID_WHEN),
                'description': drf_serializers.CharField(required=False),
            }
        ),
        responses={200: inline_serializer(
            name='SuggestSlotsResponse',
            fields={
                'barber': drf_serializers.DictField(),
                'service': drf_serializers.DictField(),
                'suggested_slots': drf_serializers.ListField(),
                'available': drf_serializers.BooleanField(),
                'message': drf_serializers.CharField(),
                'tips': drf_serializers.CharField(),
            }
        )}
    )
    def post(self, request):
        barber_id = request.data.get('barber_id')
        service_id = request.data.get('service_id')
        when = request.data.get('when')
        description = request.data.get('description')

        if not barber_id or not service_id:
            return response.Response(
                {'error': 'Selecciona primero un barbero y un servicio.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if when not in self.VALID_WHEN:
            return response.Response(
                {'error': f'when debe ser uno de: {self.VALID_WHEN}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if when == 'custom' and (not description or len(description) < 5):
            return response.Response(
                {'error': 'Cuéntanos un poco más sobre cuándo te gustaría tu cita.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            barber = User.objects.get(id=barber_id, role='barber')
            service = Service.objects.get(id=service_id, is_active=True)
        except User.DoesNotExist:
            return response.Response({'error': 'Barbero no encontrado.'}, status=404)
        except Service.DoesNotExist:
            return response.Response({'error': 'Servicio no encontrado.'}, status=404)

        try:
            result = suggest_slots_for_selection(
                barber, service, when, description, client=request.user
            )
            return response.Response(result)
        except Exception:
            return response.Response(
                {'error': 'No pudimos calcular horarios en este momento. Intenta de nuevo.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ClientPreferencesView(views.APIView):
    """
    Perfil de preferencias del cliente autenticado: servicio, barbero y
    franja horaria que más ha elegido en su historial real de citas.
    Ver apps/appointments/preferences.py para el fundamento y el cálculo
    (siempre determinista, nunca decidido por el modelo de IA).
    """
    permission_classes = [IsClient]

    @extend_schema(summary='Perfil de preferencias del cliente')
    def get(self, request):
        data = get_client_preferences(request.user)
        return response.Response(data)