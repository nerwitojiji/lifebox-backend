"""SPEC-011: gestión de PDFs y entrega privada compartida por ambos roles."""
import logging
from pathlib import PurePosixPath
import unicodedata

from django.db import DatabaseError, transaction
from django.db.models import Prefetch
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from knox.auth import TokenAuthentication
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.generics import GenericAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.course.models import Course, CourseMaterial, material_upload_path
from utils.custom_permissions import IsAdmin

logger = logging.getLogger(__name__)
MAX_PDF_BYTES = 10 * 1024 * 1024


def with_materials(queryset, prefix=""):
    """Una sola precarga de material visible por listado, no una por curso."""
    return queryset.prefetch_related(
        Prefetch(f"{prefix}materials", queryset=CourseMaterial.objects.filter(show=True))
    )


class CourseMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseMaterial
        fields = ["id", "filename", "size_bytes", "page_count", "updated_at"]
        read_only_fields = fields


class CourseWithMaterialsSerializer(serializers.ModelSerializer):
    materials = CourseMaterialSerializer(many=True, read_only=True)


class MaterialStorageUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "No se pudo guardar el PDF. El material anterior se conserva. Intenta nuevamente."
    default_code = "material_storage_unavailable"


def remove_replaced_file(storage, name):
    """La limpieza no convierte una operación ya confirmada en un falso error."""
    if not name:
        return
    try:
        storage.delete(name)
    except OSError:
        logger.exception("No se pudo limpiar un archivo de material sin referencia.")


def save_material(instance, validated_data):
    uploaded = validated_data.pop("file")
    storage = instance.file.storage
    new_name = ""
    try:
        with transaction.atomic():
            if instance.pk:
                # Evita que dos reemplazos usen una referencia vieja, y que uno
                # pendiente reactive una fila que otra petición acaba de ocultar.
                instance = get_object_or_404(
                    CourseMaterial.objects.select_for_update().filter(
                        show=True, course__show=True
                    ),
                    pk=instance.pk,
                )
            old_name = instance.file.name
            new_name = storage.save(material_upload_path(instance, uploaded.name), uploaded)
            instance.file.name = new_name
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()
            if old_name:
                transaction.on_commit(lambda: remove_replaced_file(storage, old_name))
    except (OSError, DatabaseError) as error:
        if new_name:
            remove_replaced_file(storage, new_name)
        logger.exception("No se pudo persistir un PDF de curso.")
        raise MaterialStorageUnavailable() from error
    return instance


class CourseMaterialUploadSerializer(CourseMaterialSerializer):
    file = serializers.FileField(write_only=True, max_length=255)

    class Meta(CourseMaterialSerializer.Meta):
        fields = CourseMaterialSerializer.Meta.fields + ["file"]
        read_only_fields = CourseMaterialSerializer.Meta.fields

    def validate(self, attrs):
        uploaded = attrs["file"]
        filename = uploaded.name.replace("\\", "/").rsplit("/", 1)[-1]
        filename = "".join(c for c in filename if not unicodedata.category(c).startswith("C"))
        filename = filename.strip()
        if PurePosixPath(filename).suffix.lower() != ".pdf":
            raise serializers.ValidationError({"file": ["Selecciona un archivo con extensión .pdf."]})
        if uploaded.size > MAX_PDF_BYTES:
            raise serializers.ValidationError({"file": ["El PDF debe pesar como máximo 10 MB."]})
        try:
            if uploaded.read(5) != b"%PDF-":
                raise serializers.ValidationError({"file": ["El archivo no es un PDF válido."]})
            uploaded.seek(0)
            reader = PdfReader(uploaded, strict=True)
            if reader.is_encrypted:
                raise serializers.ValidationError({
                    "file": ["El PDF está cifrado. Sube una copia sin contraseña ni cifrado."]
                })
            pages = len(reader.pages)
            if not pages:
                raise serializers.ValidationError({"file": ["El PDF debe tener al menos una página."]})
        except (PyPdfError, ValueError, TypeError, KeyError, IndexError, RecursionError, OSError) as error:
            raise serializers.ValidationError({
                "file": ["No se pudo leer el PDF. Comprueba que no esté corrupto."]
            }) from error
        finally:
            uploaded.seek(0)
        attrs.update(filename=filename, size_bytes=uploaded.size, page_count=pages)
        return attrs

    def create(self, validated_data):
        course = validated_data.pop("course")
        return save_material(CourseMaterial(course=course), validated_data)

    def update(self, instance, validated_data):
        return save_material(instance, validated_data)


def material_file_response(material):
    """Los callers ya resolvieron un material visible dentro de un curso propio."""
    try:
        stream = material.file.open("rb")
    except OSError as error:
        raise NotFound("El PDF ya no está disponible. Actualiza la ficha.") from error
    response = FileResponse(
        stream, content_type="application/pdf", filename=material.filename
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


class CourseMaterialAdminView(GenericAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = CourseMaterialUploadSerializer

    def get_course(self):
        return get_object_or_404(
            Course.objects.filter(
                organization=self.request.user.admin_profile.organization, show=True
            ),
            pk=self.kwargs["pk"],
        )

    def get_material(self, include_hidden=False):
        queryset = CourseMaterial.objects.filter(course=self.get_course())
        if not include_hidden:
            queryset = queryset.filter(show=True)
        return get_object_or_404(queryset, pk=self.kwargs["material_id"])


class CourseMaterialListView(CourseMaterialAdminView):
    def post(self, request, *args, **kwargs):
        course = self.get_course()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(course=course)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CourseMaterialDetailView(CourseMaterialAdminView):
    def put(self, request, *args, **kwargs):
        material = self.get_material()
        serializer = self.get_serializer(material, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, *args, **kwargs):
        material = self.get_material(include_hidden=True)
        if material.show:
            material.show = False
            material.save(update_fields=["show", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class CourseMaterialFileView(CourseMaterialAdminView):
    def get(self, request, *args, **kwargs):
        return material_file_response(self.get_material())
