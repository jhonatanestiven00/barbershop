from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.schedules import views

router = DefaultRouter()
router.register('', views.ScheduleViewSet, basename='schedule')

urlpatterns = [
    path('', include(router.urls)),
]