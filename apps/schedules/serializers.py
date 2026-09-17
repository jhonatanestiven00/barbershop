from rest_framework import serializers
from apps.schedules.models import Schedule


class ScheduleSerializer(serializers.ModelSerializer):
    barber_name = serializers.CharField(source='barber.get_full_name', read_only=True)
    day_display = serializers.CharField(source='get_day_display', read_only=True)

    class Meta:
        model = Schedule
        fields = '__all__'
        # "barber" no se recibe del cliente: siempre se asigna desde el
        # usuario autenticado (ver ScheduleViewSet.perform_create), así
        # un barbero no puede editar el horario de otro.
        read_only_fields = ['id', 'barber']