from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from knox.auth import TokenAuthentication
from rest_framework import serializers
from rest_framework.generics import GenericAPIView, ListAPIView, ListCreateAPIView
from rest_framework.response import Response
from rest_framework import status

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from apps.user.models import Collaborator
from utils.custom_permissions import IsAdmin


# SPEC-004 RN-5 y SPEC-005 RN-5: «inscrito vigente» = inscripción visible de un
# colaborador disponible, con el mismo criterio de disponibilidad que SPEC-003 RN-5
# usa para admitirlo. La definición vive acá una sola vez y la comparten el listado
# de cursos, el panel y la lista de inscritos: si el contador dice 3, la lista trae
# 3. Cambiar el criterio cambia los tres juntos.
INSCRITO_VIGENTE = {
    "show": True,
    "collaborator__show": True,
    "collaborator__user__show": True,
    "collaborator__user__is_active": True,
}


def vigente(prefix=""):
    """El criterio, con el prefijo de la relación desde donde se lo mire.

    Sin prefijo se filtra `CourseCollaborator` directo; con
    `course_collaborators__` se lo mira desde `Course`.
    """
    return Q(**{f"{prefix}{campo}": valor for campo, valor in INSCRITO_VIGENTE.items()})


def with_enrolled_count(queryset):
    """Anota `enrolled_count` con una sola agregación (SPEC-004 RN-6)."""
    return queryset.annotate(
        enrolled_count=Count(
            "course_collaborators", filter=vigente("course_collaborators__")
        )
    )


class CourseListSerializer(serializers.ModelSerializer):
    enrolled_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "full_name",
            "description",
            "duration_hours",
            "version",
            "is_active",
            "created_at",
            "enrolled_count",
        ]


class CourseCreateSerializer(serializers.ModelSerializer):
    # El modelo usa PositiveIntegerField, que acepta 0; el mínimo de 1 es la
    # validación añadida que pide RN-5.
    duration_hours = serializers.IntegerField(min_value=1, required=False)

    class Meta:
        model = Course
        fields = [
            "id",
            "full_name",
            "description",
            "duration_hours",
            "version",
            "is_active",
            "created_at",
        ]
        # is_active y created_at se exponen para cumplir el contrato de respuesta
        # (RN-9), pero no se aceptan como entrada: el curso nace activo (RN-8).
        read_only_fields = ["id", "is_active", "created_at"]


class CourseListCreateView(ListCreateAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CourseCreateSerializer
        return CourseListSerializer

    def get_organization(self):
        return self.request.user.admin_profile.organization

    def get_queryset(self):
        return with_enrolled_count(
            Course.objects.filter(
                organization=self.get_organization(),
                show=True,
            )
        ).order_by("-created_at")

    def perform_create(self, serializer):
        # RN-4: la organización se deriva del admin autenticado. El serializer no
        # declara el campo, así que un organization del body ya viene descartado.
        serializer.save(organization=self.get_organization())


class CourseEnrollmentSummarySerializer(serializers.ModelSerializer):
    enrolled_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = ["id", "full_name", "version", "is_active", "enrolled_count"]


class CourseEnrollmentsView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]
    serializer_class = CourseEnrollmentSummarySerializer

    def get_queryset(self):
        # RN-2: el tenant sale del admin autenticado; los query params no entran.
        organization = self.request.user.admin_profile.organization
        return with_enrolled_count(
            Course.objects.filter(organization=organization, show=True)
            # RN-7: activos antes que inactivos y, dentro de cada grupo, por
            # cantidad de inscritos y nombre. La agrupación la hace el servidor
            # para que la lista plana sea legible aun sin separarla.
        ).order_by("-is_active", "-enrolled_count", "full_name")


class AssignedCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "full_name", "version"]


class AssignedCollaboratorSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name")
    email = serializers.EmailField(source="user.email")

    class Meta:
        model = Collaborator
        fields = ["id", "full_name", "email"]


class CourseAssignmentSerializer(serializers.ModelSerializer):
    course = AssignedCourseSerializer(read_only=True)
    collaborator = AssignedCollaboratorSerializer(read_only=True)

    class Meta:
        model = CourseCollaborator
        fields = ["id", "assigned_at", "course", "collaborator"]


class CourseAssignInputSerializer(serializers.Serializer):
    collaborator_id = serializers.IntegerField()


class CourseAssignView(GenericAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]
    serializer_class = CourseAssignInputSerializer

    duplicate_error = "Este colaborador ya está inscrito en el curso."

    def get_organization(self):
        return self.request.user.admin_profile.organization

    def get_course(self):
        return get_object_or_404(
            Course.objects.filter(
                organization=self.get_organization(),
                show=True,
                is_active=True,
            ),
            pk=self.kwargs["pk"],
        )

    def get_collaborator(self, collaborator_id):
        return get_object_or_404(
            Collaborator.objects.select_related("user").filter(
                organization=self.get_organization(),
                show=True,
                user__show=True,
                user__is_active=True,
            ),
            pk=collaborator_id,
        )

    def post(self, request, *args, **kwargs):
        course = self.get_course()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        collaborator = self.get_collaborator(
            input_serializer.validated_data["collaborator_id"]
        )

        if CourseCollaborator.objects.filter(
            course=course,
            collaborator=collaborator,
        ).exists():
            raise serializers.ValidationError(
                {"collaborator_id": [self.duplicate_error]}
            )

        try:
            with transaction.atomic():
                assignment = CourseCollaborator.objects.create(
                    course=course,
                    collaborator=collaborator,
                )
        except IntegrityError:
            # La validación previa entrega el error habitual; la restricción única
            # sigue siendo la última defensa ante dos peticiones concurrentes.
            raise serializers.ValidationError(
                {"collaborator_id": [self.duplicate_error]}
            )

        output = CourseAssignmentSerializer(assignment)
        return Response(output.data, status=status.HTTP_201_CREATED)


class CourseEnrolleeSerializer(serializers.ModelSerializer):
    collaborator = AssignedCollaboratorSerializer(read_only=True)

    class Meta:
        model = CourseCollaborator
        fields = ["id", "assigned_at", "collaborator"]


class CourseCollaboratorsView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]
    serializer_class = CourseEnrolleeSerializer

    def get_course(self):
        # RN-3 y RN-4: el curso debe ser del tenant y visible, pero `is_active`
        # NO se exige, a diferencia de CourseAssignView. La divergencia es
        # deliberada: allí se crea un vínculo nuevo —y un curso retirado no admite
        # inscripciones—, mientras que acá solo se leen los que ya existen, y un
        # curso retirado conserva a su gente. No igualar las dos condiciones.
        return get_object_or_404(
            Course.objects.filter(
                organization=self.request.user.admin_profile.organization,
                show=True,
            ),
            pk=self.kwargs["pk"],
        )

    def get_queryset(self):
        return (
            CourseCollaborator.objects.filter(vigente(), course=self.get_course())
            .select_related("collaborator__user")
            .order_by("-assigned_at", "collaborator__user__first_name")
        )
