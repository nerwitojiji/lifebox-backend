# Material PDF privado — SPEC-011

Cada curso admite varios PDFs, uno por subida, de hasta **10 MiB (10.485.760 bytes)**,
con al menos una página y sin cifrado. Se comprueban extensión, cabecera y estructura
con `pypdf==6.17.0`; cambiar el nombre o el MIME no convierte otro archivo en PDF.

## Preparación y almacenamiento

```bash
pip install -r requirements.txt
python manage.py migrate
```

`CourseMaterial` vive en `apps/course/models.py`, con migración
`0002_coursematerial`. Guarda nombre original, tamaño, páginas y `FileField` bajo
`MEDIA_ROOT/courses/{course_id}/materials/{uuid}.pdf`; `media/` está ignorado por Git.
El servidor necesita permiso de escritura y almacenamiento persistente en esa carpeta.

**No publicar `/media/` como carpeta estática**, tampoco en desarrollo. Las vistas
privadas comprueban Knox, rol, organización y pertenencia al curso o inscripción.
No se devuelven rutas físicas ni `file.url` en los metadatos. Para trasladar esta
instancia, conservar tanto la base de datos como `MEDIA_ROOT`.

## Contrato

| Método | Ruta | Operación |
|---|---|---|
| POST | `/course/{id}/materials/` | Admin: agregar, `201` |
| PUT | `/course/{id}/materials/{material_id}/` | Admin: reemplazar, `200` |
| DELETE | `/course/{id}/materials/{material_id}/` | Admin: quitar, `204` |
| GET | `/course/{id}/materials/{material_id}/file/` | Admin: leer PDF del curso propio |
| GET | `/course-collaborator/my-courses/{enrollment_id}/materials/{material_id}/file/` | Colaborador: leer PDF de inscripción propia |

POST y PUT usan `multipart/form-data`, campo `file`. Todas requieren
`Authorization: Token <token>`. Los metadatos `{id, filename, size_bytes,
page_count, updated_at}` aparecen en `materials` del curso en listas y fichas.
Sin material devuelve `[]`; la nueva versión también comienza vacía.

Quitar usa `show=False` y conserva el archivo privado. Reemplazar conserva id y
posición; escribe un archivo nuevo, cambia la referencia de forma atómica y limpia
el anterior después del commit. Un error de disco o base conserva el PDF previo.
No hay historial de reemplazos ni pantalla de recuperación.

La lectura devuelve `application/pdf`, nombre de descarga, `nosniff` y
`Cache-Control: private, no-store`. Lo ajeno u oculto devuelve `404`; sin token,
`401`; rol equivocado, `403`. Un archivo físico ausente produce un `404` controlado.

## Frontend

```typescript
const body = new FormData()
body.append('file', file)
await $apiFetch(endpoints.courseMaterials(courseId), { method: 'POST', body, retry: 0 })
// El navegador agrega el boundary: no fijar Content-Type manualmente.
```

`VisorPdf.vue` solicita el PDF seleccionado con `$apiFetch`, `responseType: 'blob'`
y el token en el header. Crea una URL con `URL.createObjectURL`, la usa en el iframe
y en «Descargar PDF», y la revoca al cambiar o salir. Aborta solicitudes anteriores
para impedir que un archivo anterior reemplace al seleccionado. No usa tokens en
query strings ni enlaces públicos. Sin visor nativo se ofrece la descarga.

## Demostración

1. Ingresar como admin y abrir **Cursos → nombre del curso → Agregar PDF**.
2. Subir [guia-del-curso.pdf](demo/guia-del-curso.pdf) y después
   [actividad-de-repaso.pdf](demo/actividad-de-repaso.pdf). Seleccionar ambos para
   comprobar su contenido y descargar uno.
3. Inscribir un colaborador; ingresar con esa cuenta y abrir la tarjeta del curso.
   Se muestran los mismos documentos, sin controles de administración.
4. Como admin, reemplazar o quitar un documento desde su menú. Actualizar la ficha
   del colaborador para ver el resultado; publicar una versión nueva comienza vacía.

Los PDFs de ejemplo están incluidos en Git y tienen texto de demostración propio.
Ver [SPEC-011](specs/SPEC-011-material-pdf.md) y
[ADR-001](adr/ADR-001-material-pdf-local.md).
