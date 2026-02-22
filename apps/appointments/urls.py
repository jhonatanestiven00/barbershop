from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.appointments import views

router = DefaultRouter()
router.register('', views.AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('availability/', views.AvailabilityView.as_view(), name='availability'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('<int:pk>/status/', views.AppointmentStatusView.as_view(), name='appointment-status'),
    path('', include(router.urls)),
]