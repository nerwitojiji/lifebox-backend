from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from knox.auth import TokenAuthentication
from rest_framework import serializers
from rest_framework.generics import GenericAPIView, ListCreateAPIView
from rest_framework.response import Response
from rest_framework import status

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from apps.user.models import Collaborator
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
