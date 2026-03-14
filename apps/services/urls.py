from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.services import views

router = DefaultRouter()
router.register('categories', views.CategoryViewSet, basename='category')
router.register('', views.ServiceViewSet, basename='service')

urlpatterns = [
    path('recommend/', views.ServiceRecommendationView.as_view(), name='service-recommend'),
    path('', include(router.urls)),
]