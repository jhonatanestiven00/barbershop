from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from apps.appointments.models import Appointment
from apps.schedules.models import Schedule


class AppointmentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.get_full_name', read_only=True)
    barber_name = serializers.CharField(source='barber.get_full_name', read_only=True)
    service_name = serializers.CharField(source='service.name', read_only=True)

    class Meta:
        model = Appointment
        fields = '__all__'
        read_only_fields = ['id', 'client', 'created_at', 'updated_at', 'end_datetime']

    def validate(self, attrs):
        start = attrs.get('start_datetime')
        service = attrs.get('service')
        barber = attrs.get('barber')
        client = self.context['request'].user
        now = timezone.now()

        # Regla 1: No agendar en fechas pasadas
        if start and start < now:
            raise serializers.ValidationError(
                {'start_datetime': 'No puedes agendar una cita en una fecha u hora pasada.'}
            )

        # Regla 2: Anticipación mínima de 2 horas
        if start and start < now + timedelta(hours=2):
            raise serializers.ValidationError(
                {'start_datetime': 'Debes agendar con al menos 2 horas de anticipación.'}
            )

        # Regla 3: Anticipación máxima de 30 días
        if start and start > now + timedelta(days=30):
            raise serializers.ValidationError(
                {'start_datetime': 'No puedes agendar con más de 30 días de anticipación.'}
            )

        if start and barber and service:
            end = start + timedelta(minutes=service.duration)
            day_of_week = start.weekday()

            # Regla 4: Barbero trabaja ese día
            try:
                schedule = Schedule.objects.get(
                    barber=barber,
                    day=day_of_week,
                    is_active=True
                )
            except Schedule.DoesNotExist:
                raise serializers.ValidationError(
                    {'start_datetime': 'El barbero no trabaja ese día.'}
                )

            # Regla 5: Cita dentro del horario del barbero
            if start.time() < schedule.start_time or end.time() > schedule.end_time:
                raise serializers.ValidationError(
                    {'start_datetime': f'La cita debe estar dentro del horario del barbero '
                                      f'({schedule.start_time.strftime("%H:%M")} - '
                                      f'{schedule.end_time.strftime("%H:%M")}).'}
                )

            attrs['end_datetime'] = end

            # Regla 6: Límite de 2 citas por día por cliente
            client_daily = Appointment.objects.filter(
                client=client,
                status__in=['pending', 'confirmed'],
                start_datetime__date=start.date()
            )
            if self.instance:
                client_daily = client_daily.exclude(pk=self.instance.pk)
            if client_daily.count() >= 2:
                raise serializers.ValidationError(
                    {'start_datetime': 'No puedes tener más de 2 citas en el mismo día.'}
                )

            # Regla 7: Barbero sin conflicto de horario
            barber_conflict = Appointment.objects.filter(
                barber=barber,
                status__in=['pending', 'confirmed'],
                start_datetime__lt=end,
                end_datetime__gt=start
            )
            if self.instance:
                barber_conflict = barber_conflict.exclude(pk=self.instance.pk)
            if barber_conflict.exists():
                raise serializers.ValidationError(
                    {'start_datetime': 'El barbero ya tiene una cita en ese horario.'}
                )

            # Regla 8: Cliente sin conflicto de horario
            client_conflict = Appointment.objects.filter(
                client=client,
                status__in=['pending', 'confirmed'],
                start_datetime__lt=end,
                end_datetime__gt=start
            )
            if self.instance:
                client_conflict = client_conflict.exclude(pk=self.instance.pk)
            if client_conflict.exists():
                raise serializers.ValidationError(
                    {'start_datetime': 'Ya tienes una cita agendada en ese horario.'}
                )

        return attrs