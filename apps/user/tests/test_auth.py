from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from utils import model_factories


class AuthTests(APITestCase):
    def setUp(self):
        self.org = model_factories.create_organization()
        self.admin = model_factories.create_admin(
            organization=self.org,
            email="admin@test.com",
            password="password123",
        )
        self.collaborator = model_factories.create_collaborator(
            organization=self.org,
            email="colab@test.com",
            password="password123",
        )

    def test_login_admin_success(self):
        response = self.client.post(
            reverse("user-login"),
            {"email": "admin@test.com", "password": "password123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["user"]["role"], "admin")

    def test_login_invalid_credentials(self):
        response = self.client.post(
            reverse("user-login"),
            {"email": "admin@test.com", "password": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["text"], "Credenciales inválidas")

    def test_course_list_requires_admin(self):
        login = self.client.post(
            reverse("user-login"),
            {"email": "colab@test.com", "password": "password123"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {login.data['token']}")
        response = self.client.get(reverse("course-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # -- SPEC-007: cuentas sin perfil ----------------------------------------

    def test_login_de_usuario_sin_perfil_es_rechazado(self):
        """CA-42: RN-24 — sin perfil no hay rol, y sin rol el front rebota."""
        model_factories.create_user(
            email="huerfano@test.com",
            first_name="Sin",
            last_name="Perfil",
            password="password123",
        )

        response = self.client.post(
            reverse("user-login"),
            {"email": "huerfano@test.com", "password": "password123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("text", response.data)
        self.assertNotIn("token", response.data)

    def test_colaborador_dado_de_baja_conserva_su_perfil(self):
        """CA-43: RN-25 — a ese lo rechaza is_active, no la falta de perfil.

        Las dos causas de rechazo son distintas y no deben confundirse: se
        verifica sobre el perfil, no sobre el mensaje.
        """
        self.collaborator.show = False
        self.collaborator.save()
        self.collaborator.user.is_active = False
        self.collaborator.user.save()

        self.collaborator.user.refresh_from_db()
        self.assertTrue(hasattr(self.collaborator.user, "collaborator_profile"))

        response = self.client.post(
            reverse("user-login"),
            {"email": "colab@test.com", "password": "password123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_normal_sigue_funcionando(self):
        """CA-44: RN-24 no toca a quien sí tiene perfil."""
        for email, rol in [("admin@test.com", "admin"), ("colab@test.com", "collaborator")]:
            with self.subTest(email=email):
                response = self.client.post(
                    reverse("user-login"),
                    {"email": email, "password": "password123"},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("token", response.data)
                self.assertEqual(response.data["user"]["role"], rol)
