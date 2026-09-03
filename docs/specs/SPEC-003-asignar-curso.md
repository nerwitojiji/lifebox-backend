# SPEC-003 — Asignar curso a colaborador

- **Capacidad:** Gestión de asignaciones del administrador
- **Feature:** Asignar curso · rama `feature/asignar-curso`
- **Estado:** Aprobada
- **Repos:** `lifebox-backend` (endpoint) · `lifebox-frontend` (interfaz)

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

---

## Artículo 1 — Contexto y encuadre

SPEC-001 permite crear cursos y SPEC-002 permite crear colaboradores. El modelo
`CourseCollaborator` ya representa una inscripción mediante `course`,
`collaborator`, `assigned_at`, `show` y una restricción única para el par, pero no
existe una operación HTTP para crearlo. El frontend ya declara
`POST /course/{id}/assign/`. Esta capacidad habilita SPEC-004 (mis cursos) y
SPEC-005 (panel de inscripciones).

## Artículo 2 — Objetivo

Permitir que un administrador asigne un curso visible y activo de su organización
a un colaborador visible y habilitado del mismo tenant, sin duplicados ni cruces
entre organizaciones.

## Artículo 3 — Alcance

**Dentro de alcance:** endpoint `POST /course/{id}/assign/`, validación de curso y
colaborador, aislamiento por tenant, prevención de duplicados e interfaz admin de
asignación con estados de carga, éxito y error.

**Fuera de alcance:** mis cursos, panel agregado, `GET
/course/{id}/collaborators/`, desasignar, reactivar inscripciones ocultas,
asignaciones masivas, notificaciones y edición o baja de cursos/colaboradores.

## Artículo 4 — Actores y precondiciones

- **Actor:** administrador autenticado con `admin_profile` y organización.
- **Precondiciones:** token Knox válido; curso visible y activo; colaborador
  visible, con usuario visible y activo; ambos pertenecen al tenant del admin.
- Un colaborador autenticado NO DEBE poder crear asignaciones.

## Artículo 5 — Reglas de negocio

- **RN-1.** El sistema DEBE exponer `POST /course/{id}/assign/` para `IsAdmin`.
  Sin token DEBE responder `401`; con rol colaborador, `403`.
- **RN-2.** El curso DEBE obtenerse de `{id}` y `collaborator_id` DEBE ser un
  entero obligatorio del body.
- **RN-3.** La organización DEBE derivarse exclusivamente de
  `request.user.admin_profile.organization`. Campos de control enviados en el body
  (`course_id`, `organization`, `organization_id`, `show`, `assigned_at`) NO DEBEN
  alterar la inscripción.
- **RN-4.** El curso DEBE pertenecer al tenant, tener `show=True` e
  `is_active=True`; en caso contrario DEBE responder `404`.
- **RN-5.** El colaborador DEBE pertenecer al tenant, tener `show=True`, y su
  `User` DEBE tener `show=True` e `is_active=True`; en caso contrario DEBE
  responder `404`, sin revelar recursos de otro tenant.
- **RN-6.** El mismo par curso-colaborador NO DEBE inscribirse dos veces. Si ya
  existe —también con `show=False`— DEBE responder `400` bajo
  `collaborator_id`; esta spec NO reactiva inscripciones.
- **RN-7.** Una asignación válida DEBE crear un único `CourseCollaborator` con
  `show=True` y responder `201` con la inscripción, curso y colaborador.
- **RN-8.** Una petición fallida NO DEBE crear ni modificar inscripciones. Una
  colisión concurrente con la restricción única NO DEBE producir `500`.
- **RN-9.** La UI DEBE impedir reenvíos durante la petición y comunicar el
  resultado en español sin recargar la página.

## Artículo 6 — Criterios de aceptación

- **CA-1:** una asignación válida responde `201` y persiste un único registro.
- **CA-2:** el `201` incluye `id`, `assigned_at`, curso y colaborador.
- **CA-3:** campos de organización/control del body se ignoran.
- **CA-4:** curso de otro tenant responde `404` y no crea nada.
- **CA-5:** colaborador de otro tenant responde `404` y no crea nada.
- **CA-6:** curso inexistente responde `404`.
- **CA-7:** colaborador inexistente responde `404`.
- **CA-8:** omitir `collaborator_id` responde `400` bajo esa clave.
- **CA-9:** `collaborator_id` no entero responde `400`.
- **CA-10:** repetir el par responde `400`, no aumenta la cantidad y nunca da
  `500`; una inscripción oculta tampoco se reactiva.
- **CA-11:** un colaborador autenticado recibe `403`.
- **CA-12:** una petición sin token recibe `401`.
- **CA-13:** un curso oculto o inactivo responde `404`.
- **CA-14:** un colaborador oculto, o con usuario oculto/inactivo, responde `404`.
- **CA-15:** la UI permite asignar desde el curso, muestra carga y éxito sin
  recargar; ante error mantiene el diálogo y muestra un mensaje comprensible.
- **CA-16:** sin colaboradores, la UI presenta un estado vacío y acceso a su
  gestión.

## Artículo 7 — Contrato de interfaz

### `POST /course/{id}/assign/`

**Autenticación:** `Authorization: Token <token>` · permiso `IsAdmin`.

**Request:**

```json
{ "collaborator_id": 7 }
```

**Respuesta `201`:**

```json
{
  "id": 15,
  "assigned_at": "2026-09-03T15:30:00Z",
  "course": { "id": 3, "full_name": "Prevención de riesgos", "version": "1.0" },
  "collaborator": { "id": 7, "full_name": "Ana Pérez", "email": "ana@acme.cl" }
}
```

**Errores:** `400` por entrada inválida/duplicado (bajo `collaborator_id`), `401`,
`403` y `404` para recursos inexistentes, no disponibles o fuera del tenant.

**Frontend:** acción “Asignar colaborador” por curso en
`pages/admin/courses/index.vue`; diálogo con curso y versión, selector alimentado
por `GET /collaborator/`, envío mediante `courseAssign(id)` y feedback en español.

## Artículo 8 — Preguntas abiertas resueltas

- **PA-1:** la asignación se realiza desde una acción por curso en la pantalla de
  cursos.
- **PA-2:** la asignación es individual, una inscripción por petición.
- **PA-3:** un duplicado responde `400` bajo `collaborator_id`.
- **PA-4:** una inscripción con `show=False` no se reactiva automáticamente.
- **PA-5:** cursos inactivos no admiten nuevas inscripciones.
- **PA-6:** colaboradores ocultos o con usuario oculto/inactivo no admiten nuevas
  inscripciones.
- **PA-7:** `GET /course/{id}/collaborators/` se posterga para SPEC-005.

## Artículo 9 — Decisiones, dependencias y referencias

El backend reutiliza `Course`, `Collaborator`, `CourseCollaborator`,
`TokenAuthentication`, `IsAdmin` y el tenant del admin. La vista y sus serializers
viven en `apps/course/views.py`, respetando la arquitectura actual; no se agregan
modelos, migraciones, dependencias ni routers.

El frontend reutiliza `pages/admin/courses/index.vue`, `models/course.ts`,
`useApiEndpoints()`, `$apiFetch` y Vuetify. Depende de SPEC-001/002 y habilita
SPEC-004/005.

---

## Anexo A — Tests y verificaciones

Los tests backend se escriben primero en `apps/course/tests/test_assign_course.py`
y cubren cada CA, incluyendo aislamiento en ambas direcciones, estados ocultos e
inactivos, entrada hostil, duplicados visibles/ocultos y preservación ante error.

El frontend no incorpora un test runner nuevo: se verifica con `npm run build` y
checklist manual de apertura, selección, bloqueo durante envío, éxito, duplicado,
error y estado sin colaboradores.
