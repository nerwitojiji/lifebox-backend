from django.db.models import Q
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
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def generate_temporary_password(user=None):
    while True:
        password = get_random_string(PASSWORD_LENGTH, PASSWORD_ALPHABET)
        if user is None or not user.check_password(password):
            return password


def _positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 1 else default


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
            # SPEC-009 RN-9: la contraseña la eligió el servidor y la vio el
            # administrador; hasta que la persona ponga la suya, la cuenta la
            # conocen dos.
            user = User.objects.create_user(
                password=password, must_change_password=True, **user_data
            )
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
        queryset = Collaborator.objects.filter(
            organization=self.get_organization(),
            show=True,
        ).select_related("user").order_by(
            "user__first_name",
            "user__last_name",
            "id",
        )

        q = (self.request.query_params.get("q") or "").strip()
        if q:
            queryset = queryset.filter(
                Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
                | Q(user__email__icontains=q)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        total_items = queryset.count()
        page = _positive_int(request.query_params.get("page"), 1)
        page_size = min(
            _positive_int(request.query_params.get("page_size"), DEFAULT_PAGE_SIZE),
            MAX_PAGE_SIZE,
        )
        total_pages = (total_items + page_size - 1) // page_size if total_items else 0
        offset = (page - 1) * page_size
        page_qs = queryset[offset : offset + page_size]
        serializer = self.get_serializer(page_qs, many=True)
        return Response(
            {
                "items": serializer.data,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_previous": page > 1 and total_pages > 0,
                },
            }
        )

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
        # SPEC-009 RN-9: vuelve a haber una temporal en circulación, así que el
        # aviso se enciende otra vez. Sin esto se apagaría para siempre después
        # del primer cambio.
        collaborator.user.must_change_password = True
        collaborator.user.save(
            update_fields=["password", "must_change_password", "updated_at"]
        )
        return Response(
            {"temporary_password": password},
            status=status.HTTP_200_OK,
        )
