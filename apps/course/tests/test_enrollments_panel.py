from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils import model_factories


class EnrollmentsPanelTests(APITestCase):
    """SPEC-004 — GET /course/enrollments/ (CA-1 a CA-15)."""

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

    # -- utilidades -----------------------------------------------------------

    def authenticate(self, email):
        response = self.client.post(
            reverse("user-login"),
            {"email": email, "password": "password123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")

    def url(self):
        return reverse("course-enrollments")

    def create_course(self, full_name, organization=None, **kwargs):
        return Course.objects.create(
            full_name=full_name,
            organization=organization or self.org_a,
            **kwargs,
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

    def names_in_order(self, response):
        return [row["full_name"] for row in response.data]

    def row_for(self, response, course):
        return next(row for row in response.data if row["id"] == course.id)

    # -- CA-1, CA-2 -----------------------------------------------------------

    def test_admin_obtiene_una_fila_por_curso_visible_del_tenant(self):
        self.create_course("Prevención de riesgos")
        self.create_course("Ergonomía en oficina")
        self.create_course("Curso ajeno", organization=self.org_b)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(
            sorted(self.names_in_order(response)),
            ["Ergonomía en oficina", "Prevención de riesgos"],
        )

    def test_cada_fila_expone_el_contrato_declarado(self):
        course = self.create_course("Prevención de riesgos", version="2.0")
        self.enroll(course, self.collaborator_a)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            dict(response.data[0]),
            {
                "id": course.id,
                "full_name": "Prevención de riesgos",
                "version": "2.0",
                "is_active": True,
                "enrolled_count": 1,
            },
        )

    # -- CA-3, CA-4, CA-5 -----------------------------------------------------

    def test_curso_sin_inscritos_aparece_con_conteo_cero(self):
        course = self.create_course("Ergonomía en oficina")
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.row_for(response, course)["enrolled_count"], 0)

    def test_curso_inactivo_aparece_marcado_y_despues_de_los_activos(self):
        inactivo = self.create_course("Inducción corporativa", is_active=False)
        activo = self.create_course("Ergonomía en oficina")
        self.enroll(inactivo, self.collaborator_a)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fila = self.row_for(response, inactivo)
        self.assertFalse(fila["is_active"])
        self.assertEqual(fila["enrolled_count"], 1)
        self.assertEqual(
            self.names_in_order(response),
            [activo.full_name, inactivo.full_name],
        )

    def test_curso_oculto_no_aparece(self):
        self.create_course("Curso vigente")
        self.create_course("Curso dado de baja", show=False)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.names_in_order(response), ["Curso vigente"])

    # -- CA-6 -----------------------------------------------------------------

    def test_otra_organizacion_no_altera_filas_ni_conteos(self):
        propio = self.create_course("Prevención de riesgos")
        ajeno = self.create_course("Curso ajeno", organization=self.org_b)
        self.enroll(propio, self.collaborator_a)
        self.enroll(ajeno, self.collaborator_b)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(self.row_for(response, propio)["enrolled_count"], 1)

    def test_cada_admin_ve_solo_los_cursos_de_su_organizacion(self):
        self.create_course("Prevención de riesgos")
        ajeno = self.create_course("Curso ajeno", organization=self.org_b)
        self.enroll(ajeno, self.collaborator_b)
        self.authenticate("admin.b@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.names_in_order(response), ["Curso ajeno"])
        self.assertEqual(self.row_for(response, ajeno)["enrolled_count"], 1)

    # -- CA-7, CA-8, CA-9 -----------------------------------------------------

    def test_inscripcion_oculta_no_se_cuenta(self):
        course = self.create_course("Prevención de riesgos")
        self.enroll(course, self.collaborator_a, show=False)
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(self.row_for(response, course)["enrolled_count"], 0)

    def test_colaborador_oculto_no_se_cuenta(self):
        course = self.create_course("Prevención de riesgos")
        self.enroll(course, self.collaborator_a)
        self.collaborator_a.show = False
        self.collaborator_a.save(update_fields=["show"])
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(self.row_for(response, course)["enrolled_count"], 0)

    def test_usuario_oculto_o_inactivo_no_se_cuenta(self):
        course = self.create_course("Prevención de riesgos")
        self.enroll(course, self.collaborator_a)
        self.authenticate("admin.a@test.com")

        for field in ("show", "is_active"):
            setattr(self.collaborator_a.user, field, False)
            self.collaborator_a.user.save(update_fields=[field])
            with self.subTest(field=field):
                response = self.client.get(self.url())
                self.assertEqual(
                    self.row_for(response, course)["enrolled_count"], 0
                )
            setattr(self.collaborator_a.user, field, True)
            self.collaborator_a.user.save(update_fields=[field])

    def test_dar_de_baja_al_colaborador_es_reversible(self):
        """PA-8: la inscripción no se borra, solo deja de contarse."""
        course = self.create_course("Prevención de riesgos")
        self.enroll(course, self.collaborator_a)
        self.collaborator_a.show = False
        self.collaborator_a.save(update_fields=["show"])
        self.authenticate("admin.a@test.com")

        self.assertEqual(
            self.row_for(self.client.get(self.url()), course)["enrolled_count"], 0
        )

        self.collaborator_a.show = True
        self.collaborator_a.save(update_fields=["show"])

        self.assertEqual(
            self.row_for(self.client.get(self.url()), course)["enrolled_count"], 1
        )
        self.assertEqual(CourseCollaborator.objects.count(), 1)

    # -- CA-10 ----------------------------------------------------------------

    def test_orden_agrupa_activos_y_ordena_por_conteo_y_nombre(self):
        vacio = self.create_course("Zafiro")
        popular = self.create_course("Prevención de riesgos")
        empate_alfa = self.create_course("Alfa")
        empate_beta = self.create_course("Beta")
        inactivo = self.create_course("Inducción corporativa", is_active=False)

        segundo = self.create_collaborator("colab.2@test.com")
        tercero = self.create_collaborator("colab.3@test.com")

        for collaborator in (self.collaborator_a, segundo, tercero):
            self.enroll(popular, collaborator)
            self.enroll(inactivo, collaborator)
        self.enroll(empate_alfa, self.collaborator_a)
        self.enroll(empate_beta, self.collaborator_a)

        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(
            self.names_in_order(response),
            [
                popular.full_name,  # activo, 3 inscritos
                empate_alfa.full_name,  # activo, 1 inscrito, alfabético
                empate_beta.full_name,  # activo, 1 inscrito
                vacio.full_name,  # activo, 0 inscritos
                inactivo.full_name,  # inactivo aunque tenga 3 inscritos
            ],
        )

    # -- CA-11 ----------------------------------------------------------------

    def test_admin_sin_cursos_recibe_lista_vacia(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(list(response.data), [])

    # -- CA-12, CA-13 ---------------------------------------------------------

    def test_colaborador_no_puede_ver_el_panel(self):
        self.create_course("Prevención de riesgos")
        self.authenticate("colab.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_panel_sin_token_devuelve_401(self):
        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -- CA-14 ----------------------------------------------------------------

    def test_query_params_de_organizacion_son_ignorados(self):
        propio = self.create_course("Prevención de riesgos")
        self.create_course("Curso ajeno", organization=self.org_b)
        self.authenticate("admin.a@test.com")

        response = self.client.get(
            self.url(),
            {"organization": self.org_b.id, "organization_id": self.org_b.id},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.names_in_order(response), [propio.full_name])

    # -- CA-15 ----------------------------------------------------------------

    def test_consultas_no_crecen_con_la_cantidad_de_cursos(self):
        """RN-6: la agregación es única; nada de una consulta por curso."""
        primero = self.create_course("Curso 1")
        self.enroll(primero, self.collaborator_a)
        self.authenticate("admin.a@test.com")

        with CaptureQueriesContext(connection) as pocas:
            self.client.get(self.url())

        for indice in range(2, 8):
            course = self.create_course(f"Curso {indice}")
            collaborator = self.create_collaborator(f"colab.{indice}@test.com")
            self.enroll(course, collaborator)
            self.enroll(course, self.collaborator_a)

        with CaptureQueriesContext(connection) as muchas:
            response = self.client.get(self.url())

        self.assertEqual(len(response.data), 7)
        self.assertEqual(len(muchas), len(pocas))


class CourseListEnrolledCountTests(APITestCase):
    """SPEC-004 — CA-16: GET /course/ incorpora enrolled_count sin romper nada."""

    def setUp(self):
        self.org_a = model_factories.create_organization(name="Organización A")
        model_factories.create_admin(
            organization=self.org_a,
            email="admin.a@test.com",
            password="password123",
        )
        self.collaborator_a = model_factories.create_collaborator(
            organization=self.org_a,
            email="colab.a@test.com",
            password="password123",
        )
        self.course = Course.objects.create(
            full_name="Prevención de riesgos",
            description="Curso obligatorio",
            duration_hours=4,
            version="2.0",
            organization=self.org_a,
        )

    def authenticate(self, email):
        response = self.client.post(
            reverse("user-login"),
            {"email": email, "password": "password123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")

    def test_listado_de_cursos_incluye_enrolled_count(self):
        CourseCollaborator.objects.create(
            course=self.course, collaborator=self.collaborator_a
        )
        self.authenticate("admin.a@test.com")

        response = self.client.get(reverse("course-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        fila = response.data[0]
        self.assertEqual(fila["enrolled_count"], 1)
        self.assertEqual(
            set(fila.keys()),
            {
                "id",
                "full_name",
                "description",
                "duration_hours",
                "version",
                "is_active",
                "created_at",
                "enrolled_count",
                "materials",
            },
        )

    def test_listado_de_cursos_conserva_los_campos_previos(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(reverse("course-list"))

        fila = response.data[0]
        self.assertEqual(fila["id"], self.course.id)
        self.assertEqual(fila["full_name"], "Prevención de riesgos")
        self.assertEqual(fila["description"], "Curso obligatorio")
        self.assertEqual(fila["duration_hours"], 4)
        self.assertEqual(fila["version"], "2.0")
        self.assertTrue(fila["is_active"])
        self.assertTrue(fila["created_at"])
        self.assertEqual(fila["enrolled_count"], 0)

    def test_enrolled_count_del_listado_usa_el_mismo_criterio(self):
        CourseCollaborator.objects.create(
            course=self.course, collaborator=self.collaborator_a, show=False
        )
        self.authenticate("admin.a@test.com")

        response = self.client.get(reverse("course-list"))

        self.assertEqual(response.data[0]["enrolled_count"], 0)
