from django.contrib import admin
from apps.appointments.models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['client', 'barber', 'service', 'start_datetime', 'status']
    list_filter = ['status', 'barber']
    search_fields = ['client__username', 'barber__username']
    readonly_fields = ['end_datetime', 'created_at', 'updated_at']
    date_hierarchy = 'start_datetime'