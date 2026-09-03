from django.db import transaction
from django.utils.crypto import get_random_string
from knox.auth import TokenAuthentication
from rest_framework import serializers
from rest_framework.generics import ListCreateAPIView
from rest_framework.validators import UniqueValidator

from apps.user.models import Collaborator, User
from utils.custom_permissions import IsAdmin

# Alfabeto sin caracteres ambiguos (0/O, 1/l/I): la contraseña inicial se dicta
# por teléfono o se copia a mano, y confundir un cero con una O cuesta un alta.
PASSWORD_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PASSWORD_LENGTH = 12


def generate_initial_password():
    return get_random_string(PASSWORD_LENGTH, PASSWORD_ALPHABET)


class CollaboratorListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email")
    full_name = serializers.CharField(source="user.full_name")

    class Meta:
        model = Collaborator
        fields = ["id", "email", "full_name"]


class CollaboratorCreateSerializer(serializers.ModelSerializer):
    # Los datos del alta viven en el User; el perfil Collaborator solo aporta el
    # id y la organización, así que los campos se mapean con source="user.*".
    email = serializers.EmailField(
        source="user.email",
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="Ya existe un usuario registrado con este correo.",
            )
        ],
    )
    first_name = serializers.CharField(source="user.first_name", max_length=150)
    last_name = serializers.CharField(
        source="user.last_name",
        max_length=150,
        required=False,
        allow_blank=True,
        default="",
    )
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    # RN-8: se entrega una única vez, en esta respuesta. No se persiste en claro
    # ni aparece en el listado, que usa el serializer de lectura.
    initial_password = serializers.CharField(read_only=True)

    class Meta:
        model = Collaborator
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "initial_password",
        ]

    def create(self, validated_data):
        user_data = validated_data.pop("user")
        password = generate_initial_password()

        # RN-9: el User y su perfil nacen juntos o no nacen. Sin la transacción,
        # un fallo al crear el perfil dejaría un usuario sin rol, capaz de
        # iniciar sesión y no ser ni admin ni colaborador.
        with transaction.atomic():
            user = User.objects.create_user(password=password, **user_data)
            collaborator = Collaborator.objects.create(user=user, **validated_data)

        collaborator.initial_password = password
        return collaborator


class CollaboratorListCreateView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CollaboratorCreateSerializer
        return CollaboratorListSerializer

    def get_organization(self):
        return self.request.user.admin_profile.organization

    def get_queryset(self):
        return Collaborator.objects.filter(
            organization=self.get_organization(),
            show=True,
        ).select_related("user")

    def perform_create(self, serializer):
        # RN-6: la organización se deriva del admin autenticado. El serializer no
        # declara el campo, así que un organization del body ya viene descartado.
        serializer.save(organization=self.get_organization())
