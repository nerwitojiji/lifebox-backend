# SPEC-002 — Crear colaborador

- **Capacidad:** Gestión de colaboradores del admin (entregable 1 del enunciado)
- **Feature:** Crear colaborador · rama `feature/crear-colaborador`
- **Estado:** Aprobada
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
iniciar sesión de inmediato con una contraseña temporal que el sistema genera y
muestra una única vez. Para el caso de que el admin no la vea o el colaborador la
pierda antes de usarla, el admin puede regenerar una nueva contraseña temporal
cuando haga falta.

## Artículo 3 — Alcance

**Dentro de alcance:**
- Endpoint `POST /collaborator/` con validación de entrada.
- Creación atómica del par `User` + `Collaborator`.
- Generación de la contraseña temporal y su entrega única en la respuesta de
  creación.
- Endpoint para que el admin **regenere** una nueva contraseña temporal de un
  colaborador existente, cuantas veces lo necesite.
- Asignación de la organización desde el servidor.
- Enforcement de permiso (solo admin).
- Pantalla `pages/admin/collaborators/` con listado, formulario de creación y
  acción de regenerar contraseña *(implementación de frontend queda para un ciclo
  posterior; esta spec sí define su contrato)*.

**Fuera de alcance (otras specs / features):**
- Editar o dar de baja un colaborador (corrección → feature posterior).
- **Forzar** al colaborador a cambiar su contraseña temporal en el primer inicio de
  sesión — queda deliberadamente para una feature posterior.
- Cualquier envío de correo.
- Asignar cursos al colaborador (→ SPEC-003, feature `asignar-curso`).
- Crear administradores (el enunciado solo pide colaboradores).

## Artículo 4 — Actores y precondiciones

- **Actor:** administrador autenticado (usuario con `admin_profile`).
- **Precondiciones:** token Knox válido; el usuario tiene `admin_profile` asociado a
  una `Organization`.
- **Actor secundario:** el colaborador creado, que después inicia sesión en
  `POST /user/login/` con su correo y la contraseña temporal vigente (la de
  creación, o la última regenerada).

## Artículo 5 — Reglas de negocio (normativas)

- **RN-1.** El sistema DEBE exponer `POST /collaborator/` para crear un colaborador.
  El `GET` existente NO DEBE cambiar de forma.
- **RN-2.** Solo un usuario autenticado con perfil de admin DEBE poder crear o
  regenerar contraseñas de colaboradores. Un colaborador autenticado NO DEBE poder
  ninguna de las dos cosas, y el sistema DEBE responder `403`. Una petición sin
  token válido DEBE responder `401`.
- **RN-3.** `email` DEBE ser obligatorio y con formato de correo válido al crear. Si
  falta o es inválido, el sistema DEBE responder `400` y NO DEBE crear ningún
  registro.
- **RN-4.** El `email` DEBE ser único en todo el sistema (`User.email` es `unique`).
  Si ya existe —incluso si pertenece a otra organización o a un admin— el sistema
  DEBE responder `400` con el error bajo la clave `email`, y NO DEBE crear nada ni
  modificar el usuario existente.
- **RN-5.** `first_name` DEBE ser obligatorio y no vacío al crear. `last_name`
  PODRÍA omitirse; si se omite, DEBE persistirse vacío.
- **RN-6.** La organización del colaborador DEBE derivarse del perfil del admin
  autenticado (`request.user.admin_profile.organization`). El sistema **NO DEBE**
  aceptar ni confiar en un `organization` / `organization_id` enviado en el body; si
  llega, DEBE ignorarlo. *(Regla crítica de seguridad: enforcement server-side.)*
- **RN-7.** El sistema DEBE generar la contraseña temporal, tanto al crear como al
  regenerar. **NO DEBE** aceptarla del body en la creación: si el cliente envía
  `password`, DEBE ignorarse. La contraseña DEBE ser aleatoria, distinta en cada
  generación, y DEBE almacenarse **hasheada** (`set_password`), nunca en claro ni en
  ninguna otra forma recuperable.
- **RN-8.** La contraseña temporal generada al crear DEBE devolverse **una sola
  vez**, en el cuerpo de la respuesta `201`, bajo la clave `temporary_password`. NO
  DEBE aparecer en `GET /collaborator/` ni en ninguna otra respuesta posterior a la
  creación.
- **RN-9.** La creación DEBE ser atómica: si falla cualquier paso, NO DEBE quedar un
  `User` huérfano sin su perfil `Collaborator`.
- **RN-10.** El colaborador DEBE poder iniciar sesión en `POST /user/login/` con su
  correo y la contraseña temporal **vigente** (la de creación, o la última
  regenerada si hubo alguna), y ese login DEBE devolver `role: "collaborator"`.
- **RN-11.** Al crear, `is_active` (del `User`) DEBERÍA quedar en `true` y `show`
  DEBE quedar en `true`.
- **RN-12.** El colaborador creado DEBE aparecer de inmediato en `GET /collaborator/`
  del mismo admin, y NO DEBE ser visible para admins de otra organización.
- **RN-13.** El admin DEBE poder regenerar la contraseña temporal de un colaborador
  **existente** de su organización, en cualquier momento y las veces que necesite,
  mediante un endpoint dedicado. Cada regeneración DEBE invalidar de inmediato la
  contraseña anterior (deja de servir para login) y generar una nueva, aleatoria y
  distinta, hasheada igual que en la creación (RN-7). La nueva contraseña DEBE
  devolverse una única vez, en la respuesta de ese endpoint, bajo la misma clave
  `temporary_password`.
- **RN-14.** El sistema NO DEBE ofrecer, bajo ninguna forma, un mecanismo para
  recuperar una contraseña temporal ya mostrada — ni la de creación ni las de
  regeneraciones anteriores. La única acción disponible ante una contraseña
  perdida es regenerar una nueva (RN-13).

## Artículo 6 — Criterios de aceptación (Given / When / Then)

- **CA-1 (camino feliz).** *Dado* un admin autenticado, *cuando* hace
  `POST /collaborator/` con nombre y correo válidos, *entonces* la respuesta es
  `201`, existen el `User` y su perfil `Collaborator`, y el perfil quedó en la
  organización del admin.
- **CA-2 (contraseña entregada al crear).** *Dado* ese mismo `201`, *entonces* el
  cuerpo trae `temporary_password` no vacía y en la base la contraseña está
  hasheada (el hash no coincide en claro con lo devuelto).
- **CA-3 (la contraseña no se filtra en el listado).** *Dado* un colaborador
  creado, *cuando* el admin hace `GET /collaborator/`, *entonces* la respuesta NO
  contiene `temporary_password` ni `password`.
- **CA-4 (el colaborador puede entrar).** *Dado* un colaborador recién creado,
  *cuando* hace `POST /user/login/` con su correo y la `temporary_password`
  recibida, *entonces* obtiene un token y `role: "collaborator"`.
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
  `password: "hackeada"` en el body de creación, *entonces* esa contraseña NO sirve
  para iniciar sesión; solo sirve la `temporary_password` devuelta.
- **CA-9 (permiso colaborador al crear).** *Dado* un colaborador autenticado,
  *cuando* hace `POST /collaborator/`, *entonces* la respuesta es `403`.
- **CA-10 (sin autenticación al crear).** *Dada* una petición sin token, *cuando*
  hace `POST /collaborator/`, *entonces* la respuesta es `401`.
- **CA-11 (aparece en el listado).** *Dado* un admin que creó un colaborador,
  *cuando* hace `GET /collaborator/`, *entonces* el colaborador aparece en la lista.
- **CA-12 (aislamiento por tenant en el listado).** *Dado* un colaborador creado por
  un admin de A, *cuando* un admin de B hace `GET /collaborator/`, *entonces* NO lo
  ve.
- **CA-13 (regenerar — camino feliz).** *Dado* un admin autenticado y un
  colaborador existente de su organización, *cuando* hace
  `POST /collaborator/{id}/reset-password/`, *entonces* la respuesta es `200` con
  una `temporary_password` nueva, distinta de la de creación.
- **CA-14 (la anterior queda invalidada).** *Dado* ese colaborador con contraseña
  regenerada, *cuando* intenta iniciar sesión con la contraseña de creación,
  *entonces* el login falla.
- **CA-15 (la nueva sirve para login).** *Dado* ese mismo colaborador, *cuando*
  inicia sesión con la `temporary_password` recién regenerada, *entonces* obtiene
  token y `role: "collaborator"`.
- **CA-16 (colaborador no puede regenerar).** *Dado* un colaborador autenticado,
  *cuando* intenta `POST /collaborator/{id}/reset-password/` (sobre sí mismo o
  sobre otro), *entonces* la respuesta es `403`.
- **CA-17 (sin autenticación al regenerar).** *Dada* una petición sin token,
  *cuando* hace `POST /collaborator/{id}/reset-password/`, *entonces* la respuesta
  es `401`.
- **CA-18 (aislamiento por tenant al regenerar).** *Dado* un colaborador de la
  organización A, *cuando* un admin de la organización B intenta regenerar su
  contraseña, *entonces* la respuesta es `404` (no se filtra que el recurso existe
  en otra organización).
- **CA-19 (no se filtra tras regenerar).** *Dado* un colaborador cuya contraseña se
  regeneró, *cuando* se consulta `GET /collaborator/`, *entonces* la respuesta no
  incluye `temporary_password` en ningún ítem.
- **CA-20 (regenerar no toca otros datos).** *Dado* un colaborador existente,
  *cuando* se regenera su contraseña, *entonces* su email, nombre, apellido y
  organización no cambian.

## Artículo 7 — Contrato de interfaz

### `POST /collaborator/`

**Autenticación:** `Authorization: Token <token>` (Knox) · permiso `IsAdmin`

**Request (JSON):**

| Campo        | Tipo   | Obligatorio | Notas                              |
|--------------|--------|-------------|-------------------------------------|
| `first_name` | string | Sí          | No vacío                           |
| `last_name`  | string | No          | Default: `""`                      |
| `email`      | string | Sí          | Formato email; único en el sistema |

> Ni `organization` ni `password` forman parte del contrato de entrada.

**Respuestas:**

- `201 Created` →
  ```json
  {
    "id": 7,
    "email": "ana@acme.cl",
    "full_name": "Ana Pérez",
    "first_name": "Ana",
    "last_name": "Pérez",
    "temporary_password": "xK7pmQz3rT4h"
  }
  ```
- `400 Bad Request` → errores por campo: `{ "email": ["..."] }`
- `401 Unauthorized` / `403 Forbidden`

### `POST /collaborator/{id}/reset-password/`

**Autenticación:** igual que arriba — `IsAdmin`, y el colaborador `{id}` DEBE
pertenecer a la organización del admin. Sin body.

**Respuestas:**

- `200 OK` → `{ "temporary_password": "nuevaXyz123" }`
- `404 Not Found` → el colaborador no existe o no es de la organización del admin
- `401` / `403` → iguales al resto

**`GET /collaborator/` (sin cambios):** array de `{ id, email, full_name }`, nunca
incluye contraseñas.

## Artículo 8 — Preguntas abiertas

- **PA-1.** ¿Cómo se maneja la contraseña inicial? **Resuelta:** el servidor la
  genera y la muestra **una sola vez** al crear. Si el admin no la vio o el
  colaborador la perdió antes de usarla, el admin **regenera** una nueva (RN-13) —
  nunca hay forma de recuperar la anterior (RN-14). Forzar el cambio en el primer
  login del colaborador queda para una feature posterior. No hay envío de correo.
- **PA-2.** ¿Un campo `full_name` o `first_name` + `last_name`? **Resuelta:** dos
  campos separados, calcados del modelo `User`. Partir un `full_name` por el primer
  espacio adivina dónde termina el nombre y falla con nombres compuestos. La
  respuesta igual incluye `full_name` (propiedad del modelo) para que el listado no
  cambie de forma.
- **PA-3.** ¿Qué pasa si el correo ya existe en **otra** organización? **Propuesta:**
  `400`. `User.email` es `unique` global y un mismo correo no puede pertenecer a
  dos organizaciones. El mensaje dice que el correo ya está registrado, sin revelar
  de qué organización.
- **PA-4.** ¿Se puede reactivar un colaborador dado de baja (`show=False`) creándolo
  de nuevo con el mismo correo? **Propuesta:** no en esta spec — responde `400`
  como cualquier duplicado. La reactivación es parte de la feature de correcciones.
- **PA-5.** ¿Cómo se ve esto en la UI? **Propuesta:** un diálogo posterior al `201`
  que muestra la contraseña en monoespaciado, con botón de copiar y advertencia de
  que no se volverá a mostrar. En el listado, un botón "regenerar contraseña" por
  colaborador que pide confirmación (invalida la anterior), llama al endpoint y
  muestra el mismo diálogo con la nueva. *(Detalle final en la spec de frontend del
  próximo ciclo.)*
- **PA-6.** ¿Qué forma tiene la contraseña generada? **Propuesta:** 12 caracteres de
  `django.utils.crypto.get_random_string`, sobre un alfabeto alfanumérico sin
  caracteres ambiguos (`0`/`O`, `1`/`l`/`I`) para que se pueda dictar por teléfono
  sin errores — igual para creación y regeneración.

## Artículo 9 — Decisiones, dependencias y referencias

**Reutiliza (no reinventa):**
- Modelos `User` y `Collaborator` (`apps/user/models.py`) y
  `UserManager.create_user` / `user.set_password()`, que ya hashean.
- Permiso `IsAdmin` (`utils/custom_permissions.py`).
- Autenticación Knox (`TokenAuthentication`) y el login existente.
- `CollaboratorListSerializer` y `CollaboratorListView` ya escritos: la creación se
  agrega como `ListCreateAPIView` (mismo molde que `CourseListCreateView` de
  SPEC-001); la regeneración es una vista nueva y pequeña (`APIView` o
  `GenericAPIView`, sin serializer de entrada).

**Sin cifrado, sin campos nuevos en el modelo, sin dependencias nuevas.** Se
descartó un diseño anterior que guardaba la contraseña cifrada para poder
"revelarla" de nuevo tras la creación; acá la contraseña **nunca** se persiste de
forma recuperable — ni al crear ni al regenerar. Eso simplifica todo: no hace falta
migración, no hace falta una librería de cifrado, no hace falta limpiar nada
después. `generate_temporary_password()` (una sola función, reutilizada por ambos
endpoints) sigue el mismo patrón: `get_random_string` sobre el alfabeto sin
ambiguos.

**Regeneración:** `user.set_password(nueva_password)` +
`user.save(update_fields=["password"])` sobre el `User` del colaborador — invalida
la anterior de forma atómica e inmediata porque el hash viejo se sobrescribe.

**Contrato de frontend:** ya declarado en `endpoints/apiEndpoints.ts`
(`collaborators()`); falta la página y la acción de regenerar, que se implementan
en el ciclo de frontend aparte.

**Relación con otras specs:** SPEC-003 (asignar curso) necesita colaboradores
creados; SPEC-004 (mis cursos) necesita que puedan iniciar sesión (RN-10).

---

## Anexo A — Lista de tests derivada (puente SDD → TDD)

Escribirlos **primero** (rojo), luego implementar hasta verde. `APITestCase` con
`utils/model_factories.py`, corriendo con `make test`.

Sugerencia de `apps/user/tests/test_create_collaborator.py`:

- `test_admin_puede_crear_colaborador` → CA-1
- `test_last_name_es_opcional` → RN-5
- `test_respuesta_incluye_password_temporal_y_la_guarda_hasheada` → CA-2
- `test_cada_colaborador_recibe_una_password_distinta` → RN-7
- `test_listado_no_expone_la_password` → CA-3
- `test_colaborador_creado_puede_iniciar_sesion` → CA-4
- `test_campos_invalidos_devuelven_400` → CA-5
- `test_email_duplicado_devuelve_400` → CA-6
- `test_organizacion_del_body_es_ignorada` → CA-7
- `test_password_del_body_es_ignorada` → CA-8
- `test_colaborador_no_puede_crear_colaboradores` → CA-9
- `test_crear_colaborador_sin_token_devuelve_401` → CA-10
- `test_colaborador_creado_aparece_en_listado` → CA-11
- `test_colaborador_no_es_visible_para_otra_organizacion` → CA-12
- `test_admin_puede_regenerar_password` → CA-13
- `test_password_anterior_deja_de_servir_tras_regenerar` → CA-14
- `test_password_regenerada_sirve_para_login` → CA-15
- `test_colaborador_no_puede_regenerar_password` → CA-16
- `test_regenerar_password_sin_token_devuelve_401` → CA-17
- `test_regenerar_password_de_otra_organizacion_devuelve_404` → CA-18
- `test_listado_no_expone_password_tras_regenerar` → CA-19
- `test_regenerar_password_no_modifica_otros_datos` → CA-20

**Verificación de frontend (checklist manual, sin test runner en este repo):**
- La pantalla `admin/collaborators` lista los colaboradores de la organización.
- El formulario crea uno y muestra la contraseña temporal una vez, con botón de
  copiar y advertencia.
- Un botón "regenerar contraseña" por colaborador pide confirmación, invalida la
  anterior y muestra la nueva una vez.
- Errores de validación (`400`) se muestran por campo.
- Un colaborador no tiene acceso a la pantalla.
