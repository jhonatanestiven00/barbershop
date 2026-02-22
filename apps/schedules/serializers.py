from rest_framework import serializers
from apps.schedules.models import Schedule


class ScheduleSerializer(serializers.ModelSerializer):
    barber_name = serializers.CharField(source='barber.get_full_name', read_only=True)
    day_display = serializers.CharField(source='get_day_display', read_only=True)

    class Meta:
        model = Schedule
        fields = '__all__'
        read_only_fields = ['id']