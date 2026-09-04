from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils import model_factories


class MyCoursesTests(APITestCase):
    """SPEC-006 — GET /course-collaborator/my-courses/ (CA-1 a CA-14)."""

    def setUp(self):
        self.org_a = model_factories.create_organization(name="Organización A")
        self.org_b = model_factories.create_organization(name="Organización B")
        model_factories.create_admin(
            organization=self.org_a,
            email="admin.a@test.com",
            password="password123",
        )
        # Dos colaboradores del MISMO tenant: el aislamiento que importa acá no es
        # solo entre organizaciones, sino entre compañeros de la misma.
        self.ana = model_factories.create_collaborator(
            organization=self.org_a,
            email="ana@test.com",
            first_name="Ana",
            last_name="Pérez",
            password="password123",
        )
        self.luis = model_factories.create_collaborator(
            organization=self.org_a,
            email="luis@test.com",
            first_name="Luis",
            last_name="Rojas",
            password="password123",
        )
        self.bruno = model_factories.create_collaborator(
            organization=self.org_b,
            email="bruno@test.com",
            first_name="Bruno",
            last_name="Soto",
            password="password123",
        )

        self.curso_de_ana = Course.objects.create(
            full_name="Prevención de riesgos",
            description="Curso obligatorio de inducción",
            duration_hours=4,
            version="2.0",
            organization=self.org_a,
        )
        self.curso_de_luis = Course.objects.create(
            full_name="Ergonomía en oficina",
            organization=self.org_a,
        )
        self.curso_ajeno = Course.objects.create(
            full_name="Curso de otra organización",
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

    def url(self):
        return reverse("my-courses")

    def enroll(self, course, collaborator, **kwargs):
        return CourseCollaborator.objects.create(
            course=course, collaborator=collaborator, **kwargs
        )

    def nombres(self, response):
        return [row["course"]["full_name"] for row in response.data]

    # -- CA-1, CA-2, CA-3 -----------------------------------------------------

    def test_colaborador_ve_sus_cursos_asignados(self):
        self.enroll(self.curso_de_ana, self.ana)
        self.authenticate("ana@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.nombres(response), ["Prevención de riesgos"])

    def test_cada_fila_expone_el_contrato_declarado(self):
        enrollment = self.enroll(self.curso_de_ana, self.ana)
        self.authenticate("ana@test.com")

        response = self.client.get(self.url())

        fila = response.data[0]
        self.assertEqual(set(fila.keys()), {"id", "assigned_at", "course"})
        self.assertEqual(fila["id"], enrollment.id)
        self.assertTrue(fila["assigned_at"])
        self.assertEqual(
            dict(fila["course"]),
            {
                "id": self.curso_de_ana.id,
                "full_name": "Prevención de riesgos",
                "description": "Curso obligatorio de inducción",
                "duration_hours": 4,
                "version": "2.0",
                "is_active": True,
            },
        )

    def test_colaborador_sin_cursos_recibe_lista_vacia(self):
        self.authenticate("ana@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data), [])

    # -- CA-4, CA-5: el aislamiento, en las dos direcciones -------------------

    def test_no_ve_los_cursos_de_un_companero_de_su_organizacion(self):
        """CA-4: Ana y Luis son del mismo tenant; aun así no se ven entre sí."""
        self.enroll(self.curso_de_ana, self.ana)
        self.enroll(self.curso_de_luis, self.luis)
        self.authenticate("ana@test.com")

        response = self.client.get(self.url())

        self.assertEqual(self.nombres(response), ["Prevención de riesgos"])

    def test_cada_colaborador_ve_lo_suyo(self):
        self.enroll(self.curso_de_ana, self.ana)
        self.enroll(self.curso_de_luis, self.luis)

        self.authenticate("luis@test.com")
        self.assertEqual(self.nombres(self.client.get(self.url())), ["Ergonomía en oficina"])

        self.authenticate("ana@test.com")
        self.assertEqual(
            self.nombres(self.client.get(self.url())), ["Prevención de riesgos"]
        )

    def test_otra_organizacion_no_afecta_el_resultado(self):
        self.enroll(self.curso_de_ana, self.ana)
        self.enroll(self.curso_ajeno, self.bruno)
        self.authenticate("ana@test.com")

        response = self.client.get(self.url())

        self.assertEqual(self.nombres(response), ["Prevención de riesgos"])

    # -- CA-6 -----------------------------------------------------------------

    def test_query_params_no_permiten_suplantar_a_otro(self):
        self.enroll(self.curso_de_ana, self.ana)
        self.enroll(self.curso_de_luis, self.luis)
        self.authenticate("ana@test.com")

        response = self.client.get(
            self.url(),
            {
                "collaborator": self.luis.id,
                "collaborator_id": self.luis.id,
                "organization": self.org_b.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.nombres(response), ["Prevención de riesgos"])

    # -- CA-7, CA-8, CA-9 -----------------------------------------------------

    def test_inscripcion_oculta_no_se_lista(self):
        self.enroll(self.curso_de_ana, self.ana, show=False)
        self.authenticate("ana@test.com")

        self.assertEqual(list(self.client.get(self.url()).data), [])

    def test_curso_oculto_no_se_lista(self):
        self.enroll(self.curso_de_ana, self.ana)
        self.curso_de_ana.show = False
        self.curso_de_ana.save(update_fields=["show"])
        self.authenticate("ana@test.com")

        self.assertEqual(list(self.client.get(self.url()).data), [])

    def test_curso_inactivo_si_se_lista_marcado(self):
        """RN-5: un curso retirado no desinscribe a nadie; ocultarlo taparía
        trabajo pendiente."""
        self.enroll(self.curso_de_ana, self.ana)
        self.curso_de_ana.is_active = False
        self.curso_de_ana.save(update_fields=["is_active"])
        self.authenticate("ana@test.com")

        response = self.client.get(self.url())

        self.assertEqual(len(response.data), 1)
        self.assertFalse(response.data[0]["course"]["is_active"])

    # -- CA-10 ----------------------------------------------------------------

    def test_no_expone_datos_de_otros_colaboradores(self):
        self.enroll(self.curso_de_ana, self.ana)
        self.enroll(self.curso_de_ana, self.luis)
        self.authenticate("ana@test.com")

        response = self.client.get(self.url())

        self.assertEqual(len(response.data), 1)
        self.assertNotIn("enrolled_count", response.data[0]["course"])
        self.assertNotIn("collaborator", response.data[0])
        self.assertNotIn("luis@test.com", str(response.data))

    # -- CA-11 ----------------------------------------------------------------

    def test_orden_por_fecha_descendente(self):
        antiguo = self.enroll(self.curso_de_ana, self.ana)
        reciente = self.enroll(self.curso_de_luis, self.ana)
        CourseCollaborator.objects.filter(pk=antiguo.pk).update(
            assigned_at="2026-01-01T00:00:00Z"
        )
        CourseCollaborator.objects.filter(pk=reciente.pk).update(
            assigned_at="2026-06-01T00:00:00Z"
        )
        self.authenticate("ana@test.com")

        response = self.client.get(self.url())

        self.assertEqual(
            self.nombres(response),
            ["Ergonomía en oficina", "Prevención de riesgos"],
        )

    # -- CA-12, CA-13 ---------------------------------------------------------

    def test_admin_no_puede_ver_mis_cursos(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_token_devuelve_401(self):
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -- CA-14 ----------------------------------------------------------------

    def test_consultas_no_crecen_con_la_cantidad_de_cursos(self):
        """RN-10: select_related, nada de una consulta por curso."""
        self.enroll(self.curso_de_ana, self.ana)
        self.authenticate("ana@test.com")

        with CaptureQueriesContext(connection) as pocas:
            self.client.get(self.url())

        for indice in range(2, 8):
            curso = Course.objects.create(
                full_name=f"Curso {indice}", organization=self.org_a
            )
            self.enroll(curso, self.ana)

        with CaptureQueriesContext(connection) as muchas:
            response = self.client.get(self.url())

        self.assertEqual(len(response.data), 7)
        self.assertEqual(len(muchas), len(pocas))
