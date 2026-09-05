from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from knox.auth import TokenAuthentication
from rest_framework import serializers
from rest_framework import generics
from rest_framework.generics import (
    DestroyAPIView,
    GenericAPIView,
    ListAPIView,
    ListCreateAPIView,
)
from rest_framework.response import Response
from rest_framework import status

from apps.course.material_views import CourseWithMaterialsSerializer, with_materials
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


# SPEC-007 RN-5 y PA-15: el piso del nombre de curso se declara UNA vez y lo
# comparten la creación y la edición. Si se duplicara, `POST` y `PATCH`
# empezarían a aceptar cosas distintas a la primera corrección.
NOMBRE_MINIMO = 3


def validar_nombre_de_curso(valor):
    """Rechaza «.», «..», «---», «12» y «a».

    DRF recorta los espacios antes de validar (`trim_whitespace`), así que el
    mínimo se mide sobre el texto que se va a guardar.
    """
    if len(valor) < NOMBRE_MINIMO or not any(c.isalpha() for c in valor):
        raise serializers.ValidationError(
            "El nombre debe tener al menos 3 caracteres e incluir alguna letra."
        )


def validar_version(valor):
    """SPEC-007 RN-8: rechaza «.» y «--», admite «1.0», «2», «v3», «2026.1»."""
    if not any(c.isalnum() for c in valor):
        raise serializers.ValidationError(
            "La versión debe incluir al menos un número o una letra."
        )


def campo_nombre_de_curso(**kwargs):
    return serializers.CharField(
        max_length=255, validators=[validar_nombre_de_curso], **kwargs
    )


class CourseListSerializer(CourseWithMaterialsSerializer):
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
            "materials",
            "enrolled_count",
        ]


class CourseCreateSerializer(CourseWithMaterialsSerializer):
    # El modelo usa PositiveIntegerField, que acepta 0; el mínimo de 1 es la
    # validación añadida que pide RN-5.
    duration_hours = serializers.IntegerField(min_value=1, required=False)
    full_name = campo_nombre_de_curso()

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
            "materials",
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
        return with_materials(with_enrolled_count(
            Course.objects.filter(
                organization=self.get_organization(),
                show=True,
            )
        )).order_by("-created_at")

    def perform_create(self, serializer):
        # RN-4: la organización se deriva del admin autenticado. El serializer no
        # declara el campo, así que un organization del body ya viene descartado.
        serializer.save(organization=self.get_organization())


class CourseDetailSerializer(CourseWithMaterialsSerializer):
    """Nombre, descripción, duración y estado se corrigen en la ficha.
    SPEC-008 permite corregir la versión solo cuando no hay inscritos;
    los metadatos de SPEC-011 se gestionan mediante las rutas de material.
    """

    full_name = campo_nombre_de_curso(required=False)
    duration_hours = serializers.IntegerField(min_value=1, required=False)
    # SPEC-008 RN-1: editable, pero solo mientras nadie se haya inscrito. Ver
    # validate_version() para la condición.
    version = serializers.CharField(
        max_length=20, required=False, validators=[validar_version]
    )
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
            "materials",
            "enrolled_count",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_version(self, valor):
        """SPEC-008: corregir un tipeo no es lo mismo que publicar una versión.

        La distinción no es «editar vs. versionar», sino si alguien ya se
        inscribió: sin inscritos la versión es un dato del formulario; con
        inscritos es parte de lo que esas personas cursaron, y cambiarla
        reescribiría su historial.
        """
        curso = self.instance
        if curso is None or valor == curso.version:
            # RN-2: reenviar la misma versión no es un cambio y no puede fallar.
            return valor

        # RN-1: el conteo sale de la anotación que la vista ya trae; el criterio
        # de «inscrito vigente» es el mismo que informa el panel.
        inscritos = getattr(curso, "enrolled_count", 0)
        if inscritos:
            raise serializers.ValidationError(
                f"Este curso ya tiene {inscritos} "
                f"{'inscrito' if inscritos == 1 else 'inscritos'}, así que su "
                "versión no se puede corregir. Publica una versión nueva."
            )

        # RN-4: mismo criterio que al publicar una versión (SPEC-007 RN-10).
        ya_usada = (
            Course.objects.filter(
                organization=curso.organization,
                show=True,
                full_name=curso.full_name,
                version=valor,
            )
            .exclude(pk=curso.pk)
            .exists()
        )
        if ya_usada:
            raise serializers.ValidationError(
                "Ya existe una versión con ese número para este curso."
            )

        return valor


class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """SPEC-007 RN-1 a RN-7."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]
    serializer_class = CourseDetailSerializer
    # RN-1: el contrato son estos tres verbos. PUT obligaría a mandar el curso
    # entero para corregir un tipeo.
    http_method_names = ["get", "patch", "delete", "head", "options"]

    delete_error = (
        "No se puede eliminar un curso con inscritos. Da de baja el curso o "
        "desinscribe a sus colaboradores."
    )

    def get_queryset(self):
        # RN-2: el tenant sale del admin; un curso ajeno u oculto es
        # indistinguible de uno inexistente.
        return with_materials(with_enrolled_count(
            Course.objects.filter(
                organization=self.request.user.admin_profile.organization,
                show=True,
            )
        ))

    def perform_destroy(self, course):
        # RN-7: eliminar es para el curso creado por error. Con gente inscrita,
        # el borrado lógico del curso escondería el registro de quién lo cursó;
        # para eso está dar de baja (`is_active=False`), que lo conserva a la
        # vista. El conteo sale del mismo `enrolled_count` que informa el panel.
        if course.enrolled_count > 0:
            raise serializers.ValidationError({"detail": [self.delete_error]})

        course.show = False
        course.save(update_fields=["show", "updated_at"])


class CourseNewVersionSerializer(serializers.Serializer):
    version = serializers.CharField(max_length=20, validators=[validar_version])


class CourseNewVersionView(GenericAPIView):
    """SPEC-007 RN-8 a RN-13: publicar una versión nueva."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]
    serializer_class = CourseNewVersionSerializer

    def get_organization(self):
        return self.request.user.admin_profile.organization

    def get_course(self):
        # RN-9: la versión nueva sucede a la que está vigente, así que el
        # origen debe estar activo. Un curso ya retirado no se versiona.
        return get_object_or_404(
            Course.objects.filter(
                organization=self.get_organization(),
                show=True,
                is_active=True,
            ),
            pk=self.kwargs["pk"],
        )

    def post(self, request, *args, **kwargs):
        course = self.get_course()
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        version = input_serializer.validated_data["version"].strip()

        # RN-10: dos cursos del mismo nombre no pueden compartir versión, o
        # «cursó la 2.0» dejaría de identificar un contenido.
        ya_existe = Course.objects.filter(
            organization=self.get_organization(),
            show=True,
            full_name=course.full_name,
            version=version,
        ).exists()
        if version == course.version or ya_existe:
            raise serializers.ValidationError(
                {"version": ["Ya existe una versión con ese número para este curso."]}
            )

        # RN-12: crear la nueva y retirar la vieja es una sola operación.
        # RN-13: los inscritos NO se copian; quien cursó la 1.0 sigue en la 1.0.
        with transaction.atomic():
            nueva = Course.objects.create(
                full_name=course.full_name,
                description=course.description,
                duration_hours=course.duration_hours,
                version=version,
                organization=self.get_organization(),
            )
            course.is_active = False
            course.save(update_fields=["is_active", "updated_at"])

        nueva = with_enrolled_count(Course.objects.filter(pk=nueva.pk)).get()
        return Response(
            CourseDetailSerializer(nueva).data, status=status.HTTP_201_CREATED
        )


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

        existente = CourseCollaborator.objects.filter(
            course=course,
            collaborator=collaborator,
        ).first()
        if existente is not None:
            if existente.show:
                raise serializers.ValidationError(
                    {"collaborator_id": [self.duplicate_error]}
                )
            # SPEC-007 RN-18: la inscripción está oculta porque alguien la
            # desinscribió. La restricción única (course, collaborator) no
            # filtra por `show`, así que no hay fila nueva que crear: se
            # reactiva la que ya existe. RN-19: `assigned_at` no se toca, sigue
            # respondiendo desde cuándo tiene el curso asignado.
            existente.show = True
            existente.save(update_fields=["show", "updated_at"])
            return Response(
                CourseAssignmentSerializer(existente).data,
                status=status.HTTP_201_CREATED,
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


class CourseUnenrollView(DestroyAPIView):
    """SPEC-007 RN-14 a RN-17: desinscribir a un colaborador de un curso."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]
    lookup_url_kwarg = "enrollment_id"

    def get_queryset(self):
        # RN-15: la inscripción tiene que ser de ESTE curso y de este tenant;
        # si no, no existe. RN-16: `is_active` NO se exige —corregir una
        # inscripción de un curso retirado es justamente lo que hay que poder
        # hacer—, igual que en CourseCollaboratorsView.
        return CourseCollaborator.objects.filter(
            show=True,
            course__pk=self.kwargs["pk"],
            course__show=True,
            course__organization=self.request.user.admin_profile.organization,
        )

    def perform_destroy(self, enrollment):
        # RN-17: con `show=False` alcanza. El criterio de «inscrito vigente» ya
        # exige la inscripción visible, así que el contador, la lista de
        # inscritos y «mis cursos» se enteran solos.
        enrollment.show = False
        enrollment.save(update_fields=["show", "updated_at"])
