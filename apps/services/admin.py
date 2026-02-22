from django.contrib import admin
from apps.services.models import Category, Service


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_editable = ['is_active']
    search_fields = ['name']


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 1


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'duration', 'price', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']
    list_editable = ['is_active', 'price']
    fields = ['category', 'name', 'description', 'duration', 'price', 'image_url', 'is_active']