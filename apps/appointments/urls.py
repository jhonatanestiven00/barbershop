from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.appointments import views

router = DefaultRouter()
router.register('', views.AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('availability/', views.AvailabilityView.as_view(), name='availability'),
    path('availability/month/', views.MonthAvailabilityView.as_view(), name='availability-month'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('smart-recommendation/', views.SmartAppointmentView.as_view(), name='smart-recommendation'),
    path('suggest-slots/', views.SuggestSlotsView.as_view(), name='suggest-slots'),
    path('preferences/', views.ClientPreferencesView.as_view(), name='client-preferences'),
    path('<int:pk>/status/', views.AppointmentStatusView.as_view(), name='appointment-status'),
    path('', include(router.urls)),
]