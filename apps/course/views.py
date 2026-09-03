from knox.auth import TokenAuthentication
from rest_framework import serializers
from rest_framework.generics import ListCreateAPIView

from apps.course.models import Course
from utils.custom_permissions import IsAdmin


class CourseListSerializer(serializers.ModelSerializer):
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
        return Course.objects.filter(
            organization=self.get_organization(),
            show=True,
        ).order_by("-created_at")

    def perform_create(self, serializer):
        # RN-4: la organización se deriva del admin autenticado. El serializer no
        # declara el campo, así que un organization del body ya viene descartado.
        serializer.save(organization=self.get_organization())
