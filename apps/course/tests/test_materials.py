"""SPEC-011: PDFs reales, operaciones independientes y aislamiento de archivos."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.test import override_settings
from django.urls import reverse
from knox.models import AuthToken
from pypdf import PdfWriter
from rest_framework.test import APITestCase

from apps.course.models import Course
from apps.course_collaborator.models import CourseCollaborator
from utils import model_factories as factories

MAX_BYTES = 10 * 1024 * 1024


def pdf_bytes(pages=2, encrypted=False):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    if encrypted:
        writer.encrypt("clave-de-prueba", algorithm="RC4-128")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class CourseMaterialTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = factories.create_organization(name="Organización PDF")
        cls.other_org = factories.create_organization(name="Organización ajena PDF")
        cls.admin = factories.create_admin(organization=cls.org)
        cls.other_admin = factories.create_admin(
            organization=cls.other_org, email="admin-otro@pdf.test"
        )
        cls.student = factories.create_collaborator(organization=cls.org)
        cls.peer = factories.create_collaborator(
            organization=cls.org, email="sin-inscripcion@pdf.test"
        )
        cls.other_student = factories.create_collaborator(
            organization=cls.other_org, email="colaborador-otro@pdf.test"
        )
        cls.course = Course.objects.create(
            organization=cls.org, full_name="Inducción de seguridad"
        )
        cls.second_course = Course.objects.create(
            organization=cls.org, full_name="Primeros auxilios"
        )
        cls.foreign_course = Course.objects.create(
            organization=cls.other_org, full_name="Curso privado"
        )
        cls.enrollment = CourseCollaborator.objects.create(
            course=cls.course, collaborator=cls.student
        )

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.media_root = Path(temporary.name)
        override = override_settings(MEDIA_ROOT=temporary.name)
        override.enable()
        self.addCleanup(override.disable)
        self.login(self.admin)

    def login(self, profile):
        _, token = AuthToken.objects.create(profile.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")

    def upload(self, name="guía.pdf", content=None, course=None, **extra):
        file = SimpleUploadedFile(
            name, pdf_bytes() if content is None else content, "application/pdf"
        )
        return self.client.post(
            reverse("course-material-list", args=[(course or self.course).pk]),
            {"file": file, **extra},
            format="multipart",
        )

    def create_material(self, **kwargs):
        response = self.upload(**kwargs)
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def material_url(self, material_id, course=None):
        return reverse(
            "course-material-detail", args=[(course or self.course).pk, material_id]
        )

    def file_url(self, material_id, course=None):
        return reverse(
            "course-material-file", args=[(course or self.course).pk, material_id]
        )

    def student_file_url(self, material_id):
        return reverse(
            "my-course-material-file", args=[self.enrollment.pk, material_id]
        )

    def replace(self, material_id, content=None):
        return self.client.put(
            self.material_url(material_id),
            {"file": SimpleUploadedFile(
                "actualizado.pdf", pdf_bytes(3) if content is None else content,
                "application/pdf",
            )},
            format="multipart",
        )

    def get_bytes(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        try:
            return b"".join(response.streaming_content)
        finally:
            response.close()

    def model(self):
        return apps.get_model("course", "CourseMaterial")

    def test_varios_pdfs_con_nombre_repetido_sin_sobrescribir(self):
        first = self.create_material(content=pdf_bytes(1))
        second = self.create_material(content=pdf_bytes(3))
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(first["page_count"], 1)
        self.assertEqual(second["page_count"], 3)
        self.assertEqual(set(first), {"id", "filename", "size_bytes", "page_count", "updated_at"})
        detail = self.client.get(reverse("course-detail", args=[self.course.pk])).data
        self.assertEqual([m["id"] for m in detail["materials"]], [first["id"], second["id"]])
        self.assertEqual(self.get_bytes(self.file_url(first["id"])), pdf_bytes(1))
        self.assertEqual(self.get_bytes(self.file_url(second["id"])), pdf_bytes(3))

    def test_admin_subir_y_ver_ficha_sin_inscritos(self):
        material = self.create_material(course=self.second_course)
        response = self.client.get(reverse("course-detail", args=[self.second_course.pk]))
        self.assertEqual(response.data["materials"], [material])
        self.assertEqual(response.data["enrolled_count"], 0)

    def test_ausente_o_url_no_son_archivos(self):
        url = reverse("course-material-list", args=[self.course.pk])
        for body in ({}, {"file": "https://example.test/archivo.pdf"}):
            with self.subTest(body=body):
                response = self.client.post(url, body, format="multipart")
                self.assertEqual(response.status_code, 400)
                self.assertIn("file", response.data)

    def test_formatos_invalidos_y_pdfs_no_utilizables(self):
        cases = [
            ("vacío.pdf", b""),
            ("imagen.png", pdf_bytes()),
            ("falso.pdf", b"Esto no es un PDF"),
            ("cabecera.pdf", b"%PDF-1.7\n%%EOF"),
            ("roto.pdf", pdf_bytes()[:100]),
            ("sin-paginas.pdf", pdf_bytes(0)),
            ("cifrado.pdf", pdf_bytes(encrypted=True)),
        ]
        for name, content in cases:
            with self.subTest(name=name):
                response = self.upload(name=name, content=content)
                self.assertEqual(response.status_code, 400)
                self.assertIn("file", response.data)
        self.assertFalse(any(self.media_root.rglob("*.pdf")))

    def test_limite_exacto_y_exceso(self):
        pdf = pdf_bytes()
        # Relleno anterior al marcador EOF: sigue siendo un PDF válido.
        prefix, suffix = pdf.rsplit(b"%%EOF", 1)
        at_limit = prefix + b"\n" * (MAX_BYTES - len(pdf)) + b"%%EOF" + suffix
        response = self.upload(content=at_limit)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["size_bytes"], MAX_BYTES)
        response = self.upload(content=at_limit + b"\n")
        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data)

    def test_nombre_mayusculas_acentos_y_directorios(self):
        material = self.create_material(name="../carpeta/Guía.PDF")
        self.assertEqual(material["filename"], "Guía.PDF")
        stored = self.model().objects.get(pk=material["id"])
        self.assertTrue(Path(stored.file.path).resolve().is_relative_to(self.media_root.resolve()))
        self.assertNotIn("Guía", stored.file.name)

    def test_reemplazar_conserva_id_orden_y_otros_archivos(self):
        first = self.create_material(content=pdf_bytes(1))
        second = self.create_material(content=pdf_bytes(2))
        old_file = self.model().objects.get(pk=first["id"]).file.path
        with self.captureOnCommitCallbacks(execute=True):
            response = self.replace(first["id"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["id"], first["id"])
        self.assertEqual(response.data["page_count"], 3)
        detail = self.client.get(reverse("course-detail", args=[self.course.pk])).data
        self.assertEqual([m["id"] for m in detail["materials"]], [first["id"], second["id"]])
        self.assertEqual(detail["materials"][1], second)
        self.assertFalse(Path(old_file).exists())
        self.assertEqual(self.get_bytes(self.file_url(first["id"])), pdf_bytes(3))

    def test_reemplazo_invalido_conserva_el_anterior(self):
        material = self.create_material()
        response = self.replace(material["id"], b"No soy un PDF")
        self.assertEqual(response.status_code, 400)
        detail = self.client.get(reverse("course-detail", args=[self.course.pk])).data
        self.assertEqual(detail["materials"], [material])
        self.assertEqual(self.get_bytes(self.file_url(material["id"])), pdf_bytes())

    def test_fallo_de_disco_conserva_el_anterior(self):
        material = self.create_material()
        storage = self.model()._meta.get_field("file").storage
        with patch.object(storage, "save", side_effect=OSError("disco no disponible")):
            response = self.replace(material["id"])
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.get_bytes(self.file_url(material["id"])), pdf_bytes())

    def test_fallo_de_base_limpia_el_nuevo_archivo(self):
        material = self.create_material()
        before = set(self.media_root.rglob("*.pdf"))
        with patch.object(self.model(), "save", side_effect=OperationalError("fallo temporal")):
            response = self.replace(material["id"])
        self.assertEqual(response.status_code, 503)
        self.assertEqual(set(self.media_root.rglob("*.pdf")), before)
        self.assertEqual(self.get_bytes(self.file_url(material["id"])), pdf_bytes())

    def test_quitar_solo_un_documento_y_agregar_con_id_nuevo(self):
        first = self.create_material()
        second = self.create_material()
        response = self.client.delete(self.material_url(first["id"]))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(self.model().objects.get(pk=first["id"]).show)
        self.assertEqual(self.client.delete(self.material_url(first["id"])).status_code, 204)
        self.assertEqual(self.client.get(self.file_url(first["id"])).status_code, 404)
        detail = self.client.get(reverse("course-detail", args=[self.course.pk])).data
        self.assertEqual(detail["materials"], [second])
        self.assertTrue(CourseCollaborator.objects.get(pk=self.enrollment.pk).show)
        self.client.delete(self.material_url(second["id"]))
        detail = self.client.get(reverse("course-detail", args=[self.course.pk])).data
        self.assertEqual(detail["materials"], [])
        third = self.create_material()
        self.assertNotIn(third["id"], [first["id"], second["id"]])

    def test_material_oculto_no_se_reemplaza(self):
        material = self.create_material()
        self.client.delete(self.material_url(material["id"]))
        self.assertEqual(self.replace(material["id"]).status_code, 404)

    def test_colaborador_solo_lee(self):
        material = self.create_material()
        self.login(self.student)
        self.assertEqual(self.upload().status_code, 403)
        self.assertEqual(self.replace(material["id"]).status_code, 403)
        self.assertEqual(self.client.delete(self.material_url(material["id"])).status_code, 403)
        self.assertEqual(self.client.get(self.file_url(material["id"])).status_code, 403)
        for method in ("post", "put", "patch", "delete"):
            response = getattr(self.client, method)(self.student_file_url(material["id"]))
            self.assertEqual(response.status_code, 405)

    def test_admin_no_usa_ruta_de_colaborador(self):
        material = self.create_material()
        self.assertEqual(self.client.get(self.student_file_url(material["id"])).status_code, 403)

    def test_sin_token_todas_las_operaciones_responden_401(self):
        material = self.create_material()
        self.client.credentials()
        self.assertEqual(self.upload().status_code, 401)
        self.assertEqual(self.replace(material["id"]).status_code, 401)
        self.assertEqual(self.client.delete(self.material_url(material["id"])).status_code, 401)
        self.assertEqual(self.client.get(self.file_url(material["id"])).status_code, 401)
        self.assertEqual(self.client.get(self.student_file_url(material["id"])).status_code, 401)

    def test_admin_ajeno_no_puede_operar(self):
        material = self.create_material()
        self.login(self.other_admin)
        self.assertEqual(self.upload().status_code, 404)
        self.assertEqual(self.replace(material["id"]).status_code, 404)
        self.assertEqual(self.client.delete(self.material_url(material["id"])).status_code, 404)
        self.assertEqual(self.client.get(self.file_url(material["id"])).status_code, 404)

    def test_organizacion_del_body_y_query_no_amplia_acceso(self):
        material = self.create_material(organization=self.other_org.pk, course=self.course)
        stored = self.model().objects.get(pk=material["id"])
        self.assertEqual(stored.course_id, self.course.pk)
        self.login(self.other_admin)
        url = self.file_url(material["id"]) + f"?organization={self.org.pk}"
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_no_se_mezclan_ids_de_material_y_curso(self):
        material = self.create_material(course=self.second_course)
        for method, url in [
            ("get", self.file_url(material["id"])),
            ("delete", self.material_url(material["id"])),
            ("put", self.material_url(material["id"])),
        ]:
            self.assertEqual(getattr(self.client, method)(url).status_code, 404)
        self.login(self.student)
        self.assertEqual(self.client.get(self.student_file_url(material["id"])).status_code, 404)

    def test_colaboradores_sin_inscripcion_o_ajenos_no_leen(self):
        material = self.create_material()
        for profile in (self.peer, self.other_student):
            self.login(profile)
            self.assertEqual(self.client.get(self.student_file_url(material["id"])).status_code, 404)

    def test_desinscribir_bloquea_el_archivo(self):
        material = self.create_material()
        self.enrollment.show = False
        self.enrollment.save()
        self.login(self.student)
        self.assertEqual(self.client.get(self.student_file_url(material["id"])).status_code, 404)

    def test_curso_oculto_bloquea_gestion_y_lectura(self):
        material = self.create_material()
        self.course.show = False
        self.course.save()
        self.assertEqual(self.upload().status_code, 404)
        self.assertEqual(self.replace(material["id"]).status_code, 404)
        self.assertEqual(self.client.delete(self.material_url(material["id"])).status_code, 404)
        self.assertEqual(self.client.get(self.file_url(material["id"])).status_code, 404)
        self.login(self.student)
        self.assertEqual(self.client.get(self.student_file_url(material["id"])).status_code, 404)

    def test_baja_del_colaborador_bloquea_token_existente(self):
        material = self.create_material()
        self.login(self.student)
        self.student.user.is_active = False
        self.student.user.save()
        self.assertEqual(self.client.get(self.student_file_url(material["id"])).status_code, 401)

    def test_curso_retirado_permite_material(self):
        self.course.is_active = False
        self.course.save()
        material = self.create_material()
        self.assertEqual(self.replace(material["id"]).status_code, 200)
        self.login(self.student)
        self.assertEqual(self.get_bytes(self.student_file_url(material["id"])), pdf_bytes(3))

    def test_mismos_bytes_cabeceras_y_metadatos_para_ambos_roles(self):
        material = self.create_material()
        admin_detail = self.client.get(reverse("course-detail", args=[self.course.pk])).data
        admin_list = self.client.get(reverse("course-list")).data
        self.assertEqual(next(c for c in admin_list if c["id"] == self.course.pk)["materials"], [material])
        admin_bytes = self.get_bytes(self.file_url(material["id"]))
        self.login(self.student)
        student_detail = self.client.get(reverse("my-course-detail", args=[self.enrollment.pk])).data
        student_list = self.client.get(reverse("my-courses")).data
        self.assertEqual(student_detail["course"]["materials"], admin_detail["materials"])
        self.assertEqual(student_list[0]["course"], student_detail["course"])
        response = self.client.get(self.student_file_url(material["id"]))
        try:
            self.assertEqual(b"".join(response.streaming_content), admin_bytes)
            self.assertEqual(response["Content-Type"], "application/pdf")
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("filename", response["Content-Disposition"])
        finally:
            response.close()

    @override_settings(DEBUG=True)
    def test_media_no_expone_archivos(self):
        material = self.create_material()
        stored = self.model().objects.get(pk=material["id"])
        self.client.credentials()
        self.assertEqual(self.client.get("/media/" + stored.file.name).status_code, 404)

    def test_nueva_version_y_curso_nuevo_no_copian_pdfs(self):
        material = self.create_material()
        response = self.client.post(
            reverse("course-new-version", args=[self.course.pk]),
            {"version": "2.0"}, format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["materials"], [])
        self.assertEqual(self.get_bytes(self.file_url(material["id"])), pdf_bytes())
        response = self.client.post(reverse("course-list"), {"full_name": "Curso nuevo"}, format="json")
        self.assertEqual(response.data["materials"], [])

    def test_archivo_fisico_ausente_es_error_controlado(self):
        material = self.create_material()
        stored = self.model().objects.get(pk=material["id"])
        Path(stored.file.path).unlink()
        response = self.client.get(self.file_url(material["id"]))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(str(self.media_root), str(response.data))

    def test_listas_precargan_materiales(self):
        self.create_material()
        url = reverse("course-list")
        # Un token nuevo añade una consulta de auth constante. Se compara el
        # crecimiento, no la implementación exacta de cada consulta.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as small:
            self.client.get(url)
        for i in range(4):
            course = Course.objects.create(organization=self.org, full_name=f"Curso {i}")
            self.create_material(course=course)
        with CaptureQueriesContext(connection) as large:
            self.client.get(url)
        self.assertEqual(len(small), len(large))
