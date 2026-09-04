from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils import model_factories


class EditCourseTests(APITestCase):
    """SPEC-007 — GET/PATCH/DELETE /course/{id}/ (CA-1 a CA-13, CA-37 y CA-38)."""

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
        self.course_a = Course.objects.create(
            full_name="Prevención de riesgos",
            description="Curso base",
            duration_hours=4,
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
        return reverse("course-detail", kwargs={"pk": (course or self.course_a).pk})

    def enroll(self, course=None, collaborator=None, **kwargs):
        return CourseCollaborator.objects.create(
            course=course or self.course_a,
            collaborator=collaborator or self.collaborator_a,
            **kwargs,
        )

    # -- corregir un curso ----------------------------------------------------

    def test_admin_puede_corregir_los_datos_del_curso(self):
        """CA-1: PATCH válido devuelve 200 y persiste el cambio."""
        self.authenticate("admin.a@test.com")

        response = self.client.patch(
            self.url(),
            {
                "full_name": "Prevención de riesgos laborales",
                "description": "Corregido",
                "duration_hours": 8,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course_a.refresh_from_db()
        self.assertEqual(self.course_a.full_name, "Prevención de riesgos laborales")
        self.assertEqual(self.course_a.description, "Corregido")
        self.assertEqual(self.course_a.duration_hours, 8)

    def test_patch_ignora_la_version_del_body(self):
        """CA-2: RN-4 — la versión solo cambia publicando una versión nueva."""
        self.authenticate("admin.a@test.com")

        response = self.client.patch(
            self.url(),
            {"full_name": "Nombre corregido", "version": "9.9"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course_a.refresh_from_db()
        self.assertEqual(self.course_a.version, "1.0")
        self.assertEqual(self.course_a.full_name, "Nombre corregido")

    def test_patch_ignora_los_campos_de_control(self):
        """CA-3: RN-3 — organización, show y created_at no se tocan desde el body."""
        self.authenticate("admin.a@test.com")
        created_at_original = self.course_a.created_at

        response = self.client.patch(
            self.url(),
            {
                "full_name": "Nombre corregido",
                "organization": self.org_b.pk,
                "organization_id": self.org_b.pk,
                "show": False,
                "created_at": "2000-01-01T00:00:00Z",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course_a.refresh_from_db()
        self.assertEqual(self.course_a.organization, self.org_a)
        self.assertTrue(self.course_a.show)
        self.assertEqual(self.course_a.created_at, created_at_original)

    def test_patch_rechaza_los_nombres_invalidos(self):
        """CA-4: RN-5 — piso de 3 caracteres y al menos una letra."""
        self.authenticate("admin.a@test.com")

        for nombre in ["", ".", "..", "---", "12", "a", "  a  "]:
            with self.subTest(nombre=nombre):
                response = self.client.patch(
                    self.url(), {"full_name": nombre}, format="json"
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("full_name", response.data)
                self.course_a.refresh_from_db()
                self.assertEqual(self.course_a.full_name, "Prevención de riesgos")

    def test_patch_rechaza_una_duracion_no_positiva(self):
        """CA-5: RN-5b — duration_hours entero mayor o igual a 1."""
        self.authenticate("admin.a@test.com")

        for duracion in [0, -3]:
            with self.subTest(duracion=duracion):
                response = self.client.patch(
                    self.url(), {"duration_hours": duracion}, format="json"
                )

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("duration_hours", response.data)
                self.course_a.refresh_from_db()
                self.assertEqual(self.course_a.duration_hours, 4)

    def test_patch_sobre_curso_no_disponible_devuelve_404(self):
        """CA-6: RN-2 — otro tenant, oculto o inexistente son indistinguibles."""
        self.authenticate("admin.a@test.com")
        oculto = Course.objects.create(
            full_name="Curso oculto", organization=self.org_a, show=False
        )

        casos = {
            "otro tenant": self.url(self.course_b),
            "oculto": self.url(oculto),
            "inexistente": reverse("course-detail", kwargs={"pk": 9999}),
        }
        for caso, url in casos.items():
            with self.subTest(caso=caso):
                response = self.client.patch(
                    url, {"full_name": "Intento de edición"}, format="json"
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.course_b.refresh_from_db()
        self.assertEqual(self.course_b.full_name, "Curso ajeno")

    def test_patch_da_de_baja_y_reactiva_el_curso(self):
        """CA-7: RN-6 — is_active va y vuelve."""
        self.authenticate("admin.a@test.com")

        baja = self.client.patch(self.url(), {"is_active": False}, format="json")
        self.assertEqual(baja.status_code, status.HTTP_200_OK)
        self.course_a.refresh_from_db()
        self.assertFalse(self.course_a.is_active)

        alta = self.client.patch(self.url(), {"is_active": True}, format="json")
        self.assertEqual(alta.status_code, status.HTTP_200_OK)
        self.course_a.refresh_from_db()
        self.assertTrue(self.course_a.is_active)

    def test_dar_de_baja_no_toca_las_inscripciones(self):
        """CA-8: RN-6 — el retiro no desinscribe a nadie."""
        self.enroll()
        self.authenticate("admin.a@test.com")

        self.client.patch(self.url(), {"is_active": False}, format="json")

        detalle = self.client.get(self.url())
        self.assertEqual(detalle.data["enrolled_count"], 1)

        self.client.credentials()
        self.authenticate("colab.a@test.com")
        mis_cursos = self.client.get(reverse("my-courses"))
        self.assertEqual(
            [fila["course"]["id"] for fila in mis_cursos.data], [self.course_a.pk]
        )

    def test_get_devuelve_el_curso_con_su_conteo(self):
        """CA-9: el detalle incluye enrolled_count."""
        self.enroll()
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.course_a.pk)
        self.assertEqual(response.data["full_name"], "Prevención de riesgos")
        self.assertEqual(response.data["version"], "1.0")
        self.assertEqual(response.data["enrolled_count"], 1)

    # -- eliminar un curso ----------------------------------------------------

    def test_delete_es_borrado_logico(self):
        """CA-10: RN-7 — show=False y la fila sigue en la base."""
        self.authenticate("admin.a@test.com")

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Course.objects.filter(pk=self.course_a.pk).exists())
        self.course_a.refresh_from_db()
        self.assertFalse(self.course_a.show)

    def test_el_curso_eliminado_desaparece_de_los_listados(self):
        """CA-11: no se lista, no está en el panel y su detalle da 404."""
        self.authenticate("admin.a@test.com")
        self.client.delete(self.url())

        listado = self.client.get(reverse("course-list"))
        self.assertNotIn(self.course_a.pk, [curso["id"] for curso in listado.data])

        panel = self.client.get(reverse("course-enrollments"))
        self.assertNotIn(self.course_a.pk, [curso["id"] for curso in panel.data])

        detalle = self.client.get(self.url())
        self.assertEqual(detalle.status_code, status.HTTP_404_NOT_FOUND)

    def test_no_se_puede_eliminar_un_curso_con_inscritos(self):
        """CA-12: RN-7 — eliminar es para el curso creado por error, no para
        hacer desaparecer historial."""
        self.enroll()
        self.authenticate("admin.a@test.com")

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.course_a.refresh_from_db()
        self.assertTrue(self.course_a.show)

    def test_se_puede_eliminar_tras_desinscribir_a_todos(self):
        """CA-13: la inscripción oculta ya no bloquea el borrado."""
        inscripcion = self.enroll()
        inscripcion.show = False
        inscripcion.save()
        self.authenticate("admin.a@test.com")

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.course_a.refresh_from_db()
        self.assertFalse(self.course_a.show)

    # -- permisos -------------------------------------------------------------

    def test_sin_token_devuelve_401(self):
        """CA-37."""
        for metodo in [self.client.get, self.client.delete]:
            with self.subTest(metodo=metodo.__name__):
                self.assertEqual(
                    metodo(self.url()).status_code, status.HTTP_401_UNAUTHORIZED
                )

        response = self.client.patch(self.url(), {"full_name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_colaborador_devuelve_403(self):
        """CA-38."""
        self.authenticate("colab.a@test.com")

        for metodo in [self.client.get, self.client.delete]:
            with self.subTest(metodo=metodo.__name__):
                self.assertEqual(
                    metodo(self.url()).status_code, status.HTTP_403_FORBIDDEN
                )

        response = self.client.patch(self.url(), {"full_name": "X"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
