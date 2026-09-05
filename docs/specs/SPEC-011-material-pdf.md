# SPEC-011 — Material PDF y ficha compartida

- **Capacidad:** Publicar material de un curso y revisarlo desde ambos roles
- **Feature:** Material PDF · rama `feature/material-pdf`
- **Estado:** Aprobada por el usuario — en implementación
- **Repos:** `lifebox-backend` · `lifebox-frontend`
- **Responde a:** enunciado §6.2 y pedido de que el admin pueda revisar la ficha que ve el colaborador
- **Formato elegido por el usuario:** PDF
- **Cantidad elegida por el usuario:** varios PDFs por curso; cada versión conserva su propio material

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

## Artículo 1 — Contexto y encuadre

SPEC-010 ya permite al colaborador abrir una ficha con nombre, versión, duración,
descripción completa y estado. Su Enmienda 2 retiró las fotografías externas y
dejó un encabezado compacto con iniciales. Falta el contenido real del curso.

El administrador no tiene una ficha propia desde el catálogo. Necesita abrirla,
subir varios PDFs y comprobar su presentación y contenido con el mismo visor que usa
el colaborador, incluso antes de inscribir a alguien.

La guía `docs/FILES.md` propone almacenamiento local y uploads multipart. Su
ejemplo de URL pública debe adaptarse: el archivo forma parte de un curso privado
y su acceso debe respetar organización, rol e inscripción.

## Artículo 2 — Objetivo

Que el administrador pueda cargar, revisar y corregir los PDFs de un curso, y que
cada colaborador asignado pueda elegirlos y leerlos desde su ficha o descargarlos
para abrirlos con su lector de PDF.

## Artículo 3 — Alcance

**Dentro de alcance:**

- Varios PDFs por cada curso/versionado existente, con una lista de documentos.
- Agregar, reemplazar y quitar cada PDF desde la ficha del administrador.
- Ficha del admin accesible desde el catálogo, con el mismo contenido y visor.
- Lectura del PDF dentro de la ficha del colaborador y descarga alternativa.
- Validación del archivo, acceso autenticado, estados de carga, vacío y error.
- Persistencia local de archivos y metadatos, con la migración necesaria.
- Actualización de documentación, supuestos, guía de archivos y demostración.

**Fuera de alcance:**

- Carpetas, reordenamiento manual o una biblioteca de materiales entre cursos.
- Video, audio, imágenes de portada o enlaces a documentos externos.
- Editor de PDF, generación de PDF, OCR, anotaciones o firmas.
- Progreso, certificados, evaluaciones o registro de quién leyó el documento.
- Publicación programada, borradores, historial recuperable de reemplazos.
- Almacenamiento en la nube o proveedores externos de visualización.

## Artículo 4 — Actores y precondiciones

- **Administrador:** autenticado, con perfil de admin y organización; opera sobre
  cursos visibles de su organización, tengan inscritos o no.
- **Colaborador:** autenticado, con una inscripción propia visible y un curso
  visible de su organización, según el criterio compartido `mis_inscripciones()`.
- Un curso retirado (`is_active=False`) conserva su ficha y su material para los
  inscritos existentes. Un curso eliminado (`show=False`) no es accesible.
- La nueva versión que crea SPEC-007 es otro curso: su material es independiente.

## Artículo 5 — Reglas de negocio

### Material y validación

- **RN-1.** Un curso DEBE admitir varios PDFs, cada uno con un identificador
  propio. Crear un curso NO DEBE exigir archivos: sin material, la ficha sigue
  siendo válida. Cada operación de subida agrega un archivo; repetirla permite
  completar la lista. No se implementa carga por lotes.
- **RN-2.** El servidor DEBE aceptar solo archivos con extensión `.pdf`, ignorando
  mayúsculas, tamaño mayor que cero y máximo de **10 MiB (10.485.760 bytes)**.
  La interfaz DEBE comunicar ese límite antes de seleccionar el archivo.
- **RN-3.** La extensión y el MIME NO DEBEN bastar para aceptar el archivo: el
  servidor DEBE comprobar cabecera y estructura básica de PDF, al menos una
  página y ausencia de cifrado. Un PDF corrupto, vacío, sin páginas o cifrado
  DEBE rechazarse con un mensaje asociado a `file`.
- **RN-4.** Subir un archivo DEBE exigir un archivo real en multipart. NO DEBE
  aceptarse una URL, una ruta local del cliente ni contenido de otros formatos.
  El nombre original se conserva para mostrarlo y descargarlo, sin directorios
  ni caracteres de control; el servidor decide la ubicación de almacenamiento.
- **RN-5.** El PDF DEBE persistir tras reiniciar la aplicación. Sus metadatos DEBEN
  incluir id, nombre de archivo, tamaño en bytes, páginas y fecha de actualización.
  La lista DEBE ordenarse por fecha de creación ascendente y luego por id; un
  reemplazo NO DEBE cambiar la posición del documento.

### Permisos y entrega

- **RN-6.** Solo el admin DEBE poder subir, reemplazar o quitar material. El curso
  y la organización se resuelven del servidor; enviar otra organización en el
  body o query params NO DEBE ampliar el acceso. El id del material también DEBE
  pertenecer al curso resuelto; mezclar ids de cursos y archivos devuelve `404`.
- **RN-7.** El colaborador DEBE poder leer y descargar únicamente el material de
  sus inscripciones accesibles. Se DEBE reutilizar el filtro de lista y ficha,
  también para la entrega de los bytes del PDF.
- **RN-8.** Sin token DEBE responderse `401`; un rol incorrecto DEBE recibir
  `403`; un curso o inscripción ajena, oculta o inexistente DEBE responder
  `404`. Conocer el nombre o la ubicación del archivo NO DEBE permitir leerlo.
- **RN-9.** Los PDFs NO DEBEN exponerse por una URL pública de `/media/`, tampoco
  con `DEBUG=True`. Cada solicitud del archivo DEBE comprobar los permisos.
  Los tokens NO DEBEN viajar en URLs ni enviarse a visores externos.
- **RN-10.** La respuesta del archivo DEBE ser `application/pdf`, con nombre
  seguro, `X-Content-Type-Options: nosniff` y `Cache-Control: private, no-store`.
  La API NO DEBE exponer rutas físicas del servidor.
- **RN-11.** Desinscribir o dar de baja al colaborador, ocultar el curso o quitar
  un PDF DEBE impedir futuras descargas de ese documento. Un documento ya descargado no puede
  retirarse del dispositivo del usuario; esta feature no implementa DRM.

### Correcciones y versiones

- **RN-12.** Agregar un PDF DEBE publicarlo inmediatamente sin sustituir los
  demás. Para reemplazar uno existente, el admin DEBE elegir ese documento,
  confirmar el reemplazo y ver que afectará a los colaboradores de esa versión.
  La validación y el guardado del nuevo archivo DEBEN completarse antes de
  sustituir el elegido, conservando su id y su posición en la lista.
- **RN-13.** Si el upload, la validación o el guardado fallan, el PDF vigente DEBE
  permanecer disponible con sus metadatos previos. La interfaz NO DEBE anunciar
  éxito ni mostrar como publicado el archivo que falló.
- **RN-14.** Quitar un PDF DEBE exigir confirmación y ocultar únicamente ese
  documento mediante borrado lógico. NO DEBE borrar el curso, otros PDFs ni
  alterar inscripciones. Agregar un PDF después DEBE crear un documento nuevo;
  no se reactiva automáticamente un archivo oculto.
- **RN-15.** El admin DEBE poder corregir el material de cursos visibles, incluidos
  los retirados. El aviso DEBE explicar que el reemplazo o retiro del PDF también
  afecta a quienes conservan una inscripción en esa versión.
- **RN-16.** Publicar una nueva versión DEBE conservar el PDF de origen y crear la
  nueva versión **sin material**, sin copiar archivos ni inscritos. El admin DEBE
  recibir esta explicación en la confirmación de nueva versión.

### Ficha y visualización

- **RN-F1.** El catálogo DEBE permitir abrir `/admin/courses/{course_id}` mediante
  el nombre del curso y una acción «Ver ficha». La ficha DEBE funcionar por URL
  directa y tras recargar; no requiere inscribirse ni usar la cuenta de otro rol.
- **RN-F2.** Admin y colaborador DEBEN compartir la presentación de iniciales,
  nombre, versión, duración, descripción, estado y material. El visor y la
  descripción NO DEBEN implementarse por separado para cada rol.
- **RN-F3.** La fecha «Asignado el» DEBE aparecer solo para el colaborador. El admin
  NO DEBE mostrar una fecha inventada ni datos de una inscripción ajena.
  Los controles de gestión DEBEN ser exclusivos del admin y ocupar espacios
  propios junto a la lista; no alteran el contenido que muestra el visor.
- **RN-F4.** En la ficha del admin DEBE estar disponible «Agregar PDF» y, junto a
  cada documento, «Reemplazar PDF» y «Quitar PDF». La lista NO DEBE duplicarse para
  gestionar y previsualizar. El archivo seleccionado para subir DEBE mostrar su
  nombre y tamaño antes de confirmar.
- **RN-F5.** Debajo de la descripción DEBE aparecer «Material del curso», con una
  lista de PDFs en el orden de RN-5. Cada fila DEBE identificar nombre, tamaño y
  páginas, y permitir seleccionar el documento para verlo y descargarlo.
  Solo el PDF seleccionado DEBE cargarse en un visor integrado; NO DEBEN cargarse
  todos los archivos al abrir la ficha. El encabezado del curso sigue compacto.
- **RN-F6.** El visor DEBE mostrar el archivo guardado por el servidor, también
  después de subir o reemplazar. La revisión del admin NO DEBE limitarse a un
  archivo local que todavía no se haya guardado.
- **RN-F7.** Sin documentos visibles, el colaborador DEBE leer «Este curso todavía
  no tiene material disponible». El admin DEBE ver ese mismo estado en la ficha
  y disponer de «Agregar PDF». NO DEBE aparecer un visor vacío.
- **RN-F8.** La carga del archivo DEBE tener estado visible y un error con opción
  de reintentar. Un error del PDF NO DEBE ocultar el resto de la ficha.
  Si el navegador no ofrece visor integrado, la descarga DEBE seguir disponible.
- **RN-F9.** La vista DEBE adaptarse al ancho disponible y ofrecer un visor con
  título accesible. Descargar NO DEBE depender de descubrir los controles
  particulares del visor del navegador.
- **RN-F10.** Cambiar de documento o curso, reemplazar/quitar el seleccionado o
  cerrar sesión DEBE descartar el PDF anterior de la pantalla. Una respuesta
  tardía NO DEBE sustituir el documento que el usuario está viendo.
- **RN-F11.** Al entrar se DEBE seleccionar el primer documento visible. Después
  de agregar se DEBE seleccionar el nuevo para revisarlo. Reemplazar conserva la
  selección; si se reemplazó el seleccionado, se recarga su visor. Quitar un PDF
  distinto del seleccionado NO DEBE interrumpir la lectura; si se quitó el activo,
  se elige el primero restante o se muestra el estado vacío. Los metadatos DEBEN
  refrescarse y los botones DEBEN impedir envíos duplicados mientras se guarda.

## Artículo 6 — Criterios de aceptación

| ID | Escenario y resultado esperado |
|---|---|
| CA-1 | Admin agrega dos PDFs válidos al mismo curso: recibe `201` por cada uno, ids distintos y ambos aparecen ordenados en la lista. |
| CA-2 | Un curso sin inscritos admite subir material y abrir su ficha de admin. |
| CA-3 | Archivo ausente, vacío, con extensión incorrecta o mayor a 10 MiB: `400` en `file`, sin publicar nada. El límite exacto de tamaño se acepta si el PDF es válido. |
| CA-4 | Texto renombrado a `.pdf`, archivo con solo cabecera PDF, PDF corrupto, cifrado o sin páginas: rechazo explicado en `file`. |
| CA-5 | Un PDF válido con extensión `.PDF` y nombre con acentos se acepta; el nombre no permite elegir directorios. |
| CA-6 | Reemplazo correcto de uno entre varios: conserva id y posición; entrega sus bytes nuevos y metadatos. Los demás documentos permanecen iguales. |
| CA-7 | Reemplazo inválido o fallo de almacenamiento: el PDF anterior sigue disponible y no se anuncia éxito. |
| CA-8 | Quitar un PDF lo excluye de la lista y su lectura responde `404`; los demás PDFs, curso e inscripciones permanecen iguales. Quitar el último deja `materials: []`; agregar después funciona con un id nuevo. |
| CA-9 | Un colaborador no puede subir, reemplazar ni quitar; las rutas del colaborador no aceptan escritura. |
| CA-10 | Sin token, tanto la gestión como la lectura del PDF responden `401`. |
| CA-11 | Admin de otro tenant no puede leer, subir ni quitar material del curso, ni abrir su ficha: `404`. Mezclar ids de curso y material también responde `404`, incluso dentro del mismo tenant. Body/query params no permiten eludirlo. |
| CA-12 | Colaborador sin inscripción accesible, de otro tenant o que mezcla una inscripción propia con el id de material de otro curso: lectura `404`. |
| CA-13 | Inscripción oculta, curso oculto o usuario dado de baja bloquean nuevas lecturas según las reglas de acceso existentes. |
| CA-14 | Un curso retirado mantiene su PDF accesible a inscritos y admin; el admin puede corregirlo. |
| CA-15 | Una petición directa a la ubicación bajo `/media/` no entrega el PDF, incluso con DEBUG activo. |
| CA-16 | El archivo servido por las dos rutas de lectura contiene los mismos bytes y los encabezados de RN-10. |
| CA-17 | Nueva versión: origen conserva PDF, nueva no tiene material; no se alteran las inscripciones de origen. |
| CA-18 | Reiniciar la aplicación conserva el material. Si falta el archivo físico, la API responde un error controlado, sin revelar rutas. |
| CA-F1 | Desde Cursos, el admin abre la ficha por nombre o «Ver ficha»; funciona también por URL directa y recarga. |
| CA-F2 | El admin agrega dos PDFs y los revisa seleccionándolos. El colaborador ve la misma lista y puede abrir ambos; solo se descarga al visor el seleccionado. |
| CA-F3 | La ficha del admin muestra el contenido compartido y sus controles de gestión, sin fecha de asignación ficticia. |
| CA-F4 | Confirmar/cancelar reemplazo o retiro funciona; cancelar conserva el PDF vigente. Un error mantiene la ficha y permite reintentar. |
| CA-F5 | Sin PDFs se muestra el estado vacío; agregar, reemplazar y quitar actualizan lista y selección según RN-F11, sin recargar toda la página. |
| CA-F6 | Lectura y descarga funcionan en escritorio; en móvil se puede obtener el PDF aunque no haya visor integrado. |
| CA-F7 | Cambio rápido de documento o curso, o cierre de sesión, no muestra un PDF anterior por una petición tardía. |
| CA-F8 | Suite backend completa y build de producción frontend correctos; revisión real de subida → ficha admin → ficha colaborador → reemplazo → retiro. |

## Artículo 7 — Contrato de interfaz

### API

| Método | Ruta | Resultado |
|---|---|---|
| GET | `/course/{id}/` | Existente, admin: datos del curso con `materials` agregado. |
| POST | `/course/{id}/materials/` | Admin: agregar un PDF. Multipart con campo `file`; `201` con metadatos del documento. |
| PUT | `/course/{id}/materials/{material_id}/` | Admin: reemplazar ese PDF. Multipart con campo `file`; `200` con sus metadatos actualizados. |
| DELETE | `/course/{id}/materials/{material_id}/` | Admin: ocultar ese PDF; `204`. Repetir sobre el mismo documento oculto del curso accesible también devuelve `204`; un id inexistente o de otro curso devuelve `404`. |
| GET | `/course/{id}/materials/{material_id}/file/` | Admin: bytes del PDF de un curso propio; `200` o `404` si no es accesible. |
| GET | `/course-collaborator/my-courses/{enrollment_id}/materials/{material_id}/file/` | Colaborador: bytes del PDF perteneciente al curso de una inscripción propia; `200` o `404`. |

El archivo se identifica dentro del curso en el admin y dentro de la inscripción
en el colaborador. En ambos casos debe pertenecer al curso resuelto. La descarga
del cliente usa la misma entrega autenticada que la lectura.

La propiedad `materials` se agrega al curso de las respuestas de lista y ficha de
ambos roles; es de solo lectura y vale `[]` si no hay PDFs visibles. No cambia la
forma exterior de `MyEnrollment`. Los listados no descargan archivos binarios.
Crear un curso o publicar una versión nueva devuelve `materials: []`.

Ejemplo de metadatos de un documento; POST y PUT devuelven este mismo formato:

```json
{
  "id": 17,
  "filename": "guia-de-seguridad.pdf",
  "size_bytes": 248320,
  "page_count": 8,
  "updated_at": "2026-09-05T18:30:00Z"
}
```

Error de validación:

```json
{ "file": ["El archivo debe ser un PDF válido de hasta 10 MB y sin cifrado."] }
```

Los mensajes concretos DEBEN distinguir ausencia, tamaño, formato y cifrado.
Para un archivo físico no disponible, la lectura responde `404` con un mensaje
controlado. Los errores de autenticación conservan el contrato existente.

### Pantallas

- **Admin:** catálogo → ficha → seleccionar PDF → confirmar subida →
  revisar el PDF persistido en el contenido compartido.
- **Colaborador:** Mis cursos → ficha → material → leer o descargar.
- El admin conserva su layout y el colaborador el suyo. Cambian los controles
  disponibles por rol, no el contenido del curso que presentan.

## Artículo 8 — Preguntas abiertas y supuestos

- **PA-1 — resuelta por el usuario:** varios PDFs por curso. Cada documento puede
  reemplazarse o quitarse sin tocar los demás. Se sube un archivo por operación
  para que sus errores y resultado sean inequívocos; no hay carga por lotes.
- **PA-2 — resuelta y aprobada:** máximo 10 MiB y PDFs sin cifrado.
  Acota el tiempo de subida y carga; no se añade un segundo flujo de contraseñas.
- **PA-3 — resuelta y aprobada:** subir publica de inmediato. El admin revisa
  lo que está guardado; no se introduce un estado de borrador separado.
- **PA-4 — resuelta y aprobada:** reemplazar es una corrección de material y
  afecta a los inscritos de esa versión. No cambia por sí solo el número de
  versión; para otro contenido formativo se usa la nueva versión existente.
- **PA-5 — resuelta y aprobada:** la nueva versión empieza sin PDF.
  Evita heredar material anterior sin que el admin lo elija conscientemente.
- **PA-6 — resuelta y aprobada:** quitar usa borrado lógico. No se agrega una
  pantalla de recuperación ni un historial de archivos reemplazados. Agregar otro
  archivo, incluso con el mismo nombre, crea otro id; reemplazar es la acción que
  conserva id y posición. Dos documentos pueden compartir nombre sin sobrescribirse.
- **PA-7 — resuelta:** el admin puede abrir la ficha sin inscripción. Su pregunta
  es «¿qué contenido publiqué y cómo se ve?»; esto sustituye la exclusión de ficha
  admin de SPEC-010 Artículo 3 y PA-9.
- **PA-8 — resuelta:** mismo contenido no significa suplantar al colaborador.
  No se cambia la sesión ni se inventa fecha de asignación.
- **PA-9 — resuelta y aprobada:** se permite descargar. Es una alternativa
  concreta cuando el navegador no muestra el PDF dentro de la ficha.
- **PA-10 — resuelta:** el almacenamiento es local, como pide la guía del repo,
  con entrega autenticada. No se requieren cuentas ni credenciales externas.
- **PA-11 — resuelta y aprobada:** orden de subida, de más antiguo a más
  reciente, para que el admin arme una secuencia sencilla. Un único visor muestra
  el seleccionado: abrir la ficha no debe descargar varios PDFs de 10 MiB a la vez.

## Artículo 9 — Decisiones, dependencias y referencias

- Las decisiones de almacenamiento, validación y visor se documentan en
  `docs/adr/ADR-001-material-pdf-local.md`, separado de las reglas de producto.
- Se extienden las respuestas de SPEC-010 conservando la igualdad entre curso en
  lista y ficha; se mantiene el criterio de inscripciones propias compartido.
- Se incorpora almacenamiento de material con su migración: la restricción de
  SPEC-010 de no agregar campos no se extiende a esta nueva capacidad.
- Se mantiene Model → Serializer → View, los permisos existentes, Vuetify, los
  layouts, Pinia y `$apiFetch`. Las rutas se declaran en `apiEndpoints.ts`.
- Primero se aprueba la spec, luego se escriben los tests backend y se implementa.
  Al cerrar se actualizan `CLAUDE.md`, `SUPUESTOS.md`, `MEJORAS.md`, `README.md`
  y `docs/FILES.md`, incluyendo los pasos para demostrar el flujo con PDF.
- Referencias de producto: enunciado §6.2, SPEC-007 (versiones y bajas),
  SPEC-010 con Enmienda 2 y decisión de aislamiento entre organizaciones.
