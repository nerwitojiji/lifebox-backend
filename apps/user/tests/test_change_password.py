from django.urls import reverse
from knox.models import AuthToken
from rest_framework import status
from rest_framework.test import APITestCase

from utils import model_factories


class ChangePasswordTests(APITestCase):
    """SPEC-009 — POST /user/change-password/ (CA-1 a CA-9 y CA-14)."""

    ACTUAL = "password123"
    NUEVA = "MiClaveNueva2026"

    def setUp(self):
        self.org = model_factories.create_organization(name="Organización A")
        self.admin = model_factories.create_admin(
            organization=self.org,
            email="admin@test.com",
            password=self.ACTUAL,
        )
        self.collaborator = model_factories.create_collaborator(
            organization=self.org,
            email="colab@test.com",
            first_name="Ana",
            last_name="Pérez",
            password=self.ACTUAL,
        )
        self.url = reverse("user-change-password")

    # -- utilidades -----------------------------------------------------------

    def login(self, email, password=None):
        """Devuelve la respuesta del login, sin dejar credenciales puestas."""
        self.client.credentials()
        return self.client.post(
            reverse("user-login"),
            {"email": email, "password": password or self.ACTUAL},
            format="json",
        )

    def authenticate(self, email, password=None):
        token = self.login(email, password).data["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return token

    def cambiar(self, actual=None, nueva=None):
        cuerpo = {}
        if actual is not None:
            cuerpo["current_password"] = actual
        if nueva is not None:
            cuerpo["new_password"] = nueva
        return self.client.post(self.url, cuerpo, format="json")

    # -- el cambio ------------------------------------------------------------

    def test_cambio_valido(self):
        """CA-1 y CA-14: la nueva sirve, la vieja no, y no viaja ninguna clave."""
        self.authenticate("colab@test.com")

        response = self.cambiar(self.ACTUAL, self.NUEVA)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cuerpo = str(response.data)
        self.assertNotIn(self.NUEVA, cuerpo)
        self.assertNotIn(self.ACTUAL, cuerpo)

        self.assertEqual(
            self.login("colab@test.com", self.NUEVA).status_code, status.HTTP_200_OK
        )
        self.assertEqual(
            self.login("colab@test.com", self.ACTUAL).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_el_cambio_apaga_el_aviso(self):
        """CA-2: RN-9 — ya eligió la suya, no hay nada que recordarle."""
        self.collaborator.user.must_change_password = True
        self.collaborator.user.save()
        self.authenticate("colab@test.com")

        self.cambiar(self.ACTUAL, self.NUEVA)

        self.collaborator.user.refresh_from_db()
        self.assertFalse(self.collaborator.user.must_change_password)

    def test_contrasena_actual_incorrecta(self):
        """CA-3: RN-3 — es lo que impide que un token robado tome la cuenta."""
        self.authenticate("colab@test.com")

        response = self.cambiar("no-es-la-mia", self.NUEVA)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current_password", response.data)
        self.assertEqual(
            self.login("colab@test.com", self.ACTUAL).status_code, status.HTTP_200_OK
        )

    def test_la_nueva_pasa_los_validadores_de_django(self):
        """CA-4: RN-4 — la fuerza la deciden AUTH_PASSWORD_VALIDATORS."""
        self.authenticate("colab@test.com")

        for nueva in ["abc", "colab@test.com"]:
            with self.subTest(nueva=nueva):
                response = self.cambiar(self.ACTUAL, nueva)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn("new_password", response.data)

        self.assertEqual(
            self.login("colab@test.com", self.ACTUAL).status_code, status.HTTP_200_OK
        )

    def test_la_nueva_debe_ser_distinta(self):
        """CA-5: RN-5."""
        self.authenticate("colab@test.com")

        response = self.cambiar(self.ACTUAL, self.ACTUAL)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", response.data)

    def test_faltan_campos(self):
        """CA-6: RN-2."""
        self.authenticate("colab@test.com")

        casos = {
            "current_password": self.cambiar(nueva=self.NUEVA),
            "new_password": self.cambiar(actual=self.ACTUAL),
        }
        for clave, response in casos.items():
            with self.subTest(clave=clave):
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(clave, response.data)

    def test_sin_token_devuelve_401(self):
        """CA-7."""
        response = self.cambiar(self.ACTUAL, self.NUEVA)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_el_admin_tambien_cambia_la_suya(self):
        """CA-8: RN-1 — es quien entra con la clave del seeder; restringirlo
        además costaría código extra, porque el endpoint opera sobre el token."""
        self.authenticate("admin@test.com")

        response = self.cambiar(self.ACTUAL, self.NUEVA)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.login("admin@test.com", self.NUEVA).status_code, status.HTTP_200_OK
        )

    def test_los_demas_tokens_se_invalidan(self):
        """CA-9: RN-7 — la razón de seguridad de toda la feature. La contraseña
        temporal la conocía el admin; si abrió sesión con ella, muere acá."""
        viejo = self.authenticate("colab@test.com")
        actual = self.authenticate("colab@test.com")
        self.assertNotEqual(viejo, actual)
        self.assertEqual(AuthToken.objects.filter(user=self.collaborator.user).count(), 2)

        self.cambiar(self.ACTUAL, self.NUEVA)

        # El token con el que se hizo el cambio sigue sirviendo: no se expulsa a
        # quien acaba de hacer lo correcto.
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {actual}")
        self.assertEqual(
            self.client.get(reverse("user-me")).status_code, status.HTTP_200_OK
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {viejo}")
        self.assertEqual(
            self.client.get(reverse("user-me")).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
