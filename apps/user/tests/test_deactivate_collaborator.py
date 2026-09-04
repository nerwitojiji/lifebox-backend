from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from apps.user.models import Collaborator
from utils import model_factories


class DeactivateCollaboratorTests(APITestCase):
    """SPEC-007 — DELETE /collaborator/{id}/ (CA-32 a CA-36, CA-37 y CA-38)."""

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
        self.otro_colaborador = model_factories.create_collaborator(
            organization=self.org_a,
            email="colab.otro@test.com",
            first_name="Luis",
            last_name="Rojas",
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

    def url(self, collaborator=None):
        return reverse(
            "collaborator-detail",
            kwargs={"pk": (collaborator or self.collaborator_a).pk},
        )

    def login(self, email, password="password123"):
        self.client.credentials()
        return self.client.post(
            reverse("user-login"),
            {"email": email, "password": password},
            format="json",
        )

    # -- dar de baja ----------------------------------------------------------

    def test_dar_de_baja_oculta_el_perfil_y_desactiva_el_usuario(self):
        """CA-32: RN-21 — las dos escrituras, en una sola operación."""
        self.authenticate("admin.a@test.com")

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.collaborator_a.refresh_from_db()
        self.collaborator_a.user.refresh_from_db()
        self.assertFalse(self.collaborator_a.show)
        self.assertFalse(self.collaborator_a.user.is_active)
        self.assertTrue(Collaborator.objects.filter(pk=self.collaborator_a.pk).exists())

    def test_el_colaborador_dado_de_baja_sale_de_los_listados_y_del_conteo(self):
        """CA-33: RN-22 — el criterio de «inscrito vigente» ya lo excluye."""
        self.authenticate("admin.a@test.com")

        self.client.delete(self.url())

        listado = self.client.get(reverse("collaborator-list"))
        self.assertNotIn(
            self.collaborator_a.pk, [fila["id"] for fila in listado.data]
        )

        detalle = self.client.get(
            reverse("course-detail", kwargs={"pk": self.course_a.pk})
        )
        self.assertEqual(detalle.data["enrolled_count"], 0)

    def test_dar_de_baja_no_borra_sus_inscripciones(self):
        """CA-34: RN-22 — el vínculo histórico permanece."""
        self.authenticate("admin.a@test.com")

        self.client.delete(self.url())

        self.assertTrue(
            CourseCollaborator.objects.filter(pk=self.inscripcion.pk).exists()
        )
        self.inscripcion.refresh_from_db()
        self.assertTrue(self.inscripcion.show)

    def test_dar_de_baja_a_quien_no_corresponde_devuelve_404(self):
        """CA-35: RN-20 — otro tenant, ya oculto o inexistente."""
        self.authenticate("admin.a@test.com")
        ya_oculto = model_factories.create_collaborator(
            organization=self.org_a,
            email="colab.oculto@test.com",
            password="password123",
        )
        ya_oculto.show = False
        ya_oculto.save()

        casos = {
            "otro tenant": self.url(self.collaborator_b),
            "ya oculto": self.url(ya_oculto),
            "inexistente": reverse("collaborator-detail", kwargs={"pk": 9999}),
        }
        for caso, url in casos.items():
            with self.subTest(caso=caso):
                self.assertEqual(
                    self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND
                )

        self.collaborator_b.refresh_from_db()
        self.assertTrue(self.collaborator_b.show)

    def test_el_colaborador_dado_de_baja_no_puede_iniciar_sesion(self):
        """CA-36: RN-21 — sin esto, la baja sería solo cosmética."""
        self.assertEqual(self.login("colab.a@test.com").status_code, status.HTTP_200_OK)

        self.authenticate("admin.a@test.com")
        self.client.delete(self.url())

        response = self.login("colab.a@test.com")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("token", response.data)

    # -- permisos -------------------------------------------------------------

    def test_sin_token_devuelve_401(self):
        """CA-37."""
        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.collaborator_a.refresh_from_db()
        self.assertTrue(self.collaborator_a.show)

    def test_colaborador_devuelve_403(self):
        """CA-38: nadie se da de baja a sí mismo ni a un compañero."""
        self.authenticate("colab.a@test.com")

        for objetivo in [self.collaborator_a, self.otro_colaborador]:
            with self.subTest(objetivo=objetivo.user.email):
                response = self.client.delete(self.url(objetivo))
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.collaborator_a.refresh_from_db()
        self.assertTrue(self.collaborator_a.show)
