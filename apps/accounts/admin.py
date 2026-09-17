from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from apps.accounts.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # Lista y edición recortadas a lo que este proyecto usa de verdad:
    # el sistema de permisos (grupos/permisos de Django, superusuario)
    # no se usa aquí, la autorización se hace por el campo `role` propio
    # (ver apps/accounts/permissions.py), así que no aparece en el admin.
    list_display = ['email', 'phone', 'first_name', 'last_name', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    search_fields = ['username', 'email', 'phone', 'first_name', 'last_name']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información personal', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'image_url'),
        }),
        ('Rol y estado', {'fields': ('role', 'is_active', 'is_staff')}),
        ('Fechas importantes', {'fields': ('last_login', 'date_joined')}),
    )