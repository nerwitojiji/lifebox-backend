from uuid import uuid4

from django.db import models

from utils.base_model import BaseAbstractModel


class Course(BaseAbstractModel):
    full_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    duration_hours = models.PositiveIntegerField(default=1)
    version = models.CharField(max_length=20, default="1.0")
    organization = models.ForeignKey(
        "organization.Organization",
        on_delete=models.CASCADE,
        related_name="courses",
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.full_name} ({self.version})"


def material_upload_path(instance, filename):
    # El nombre del cliente nunca decide dónde se escribe ni qué se reemplaza.
    return f"courses/{instance.course_id}/materials/{uuid4().hex}.pdf"


class CourseMaterial(BaseAbstractModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="materials")
    file = models.FileField(upload_to=material_upload_path)
    filename = models.CharField(max_length=255)
    size_bytes = models.PositiveIntegerField()
    page_count = models.PositiveIntegerField()

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.filename
