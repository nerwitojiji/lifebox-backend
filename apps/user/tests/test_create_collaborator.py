from unittest.mock import patch

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.user.models import Collaborator, User
from utils import model_factories


class CreateCollaboratorTests(APITestCase):
    """SPEC-002 — alta y regeneración de contraseña de colaboradores."""

    def setUp(self):
        self.org_a = model_factories.create_organization(name="Organización A")
        self.org_b = model_factories.create_organization(name="Organización B")
        self.admin_a = model_factories.create_admin(
            organization=self.org_a,
            email="admin.a@test.com",
            password="password123",
        )
        self.admin_b = model_factories.create_admin(
            organization=self.org_b,
            email="admin.b@test.com",
            password="password123",
        )
        self.existing_collaborator = model_factories.create_collaborator(
            organization=self.org_a,
            email="colab.a@test.com",
            password="password123",
        )
        self.list_url = reverse("collaborator-list")
        self.login_url = reverse("user-login")

    def authenticate(self, email, password="password123"):
        response = self.client.post(
            self.login_url,
            {"email": email, "password": password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")

    def create_collaborator(self, **fields):
        payload = {
            "first_name": "Ana",
            "last_name": "Pérez",
            "email": "ana@test.com",
        }
        payload.update(fields)
        return self.client.post(self.list_url, payload, format="json")

    def reset_url(self, collaborator=None):
        collaborator = collaborator or self.existing_collaborator
        return reverse(
            "collaborator-reset-password",
            kwargs={"pk": collaborator.pk},
        )

    def test_admin_puede_crear_colaborador(self):
        self.authenticate("admin.a@test.com")

        response = self.create_collaborator()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collaborator = Collaborator.objects.get(pk=response.data["id"])
        self.assertEqual(collaborator.organization, self.org_a)
        self.assertTrue(collaborator.show)
        self.assertEqual(collaborator.user.email, "ana@test.com")
        self.assertEqual(collaborator.user.first_name, "Ana")
        self.assertEqual(collaborator.user.last_name, "Pérez")
        self.assertTrue(collaborator.user.is_active)
        self.assertEqual(response.data["full_name"], "Ana Pérez")

    def test_last_name_es_opcional(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.list_url,
            {"first_name": "Bruno", "email": "bruno@test.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collaborator = Collaborator.objects.get(pk=response.data["id"])
        self.assertEqual(collaborator.user.last_name, "")

    def test_respuesta_incluye_password_temporal_y_la_guarda_hasheada(self):
        self.authenticate("admin.a@test.com")

        response = self.create_collaborator()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        temporary_password = response.data.get("temporary_password")
        self.assertTrue(temporary_password)
        user = User.objects.get(email="ana@test.com")
        self.assertNotEqual(user.password, temporary_password)
        self.assertTrue(user.check_password(temporary_password))

    def test_cada_colaborador_recibe_una_password_distinta(self):
        self.authenticate("admin.a@test.com")

        first = self.create_collaborator(email="uno@test.com")
        second = self.create_collaborator(email="dos@test.com")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(
            first.data["temporary_password"],
            second.data["temporary_password"],
        )

    def test_listado_no_expone_la_password(self):
        self.authenticate("admin.a@test.com")
        self.assertEqual(
            self.create_collaborator().status_code,
            status.HTTP_201_CREATED,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data:
            self.assertNotIn("temporary_password", item)
            self.assertNotIn("password", item)

    def test_colaborador_creado_puede_iniciar_sesion(self):
        self.authenticate("admin.a@test.com")
        creation = self.create_collaborator()
        self.assertEqual(creation.status_code, status.HTTP_201_CREATED)

        self.client.credentials()
        login = self.client.post(
            self.login_url,
            {
                "email": "ana@test.com",
                "password": creation.data["temporary_password"],
            },
            format="json",
        )

        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertTrue(login.data.get("token"))
        self.assertEqual(login.data["user"]["role"], "collaborator")
        self.assertEqual(login.data["user"]["organization_id"], self.org_a.pk)

    def test_campos_invalidos_devuelven_400(self):
        self.authenticate("admin.a@test.com")
        users_before = User.objects.count()
        cases = [
            ({"first_name": "Ana"}, "email"),
            ({"first_name": "Ana", "email": ""}, "email"),
            ({"first_name": "Ana", "email": "no-es-un-correo"}, "email"),
            ({"email": "ana@test.com"}, "first_name"),
            ({"first_name": "", "email": "ana@test.com"}, "first_name"),
            ({"first_name": "   ", "email": "ana@test.com"}, "first_name"),
        ]

        for payload, field in cases:
            with self.subTest(payload=payload):
                response = self.client.post(self.list_url, payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)

        self.assertEqual(User.objects.count(), users_before)

    def test_email_duplicado_devuelve_400(self):
        self.authenticate("admin.a@test.com")
        users_before = User.objects.count()

        for email in ("colab.a@test.com", "admin.b@test.com"):
            with self.subTest(email=email):
                response = self.create_collaborator(email=email)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("email", response.data)

        self.assertEqual(User.objects.count(), users_before)

    def test_organizacion_del_body_es_ignorada(self):
        self.authenticate("admin.a@test.com")

        response = self.create_collaborator(
            organization=self.org_b.pk,
            organization_id=self.org_b.pk,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        collaborator = Collaborator.objects.get(pk=response.data["id"])
        self.assertEqual(collaborator.organization, self.org_a)

    def test_password_del_body_es_ignorada(self):
        self.authenticate("admin.a@test.com")

        response = self.create_collaborator(password="hackeada")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="ana@test.com")
        self.assertFalse(user.check_password("hackeada"))
        self.assertTrue(user.check_password(response.data["temporary_password"]))

    def test_creacion_es_atomica_si_falla_el_perfil(self):
        self.authenticate("admin.a@test.com")
        users_before = User.objects.count()

        with patch(
            "apps.user.collaborator_views.Collaborator.objects.create",
            side_effect=RuntimeError("fallo simulado"),
        ):
            with self.assertRaises(RuntimeError):
                self.create_collaborator()

        self.assertEqual(User.objects.count(), users_before)
        self.assertFalse(User.objects.filter(email="ana@test.com").exists())

    def test_colaborador_no_puede_crear_colaboradores(self):
        self.authenticate("colab.a@test.com")
        users_before = User.objects.count()

        response = self.create_collaborator()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(User.objects.count(), users_before)

    def test_crear_colaborador_sin_token_devuelve_401(self):
        users_before = User.objects.count()

        response = self.create_collaborator()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(User.objects.count(), users_before)

    def test_colaborador_creado_aparece_en_listado(self):
        self.authenticate("admin.a@test.com")
        self.assertEqual(
            self.create_collaborator().status_code,
            status.HTTP_201_CREATED,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("ana@test.com", [item["email"] for item in response.data])

    def test_colaborador_no_es_visible_para_otra_organizacion(self):
        self.authenticate("admin.a@test.com")
        self.assertEqual(
            self.create_collaborator().status_code,
            status.HTTP_201_CREATED,
        )

        self.authenticate("admin.b@test.com")
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("ana@test.com", [item["email"] for item in response.data])

    def test_admin_puede_regenerar_password(self):
        self.authenticate("admin.a@test.com")

        response = self.client.post(self.reset_url(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        temporary_password = response.data.get("temporary_password")
        self.assertTrue(temporary_password)
        self.assertNotEqual(temporary_password, "password123")
        self.existing_collaborator.user.refresh_from_db()
        self.assertTrue(
            self.existing_collaborator.user.check_password(temporary_password)
        )

    def test_password_anterior_deja_de_servir_tras_regenerar(self):
        self.authenticate("admin.a@test.com")
        response = self.client.post(self.reset_url(), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.credentials()
        login = self.client.post(
            self.login_url,
            {"email": "colab.a@test.com", "password": "password123"},
            format="json",
        )

        self.assertEqual(login.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_regenerada_sirve_para_login(self):
        self.authenticate("admin.a@test.com")
        response = self.client.post(self.reset_url(), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.credentials()
        login = self.client.post(
            self.login_url,
            {
                "email": "colab.a@test.com",
                "password": response.data["temporary_password"],
            },
            format="json",
        )

        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertTrue(login.data.get("token"))
        self.assertEqual(login.data["user"]["role"], "collaborator")

    def test_colaborador_no_puede_regenerar_password(self):
        self.authenticate("colab.a@test.com")

        response = self.client.post(self.reset_url(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_regenerar_password_sin_token_devuelve_401(self):
        response = self.client.post(self.reset_url(), format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regenerar_password_de_otra_organizacion_devuelve_404(self):
        self.authenticate("admin.b@test.com")

        response = self.client.post(self.reset_url(), format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_listado_no_expone_password_tras_regenerar(self):
        self.authenticate("admin.a@test.com")
        self.assertEqual(
            self.client.post(self.reset_url(), format="json").status_code,
            status.HTTP_200_OK,
        )

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data:
            self.assertNotIn("temporary_password", item)
            self.assertNotIn("password", item)

    def test_regenerar_password_no_modifica_otros_datos(self):
        collaborator = self.existing_collaborator
        original = {
            "email": collaborator.user.email,
            "first_name": collaborator.user.first_name,
            "last_name": collaborator.user.last_name,
            "organization_id": collaborator.organization_id,
        }
        self.authenticate("admin.a@test.com")

        response = self.client.post(self.reset_url(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        collaborator.refresh_from_db()
        collaborator.user.refresh_from_db()
        self.assertEqual(collaborator.user.email, original["email"])
        self.assertEqual(collaborator.user.first_name, original["first_name"])
        self.assertEqual(collaborator.user.last_name, original["last_name"])
        self.assertEqual(collaborator.organization_id, original["organization_id"])

    # -- SPEC-009: el aviso de cambiar la contraseña temporal -----------------

    def test_el_colaborador_creado_debe_cambiar_su_contrasena(self):
        """CA-10: RN-9 — nació con una contraseña que eligió el servidor y vio
        el administrador; hay que avisarle."""
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.list_url,
            {"first_name": "Nueva", "email": "nueva@test.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        usuario = User.objects.get(email="nueva@test.com")
        self.assertTrue(usuario.must_change_password)

    def test_regenerar_la_contrasena_vuelve_a_encender_el_aviso(self):
        """CA-11: RN-9 — sin esto, el flag se apagaría para siempre después del
        primer cambio y la persona no se enteraría de la temporal nueva."""
        collaborator = self.existing_collaborator
        collaborator.user.must_change_password = False
        collaborator.user.save()
        self.authenticate("admin.a@test.com")

        response = self.client.post(self.reset_url(), format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        collaborator.user.refresh_from_db()
        self.assertTrue(collaborator.user.must_change_password)

    def test_el_admin_no_arrastra_el_aviso(self):
        """CA-12: RN-9 — nunca recibió una contraseña temporal."""
        self.assertFalse(self.admin_a.user.must_change_password)
