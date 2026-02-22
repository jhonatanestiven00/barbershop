# Barbershop API

API REST para gestión de citas en barberías, desarrollada con Django REST Framework.

## Stack tecnológico

- Python 3.12
- Django 6.0
- Django REST Framework
- PostgreSQL
- JWT Authentication
- Docker

## Requisitos

- Docker y Docker Compose
- Python 3.12 (para desarrollo local)

## Instalación con Docker

1. Clona el repositorio:
\```bash
git clone <url-del-repo>
cd barbershop
\```

2. Crea el archivo `.env` basado en `.env.example`:
\```bash
cp .env.example .env
\```

3. Levanta los contenedores:
\```bash
docker-compose up --build
\```

4. La API estará disponible en `http://localhost:8000`

## Instalación local

1. Crea el entorno virtual:
\```bash
python -m venv venv
venv\Scripts\activate
\```

2. Instala dependencias:
\```bash
pip install -r requirements/base.txt
\```

3. Configura el `.env` con tus credenciales de PostgreSQL

4. Corre las migraciones:
\```bash
python manage.py migrate
\```

5. Crea el superusuario:
\```bash
python manage.py createsuperuser
\```

6. Inicia el servidor:
\```bash
python manage.py runserver
\```

## Documentación

- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- Admin: `http://localhost:8000/admin/`

## Endpoints principales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/accounts/register/` | Registro de usuario |
| POST | `/api/accounts/login/` | Login y obtención de token |
| GET | `/api/accounts/profile/` | Perfil del usuario autenticado |
| GET | `/api/accounts/barbers/` | Lista de barberos |
| GET | `/api/services/categories/` | Categorías con servicios |
| GET | `/api/services/` | Lista de servicios |
| GET | `/api/schedules/` | Horarios de barberos |
| GET | `/api/appointments/availability/` | Disponibilidad en tiempo real |
| POST | `/api/appointments/` | Crear cita |
| PATCH | `/api/appointments/{id}/status/` | Cambiar estado de cita |
| GET | `/api/appointments/dashboard/` | Dashboard administrativo |

## Roles del sistema

| Rol | Permisos |
|-----|----------|
| Superusuario | Acceso total |
| Admin | Gestión completa excepto configuración del sistema |
| Barbero | Ver y gestionar sus propias citas |
| Cliente | Agendar y ver sus propias citas |

## Reglas de negocio

- No se pueden agendar citas en fechas pasadas
- Anticipación mínima de 2 horas para agendar
- Anticipación máxima de 30 días para agendar
- El barbero debe trabajar ese día y en ese horario
- Un cliente no puede tener más de 2 citas por día
- No se permiten conflictos de horario para barbero ni cliente
- El flujo de estados es controlado: pendiente → confirmada → completada/cancelada
- Solo se puede cancelar con al menos 2 horas de anticipación

## Tests

\```bash
pytest tests/ -v
\```

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| SECRET_KEY | Clave secreta de Django |
| DEBUG | Modo debug (True/False) |
| ALLOWED_HOSTS | Hosts permitidos |
| DATABASE_URL | URL de conexión a PostgreSQL |