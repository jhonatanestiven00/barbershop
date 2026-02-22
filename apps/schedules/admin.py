from django.contrib import admin
from apps.schedules.models import Schedule


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ['barber', 'get_day_display', 'start_time', 'end_time', 'is_active']
    list_filter = ['day', 'is_active']
    search_fields = ['barber__username', 'barber__first_name']