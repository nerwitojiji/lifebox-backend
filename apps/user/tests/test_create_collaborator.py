from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.user.models import Collaborator, User
from utils import model_factories


class CreateCollaboratorTests(APITestCase):
    """SPEC-002 — POST /collaborator/ (criterios de aceptación CA-1 a CA-12)."""

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
        self.url = reverse("collaborator-list")
        self.login_url = reverse("user-login")

    def authenticate(self, email):
        response = self.client.post(
            self.login_url,
            {"email": email, "password": "password123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")

    def crear_colaborador(self, **campos):
        """POST del camino feliz; devuelve la respuesta para inspeccionarla."""
        payload = {
            "first_name": "Ana",
            "last_name": "Pérez",
            "email": "ana@test.com",
        }
        payload.update(campos)
        return self.client.post(self.url, payload, format="json")

    def test_admin_puede_crear_colaborador(self):
        """CA-1: 201, se crean User + perfil, en la organización del admin."""
        self.authenticate("admin.a@test.com")

        response = self.crear_colaborador()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

        colaborador = Collaborator.objects.get(id=response.data["id"])
        self.assertEqual(colaborador.organization, self.org_a)  # RN-6
        self.assertTrue(colaborador.show)  # RN-11
        self.assertEqual(colaborador.user.email, "ana@test.com")
        self.assertEqual(colaborador.user.first_name, "Ana")
        self.assertEqual(colaborador.user.last_name, "Pérez")
        self.assertTrue(colaborador.user.is_active)  # RN-11
        self.assertEqual(response.data["full_name"], "Ana Pérez")

    def test_last_name_es_opcional(self):
        """RN-5: sin last_name se persiste vacío, no falla."""
        self.authenticate("admin.a@test.com")

        response = self.client.post(
            self.url,
            {"first_name": "Bruno", "email": "bruno@test.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        colaborador = Collaborator.objects.get(id=response.data["id"])
        self.assertEqual(colaborador.user.last_name, "")

    def test_respuesta_incluye_password_inicial_y_la_guarda_hasheada(self):
        """CA-2: initial_password viene en el 201 y en la base va hasheada (RN-7, RN-8)."""
        self.authenticate("admin.a@test.com")

        response = self.crear_colaborador()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        password = response.data.get("initial_password")
        self.assertTrue(password)

        usuario = User.objects.get(email="ana@test.com")
        self.assertNotEqual(usuario.password, password)  # no se guarda en claro
        self.assertTrue(usuario.check_password(password))

    def test_cada_colaborador_recibe_una_password_distinta(self):
        """RN-7: la contraseña es aleatoria, no una constante del sistema."""
        self.authenticate("admin.a@test.com")

        primera = self.crear_colaborador(email="uno@test.com")
        segunda = self.crear_colaborador(email="dos@test.com")

        self.assertEqual(primera.status_code, status.HTTP_201_CREATED)
        self.assertEqual(segunda.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(
            primera.data["initial_password"],
            segunda.data["initial_password"],
        )

    def test_listado_no_expone_la_password(self):
        """CA-3: la contraseña se entrega una sola vez y no reaparece (RN-8)."""
        self.authenticate("admin.a@test.com")
        self.assertEqual(self.crear_colaborador().status_code, status.HTTP_201_CREATED)

        listado = self.client.get(self.url)

        self.assertEqual(listado.status_code, status.HTTP_200_OK)
        for item in listado.data:
            self.assertNotIn("initial_password", item)
            self.assertNotIn("password", item)

    def test_colaborador_creado_puede_iniciar_sesion(self):
        """CA-4: el alta deja al colaborador operativo de inmediato (RN-10)."""
        self.authenticate("admin.a@test.com")
        creacion = self.crear_colaborador()
        self.assertEqual(creacion.status_code, status.HTTP_201_CREATED)

        self.client.credentials()  # el colaborador entra por su cuenta
        login = self.client.post(
            self.login_url,
            {
                "email": "ana@test.com",
                "password": creacion.data["initial_password"],
            },
            format="json",
        )

        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertTrue(login.data.get("token"))
        self.assertEqual(login.data["user"]["role"], "collaborator")
        self.assertEqual(login.data["user"]["organization_id"], self.org_a.id)

    def test_campos_invalidos_devuelven_400(self):
        """CA-5: email obligatorio y válido, first_name obligatorio (RN-3, RN-5)."""
        self.authenticate("admin.a@test.com")
        usuarios_antes = User.objects.count()

        casos = [
            ({"first_name": "Ana"}, "email"),
            ({"first_name": "Ana", "email": ""}, "email"),
            ({"first_name": "Ana", "email": "no-es-un-correo"}, "email"),
            ({"email": "ana@test.com"}, "first_name"),
            ({"first_name": "", "email": "ana@test.com"}, "first_name"),
            ({"first_name": "   ", "email": "ana@test.com"}, "first_name"),
        ]
        for payload, campo in casos:
            with self.subTest(payload=payload):
                response = self.client.post(self.url, payload, format="json")

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(campo, response.data)

        self.assertEqual(User.objects.count(), usuarios_antes)

    def test_email_duplicado_devuelve_400(self):
        """CA-6: el email es único en todo el sistema, aun entre organizaciones (RN-4)."""
        self.authenticate("admin.a@test.com")
        usuarios_antes = User.objects.count()

        for email in ("colab.a@test.com", "admin.b@test.com"):
            with self.subTest(email=email):
                response = self.crear_colaborador(email=email)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("email", response.data)

        self.assertEqual(User.objects.count(), usuarios_antes)

    def test_organizacion_del_body_es_ignorada(self):
        """CA-7: la organización se deriva del servidor, nunca del body (RN-6)."""
        self.authenticate("admin.a@test.com")

        response = self.crear_colaborador(
            organization=self.org_b.id,
            organization_id=self.org_b.id,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        colaborador = Collaborator.objects.get(id=response.data["id"])
        self.assertEqual(colaborador.organization, self.org_a)

    def test_password_del_body_es_ignorada(self):
        """CA-8: la contraseña la fija el servidor, no el cliente (RN-7)."""
        self.authenticate("admin.a@test.com")

        creacion = self.crear_colaborador(password="hackeada")
        self.assertEqual(creacion.status_code, status.HTTP_201_CREATED)

        usuario = User.objects.get(email="ana@test.com")
        self.assertFalse(usuario.check_password("hackeada"))
        self.assertTrue(usuario.check_password(creacion.data["initial_password"]))

    def test_colaborador_no_puede_crear_colaboradores(self):
        """CA-9: un colaborador autenticado recibe 403 (RN-2)."""
        self.authenticate("colab.a@test.com")
        usuarios_antes = User.objects.count()

        response = self.crear_colaborador()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(User.objects.count(), usuarios_antes)

    def test_crear_colaborador_sin_token_devuelve_401(self):
        """CA-10: sin token válido, 401 (RN-2)."""
        usuarios_antes = User.objects.count()

        response = self.crear_colaborador()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(User.objects.count(), usuarios_antes)

    def test_colaborador_creado_aparece_en_listado(self):
        """CA-11: queda disponible de inmediato en GET /collaborator/ (RN-12)."""
        self.authenticate("admin.a@test.com")
        self.assertEqual(self.crear_colaborador().status_code, status.HTTP_201_CREATED)

        listado = self.client.get(self.url)

        self.assertEqual(listado.status_code, status.HTTP_200_OK)
        self.assertIn("ana@test.com", [item["email"] for item in listado.data])

    def test_colaborador_no_es_visible_para_otra_organizacion(self):
        """CA-12: aislamiento entre organizaciones (RN-12)."""
        self.authenticate("admin.a@test.com")
        self.assertEqual(self.crear_colaborador().status_code, status.HTTP_201_CREATED)

        self.authenticate("admin.b@test.com")
        listado = self.client.get(self.url)

        self.assertEqual(listado.status_code, status.HTTP_200_OK)
        self.assertNotIn("ana@test.com", [item["email"] for item in listado.data])
