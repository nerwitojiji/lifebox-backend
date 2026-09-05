from knox.auth import TokenAuthentication
from rest_framework import serializers
from rest_framework.generics import ListAPIView, RetrieveAPIView

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils.custom_permissions import IsCollaborator


class MyCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        # Sin enrolled_count ni nada de otros inscritos (SPEC-006 RN-8): cuántos
        # compañeros tiene el curso no es información del colaborador. SPEC-010
        # RN-6 lo mantiene: la ficha no agrega ni un campo más que la lista.
        fields = [
            "id",
            "full_name",
            "description",
            "duration_hours",
            "version",
            "is_active",
        ]


class MyEnrollmentSerializer(serializers.ModelSerializer):
    course = MyCourseSerializer(read_only=True)

    class Meta:
        model = CourseCollaborator
        fields = ["id", "assigned_at", "course"]


# SPEC-010 RN-4: «lo que este colaborador tiene asignado» se define UNA vez y lo
# comparten la lista y la ficha. Si cada vista escribiera su propio filtro, la
# ficha podría abrir un curso que la lista no muestra —o al revés— y el
# colaborador vería dos verdades distintas sobre lo mismo. El test CA-12 compara
# las dos respuestas justamente para que esto no se separe en silencio.
def mis_inscripciones(collaborator):
    """Las inscripciones vigentes del colaborador, listas para serializar.

    SPEC-006 RN-2: el colaborador llega como argumento y sale del token en la
    vista; acá no se lee nada de la petición.
    """
    return CourseCollaborator.objects.filter(
        collaborator=collaborator,
        show=True,
        course__show=True,
        # SPEC-006 RN-6: defensa en profundidad. La asignación ya impide cruzar
        # tenants, pero el modelo no lo garantiza por sí solo.
        course__organization=collaborator.organization,
        # SPEC-006 RN-5 y SPEC-010 RN-5: `course__is_active` NO se filtra. Un
        # curso retirado no desinscribe a nadie y quien lo tenía asignado
        # conserva la obligación; se muestra marcado para que la interfaz lo
        # distinga, tanto en la lista como en la ficha.
    ).select_related("course")


class MyCoursesView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsCollaborator]
    serializer_class = MyEnrollmentSerializer

    def get_queryset(self):
        collaborator = self.request.user.collaborator_profile
        return mis_inscripciones(collaborator).order_by(
            "-assigned_at", "course__full_name"
        )


class MyCourseDetailView(RetrieveAPIView):
    """SPEC-010 RN-1 a RN-8: la ficha de una inscripción propia.

    Se busca por id de inscripción y no de curso (PA-3): así «solo lo que me
    asignaron» es cierto por construcción —no hay un curso que encontrar primero
    y autorizar después—, y la respuesta sale del mismo serializer que la lista.

    RN-3 y PA-4: una inscripción ajena, oculta o de otro tenant simplemente no
    está en el queryset, así que responde 404. Un 403 confirmaría que existe.

    RN-8: `RetrieveAPIView` no expone verbos de escritura. El colaborador lee;
    la escritura es del administrador.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsCollaborator]
    serializer_class = MyEnrollmentSerializer

    def get_queryset(self):
        return mis_inscripciones(self.request.user.collaborator_profile)
