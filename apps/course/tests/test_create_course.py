from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.course.models import Course
from utils import model_factories


class CreateCourseTests(APITestCase):
    """SPEC-001 — POST /course/ (criterios de aceptación CA-1 a CA-8)."""

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
        model_factories.create_collaborator(
            organization=self.org_a,
            email="colab.a@test.com",
            password="password123",
        )
        self.url = reverse("course-list")

    def authenticate(self, email):
        response = self.client.post(
            reverse("user-login"),
            {"email": email, "password": "password123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")

    def test_admin_puede_crear_curso(self):
        """CA-1: creación válida devuelve 201 y persiste con la org del admin."""
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url,
            {"full_name": "Inducción de seguridad"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

        curso = Course.objects.get(id=response.data["id"])
        self.assertEqual(curso.full_name, "Inducción de seguridad")
        self.assertEqual(curso.organization, self.org_a)  # RN-4
        self.assertEqual(curso.description, "")  # RN-6
        self.assertEqual(curso.duration_hours, 1)  # RN-5 (default)
        self.assertEqual(curso.version, "1.0")  # RN-7
        self.assertTrue(curso.is_active)  # RN-8
        self.assertTrue(curso.show)  # RN-8

    def test_crear_curso_sin_full_name_devuelve_400(self):
        """CA-2: full_name obligatorio y no vacío; no se crea nada."""
        self.authenticate("admin.a@test.com")

        for payload in ({"description": "Sin nombre"}, {"full_name": ""}, {"full_name": "   "}):
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("full_name", response.data)

        self.assertEqual(Course.objects.count(), 0)

    def test_organizacion_del_body_es_ignorada(self):
        """CA-3: la organización se deriva del servidor, nunca del body (RN-4)."""
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url,
            {
                "full_name": "Curso con organización falsificada",
                "organization": self.org_b.id,
                "organization_id": self.org_b.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        curso = Course.objects.get(id=response.data["id"])
        self.assertEqual(curso.organization, self.org_a)

    def test_colaborador_no_puede_crear_curso(self):
        """CA-4: un colaborador autenticado recibe 403."""
        self.authenticate("colab.a@test.com")

        response = self.client.post(
            self.url,
            {"full_name": "Curso prohibido"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Course.objects.count(), 0)

    def test_crear_curso_sin_token_devuelve_401(self):
        """CA-5: sin token válido, 401."""
        response = self.client.post(
            self.url,
            {"full_name": "Curso anónimo"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Course.objects.count(), 0)

    def test_duration_hours_invalida_devuelve_400(self):
        """CA-6: duration_hours debe ser un entero >= 1 (RN-5)."""
        self.authenticate("admin.a@test.com")

        for valor in (0, -5, "no-es-un-numero"):
            with self.subTest(duration_hours=valor):
                response = self.client.post(
                    self.url,
                    {"full_name": "Curso con duración inválida", "duration_hours": valor},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("duration_hours", response.data)

        self.assertEqual(Course.objects.count(), 0)

    def test_curso_creado_aparece_en_listado(self):
        """CA-7: el curso creado queda disponible de inmediato en GET /course/."""
        self.authenticate("admin.a@test.com")

        creacion = self.client.post(
            self.url,
            {"full_name": "Primeros auxilios"},
            format="json",
        )
        self.assertEqual(creacion.status_code, status.HTTP_201_CREATED)

        listado = self.client.get(self.url)

        self.assertEqual(listado.status_code, status.HTTP_200_OK)
        self.assertIn("Primeros auxilios", [curso["full_name"] for curso in listado.data])

    def test_curso_no_es_visible_para_otra_organizacion(self):
        """CA-8: aislamiento entre organizaciones (RN-10)."""
        self.authenticate("admin.a@test.com")
        creacion = self.client.post(
            self.url,
            {"full_name": "Curso interno de A"},
            format="json",
        )
        self.assertEqual(creacion.status_code, status.HTTP_201_CREATED)

        self.authenticate("admin.b@test.com")
        listado = self.client.get(self.url)

        self.assertEqual(listado.status_code, status.HTTP_200_OK)
        self.assertNotIn("Curso interno de A", [curso["full_name"] for curso in listado.data])
