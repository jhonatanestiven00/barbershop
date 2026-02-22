from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from apps.accounts.models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.CLIENT)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'first_name', 'last_name',
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

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'phone', 'image_url', 'role', 'role_display'
        ]
        read_only_fields = ['id']