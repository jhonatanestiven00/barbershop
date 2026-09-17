from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPERUSER = 'superuser', 'Superusuario'
        ADMIN = 'admin', 'Administrador'
        BARBER = 'barber', 'Barbero'
        CLIENT = 'client', 'Cliente'

    role = models.CharField(
        max_length=15,
        choices=Role.choices,
        default=Role.CLIENT
    )
    # Únicos porque el login se hace con cualquiera de los dos; null=True
    # (en vez de solo blank) para que Postgres no choque el UNIQUE
    # constraint entre varias filas con cadena vacía.
    email = models.EmailField(blank=True, null=True, unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True, unique=True)
    image_url = models.URLField(blank=True, help_text='Enlace de imagen de perfil')

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role in [self.Role.ADMIN, self.Role.SUPERUSER]

    @property
    def is_barber(self):
        return self.role == self.Role.BARBER

    @property
    def is_client(self):
        return self.role == self.Role.CLIENT

    @property
    def is_superuser_role(self):
        return self.role == self.Role.SUPERUSER