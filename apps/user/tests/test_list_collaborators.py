from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from utils import model_factories


class ListCollaboratorsTests(APITestCase):
    """Listado de colaboradores: búsqueda por texto y respuesta paginada."""

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
        self.ana = model_factories.create_collaborator(
            organization=self.org_a,
            email="ana.perez@test.com",
            first_name="Ana",
            last_name="Perez",
            password="password123",
        )
        self.bruno = model_factories.create_collaborator(
            organization=self.org_a,
            email="bruno.diaz@test.com",
            first_name="Bruno",
            last_name="Diaz",
            password="password123",
        )
        self.carla = model_factories.create_collaborator(
            organization=self.org_a,
            email="carla.soto@test.com",
            first_name="Carla",
            last_name="Soto",
            password="password123",
        )
        self.otra_org = model_factories.create_collaborator(
            organization=self.org_b,
            email="ana.otra@test.com",
            first_name="Ana",
            last_name="Otra",
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

    def test_listado_devuelve_items_y_pagination(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("items", response.data)
        self.assertIn("pagination", response.data)
        self.assertIsInstance(response.data["items"], list)
        pagination = response.data["pagination"]
        for clave in (
            "page",
            "page_size",
            "total_items",
            "total_pages",
            "has_next",
            "has_previous",
        ):
            self.assertIn(clave, pagination)
        self.assertEqual(pagination["page"], 1)
        self.assertEqual(pagination["page_size"], 20)
        self.assertEqual(pagination["total_items"], 3)
        self.assertEqual(pagination["total_pages"], 1)
        self.assertFalse(pagination["has_next"])
        self.assertFalse(pagination["has_previous"])
        emails = [item["email"] for item in response.data["items"]]
        self.assertCountEqual(
            emails,
            ["ana.perez@test.com", "bruno.diaz@test.com", "carla.soto@test.com"],
        )
        for item in response.data["items"]:
            self.assertEqual(set(item.keys()), {"id", "email", "full_name"})

    def test_q_filtra_por_nombre(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.list_url, {"q": "bru"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [item["email"] for item in response.data["items"]]
        self.assertEqual(emails, ["bruno.diaz@test.com"])
        self.assertEqual(response.data["pagination"]["total_items"], 1)

    def test_q_filtra_por_apellido(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.list_url, {"q": "perez"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [item["email"] for item in response.data["items"]]
        self.assertEqual(emails, ["ana.perez@test.com"])

    def test_q_filtra_por_correo(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.list_url, {"q": "carla.soto"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [item["email"] for item in response.data["items"]]
        self.assertEqual(emails, ["carla.soto@test.com"])

    def test_q_sin_coincidencias_devuelve_items_vacios(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.list_url, {"q": "xyz-no-existe"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [])
        self.assertEqual(response.data["pagination"]["total_items"], 0)
        self.assertEqual(response.data["pagination"]["total_pages"], 0)

    def test_q_no_cruza_organizaciones(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.list_url, {"q": "ana"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [item["email"] for item in response.data["items"]]
        self.assertEqual(emails, ["ana.perez@test.com"])
        self.assertNotIn("ana.otra@test.com", emails)

    def test_colaborador_no_puede_listar(self):
        self.authenticate("ana.perez@test.com")

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_paginacion_parte_el_listado(self):
        self.authenticate("admin.a@test.com")

        primera = self.client.get(self.list_url, {"page": 1, "page_size": 2})
        segunda = self.client.get(self.list_url, {"page": 2, "page_size": 2})

        self.assertEqual(primera.status_code, status.HTTP_200_OK)
        self.assertEqual(segunda.status_code, status.HTTP_200_OK)
        self.assertEqual(len(primera.data["items"]), 2)
        self.assertEqual(len(segunda.data["items"]), 1)
        self.assertEqual(primera.data["pagination"]["total_items"], 3)
        self.assertEqual(primera.data["pagination"]["total_pages"], 2)
        self.assertTrue(primera.data["pagination"]["has_next"])
        self.assertFalse(primera.data["pagination"]["has_previous"])
        self.assertFalse(segunda.data["pagination"]["has_next"])
        self.assertTrue(segunda.data["pagination"]["has_previous"])
        ids_primera = {item["id"] for item in primera.data["items"]}
        ids_segunda = {item["id"] for item in segunda.data["items"]}
        self.assertTrue(ids_primera.isdisjoint(ids_segunda))

    def test_page_size_respeta_tope_de_100(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.list_url, {"page_size": 500})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["page_size"], 100)

    def test_q_en_blanco_no_filtra(self):
        self.authenticate("admin.a@test.com")

        response = self.client.get(self.list_url, {"q": "   "})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pagination"]["total_items"], 3)
