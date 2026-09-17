import re

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=True, allow_blank=False)
    last_name = serializers.CharField(required=False, allow_blank=True, default='')
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all(), message='Este correo ya está registrado.')],
    )
    phone = serializers.CharField(
        required=True,
        allow_blank=False,
        validators=[UniqueValidator(queryset=User.objects.all(), message='Este teléfono ya está registrado.')],
    )
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.CLIENT)

    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name',
            'phone', 'image_url', 'password', 'password2', 'role'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Las contraseñas no coinciden.'})

        # Solo superusuario puede crear admins o superusuarios
        request = self.context.get('request')
        restricted_roles = [User.Role.ADMIN, User.Role.SUPERUSER]
        if attrs.get('role') in restricted_roles:
            if not request or not request.user.is_authenticated or not request.user.is_superuser_role:
                raise serializers.ValidationError(
                    {'role': 'No tienes permiso para asignar este rol.'}
                )
        return attrs

    @staticmethod
    def _generate_username(email):
        # El modelo sigue necesitando un username único internamente
        # (lo exige AbstractUser), pero ya no se lo pedimos al cliente:
        # se genera solo a partir del correo.
        base = re.sub(r'[^a-zA-Z0-9_.]', '', email.split('@')[0])[:25] or 'user'
        username = base
        counter = 1
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base}{counter}"
            counter += 1
        return username

    def create(self, validated_data):
        validated_data.pop('password2')
        validated_data['username'] = self._generate_username(validated_data['email'])
        user = User.objects.create_user(**validated_data)
        return user


class EmailOrPhoneTokenObtainPairSerializer(serializers.Serializer):
    """
    Login con correo o teléfono (cualquiera de los dos) + contraseña,
    en vez del username tradicional.
    """
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get('identifier', '').strip()
        password = attrs.get('password')

        user = User.objects.filter(
            Q(email__iexact=identifier) | Q(phone=identifier)
        ).first()

        if user is None or not user.check_password(password):
            raise serializers.ValidationError(
                {'detail': 'Correo/teléfono o contraseña incorrectos.'}
            )

        if not user.is_active:
            raise serializers.ValidationError({'detail': 'Esta cuenta está inactiva.'})

        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone', 'image_url', 'role', 'role_display'
        ]
        read_only_fields = ['id']