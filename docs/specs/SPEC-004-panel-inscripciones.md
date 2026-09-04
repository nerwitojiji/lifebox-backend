# SPEC-004 — Panel de inscripciones

- **Capacidad:** Visibilidad de inscripciones para el administrador
- **Feature:** Panel de inscripciones · rama `feature/panel-inscripciones`
- **Estado:** Aprobada
- **Repos:** `lifebox-backend` (endpoint) · `lifebox-frontend` (interfaz)

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

---

## Artículo 1 — Contexto y encuadre

SPEC-003 permite inscribir un colaborador en un curso, pero la inscripción queda
invisible: tras confirmar, el administrador ve un mensaje efímero y la pantalla de
cursos no refleja ningún cambio. No existe ninguna vista que responda «cuántos
inscritos tiene cada curso».

El objetivo 3 de la entrega pide exactamente eso: un resumen por curso con nombre,
versión y cantidad de inscritos, todo junto. El frontend ya declara
`GET /course/enrollments/` en `endpoints/apiEndpoints.ts` y la página
`pages/admin/enrollments/index.vue` es un stub «Próximamente».

Esta spec cubre el **conteo** agregado. Ver **quiénes** son los inscritos de un
curso (`GET /course/{id}/collaborators/`) queda para SPEC-005, como fijó SPEC-003
en su PA-7.

> **Nota de numeración:** el Artículo 1 de SPEC-003 anticipó «SPEC-004 (mis
> cursos) y SPEC-005 (panel de inscripciones)», mientras que su PA-7 asignó a
> SPEC-005 el detalle de inscritos. Se resuelve la ambigüedad así: **SPEC-004 =
> panel de inscripciones**, **SPEC-005 = detalle de inscritos por curso**, y mis
> cursos toma el número siguiente.

## Artículo 2 — Objetivo

Permitir que un administrador vea, en una sola pantalla, cada curso de su
organización con su nombre, versión y cantidad de colaboradores inscritos; y que
ese mismo conteo aparezca en la pantalla de cursos, de modo que asignar un
colaborador produzca un cambio visible y permanente.

## Artículo 3 — Alcance

**Dentro de alcance:** endpoint `GET /course/enrollments/` resuelto con una sola
agregación del ORM; campo `enrolled_count` agregado a `GET /course/`; pantalla
`admin/enrollments` con el resumen y totales, separando cursos activos de
inactivos en secciones distintas; columna «Inscritos» en la pantalla de cursos
con refresco tras asignar.

**Fuera de alcance:** el detalle de quiénes están inscritos (SPEC-005), mis
cursos, desasignar, reactivar inscripciones ocultas, paginación, filtros,
búsqueda, orden configurable por el usuario, exportar y gráficos.

## Artículo 4 — Actores y precondiciones

- **Actor:** administrador autenticado con `admin_profile` y organización.
- **Precondiciones:** token Knox válido. No se requieren cursos ni inscripciones
  previas: la ausencia de datos es un estado válido y representable.
- Un colaborador autenticado NO DEBE poder consultar el panel.

## Artículo 5 — Reglas de negocio

- **RN-1.** El sistema DEBE exponer `GET /course/enrollments/` para `IsAdmin`.
  Sin token DEBE responder `401`; con rol colaborador, `403`.
- **RN-2.** La organización DEBE derivarse exclusivamente de
  `request.user.admin_profile.organization`. Cualquier `organization`,
  `organization_id` o identificador de tenant recibido por query param NO DEBE
  alterar el resultado.
- **RN-3.** El panel DEBE incluir todos los cursos del tenant con `show=True`,
  **incluidos los que tienen cero inscritos** y los que tienen `is_active=False`.
  Un curso inactivo no desinscribe a nadie: conserva inscritos vigentes y DEBE
  seguir siendo auditable. La respuesta DEBE exponer `is_active` para que la
  interfaz separe ambos grupos.
- **RN-4.** Los cursos con `show=False` NO DEBEN aparecer, y ningún curso de otra
  organización DEBE aparecer.
- **RN-5.** `enrolled_count` DEBE contar únicamente las inscripciones con
  `show=True` cuyo colaborador esté disponible: `collaborator.show=True`,
  `collaborator.user.show=True` y `collaborator.user.is_active=True`. El conteo
  refleja inscritos vigentes, con el mismo criterio de disponibilidad que RN-5 de
  SPEC-003 usa para admitirlos.
- **RN-6.** El conteo DEBE resolverse con una única consulta agregada
  (`annotate(Count(..., filter=Q(...)))`). NO DEBE contarse en Python ni emitir
  una consulta por curso.
- **RN-7.** El resultado DEBE llegar agrupado por estado: primero los cursos
  activos, luego los inactivos. Dentro de cada grupo DEBE ordenarse por
  `enrolled_count` descendente y, ante empate, por `full_name` ascendente, de modo
  que el orden sea estable y determinista. La agrupación la resuelve el servidor
  para que la lista plana sea legible aun sin separarla.
- **RN-8.** `GET /course/` DEBE incorporar `enrolled_count` con la misma
  definición de RN-5. La incorporación es aditiva: los campos ya existentes del
  listado NO DEBEN cambiar de nombre, tipo ni orden.
- **RN-9.** Tras una asignación exitosa, la pantalla de cursos DEBE reflejar el
  nuevo conteo sin recargar la página.
- **RN-10.** La interfaz DEBE representar en español los estados de carga, error
  y vacío, y NO DEBE presentar un panel en blanco cuando no hay cursos.
- **RN-11.** La interfaz NO DEBE mezclar cursos activos e inactivos en una misma
  tabla. Los activos DEBEN ocupar la sección principal; los inactivos DEBEN ir en
  una sección propia, posterior y rotulada, que declare cuántos cursos agrupa y
  cuántos inscritos vigentes suman. Si no hay cursos inactivos, esa sección NO
  DEBE mostrarse.
- **RN-12.** Los totales de cabecera DEBEN calcularse **solo sobre cursos
  activos** (cursos activos, inscripciones vigentes en ellos y cursos activos sin
  inscritos). Incluir cursos retirados distorsionaría la lectura del programa
  vigente, que es lo que esos totales responden.

## Artículo 6 — Criterios de aceptación

- **CA-1:** un admin con cursos e inscripciones recibe `200` con una fila por
  curso visible del tenant.
- **CA-2:** cada fila incluye `id`, `full_name`, `version`, `is_active` y
  `enrolled_count`.
- **CA-3:** un curso sin inscripciones aparece con `enrolled_count` igual a `0`.
- **CA-4:** un curso con `is_active=False` aparece, con su conteo y su bandera, y
  se ubica después de todos los activos.
- **CA-5:** un curso con `show=False` no aparece.
- **CA-6:** los cursos e inscripciones de otra organización no afectan ni las
  filas ni los conteos.
- **CA-7:** una inscripción con `show=False` no se cuenta.
- **CA-8:** una inscripción cuyo colaborador tiene `show=False` no se cuenta.
- **CA-9:** una inscripción cuyo usuario tiene `show=False` o `is_active=False`
  no se cuenta.
- **CA-10:** el orden agrupa activos antes que inactivos y, dentro de cada grupo,
  es por conteo descendente y, ante empate, alfabético por nombre. Un curso
  inactivo con muchos inscritos NO precede a un curso activo con pocos.
- **CA-11:** un admin sin cursos recibe `200` con una lista vacía.
- **CA-12:** un colaborador autenticado recibe `403`.
- **CA-13:** una petición sin token recibe `401`.
- **CA-14:** un `organization` enviado por query param no altera el resultado.
- **CA-15:** la respuesta se resuelve en una cantidad de consultas constante,
  independiente de la cantidad de cursos.
- **CA-16:** `GET /course/` incluye `enrolled_count` con el mismo criterio, sin
  alterar los demás campos.
- **CA-17:** la pantalla `admin/enrollments` muestra el resumen, sus totales y los
  estados de carga, error y vacío.
- **CA-18:** asignar un colaborador incrementa el conteo visible en la pantalla de
  cursos sin recargar.
- **CA-19:** la pantalla presenta los cursos activos y los inactivos en secciones
  separadas, y la sección de inactivos declara cuántos cursos e inscritos agrupa.
- **CA-20:** sin cursos inactivos, esa sección no se muestra y la pantalla no deja
  un hueco ni un encabezado vacío.
- **CA-21:** los totales de cabecera no incluyen cursos inactivos ni sus
  inscritos.

## Artículo 7 — Contrato de interfaz

### `GET /course/enrollments/`

**Autenticación:** `Authorization: Token <token>` · permiso `IsAdmin`.

**Respuesta `200`** — lista plana, ya agrupada: activos primero, luego inactivos;
dentro de cada grupo, por conteo descendente y nombre (RN-7).

```json
[
  {
    "id": 3,
    "full_name": "Prevención de riesgos",
    "version": "1.0",
    "is_active": true,
    "enrolled_count": 12
  },
  {
    "id": 8,
    "full_name": "Ergonomía en oficina",
    "version": "1.0",
    "is_active": true,
    "enrolled_count": 0
  },
  {
    "id": 5,
    "full_name": "Inducción corporativa",
    "version": "1.0",
    "is_active": false,
    "enrolled_count": 4
  }
]
```

El último elemento ilustra por qué los inactivos no se esconden: el curso está
retirado y aun así cuatro personas siguen inscritas.

**Errores:** `401` sin token, `403` con rol colaborador.

### `GET /course/` (cambio aditivo)

Cada elemento incorpora `enrolled_count` junto a los campos actuales (`id`,
`full_name`, `description`, `duration_hours`, `version`, `is_active`,
`created_at`).

**Frontend:**

- `pages/admin/enrollments/index.vue` reemplaza el stub por el resumen, en dos
  secciones. Cabecera con tarjetas de cursos activos, inscripciones vigentes y
  cursos activos sin inscritos (RN-12). **Sección principal:** tabla de cursos
  activos con nombre, versión y cantidad de inscritos. **Sección de inactivos:**
  tabla aparte, visualmente atenuada, precedida por un rótulo del tipo «Cursos
  inactivos · N cursos · M inscritos vigentes», presente solo si hay alguno
  (RN-11). Estados de carga, error y vacío con acceso a la creación de cursos.
- `pages/admin/courses/index.vue` suma la columna «Inscritos» y llama a `refresh()`
  tras una asignación exitosa.
- `models/course.ts` incorpora `enrolled_count` en `Course` y el tipo
  `CourseEnrollmentSummary`.

## Artículo 8 — Preguntas abiertas resueltas

- **PA-1:** los cursos sin inscritos SÍ aparecen, con conteo `0`. Ocultarlos haría
  desaparecer del panel justo a los cursos que necesitan atención.
- **PA-2:** los cursos inactivos SÍ aparecen, pero **no mezclados con los
  activos**: van en una sección propia y quedan fuera de los totales de cabecera.
  El panel es un reporte y desactivar un curso no desinscribe a nadie, así que
  esconderlos ocultaría inscripciones vigentes; mezclarlos, en cambio,
  distorsionaría la lectura del programa vigente. La separación resuelve ambas.
- **PA-3:** el conteo excluye inscripciones ocultas y colaboradores no
  disponibles: mide inscritos vigentes, no historial.
- **PA-4:** el orden lo fija el servidor (conteo descendente, luego nombre); no se
  ofrece ordenamiento configurable.
- **PA-5:** el conteo en la pantalla de cursos se resuelve extendiendo
  `GET /course/`, no consumiendo el panel desde esa pantalla. Evita una segunda
  petición y el cruce de dos listas en el cliente.
- **PA-6:** la respuesta es una lista plana, sin envoltorio ni paginación,
  coherente con los demás listados del proyecto. La separación entre activos e
  inactivos es de presentación: el servidor entrega la lista ya agrupada (RN-7) y
  la interfaz la corta, en vez de devolver `{ "active": [], "inactive": [] }`. Los
  totales se derivan en la interfaz.
- **PA-7:** el detalle de inscritos por curso se mantiene en SPEC-005.
- **PA-8:** dar de baja a un colaborador lo saca del conteo, y el efecto es
  reversible: la inscripción no se borra, solo deja de contarse, de modo que
  reactivarlo restituye el número sin intervención. Esto expone un hueco previo
  del código: `IsCollaborator` no verifica `show`, así que un colaborador con
  `Collaborator.show=False` y `user.is_active=True` queda invisible para el admin
  pero puede seguir iniciando sesión y vería sus cursos, haciendo que el panel
  informe menos inscritos de los que en la práctica acceden al curso. Este spec NO
  corrige el hueco —está fuera de alcance—, pero **la futura capacidad de baja
  DEBE apagar ambos estados a la vez** (`Collaborator.show=False` y
  `user.is_active=False`). Con esa condición el criterio de RN-5 queda íntegro y
  no hace falta modificar los permisos.

## Artículo 9 — Decisiones, dependencias y referencias

El backend reutiliza `Course`, `CourseCollaborator`, `TokenAuthentication`,
`IsAdmin` y el tenant del admin. La vista es un `ListAPIView` con su serializer en
`apps/course/views.py`, siguiendo la convención del repo. La ruta se declara en
`apps/course/urls.py` como `enrollments/` antes de `<int:pk>/assign/`; no hay
colisión con el conversor `int`, pero el orden explícito documenta la intención.
No se agregan modelos, migraciones, dependencias ni routers.

El conteo se obtiene con `annotate(Count("course_collaborators", filter=Q(...)))`
sobre el queryset ya filtrado por tenant, y el mismo anotado alimenta
`GET /course/`, de modo que exista una sola definición de «inscrito vigente».

El frontend reutiliza `layouts/admin.vue` (la entrada «Inscripciones» ya existe en
el menú), `useApiEndpoints()`, `$apiFetch`, `useAsyncData` y Vuetify. Depende de
SPEC-001, SPEC-002 y SPEC-003, y no bloquea a SPEC-005.

---

## Anexo A — Tests y verificaciones

Los tests backend se escriben primero en
`apps/course/tests/test_enrollments_panel.py` y cubren cada CA: contrato de campos,
cursos sin inscritos, cursos inactivos y ocultos, aislamiento entre organizaciones
en ambas direcciones, inscripciones y colaboradores no vigentes, orden
determinista, permisos `401`/`403`, query params hostiles y `assertNumQueries` para
CA-15. Se agrega además la verificación de `enrolled_count` en el listado de cursos
(CA-16), comprobando que los campos previos se mantienen.

El frontend se verifica con `npm run build` y checklist manual: panel con datos,
panel vacío, error de red, sección de inactivos presente con su rótulo y ausente
cuando no corresponde, totales de cabecera sin contar inactivos, columna
«Inscritos» en cursos e incremento del conteo tras una asignación exitosa.
