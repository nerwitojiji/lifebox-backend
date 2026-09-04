from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils import model_factories


class CourseVersionTests(APITestCase):
    """SPEC-007 — POST /course/{id}/new-version/ (CA-14 a CA-21, CA-37 y CA-38)."""

    def setUp(self):
        self.org_a = model_factories.create_organization(name="Organización A")
        self.org_b = model_factories.create_organization(name="Organización B")
        model_factories.create_admin(
            organization=self.org_a,
            email="admin.a@test.com",
            password="password123",
        )
        self.collaborator_a = model_factories.create_collaborator(
            organization=self.org_a,
            email="colab.a@test.com",
            first_name="Ana",
            last_name="Pérez",
            password="password123",
        )
        self.course_a = Course.objects.create(
            full_name="Prevención de riesgos",
            description="Contenido de la 1.0",
            duration_hours=6,
            version="1.0",
            organization=self.org_a,
        )
        self.course_b = Course.objects.create(
            full_name="Curso ajeno",
            organization=self.org_b,
        )

    # -- utilidades -----------------------------------------------------------

    def authenticate(self, email):
        response = self.client.post(
            reverse("user-login"),
            {"email": email, "password": "password123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")

    def url(self, course=None):
        return reverse(
            "course-new-version", kwargs={"pk": (course or self.course_a).pk}
        )

    # -- publicar una versión -------------------------------------------------

    def test_versionar_crea_un_curso_nuevo_copiando_el_contenido(self):
        """CA-14: RN-11 — 201 con un curso distinto, activo y con los mismos datos."""
        self.authenticate("admin.a@test.com")

        response = self.client.post(self.url(), {"version": "2.0"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response.data["id"], self.course_a.pk)
        self.assertEqual(response.data["full_name"], "Prevención de riesgos")
        self.assertEqual(response.data["description"], "Contenido de la 1.0")
        self.assertEqual(response.data["duration_hours"], 6)
        self.assertEqual(response.data["version"], "2.0")
        self.assertTrue(response.data["is_active"])

        nuevo = Course.objects.get(pk=response.data["id"])
        self.assertEqual(nuevo.organization, self.org_a)
        self.assertTrue(nuevo.show)

    def test_versionar_retira_el_curso_de_origen(self):
        """CA-15: RN-12 — el origen queda inactivo pero visible."""
        self.authenticate("admin.a@test.com")

        self.client.post(self.url(), {"version": "2.0"}, format="json")

        self.course_a.refresh_from_db()
        self.assertFalse(self.course_a.is_active)
        self.assertTrue(self.course_a.show)

    def test_versionar_no_migra_los_inscritos(self):
        """CA-16: RN-13 — quien cursó la 1.0 sigue en la 1.0, y la 2.0 nace vacía."""
        CourseCollaborator.objects.create(
            course=self.course_a, collaborator=self.collaborator_a
        )
        self.authenticate("admin.a@test.com")

        response = self.client.post(self.url(), {"version": "2.0"}, format="json")

        self.assertEqual(response.data["enrolled_count"], 0)
        self.assertEqual(
            CourseCollaborator.objects.filter(course=self.course_a).count(), 1
        )
        self.assertEqual(
            CourseCollaborator.objects.filter(course_id=response.data["id"]).count(), 0
        )

    def test_versionar_con_la_misma_version_devuelve_400(self):
        """CA-17: RN-10."""
        self.authenticate("admin.a@test.com")

        response = self.client.post(self.url(), {"version": "1.0"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", response.data)

    def test_versionar_con_una_version_ya_usada_devuelve_400(self):
        """CA-18: RN-10 — otro curso visible del mismo nombre ya la ocupa."""
        Course.objects.create(
            full_name="Prevención de riesgos",
            version="2.0",
            organization=self.org_a,
        )
        self.authenticate("admin.a@test.com")

        response = self.client.post(self.url(), {"version": "2.0"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("version", response.data)

    def test_versionar_rechaza_las_versiones_invalidas(self):
        """CA-19: RN-8 — obligatoria y con al menos un carácter alfanumérico."""
        self.authenticate("admin.a@test.com")

        for payload in [{}, {"version": ""}, {"version": "."}, {"version": "--"}]:
            with self.subTest(payload=payload):
                response = self.client.post(self.url(), payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("version", response.data)

    def test_versionar_un_curso_no_disponible_devuelve_404(self):
        """CA-20: RN-9 — inactivo, oculto, de otro tenant o inexistente."""
        self.authenticate("admin.a@test.com")
        inactivo = Course.objects.create(
            full_name="Curso retirado", organization=self.org_a, is_active=False
        )
        oculto = Course.objects.create(
            full_name="Curso oculto", organization=self.org_a, show=False
        )

        casos = {
            "inactivo": self.url(inactivo),
            "oculto": self.url(oculto),
            "otro tenant": self.url(self.course_b),
            "inexistente": reverse("course-new-version", kwargs={"pk": 9999}),
        }
        for caso, url in casos.items():
            with self.subTest(caso=caso):
                response = self.client.post(url, {"version": "2.0"}, format="json")
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_un_400_no_deja_nada_a_medias(self):
        """CA-21: RN-12 — atomicidad, ni curso nuevo ni origen retirado."""
        self.authenticate("admin.a@test.com")
        cursos_antes = Course.objects.count()

        response = self.client.post(self.url(), {"version": "1.0"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Course.objects.count(), cursos_antes)
        self.course_a.refresh_from_db()
        self.assertTrue(self.course_a.is_active)

    # -- permisos -------------------------------------------------------------

    def test_sin_token_devuelve_401(self):
        """CA-37."""
        response = self.client.post(self.url(), {"version": "2.0"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_colaborador_devuelve_403(self):
        """CA-38."""
        self.authenticate("colab.a@test.com")

        response = self.client.post(self.url(), {"version": "2.0"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.course_a.refresh_from_db()
        self.assertTrue(self.course_a.is_active)
