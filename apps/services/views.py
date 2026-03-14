from rest_framework import viewsets, permissions, views, response, status
from apps.services.models import Category, Service
from apps.services.serializers import CategorySerializer, ServiceSerializer
from apps.services.ai import get_service_recommendation
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]


class ServiceViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceSerializer

    def get_queryset(self):
        queryset = Service.objects.filter(is_active=True).select_related('category')
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category__id=category)
        return queryset

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAdminUser()]


class ServiceRecommendationView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary='Recomendar servicio con IA',
        request=inline_serializer(
            name='ServiceRecommendationRequest',
            fields={'description': drf_serializers.CharField()}
        ),
        responses={200: inline_serializer(
            name='ServiceRecommendationResponse',
            fields={
                'service_name': drf_serializers.CharField(),
                'reason': drf_serializers.CharField(),
                'tips': drf_serializers.CharField(),
                'service_id': drf_serializers.IntegerField(),
                'price': drf_serializers.CharField(),
                'duration': drf_serializers.IntegerField(),
                'category': drf_serializers.CharField(),
            }
        )}
    )
    def post(self, request):
        description = request.data.get('description')

        if not description:
            return response.Response(
                {'error': 'El campo description es requerido.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if len(description) < 5:
            return response.Response(
                {'error': 'La descripción es muy corta, sé más específico.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            recommendation = get_service_recommendation(description)
            return response.Response(recommendation)
        except Exception as e:
            return response.Response(
                {'error': 'No se pudo generar la recomendación. Intenta de nuevo.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )