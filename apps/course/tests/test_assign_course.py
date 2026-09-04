from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils import model_factories


class AssignCourseTests(APITestCase):
    """SPEC-003 — POST /course/{id}/assign/ (CA-1 a CA-14)."""

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
            password="password123",
        )
        self.collaborator_b = model_factories.create_collaborator(
            organization=self.org_b,
            email="colab.b@test.com",
            password="password123",
        )
        self.course_a = Course.objects.create(
            full_name="Curso A",
            version="2.0",
            organization=self.org_a,
        )
        self.course_b = Course.objects.create(
            full_name="Curso B",
            organization=self.org_b,
        )

    def authenticate(self, email):
        response = self.client.post(
            reverse("user-login"),
            {"email": email, "password": "password123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")

    def url(self, course=None):
        return reverse("course-assign", kwargs={"pk": (course or self.course_a).pk})

    def test_admin_puede_asignar_curso_a_colaborador(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(), {"collaborator_id": self.collaborator_a.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enrollment = CourseCollaborator.objects.get()
        self.assertEqual(enrollment.course, self.course_a)
        self.assertEqual(enrollment.collaborator, self.collaborator_a)
        self.assertTrue(enrollment.show)

    def test_respuesta_incluye_datos_de_la_inscripcion(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(), {"collaborator_id": self.collaborator_a.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsInstance(response.data["id"], int)
        self.assertTrue(response.data["assigned_at"])
        self.assertEqual(
            response.data["course"],
            {"id": self.course_a.id, "full_name": "Curso A", "version": "2.0"},
        )
        self.assertEqual(response.data["collaborator"]["id"], self.collaborator_a.id)
        self.assertEqual(response.data["collaborator"]["full_name"], "Colaborador Uno")
        self.assertEqual(response.data["collaborator"]["email"], "colab.a@test.com")

    def test_campos_de_control_del_body_son_ignorados(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(),
            {
                "collaborator_id": self.collaborator_a.id,
                "course_id": self.course_b.id,
                "organization": self.org_b.id,
                "organization_id": self.org_b.id,
                "show": False,
                "assigned_at": "2000-01-01T00:00:00Z",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enrollment = CourseCollaborator.objects.get()
        self.assertEqual(enrollment.course, self.course_a)
        self.assertTrue(enrollment.show)
        self.assertNotEqual(enrollment.assigned_at.year, 2000)

    def test_curso_de_otra_organizacion_devuelve_404(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(self.course_b),
            {"collaborator_id": self.collaborator_a.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(CourseCollaborator.objects.exists())

    def test_colaborador_de_otra_organizacion_devuelve_404(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(), {"collaborator_id": self.collaborator_b.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(CourseCollaborator.objects.exists())

    def test_curso_inexistente_devuelve_404(self):
        self.authenticate("admin.a@test.com")
        url = reverse("course-assign", kwargs={"pk": 999999})

        response = self.client.post(
            url, {"collaborator_id": self.collaborator_a.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(CourseCollaborator.objects.exists())

    def test_colaborador_inexistente_devuelve_404(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(), {"collaborator_id": 999999}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(CourseCollaborator.objects.exists())

    def test_collaborator_id_es_obligatorio(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(self.url(), {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("collaborator_id", response.data)
        self.assertFalse(CourseCollaborator.objects.exists())

    def test_collaborator_id_debe_ser_entero(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(), {"collaborator_id": "no-es-entero"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("collaborator_id", response.data)
        self.assertFalse(CourseCollaborator.objects.exists())

    def test_asignacion_duplicada_devuelve_400_sin_crear_otra(self):
        CourseCollaborator.objects.create(
            course=self.course_a, collaborator=self.collaborator_a
        )
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(), {"collaborator_id": self.collaborator_a.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("collaborator_id", response.data)
        self.assertEqual(CourseCollaborator.objects.count(), 1)

    def test_asignacion_oculta_se_reactiva(self):
        """SPEC-007 RN-18 supersede a SPEC-003 RN-6/CA-10.

        Este test afirmaba lo contrario —que una inscripción oculta devolvía
        400 y no se reactivaba— y era correcto mientras nada podía ocultar una
        inscripción. Al existir la desinscripción (borrado lógico), mantenerlo
        haría que desinscribir por error fuera irreversible: el 400 diría «ya
        está inscrito» sobre una fila que nadie ve. La reinscripción tiene su
        cobertura completa en test_unenroll.py (CA-29 y CA-30).
        """
        enrollment = CourseCollaborator.objects.create(
            course=self.course_a,
            collaborator=self.collaborator_a,
            show=False,
        )
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(), {"collaborator_id": self.collaborator_a.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        enrollment.refresh_from_db()
        self.assertTrue(enrollment.show)
        self.assertEqual(CourseCollaborator.objects.count(), 1)

    def test_colaborador_no_puede_asignar_cursos(self):
        self.authenticate("colab.a@test.com")

        response = self.client.post(
            self.url(), {"collaborator_id": self.collaborator_a.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(CourseCollaborator.objects.exists())

    def test_asignar_sin_token_devuelve_401(self):
        response = self.client.post(
            self.url(), {"collaborator_id": self.collaborator_a.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(CourseCollaborator.objects.exists())

    def test_curso_inactivo_u_oculto_no_se_puede_asignar(self):
        self.authenticate("admin.a@test.com")

        for field in ("is_active", "show"):
            setattr(self.course_a, field, False)
            self.course_a.save(update_fields=[field])
            with self.subTest(field=field):
                response = self.client.post(
                    self.url(),
                    {"collaborator_id": self.collaborator_a.id},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertFalse(CourseCollaborator.objects.exists())
            setattr(self.course_a, field, True)
            self.course_a.save(update_fields=[field])

    def test_colaborador_oculto_no_se_puede_asignar(self):
        self.collaborator_a.show = False
        self.collaborator_a.save(update_fields=["show"])
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url(), {"collaborator_id": self.collaborator_a.id}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(CourseCollaborator.objects.exists())

    def test_usuario_oculto_o_inactivo_no_se_puede_asignar(self):
        self.authenticate("admin.a@test.com")

        for field in ("show", "is_active"):
            setattr(self.collaborator_a.user, field, False)
            self.collaborator_a.user.save(update_fields=[field])
            with self.subTest(field=field):
                response = self.client.post(
                    self.url(),
                    {"collaborator_id": self.collaborator_a.id},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
                self.assertFalse(CourseCollaborator.objects.exists())
            setattr(self.collaborator_a.user, field, True)
            self.collaborator_a.user.save(update_fields=[field])
