# ADR-001 — PDFs locales con entrega autenticada y visor compartido

- **Estado:** Aceptado con SPEC-011
- **Fecha:** 2026-09-05
- **Relacionado:** SPEC-011 — Material PDF y ficha compartida

## Contexto

El usuario eligió varios PDFs por curso, gestionados por el administrador y
consultados por colaboradores inscritos. El proyecto ya usa Django/DRF/Knox y
almacenamiento local; no tiene una biblioteca de archivos ni servicios externos.

La guía de uploads incluye servir `MEDIA_ROOT` con una ruta estática de desarrollo.
Eso no ejecuta los permisos de la ficha. La autorización debe acompañar también
a la entrega de cada archivo.

## Decisiones

### Modelo y almacenamiento

Crear `CourseMaterial` en `apps/course`, con relación de varios documentos a
`Course`, heredando `BaseAbstractModel`. Almacenar `FileField`, nombre original
seguro, tamaño y número de páginas; reutilizar id, show, created_at y updated_at.

Usar el almacenamiento local de Django bajo `MEDIA_ROOT`, ya excluido de Git.
Generar nombres internos únicos por curso, independientes del nombre original,
para que archivos homónimos o reemplazos no sobrescriban otros documentos.

Retirar el montaje estático de `/media/` en `academy/urls.py` y entregar los PDFs
solo mediante vistas autenticadas. Actualizar `docs/FILES.md` para explicar esta
decisión. En despliegue, tampoco se debe publicar esa carpeta como un alias
estático. La aplicación no tiene otros uploads implementados que dependan de él.

Quitar un documento escribe `show=False` y conserva su fila y archivo privados.
Reemplazar conserva la fila y su posición; guarda primero el nuevo archivo y solo
cambia la referencia si el guardado termina. Un archivo recién guardado debe
limpiarse si falla la escritura de metadatos; el anterior se limpia únicamente
después de confirmar el reemplazo en la base de datos. No se borra una fila de
dominio ni se implementa un historial de revisiones.

### Validación

Usar un serializer de subida en el módulo de vistas del dominio y
`MultiPartParser` de DRF. El límite de 10 MiB se valida explícitamente:
`FILE_UPLOAD_MAX_MEMORY_SIZE` regula el uso de memoria y no sustituye el límite
de tamaño del material.

Usar `pypdf==6.17.0` como única dependencia nueva del backend. Comprobar extensión, tamaño y cabecera, y luego leer la estructura
con `PdfReader` en modo estricto. Rechazar cifrado y exigir al menos una página.
El MIME declarado por el cliente no demuestra que los bytes sean un PDF.

La validación comprueba el formato básico; no es una certificación de inocuidad
del documento ni garantiza que todo lector de PDF lo represente igual. No se
ejecuta contenido, no se extrae texto ni se añade un servicio de análisis.

### API y permisos

Vistas genéricas de DRF con los permisos existentes `IsAdmin`/`IsCollaborator`.
Cada vista resuelve primero un curso propio o una inscripción accesible y luego
busca el documento visible dentro de ese curso. Nunca se busca el archivo solo
por `material_id` sin verificar su relación con el curso.

Las vistas de colaborador reutilizan `mis_inscripciones()`. Un helper compartido
entrega un `FileResponse` con tipo PDF, nombre seguro y cabeceras de RN-10.
Los metadatos no exponen `FileField.url` ni rutas del disco.

Una serialización compartida de materiales mantiene la misma información en las
fichas y listas. Usar precarga de documentos visibles para evitar una consulta
adicional por curso; orden por `created_at`, `id`. Los bytes solo se solicitan
cuando se selecciona o descarga un documento.

### Frontend

Extraer la presentación del curso de la ficha existente a un componente
compartido, usado por `pages/admin/courses/[id].vue` y la ficha del colaborador.
La fecha de asignación es opcional y solo existe en la vista del colaborador.

Un componente de material presenta una única lista y un único visor. Las acciones
de administración se incorporan en espacios reservados para ese rol, sin duplicar
la lista ni mantener dos implementaciones de lectura.

Recuperar el PDF con `$apiFetch` autenticado, `responseType: 'blob'` y sin caché.
Crear una URL de objeto para el visor nativo y la descarga con el nombre de los
metadatos. No poner un token en el src del iframe ni usar un visor remoto.

Mantener la carga del Blob en el cliente. Revocar las URLs de objeto al cambiar de
archivo, salir de la ficha o cerrar sesión; cancelar peticiones obsoletas y evitar
que su respuesta sustituya el documento seleccionado. El visor tiene un título
accesible y la descarga se ofrece explícitamente, incluso si no hay visor nativo.

Al terminar una subida o reemplazo, volver a leer los metadatos del servidor.
La vista previa usa los bytes persistidos, no solo el archivo del selector.

## Alternativas consideradas

- **Un archivo en Course:** no corresponde a la elección de varios PDFs.
- **URL pública bajo /media/:** elude los permisos de curso e inscripción.
- **Servicio externo de visor o almacenamiento:** agrega cuentas, dependencia de
  red o exposición a terceros que esta entrega no necesita.
- **PDF.js y visor propio:** permitiría controlar la representación, pero agrega
  dependencia, worker y mantenimiento de controles. Se propone el visor nativo
  y descarga alternativa para este alcance.
- **Validar solo extensión/MIME:** permitiría aceptar archivos que no son PDFs.
- **Cargar todos los PDFs al abrir la ficha:** multiplica transferencia y memoria
  sin que el usuario haya elegido qué documento leer.

## Verificación prevista

Tests de API con archivos temporales y un almacenamiento aislado, cubriendo
varios documentos, reemplazo independiente, bajas y cruces de ids/tenants.
Los tests deben generar PDFs pequeños reales y muestras inválidas; no deben
escribir en el material de demostración.

Build de producción y revisión del flujo completo en navegador. Comprobar lectura
real de un PDF de varias páginas, cambio de documento, descarga, reemplazo,
retiro y que /media/ no exponga los bytes. Mantener los tests existentes verdes.

## Referencias técnicas

- [DRF: MultiPartParser](https://www.django-rest-framework.org/api-guide/parsers/#multipartparser).
- [Django 4.2: FileResponse](https://docs.djangoproject.com/en/4.2/ref/request-response/#fileresponse-objects).
- [Django: límites de la validación del contenido subido](https://docs.djangoproject.com/en/4.2/topics/security/#user-uploaded-content).
- [pypdf: PdfReader, modo estricto y cifrado](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html).
- [MDN: URL de objeto para un Blob y liberación de recursos](https://developer.mozilla.org/en-US/docs/Web/API/URL/createObjectURL_static).
