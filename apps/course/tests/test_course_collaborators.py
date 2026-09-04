from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils import model_factories


class CourseCollaboratorsTests(APITestCase):
    """SPEC-005 — GET /course/{id}/collaborators/ (CA-1 a CA-15)."""

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
            version="2.0",
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
            "course-collaborators", kwargs={"pk": (course or self.course_a).pk}
        )

    def create_collaborator(self, email, organization=None, **kwargs):
        return model_factories.create_collaborator(
            organization=organization or self.org_a,
            email=email,
            password="password123",
            **kwargs,
        )

    def enroll(self, course, collaborator, **kwargs):
        return CourseCollaborator.objects.create(
            course=course, collaborator=collaborator, **kwargs
        )

    def emails(self, response):
        return [row["collaborator"]["email"] for row in response.data]

    # -- CA-1, CA-2, CA-3 -----------------------------------------------------

    def test_admin_obtiene_los_inscritos_del_curso(self):
        self.enroll(self.course_a, self.collaborator_a)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_cada_fila_expone_el_contrato_declarado(self):
        enrollment = self.enroll(self.course_a, self.collaborator_a)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        fila = response.data[0]
        self.assertEqual(set(fila.keys()), {"id", "assigned_at", "collaborator"})
        self.assertEqual(fila["id"], enrollment.id)
        self.assertTrue(fila["assigned_at"])
        self.assertEqual(
            dict(fila["collaborator"]),
            {
                "id": self.collaborator_a.id,
                "full_name": "Ana Pérez",
                "email": "colab.a@test.com",
            },
        )

    def test_curso_sin_inscritos_devuelve_lista_vacia(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data), [])

    # -- CA-4: la divergencia deliberada de RN-4 ------------------------------

    def test_curso_inactivo_igual_devuelve_su_lista(self):
        """RN-4: al revés que asignar, leer los inscritos de un curso retirado
        DEBE funcionar. Un curso inactivo conserva a su gente."""
        self.enroll(self.course_a, self.collaborator_a)
        self.course_a.is_active = False
        self.course_a.save(update_fields=["is_active"])
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.emails(response), ["colab.a@test.com"])

    def test_asignar_sigue_rechazando_el_curso_inactivo(self):
        """La divergencia es deliberada: este endpoint lee, el otro crea."""
        self.course_a.is_active = False
        self.course_a.save(update_fields=["is_active"])
        self.authenticate("admin.a@test.com")

        listar = self.client.get(self.url())
        asignar = self.client.post(
            reverse("course-assign", kwargs={"pk": self.course_a.pk}),
            {"collaborator_id": self.collaborator_a.id},
            format="json",
        )

        self.assertEqual(listar.status_code, status.HTTP_200_OK)
        self.assertEqual(asignar.status_code, status.HTTP_404_NOT_FOUND)

    # -- CA-5, CA-6, CA-7 -----------------------------------------------------

    def test_curso_oculto_devuelve_404(self):
        self.course_a.show = False
        self.course_a.save(update_fields=["show"])
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_curso_de_otra_organizacion_devuelve_404(self):
        self.enroll(self.course_b, self.collaborator_b)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url(self.course_b))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_curso_inexistente_devuelve_404(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(
            reverse("course-collaborators", kwargs={"pk": 999999})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -- CA-8, CA-9, CA-10 ----------------------------------------------------

    def test_inscripcion_oculta_no_se_lista(self):
        self.enroll(self.course_a, self.collaborator_a, show=False)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(list(response.data), [])

    def test_colaborador_oculto_no_se_lista(self):
        self.enroll(self.course_a, self.collaborator_a)
        self.collaborator_a.show = False
        self.collaborator_a.save(update_fields=["show"])
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(list(response.data), [])

    def test_usuario_oculto_o_inactivo_no_se_lista(self):
        self.enroll(self.course_a, self.collaborator_a)
        self.authenticate("admin.a@test.com")

        for field in ("show", "is_active"):
            setattr(self.collaborator_a.user, field, False)
            self.collaborator_a.user.save(update_fields=[field])
            with self.subTest(field=field):
                self.assertEqual(list(self.client.get(self.url()).data), [])
            setattr(self.collaborator_a.user, field, True)
            self.collaborator_a.user.save(update_fields=[field])

    # -- CA-11: la lista y el contador no pueden separarse --------------------

    def test_la_cantidad_coincide_con_el_contador_del_panel(self):
        """RN-5: el largo de la lista DEBE ser igual al enrolled_count."""
        segundo = self.create_collaborator("colab.2@test.com")
        tercero = self.create_collaborator("colab.3@test.com")
        cuarto = self.create_collaborator("colab.4@test.com")

        self.enroll(self.course_a, self.collaborator_a)
        self.enroll(self.course_a, segundo)
        self.enroll(self.course_a, tercero, show=False)  # oculta: no cuenta
        self.enroll(self.course_a, cuarto)
        cuarto.show = False  # colaborador de baja: tampoco cuenta
        cuarto.save(update_fields=["show"])

        self.authenticate("admin.a@test.com")

        lista = self.client.get(self.url())
        panel = self.client.get(reverse("course-enrollments"))
        fila = next(r for r in panel.data if r["id"] == self.course_a.id)

        self.assertEqual(len(lista.data), fila["enrolled_count"])
        self.assertEqual(len(lista.data), 2)

    # -- CA-12 ----------------------------------------------------------------

    def test_orden_por_fecha_descendente(self):
        segundo = self.create_collaborator("colab.2@test.com")
        primero = self.enroll(self.course_a, self.collaborator_a)
        ultimo = self.enroll(self.course_a, segundo)
        # auto_now_add fija la fecha al crear; se separan para que el orden sea
        # inequívoco y no dependa de la resolución del reloj.
        CourseCollaborator.objects.filter(pk=primero.pk).update(
            assigned_at="2026-01-01T00:00:00Z"
        )
        CourseCollaborator.objects.filter(pk=ultimo.pk).update(
            assigned_at="2026-06-01T00:00:00Z"
        )
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(
            self.emails(response), ["colab.2@test.com", "colab.a@test.com"]
        )

    # -- CA-13, CA-14 ---------------------------------------------------------

    def test_colaborador_no_puede_ver_los_inscritos(self):
        self.authenticate("colab.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_token_devuelve_401(self):
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -- CA-15 ----------------------------------------------------------------

    def test_consultas_no_crecen_con_la_cantidad_de_inscritos(self):
        """RN-8: select_related, nada de una consulta por colaborador."""
        self.enroll(self.course_a, self.collaborator_a)
        self.authenticate("admin.a@test.com")

        with CaptureQueriesContext(connection) as pocas:
            self.client.get(self.url())

        for indice in range(2, 8):
            self.enroll(
                self.course_a, self.create_collaborator(f"colab.{indice}@test.com")
            )

        with CaptureQueriesContext(connection) as muchas:
            response = self.client.get(self.url())

        self.assertEqual(len(response.data), 7)
        self.assertEqual(len(muchas), len(pocas))
