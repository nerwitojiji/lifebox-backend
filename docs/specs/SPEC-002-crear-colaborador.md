# SPEC-002 — Crear colaborador

- **Capacidad:** Gestión de colaboradores del admin (entregable 1 del enunciado)
- **Feature:** Crear colaborador · rama `feature/crear-colaborador`
- **Estado:** Borrador para revisión
- **Repos:** `lifebox-backend` (endpoint) · `lifebox-frontend` (pantalla + formulario)

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

---

## Artículo 1 — Contexto y encuadre

Un colaborador no es un modelo suelto: es un **par** `User` + `Collaborator`. El
`User` (`apps/user/models.py`) tiene el email como `USERNAME_FIELD` y la
contraseña; el perfil `Collaborator` cuelga 1-a-1 de ese `User` y lo ata a una
`Organization`. El rol no es un campo — se deriva de la existencia del perfil, y de
eso dependen el permiso `IsCollaborator` y el ruteo del frontend.

Hoy existe `CollaboratorListView` (`apps/user/collaborator_views.py`): **solo**
`GET /collaborator/`, permiso `IsAdmin`, queryset filtrado por la organización del
admin y `show=True`, devolviendo `{id, email, full_name}`. **No existe** endpoint de
creación, así que los únicos colaboradores del sistema son los que planta
`seeder.py`. Sin este endpoint no hay a quién asignarle un curso (SPEC-003) ni quién
inicie sesión para ver los suyos (SPEC-004).

En el frontend, `endpoints/apiEndpoints.ts` ya declara `collaborators()` →
`/collaborator/`, pero **ninguna página lo consume**: `pages/admin/` solo tiene
`index`, `courses/` y `enrollments/`.

Esta spec cubre la creación de colaboradores de punta a punta, reutilizando el
modelo, el permiso y la autenticación existentes.

## Artículo 2 — Objetivo

Permitir que un administrador autenticado dé de alta a un colaborador de su
organización indicando nombre y correo, y que ese colaborador quede habilitado para
iniciar sesión de inmediato con una contraseña inicial que el sistema genera y le
entrega al admin una única vez.

## Artículo 3 — Alcance

**Dentro de alcance:**
- Endpoint `POST /collaborator/` con validación de entrada.
- Creación atómica del par `User` + `Collaborator`.
- Generación de la contraseña inicial y su entrega única en la respuesta.
- Asignación de la organización desde el servidor.
- Enforcement de permiso (solo admin).
- Pantalla `pages/admin/collaborators/` con listado y formulario de creación.

**Fuera de alcance (otras specs / features):**
- Editar o dar de baja un colaborador (corrección → feature posterior).
- Restablecer o cambiar la contraseña, y cualquier envío de correo.
- Asignar cursos al colaborador (→ SPEC-003, feature `asignar-curso`).
- Crear administradores (el enunciado solo pide colaboradores).

## Artículo 4 — Actores y precondiciones

- **Actor:** administrador autenticado (usuario con `admin_profile`).
- **Precondiciones:** token Knox válido; el usuario tiene `admin_profile` asociado a
  una `Organization`.
- **Actor secundario:** el colaborador creado, que después inicia sesión en
  `POST /user/login/` con su correo y la contraseña inicial.

## Artículo 5 — Reglas de negocio (normativas)

- **RN-1.** El sistema DEBE exponer `POST /collaborator/` para crear un colaborador.
  El `GET` existente NO DEBE cambiar de forma.
- **RN-2.** Solo un usuario autenticado con perfil de admin DEBE poder crear
  colaboradores. Un colaborador autenticado NO DEBE poder, y el sistema DEBE
  responder `403`. Una petición sin token válido DEBE responder `401`.
- **RN-3.** `email` DEBE ser obligatorio y con formato de correo válido. Si falta o
  es inválido, el sistema DEBE responder `400` y NO DEBE crear ningún registro.
- **RN-4.** El `email` DEBE ser único en todo el sistema (`User.email` es `unique`).
  Si ya existe —incluso si pertenece a otra organización o a un admin— el sistema
  DEBE responder `400` con el error bajo la clave `email`, y NO DEBE crear nada ni
  modificar el usuario existente.
- **RN-5.** `first_name` DEBE ser obligatorio y no vacío. `last_name` PODRÍA
  omitirse; si se omite, DEBE persistirse vacío.
- **RN-6.** La organización del colaborador DEBE derivarse del perfil del admin
  autenticado (`request.user.admin_profile.organization`). El sistema **NO DEBE**
  aceptar ni confiar en un `organization` / `organization_id` enviado en el body; si
  llega, DEBE ignorarlo. *(Regla crítica de seguridad: enforcement server-side.)*
- **RN-7.** El sistema DEBE generar la contraseña inicial. **NO DEBE** aceptarla del
  body: si el cliente envía `password`, DEBE ignorarse. La contraseña DEBE ser
  aleatoria, distinta para cada colaborador, y DEBE almacenarse **hasheada**
  (`set_password`), nunca en claro.
- **RN-8.** La contraseña generada DEBE devolverse **una sola vez**, en el cuerpo de
  la respuesta `201`, bajo la clave `initial_password`. NO DEBE aparecer en
  `GET /collaborator/` ni en ninguna otra respuesta posterior, y el sistema NO DEBE
  ofrecer forma de recuperarla.
- **RN-9.** La creación DEBE ser atómica: si falla cualquier paso, NO DEBE quedar un
  `User` huérfano sin su perfil `Collaborator`.
- **RN-10.** El colaborador creado DEBE poder iniciar sesión de inmediato en
  `POST /user/login/` con su correo y la contraseña inicial, y ese login DEBE
  devolver `role: "collaborator"`.
- **RN-11.** Al crear, `is_active` (del `User`) DEBERÍA quedar en `true` y `show`
  DEBE quedar en `true`.
- **RN-12.** El colaborador creado DEBE aparecer de inmediato en `GET /collaborator/`
  del mismo admin, y NO DEBE ser visible para admins de otra organización.

## Artículo 6 — Criterios de aceptación (Given / When / Then)

- **CA-1 (camino feliz).** *Dado* un admin autenticado, *cuando* hace
  `POST /collaborator/` con nombre y correo válidos, *entonces* la respuesta es
  `201`, existen el `User` y su perfil `Collaborator`, y el perfil quedó en la
  organización del admin.
- **CA-2 (contraseña entregada una vez).** *Dado* ese mismo `201`, *entonces* el
  cuerpo trae `initial_password` no vacía y en la base la contraseña está hasheada
  (el hash no coincide en claro con lo devuelto).
- **CA-3 (la contraseña no se filtra después).** *Dado* un colaborador creado,
  *cuando* el admin hace `GET /collaborator/`, *entonces* la respuesta NO contiene
  `initial_password` ni `password`.
- **CA-4 (el colaborador puede entrar).** *Dado* un colaborador recién creado,
  *cuando* hace `POST /user/login/` con su correo y la `initial_password` recibida,
  *entonces* obtiene un token y `role: "collaborator"`.
- **CA-5 (validación de campos).** *Dado* un admin autenticado, *cuando* hace `POST`
  sin `email`, con un `email` mal formado, o sin `first_name`, *entonces* la
  respuesta es `400` con el error bajo la clave del campo y no se crea nada.
- **CA-6 (email duplicado).** *Dado* un correo que ya pertenece a otro usuario,
  *cuando* el admin hace `POST` con ese correo, *entonces* la respuesta es `400` con
  la clave `email` y la cantidad de usuarios no cambia.
- **CA-7 (org server-side).** *Dado* un admin de la organización A, *cuando* hace
  `POST` incluyendo `organization_id` de otra organización B en el body, *entonces*
  el colaborador se crea en **A** (el body se ignora).
- **CA-8 (contraseña del body ignorada).** *Dado* un admin que envía
  `password: "hackeada"` en el body, *entonces* esa contraseña NO sirve para iniciar
  sesión; solo sirve la `initial_password` devuelta.
- **CA-9 (permiso colaborador).** *Dado* un colaborador autenticado, *cuando* hace
  `POST /collaborator/`, *entonces* la respuesta es `403`.
- **CA-10 (sin autenticación).** *Dada* una petición sin token, *cuando* hace
  `POST /collaborator/`, *entonces* la respuesta es `401`.
- **CA-11 (aparece en el listado).** *Dado* un admin que creó un colaborador,
  *cuando* hace `GET /collaborator/`, *entonces* el colaborador aparece en la lista.
- **CA-12 (aislamiento por tenant).** *Dado* un colaborador creado por un admin de A,
  *cuando* un admin de B hace `GET /collaborator/`, *entonces* NO lo ve.

## Artículo 7 — Contrato de interfaz

**Endpoint:** `POST /collaborator/`
**Autenticación:** `Authorization: Token <token>` (Knox) · permiso `IsAdmin`

**Request (JSON):**

| Campo        | Tipo   | Obligatorio | Notas                              |
|--------------|--------|-------------|------------------------------------|
| `first_name` | string | Sí          | No vacío                           |
| `last_name`  | string | No          | Default: `""`                      |
| `email`      | string | Sí          | Formato email; único en el sistema |

> Ni `organization` ni `password` forman parte del contrato de entrada: la primera se
> deriva del servidor, la segunda la genera el servidor.

**Respuestas:**

- `201 Created` →
  ```json
  {
    "id": 7,
    "email": "ana@acme.cl",
    "full_name": "Ana Pérez",
    "first_name": "Ana",
    "last_name": "Pérez",
    "initial_password": "xK7pmQz3rT4h"
  }
  ```
  `initial_password` aparece **solo acá**. `id` es el del perfil `Collaborator`
  (mismo criterio que el `GET`, no el `id` del `User`).
- `400 Bad Request` → errores por campo: `{ "email": ["..."] }`
- `401 Unauthorized` → sin token válido
- `403 Forbidden` → autenticado pero sin perfil de admin

**`GET /collaborator/` (sin cambios):** array de `{ id, email, full_name }`.

## Artículo 8 — Preguntas abiertas

Cada resolución propuesta, una vez confirmada, baja a `SUPUESTOS.md`.

- **PA-1.** ¿Cómo se maneja la contraseña inicial? *(El enunciado pide documentarlo.)*
  **Resuelta:** la genera el servidor y se devuelve **una única vez** en el `201`; el
  admin se la comunica al colaborador por fuera. No se puede recuperar después. Se
  descartó que el admin la eligiera (le da a conocer una credencial ajena y obliga a
  validar fortaleza) y que fuera fija y conocida (todo colaborador nacería con la
  misma clave). No hay envío de correo: montar SMTP excede el alcance de la entrega y
  dejaría el flujo sin poder demostrarse offline.
- **PA-2.** ¿Un campo `full_name` o `first_name` + `last_name`?
  **Resuelta:** dos campos separados, calcados del modelo `User`. Partir un
  `full_name` por el primer espacio adivina dónde termina el nombre y falla con
  nombres compuestos. La respuesta igual incluye `full_name` (propiedad del modelo)
  para que el listado no cambie de forma.
- **PA-3.** ¿Qué pasa si el correo ya existe en **otra** organización?
  **Propuesta:** `400`. `User.email` es `unique` global y un mismo correo no puede
  pertenecer a dos organizaciones. El mensaje dice que el correo ya está registrado,
  sin revelar de qué organización — es la mínima filtración posible dado que el
  sistema no puede aceptarlo.
- **PA-4.** ¿Se puede reactivar un colaborador dado de baja (`show=False`) creándolo
  de nuevo con el mismo correo?
  **Propuesta:** no en esta spec — responde `400` como cualquier duplicado. La
  reactivación es parte de la feature de correcciones, y hacerla implícita acá
  escondería un `update` dentro de un `create`.
- **PA-5.** ¿Cómo se ve la contraseña en la UI?
  **Propuesta:** un diálogo posterior al `201` que la muestra en monoespaciado, con
  botón de copiar y una advertencia de que no se volverá a mostrar. No va en el
  snackbar, que desaparece solo.
- **PA-6.** ¿Qué forma tiene la contraseña generada?
  **Propuesta:** 12 caracteres de `django.utils.crypto.get_random_string`, sobre un
  alfabeto alfanumérico sin caracteres ambiguos (`0`/`O`, `1`/`l`/`I`) para que se
  pueda dictar por teléfono sin errores.

## Artículo 9 — Decisiones, dependencias y referencias

**Reutiliza (no reinventa):**
- Modelos `User` y `Collaborator` (`apps/user/models.py`) y `UserManager.create_user`,
  que ya hashea con `set_password`.
- Permiso `IsAdmin` (`utils/custom_permissions.py`).
- Autenticación Knox (`TokenAuthentication`) y el login existente.
- `CollaboratorListSerializer` y `CollaboratorListView` ya escritos: la vista se
  extiende a `ListCreateAPIView`, mismo molde que `CourseListCreateView` en SPEC-001.

**Contrato de frontend:** ya declarado en `endpoints/apiEndpoints.ts`
(`collaborators()`); falta la página que lo consuma.

**Implementación esperada (backend):** en `apps/user/collaborator_views.py`, un
`CollaboratorCreateSerializer` con `first_name`, `last_name`, `email` de entrada, que
en `create()` genere la contraseña, cree el `User` y el `Collaborator` dentro de
`transaction.atomic()` (RN-9) y exponga `initial_password` como campo de solo lectura
de la respuesta (RN-8). La organización llega por `serializer.save(...)` desde la
vista (RN-6), igual que en SPEC-001.

**Relación con otras specs:** SPEC-003 (asignar curso) necesita colaboradores
creados; SPEC-004 (mis cursos) necesita que puedan iniciar sesión (RN-10).

---

## Anexo A — Lista de tests derivada (puente SDD → TDD)

Escribirlos **primero** (rojo), luego implementar hasta verde. `APITestCase` con
`utils/model_factories.py`, corriendo con `make test`.

Sugerencia de `apps/user/tests/test_create_collaborator.py`:

- `test_admin_puede_crear_colaborador` → CA-1
- `test_respuesta_incluye_password_inicial_y_la_guarda_hasheada` → CA-2
- `test_listado_no_expone_la_password` → CA-3
- `test_colaborador_creado_puede_iniciar_sesion` → CA-4
- `test_campos_invalidos_devuelven_400` → CA-5
- `test_email_duplicado_devuelve_400` → CA-6
- `test_organizacion_del_body_es_ignorada` → CA-7
- `test_password_del_body_es_ignorada` → CA-8
- `test_colaborador_no_puede_crear_colaboradores` → CA-9 (403)
- `test_crear_colaborador_sin_token_devuelve_401` → CA-10
- `test_colaborador_creado_aparece_en_listado` → CA-11
- `test_colaborador_no_es_visible_para_otra_organizacion` → CA-12

**Verificación de frontend (checklist manual, sin test runner en este repo):**
- La pantalla `admin/collaborators` lista los colaboradores de la organización.
- El formulario crea uno y lo refleja en la tabla sin recargar.
- La contraseña inicial se muestra una vez, con botón de copiar y advertencia.
- Errores de validación (`400`, incluido el correo duplicado) se muestran por campo.
- Un colaborador no tiene acceso a la pantalla.
