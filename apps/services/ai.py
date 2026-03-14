from groq import Groq
from django.conf import settings
from apps.services.models import Service, Category


def get_service_recommendation(user_description: str) -> dict:
    """
    Recibe una descripción del cliente y recomienda
    el servicio más adecuado del catálogo.
    """
    # Obtener catálogo actual de servicios
    services = Service.objects.filter(is_active=True).select_related('category')
    
    catalog = []
    for service in services:
        catalog.append(
            f"- {service.name} (Categoría: {service.category.name}, "
            f"Duración: {service.duration} min, "
            f"Precio: ${service.price})"
        )
    
    catalog_text = "\n".join(catalog)

    prompt = f"""Eres un experto asesor de barbería. Tu tarea es recomendar el servicio 
más adecuado basándote en la descripción del cliente.

Catálogo de servicios disponibles:
{catalog_text}

Descripción del cliente: "{user_description}"

Responde SOLO en formato JSON con esta estructura exacta:
{{
    "service_name": "nombre exacto del servicio recomendado",
    "reason": "explicación breve de por qué este servicio es el más adecuado",
    "tips": "consejo adicional para el cliente"
}}

No agregues texto fuera del JSON."""

    client = Groq(api_key=settings.GROQ_API_KEY)
    
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=500
    )

    import json
    content = response.choices[0].message.content.strip()
    result = json.loads(content)

    # Buscar el servicio recomendado en la base de datos
    try:
        service = Service.objects.get(name=result['service_name'], is_active=True)
        result['service_id'] = service.id
        result['price'] = str(service.price)
        result['duration'] = service.duration
        result['category'] = service.category.name
    except Service.DoesNotExist:
        result['service_id'] = None

    return result