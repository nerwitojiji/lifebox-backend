from knox.auth import TokenAuthentication
from rest_framework import serializers
from rest_framework.generics import ListAPIView

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils.custom_permissions import IsCollaborator


class MyCourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        # Sin enrolled_count ni nada de otros inscritos (RN-8): cuántos compañeros
        # tiene el curso no es información del colaborador.
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


class MyCoursesView(ListAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsCollaborator]
    serializer_class = MyEnrollmentSerializer

    def get_queryset(self):
        # RN-2: el colaborador sale del token y de ningún otro lado. No hay forma
        # de pedir los cursos de otra persona: no se lee nada de la petición.
        collaborator = self.request.user.collaborator_profile
        return (
            CourseCollaborator.objects.filter(
                collaborator=collaborator,
                show=True,
                course__show=True,
                # RN-6: defensa en profundidad. La asignación ya impide cruzar
                # tenants, pero el modelo no lo garantiza por sí solo.
                course__organization=collaborator.organization,
            )
            # RN-5: `course__is_active` NO se filtra. Un curso retirado no
            # desinscribe a nadie y quien lo tenía asignado conserva la
            # obligación; se lista marcado para que la interfaz lo distinga.
            .select_related("course")
            .order_by("-assigned_at", "course__full_name")
        )
