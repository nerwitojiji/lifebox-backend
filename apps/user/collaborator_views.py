from django.db import transaction
from django.utils.crypto import get_random_string
from knox.auth import TokenAuthentication
from rest_framework import serializers, status
from rest_framework.generics import (
    DestroyAPIView,
    GenericAPIView,
    ListCreateAPIView,
)
from rest_framework.response import Response
from rest_framework.validators import UniqueValidator

from apps.user.models import Collaborator, User
from utils.custom_permissions import IsAdmin


PASSWORD_ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
PASSWORD_LENGTH = 12


def generate_temporary_password(user=None):
    while True:
        password = get_random_string(PASSWORD_LENGTH, PASSWORD_ALPHABET)
        if user is None or not user.check_password(password):
            return password


class CollaboratorListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email")
    full_name = serializers.CharField(source="user.full_name")

    class Meta:
        model = Collaborator
        fields = ["id", "email", "full_name"]


class CollaboratorCreateSerializer(serializers.ModelSerializer):
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
    temporary_password = serializers.CharField(read_only=True)

    class Meta:
        model = Collaborator
        fields = [
            "id",
            "email",
            "full_name",
            "first_name",
            "last_name",
            "temporary_password",
        ]

    def create(self, validated_data):
        user_data = validated_data.pop("user")
        password = generate_temporary_password()

        with transaction.atomic():
            user = User.objects.create_user(password=password, **user_data)
            collaborator = Collaborator.objects.create(user=user, **validated_data)

        collaborator.temporary_password = password
        return collaborator


class CollaboratorListView(ListCreateAPIView):
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
        serializer.save(organization=self.get_organization())


class CollaboratorDeactivateView(DestroyAPIView):
    """SPEC-007 RN-20 a RN-23: dar de baja a un colaborador."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]

    def get_queryset(self):
        # El tenant sale del admin autenticado; un colaborador de otra
        # organización o ya dado de baja es indistinguible de uno inexistente.
        organization = self.request.user.admin_profile.organization
        return Collaborator.objects.filter(
            organization=organization,
            show=True,
        ).select_related("user")

    def perform_destroy(self, collaborator):
        # RN-21: las dos escrituras van juntas. Sin desactivar el usuario, la
        # baja sería cosmética: seguiría iniciando sesión y viendo sus cursos.
        # RN-22: las inscripciones no se tocan; dejan de contar por el criterio
        # de «inscrito vigente», que ya exige el colaborador disponible.
        with transaction.atomic():
            collaborator.show = False
            collaborator.save(update_fields=["show", "updated_at"])
            collaborator.user.is_active = False
            collaborator.user.save(update_fields=["is_active", "updated_at"])


class CollaboratorResetPasswordView(GenericAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]

    def get_queryset(self):
        organization = self.request.user.admin_profile.organization
        return Collaborator.objects.filter(
            organization=organization,
            show=True,
        ).select_related("user")

    def post(self, request, *args, **kwargs):
        collaborator = self.get_object()
        password = generate_temporary_password(user=collaborator.user)
        collaborator.user.set_password(password)
        collaborator.user.save(update_fields=["password"])
        return Response(
            {"temporary_password": password},
            status=status.HTTP_200_OK,
        )
