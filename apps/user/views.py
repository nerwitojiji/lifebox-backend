from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from knox.models import AuthToken
from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.user.models import User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    organization_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "organization_id",
            # SPEC-009 RN-10: viaja en login, me y verify-token. El front no lo
            # infiere de ningún otro dato.
            "must_change_password",
        ]

    def get_full_name(self, obj):
        return obj.full_name

    def get_role(self, obj):
        if hasattr(obj, "admin_profile"):
            return "admin"
        if hasattr(obj, "collaborator_profile"):
            return "collaborator"
        return None

    def get_organization_id(self, obj):
        if hasattr(obj, "admin_profile"):
            return obj.admin_profile.organization_id
        if hasattr(obj, "collaborator_profile"):
            return obj.collaborator_profile.organization_id
        return None


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"text": "Credenciales inválidas"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # SPEC-007 RN-24: el rol se deriva de la existencia del perfil, así que
        # sin perfil no hay rol y el front queda rebotando entre /admin y
        # /colaborador. Se le dice, en vez de mentirle con «credenciales
        # inválidas»: la contraseña ya la acertó, es su cuenta.
        if not hasattr(user, "admin_profile") and not hasattr(
            user, "collaborator_profile"
        ):
            return Response(
                {"text": "Tu cuenta no tiene un perfil asociado. Contacta al administrador."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _, token = AuthToken.objects.create(user)
        return Response(
            {
                "token": token,
                "user": UserSerializer(user).data,
            }
        )


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, valor):
        # RN-3: exigirla aunque haya token es lo que impide que un token
        # olvidado en un equipo prestado se apropie de la cuenta.
        if not self.context["request"].user.check_password(valor):
            raise serializers.ValidationError("La contraseña actual no es correcta.")
        return valor

    def validate_new_password(self, valor):
        # RN-4: la fuerza la deciden los AUTH_PASSWORD_VALIDATORS que ya
        # gobiernan la contraseña temporal. No se reescribe la regla acá.
        validate_password(valor, user=self.context["request"].user)
        return valor

    def validate(self, attrs):
        if attrs["current_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": ["La contraseña nueva debe ser distinta de la actual."]}
            )
        return attrs


class ChangePasswordView(GenericAPIView):
    """SPEC-009: cualquier usuario autenticado cambia la suya, admin incluido."""

    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        with transaction.atomic():
            user.set_password(serializer.validated_data["new_password"])
            # RN-9: ya eligió la suya, no hay nada que recordarle.
            user.must_change_password = False
            user.save(update_fields=["password", "must_change_password", "updated_at"])

            # RN-7: la contraseña temporal la conocía el administrador. Si abrió
            # sesión con ella, esa sesión muere acá. El token de esta petición se
            # conserva para no expulsar a quien acaba de hacer lo correcto.
            AuthToken.objects.filter(user=user).exclude(pk=request.auth.pk).delete()

        return Response({"detail": "Tu contraseña fue actualizada."})


class VerifyTokenView(APIView):
    def post(self, request):
        return Response({"user": UserSerializer(request.user).data})


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)
