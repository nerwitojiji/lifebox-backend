from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils import model_factories


class UnenrollTests(APITestCase):
    """SPEC-007 — DELETE /course/{id}/collaborators/{enrollment_id}/ y la
    reinscripción que reactiva (CA-22 a CA-31, CA-37 y CA-38)."""

    def setUp(self):
        self.org_a = model_factories.create_organization(name="Organización A")
        self.org_b = model_factories.create_organization(name="Organización B")
        model_factories.create_admin(
            organization=self.org_a,
            email="admin.a@test.com",
            password="password123",
        )
        model_factories.create_admin(
            organization=self.org_b,
            email="admin.b@test.com",
            password="password123",
        )
        self.collaborator_a = model_factories.create_collaborator(
            organization=self.org_a,
            email="colab.a@test.com",
            first_name="Ana",
            last_name="Pérez",
            password="password123",
        )
        self.collaborator_b = model_factories.create_collaborator(
            organization=self.org_b,
            email="colab.b@test.com",
            first_name="Bruno",
            last_name="Soto",
            password="password123",
        )
        self.course_a = Course.objects.create(
            full_name="Prevención de riesgos",
            organization=self.org_a,
        )
        self.otro_curso = Course.objects.create(
            full_name="Manejo de extintores",
            organization=self.org_a,
        )
        self.course_b = Course.objects.create(
            full_name="Curso ajeno",
            organization=self.org_b,
        )
        self.inscripcion = CourseCollaborator.objects.create(
            course=self.course_a, collaborator=self.collaborator_a
        )

    # -- utilidades -----------------------------------------------------------

    def authenticate(self, email):
        response = self.client.post(
            reverse("user-login"),
            {"email": email, "password": "password123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")

    def url(self, course=None, enrollment=None):
        return reverse(
            "course-unenroll",
            kwargs={
                "pk": (course or self.course_a).pk,
                "enrollment_id": (enrollment or self.inscripcion).pk,
            },
        )

    # -- desinscribir ---------------------------------------------------------

    def test_desinscribir_es_borrado_logico(self):
        """CA-22: RN-14 — show=False y la fila sigue en la base."""
        self.authenticate("admin.a@test.com")

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(
            CourseCollaborator.objects.filter(pk=self.inscripcion.pk).exists()
        )
        self.inscripcion.refresh_from_db()
        self.assertFalse(self.inscripcion.show)

    def test_desinscribir_baja_el_conteo_y_saca_de_la_lista(self):
        """CA-23: RN-17 — el criterio de «inscrito vigente» hace el resto."""
        self.authenticate("admin.a@test.com")

        self.client.delete(self.url())

        detalle = self.client.get(
            reverse("course-detail", kwargs={"pk": self.course_a.pk})
        )
        self.assertEqual(detalle.data["enrolled_count"], 0)

        inscritos = self.client.get(
            reverse("course-collaborators", kwargs={"pk": self.course_a.pk})
        )
        self.assertEqual(inscritos.data, [])

    def test_desinscribir_saca_el_curso_de_mis_cursos(self):
        """CA-24: RN-17 — del lado del colaborador también desaparece."""
        self.authenticate("admin.a@test.com")
        self.client.delete(self.url())

        self.client.credentials()
        self.authenticate("colab.a@test.com")
        response = self.client.get(reverse("my-courses"))

        self.assertEqual(response.data, [])

    def test_desinscribir_una_inscripcion_ya_oculta_devuelve_404(self):
        """CA-25: RN-15."""
        self.inscripcion.show = False
        self.inscripcion.save()
        self.authenticate("admin.a@test.com")

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_la_inscripcion_debe_pertenecer_al_curso_de_la_url(self):
        """CA-26: RN-15 — no se puede desinscribir por el curso equivocado."""
        self.authenticate("admin.a@test.com")

        response = self.client.delete(
            self.url(course=self.otro_curso, enrollment=self.inscripcion)
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.inscripcion.refresh_from_db()
        self.assertTrue(self.inscripcion.show)

    def test_no_se_puede_desinscribir_de_otro_tenant(self):
        """CA-27: RN-15."""
        ajena = CourseCollaborator.objects.create(
            course=self.course_b, collaborator=self.collaborator_b
        )
        self.authenticate("admin.a@test.com")

        response = self.client.delete(self.url(course=self.course_b, enrollment=ajena))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        ajena.refresh_from_db()
        self.assertTrue(ajena.show)

    def test_se_puede_desinscribir_de_un_curso_inactivo(self):
        """CA-28: RN-16 — corregir un curso retirado sigue siendo posible."""
        self.course_a.is_active = False
        self.course_a.save()
        self.authenticate("admin.a@test.com")

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    # -- reinscribir ----------------------------------------------------------

    def test_reinscribir_reactiva_la_inscripcion_existente(self):
        """CA-29: RN-18 — 201 sin crear una segunda fila."""
        self.authenticate("admin.a@test.com")
        self.client.delete(self.url())

        response = self.client.post(
            reverse("course-assign", kwargs={"pk": self.course_a.pk}),
            {"collaborator_id": self.collaborator_a.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            CourseCollaborator.objects.filter(
                course=self.course_a, collaborator=self.collaborator_a
            ).count(),
            1,
        )
        self.inscripcion.refresh_from_db()
        self.assertTrue(self.inscripcion.show)
        self.assertEqual(response.data["id"], self.inscripcion.pk)

    def test_reactivar_conserva_la_fecha_de_asignacion(self):
        """CA-30: RN-19 — assigned_at responde desde cuándo, no cuándo se corrigió."""
        assigned_at_original = self.inscripcion.assigned_at
        self.authenticate("admin.a@test.com")
        self.client.delete(self.url())

        self.client.post(
            reverse("course-assign", kwargs={"pk": self.course_a.pk}),
            {"collaborator_id": self.collaborator_a.pk},
            format="json",
        )

        self.inscripcion.refresh_from_db()
        self.assertEqual(self.inscripcion.assigned_at, assigned_at_original)

    def test_inscribir_a_alguien_ya_inscrito_sigue_dando_400(self):
        """CA-31: RN-18 — una inscripción visible no se reactiva, se rechaza."""
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            reverse("course-assign", kwargs={"pk": self.course_a.pk}),
            {"collaborator_id": self.collaborator_a.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("collaborator_id", response.data)

    # -- permisos -------------------------------------------------------------

    def test_sin_token_devuelve_401(self):
        """CA-37."""
        response = self.client.delete(self.url())
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_colaborador_devuelve_403(self):
        """CA-38."""
        self.authenticate("colab.a@test.com")

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.inscripcion.refresh_from_db()
        self.assertTrue(self.inscripcion.show)
