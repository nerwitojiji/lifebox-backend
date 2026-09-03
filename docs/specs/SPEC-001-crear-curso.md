# SPEC-001 — Crear curso

- **Capacidad:** Gestión de cursos del admin (entregable 1 del enunciado)
- **Feature:** Crear curso · rama `feature/crear-curso`
- **Estado:** Borrador para revisión
- **Repos:** `lifebox-backend` (endpoint) · `lifebox-frontend` (formulario)

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.
> Los nombres de los artículos siguen la anatomía de nueve artículos; ajusta los
> encabezados si tu plantilla de referencia usa otros títulos.

---

## Artículo 1 — Contexto y encuadre

El módulo de administrador gestiona cursos. Hoy el modelo `Course` ya existe en
`apps/course/models.py` con los campos `full_name`, `description`,
`duration_hours`, `version`, `organization` (FK), `is_active`, más los heredados
de `BaseAbstractModel` (`created_at`, `updated_at`, `show`).

La vista actual `CourseListView` expone **solo** `GET /course/` (`ListAPIView`,
permiso `IsAdmin`, queryset filtrado por la organización del admin y `show=True`).
**No existe** un endpoint de creación. En el frontend, `endpoints/apiEndpoints.ts`
ya declara `courses()` → `/course/` (usado hoy para el GET; la creación es un POST
a la misma ruta), y la página `pages/admin/courses/index.vue` solo lista en una
tabla, sin UI para crear.

Esta spec cubre agregar la creación de cursos, de punta a punta (backend +
frontend), reutilizando el modelo, el permiso y la autenticación existentes.

## Artículo 2 — Objetivo

Permitir que un administrador autenticado cree un curso dentro de su organización,
indicando nombre, descripción, duración aproximada y versión, y que ese curso
quede disponible de inmediato en el listado de cursos de su organización.

## Artículo 3 — Alcance

**Dentro de alcance:**
- Endpoint `POST /course/` con validación de entrada.
- Asignación de la organización desde el servidor.
- Enforcement de permiso (solo admin).
- Formulario de creación en `pages/admin/courses/`.

**Fuera de alcance (otras specs / features):**
- Editar o versionar un curso existente (corrección de versión → feature posterior).
- Eliminar / desactivar cursos.
- Subir material del curso (PDF/video/audio → bonus, `docs/FILES.md`).
- Asignar colaboradores al curso (→ SPEC-003, feature `asignar-curso`).

## Artículo 4 — Actores y precondiciones

- **Actor:** administrador autenticado (usuario con `admin_profile`).
- **Precondiciones:** token Knox válido; el usuario tiene `admin_profile` asociado
  a una `Organization`.

## Artículo 5 — Reglas de negocio (normativas)

- **RN-1.** El sistema DEBE exponer `POST /course/` para crear un curso.
- **RN-2.** Solo un usuario autenticado con perfil de admin DEBE poder crear
  cursos. Un colaborador autenticado NO DEBE poder, y el sistema DEBE responder
  `403`. Una petición sin token válido DEBE responder `401`.
- **RN-3.** `full_name` DEBE ser obligatorio y no vacío. Si falta o viene vacío, el
  sistema DEBE responder `400` y NO DEBE crear ningún registro.
- **RN-4.** La organización del curso DEBE derivarse del perfil del admin
  autenticado (`request.user.admin_profile.organization`). El sistema **NO DEBE**
  aceptar ni confiar en un `organization` / `organization_id` enviado en el body;
  si llega, DEBE ignorarlo. *(Regla crítica de seguridad: enforcement server-side.)*
- **RN-5.** `duration_hours`, si se envía, DEBE ser un entero positivo (≥ 1). Un
  valor ≤ 0 o no numérico DEBE rechazarse con `400`. Si se omite, DEBERÍA usar el
  valor por defecto del modelo (1).
- **RN-6.** `description` PODRÍA omitirse; si se omite, DEBE persistirse vacía.
- **RN-7.** `version`, si se omite, DEBERÍA usar el valor por defecto `"1.0"`.
- **RN-8.** Al crear, `is_active` DEBERÍA quedar en `true` y `show` DEBE quedar en
  `true` (el curso nace visible y activo).
- **RN-9.** Ante una creación válida, el sistema DEBE responder `201` con la
  representación del curso creado (incluyendo su `id`).
- **RN-10.** El curso creado DEBE aparecer de inmediato en `GET /course/` del mismo
  admin, y NO DEBE ser visible para admins de otra organización.

## Artículo 6 — Criterios de aceptación (Given / When / Then)

- **CA-1 (camino feliz).** *Dado* un admin autenticado, *cuando* hace
  `POST /course/` con `full_name` válido, *entonces* la respuesta es `201` y el
  curso queda persistido con la organización del admin.
- **CA-2 (validación).** *Dado* un admin autenticado, *cuando* hace `POST` sin
  `full_name`, *entonces* la respuesta es `400` y no se crea ningún curso.
- **CA-3 (org server-side).** *Dado* un admin de la organización A, *cuando* hace
  `POST` incluyendo `organization_id` de otra organización B en el body,
  *entonces* el curso se crea en **A** (el body se ignora).
- **CA-4 (permiso colaborador).** *Dado* un colaborador autenticado, *cuando* hace
  `POST /course/`, *entonces* la respuesta es `403`.
- **CA-5 (sin autenticación).** *Dada* una petición sin token, *cuando* hace
  `POST /course/`, *entonces* la respuesta es `401`.
- **CA-6 (duración inválida).** *Dado* un admin autenticado, *cuando* hace `POST`
  con `duration_hours = 0` (o negativo), *entonces* la respuesta es `400`.
- **CA-7 (aparece en el listado).** *Dado* un admin que creó un curso, *cuando*
  hace `GET /course/`, *entonces* el curso aparece en la lista.
- **CA-8 (aislamiento por tenant).** *Dado* un curso creado por un admin de A,
  *cuando* un admin de B hace `GET /course/`, *entonces* NO ve ese curso.

## Artículo 7 — Contrato de interfaz

**Endpoint:** `POST /course/`
**Autenticación:** `Authorization: Token <token>` (Knox) · permiso `IsAdmin`

**Request (JSON):**

| Campo            | Tipo   | Obligatorio | Notas                              |
|------------------|--------|-------------|------------------------------------|
| `full_name`      | string | Sí          | No vacío                           |
| `description`    | string | No          | Default: `""`                      |
| `duration_hours` | int    | No          | ≥ 1; default 1                     |
| `version`        | string | No          | Default `"1.0"`; texto libre       |

> `organization` **no** forma parte del contrato de entrada: se deriva del servidor.

**Respuestas:**
- `201 Created` → objeto del curso: `{ id, full_name, description, duration_hours, version, is_active, created_at }`
- `400 Bad Request` → errores de validación por campo: `{ "full_name": ["..."] }`
- `401 Unauthorized` → sin token válido
- `403 Forbidden` → autenticado pero sin perfil de admin

## Artículo 8 — Preguntas abiertas

Cada resolución propuesta, una vez confirmada, baja a `SUPUESTOS.md`.

- **PA-1.** ¿`duration_hours` obligatorio u opcional con default?
  **Propuesta:** opcional, default 1; si se envía se valida ≥ 1.
  *(Nota: `PositiveIntegerField` de Django admite 0; el ≥ 1 es validación añadida.)*
- **PA-2.** ¿Se valida el formato de `version` (p. ej. semver) o es texto libre?
  **Propuesta:** texto libre (el modelo es `CharField(20)`). Interpretamos la
  "versión corta" del enunciado como texto tipo `"1.0.1"`.
- **PA-3.** ¿El admin puede fijar `is_active` al crear?
  **Propuesta:** no; nace `true`. Activar/desactivar sería otra acción, fuera de
  alcance.
- **PA-4.** ¿Cómo se modela la "duración aproximada"?
  **Propuesta:** en horas, entero (`duration_hours`); el label en UI será
  "Duración aproximada (horas)".
- **PA-5.** ¿Vista única `ListCreateAPIView` o vistas separadas para GET y POST?
  **Propuesta:** `ListCreateAPIView` con **serializer de escritura separado** del
  de lectura (o `get_serializer_class`), para no exponer campos de solo lectura en
  la creación. Es decisión de diseño menor; si se quisiera formalizar, iría en un
  ADR aparte.

## Artículo 9 — Decisiones, dependencias y referencias

**Reutiliza (no reinventa):**
- Modelo `Course` (`apps/course/models.py`).
- Permiso `IsAdmin` (`utils/custom_permissions.py`).
- Autenticación Knox (`TokenAuthentication`).
- `BaseAbstractModel` (aporta `show`, `created_at`, `updated_at`).

**Contrato de frontend:** ya declarado en `endpoints/apiEndpoints.ts` (`courses()`).

**Implementación esperada (backend):** convertir/extender la vista a
`ListCreateAPIView`, con `IsAdmin`, y en `perform_create` asignar la organización:
`serializer.save(organization=self.request.user.admin_profile.organization)` — ahí
queda enforzada la RN-4.

**Relación con otras specs:** SPEC-002 (crear colaborador), SPEC-003 (asignar
curso), SPEC-004 (mis cursos) y SPEC-005 (panel de inscripciones) reutilizan esta
misma anatomía y patrones.

---

## Anexo A — Lista de tests derivada (puente SDD → TDD)

Cada criterio de aceptación se traduce a un test en un `APITestCase` del backend,
usando `utils/model_factories.py` y corriendo con `make test`. Escríbelos **primero**
(rojo), luego implementa hasta verde, luego refactoriza.

Sugerencia de `apps/course/tests/test_create_course.py`:

- `test_admin_puede_crear_curso` → CA-1 (201 + org del admin persistida)
- `test_crear_curso_sin_full_name_devuelve_400` → CA-2
- `test_organizacion_del_body_es_ignorada` → CA-3
- `test_colaborador_no_puede_crear_curso` → CA-4 (403)
- `test_crear_curso_sin_token_devuelve_401` → CA-5
- `test_duration_hours_invalida_devuelve_400` → CA-6
- `test_curso_creado_aparece_en_listado` → CA-7
- `test_curso_no_es_visible_para_otra_organizacion` → CA-8 (aislamiento tenant)

**Verificación de frontend (checklist manual, sin test runner en este repo):**
- El formulario en `admin/courses` crea un curso y lo refleja en la tabla sin recargar.
- Errores de validación (`400`) se muestran al usuario de forma clara.
- Un colaborador no tiene acceso a la pantalla de creación.