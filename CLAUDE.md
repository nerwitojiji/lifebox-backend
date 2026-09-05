# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Repo**: `lifebox-backend` — API del producto **Lifebox Academy**.
> El contexto compartido de los dos repos vive en `Proyecto Entrevista/.claude/CLAUDE.md`
> (fuera de este repo). Ese archivo manda sobre metodología (SDD/TDD), git y objetivos
> de entrega; este archivo cubre lo específico del backend.
> Idioma de UI, errores y docs: **español (es-cl)**.

## Comandos

```bash
python3.11 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt      # o: make install
cp .env.example .env

make migrate        # python manage.py migrate
make makemigrations # tras tocar cualquier models.py
make seed           # python seeder.py — org demo + 1 admin + 2 colaboradores (idempotente)
make runserver      # http://127.0.0.1:8000
make test           # python manage.py test
```

Correr un subconjunto de tests (el `Makefile` no lo cubre, usar `manage.py` directo):

```bash
python manage.py test apps.user                                          # una app
python manage.py test apps.user.tests.test_auth                          # un módulo
python manage.py test apps.user.tests.test_auth.AuthTests.test_login_admin_success  # un test
```

En Windows sin `make`, cada target es un one-liner equivalente sobre `manage.py`
(ver `Makefile`); `make seed` es `python seeder.py`.

## Arquitectura

Django 4.2 + DRF 3.15 + **Knox 4.2** (tokens), SQLite en disco (`db.sqlite3`).
Proyecto = `academy/`; el dominio vive en `apps/`.

**Monolito modular por dominio.** No es hexagonal/clean/DDD y no debe serlo:
lo nuevo cae en los moldes que ya existen.

```
academy/settings.py   AUTH_USER_MODEL=user.User, Knox como auth por defecto, CORS, MEDIA
academy/urls.py       monta los prefijos de URL (ver "Ruteo")
apps/organization/    Organization — el tenant
apps/user/            User (email como USERNAME_FIELD), Admin, Collaborator, login
apps/course/          Course
apps/course_collaborator/  CourseCollaborator (la inscripción); views.py aún vacío
utils/                BaseAbstractModel, IsAdmin/IsCollaborator, model_factories
docs/FILES.md         guía de uploads a MEDIA_ROOT local (sin S3/Azure)
```

### Modelo de datos

`User` es custom (`AbstractBaseUser + PermissionsMixin`), login por **email**, sin
`username`. El rol **no** es un campo: se deriva de la existencia del perfil
1-a-1 `user.admin_profile` / `user.collaborator_profile`. Ambos perfiles cuelgan
de una `Organization`.

`CourseCollaborator` es la tabla de inscripción, con `UniqueConstraint(course,
collaborator)` — reasignar el mismo par revienta con `IntegrityError`, hay que
manejarlo con `get_or_create` o validación en el serializer.

Todos los modelos heredan `utils.base_model.BaseAbstractModel`: `created_at`,
`updated_at` y **`show`** (soft-delete). Dar de baja = `show=False`, nunca
`.delete()`; y todo queryset de lectura filtra `show=True`.

### Patrón de vista (seguirlo tal cual)

**No hay `serializers.py`.** Los serializers se declaran en el mismo `views.py`,
arriba de la vista que los usa (ver `apps/course/views.py`,
`apps/user/collaborator_views.py`). Mantener esa convención.

Cada vista usa una **genérica de DRF** (`ListAPIView`, `CreateAPIView`, …) y
redeclara explícitamente:

```python
authentication_classes = [TokenAuthentication]   # knox.auth
permission_classes = [IsAdmin]                   # utils.custom_permissions
```

(aunque Knox + `IsAuthenticated` ya sean el default en `REST_FRAMEWORK`).

### Multi-tenant — regla dura

La `organization` **SIEMPRE** se deriva del servidor:

```python
organization = self.request.user.admin_profile.organization       # vistas de admin
organization = self.request.user.collaborator_profile.organization # vistas de colaborador
```

**NUNCA** del body, de query params ni de la URL. Al listar, filtrar el queryset
por ese tenant; al crear, asignarlo en `perform_create`. El aislamiento se hace
valer en el backend (queryset filtrado), sin confiar en el front.

### Ruteo (tiene una vuelta poco obvia)

`academy/urls.py` monta prefijos, no un router de DRF:

| Prefijo | Incluye | Ojo |
|---|---|---|
| `/user/` | `apps.user.urls` | login, verify-token, me |
| `/course/` | `apps.course.urls` | |
| `/collaborator/` | `apps.user.collaborator_urls` | **el CRUD de colaboradores vive en `apps/user/`**, en el par `collaborator_urls.py` / `collaborator_views.py`, no en una app propia |
| `/course-collaborator/` | `apps.course_collaborator.urls` | `my-courses/` — la única vista del lado del colaborador |

### Contrato con el frontend

`lifebox-frontend/endpoints/apiEndpoints.ts` es la **fuente de verdad** de las
rutas: si el front ya declara una URL, el backend la implementa con ese path exacto.

Ya implementado:

| Método | Ruta | Auth |
|---|---|---|
| POST | `/user/login/` | pública → `{ token, user }` |
| POST | `/user/verify-token/` | token (la llama el middleware del front en **cada** navegación) |
| GET | `/user/me/` | token |
| GET | `/course/` | `IsAdmin` |
| GET | `/collaborator/` | `IsAdmin` |
| POST | `/course/` | `IsAdmin` — SPEC-001; organización derivada del servidor |
| POST | `/collaborator/` | `IsAdmin` — SPEC-002; crea `User` + `Collaborator` atómicamente y entrega `temporary_password` solo en el `201` |
| POST | `/collaborator/{id}/reset-password/` | `IsAdmin` — SPEC-002; regenera la contraseña temporal dentro del tenant, sin body |
| POST | `/course/{id}/assign/` | `IsAdmin` — SPEC-003; crea `CourseCollaborator` validando tenant, estados y duplicados |
| GET | `/course/enrollments/` | `IsAdmin` — SPEC-004; panel agregado con `annotate(Count(..., filter=...))`, ordenado activos→inactivos |
| GET | `/course/{id}/collaborators/` | `IsAdmin` — SPEC-005; inscritos vigentes de un curso, `-assigned_at` |
| GET | `/course-collaborator/my-courses/` | `IsCollaborator` — SPEC-006; los cursos del colaborador del token, sin datos de otros |
| GET/PATCH/DELETE | `/course/{id}/` | `IsAdmin` — SPEC-007; corregir, dar de baja (`is_active`) y eliminar (`show`). El `DELETE` responde `400` si el curso tiene inscritos vigentes |
| POST | `/course/{id}/new-version/` | `IsAdmin` — SPEC-007; crea un curso nuevo con la versión pedida y deja el de origen inactivo, sin migrar inscritos |
| DELETE | `/course/{id}/collaborators/{enrollment_id}/` | `IsAdmin` — SPEC-007; desinscribe (`show=False`); admite cursos inactivos |
| DELETE | `/collaborator/{id}/` | `IsAdmin` — SPEC-007; da de baja: `Collaborator.show=False` **y** `user.is_active=False` en una transacción |

**Los cinco endpoints de SPEC-007 todavía no están declarados en
`apiEndpoints.ts`**: son bonus, no parte del contrato original. Al implementar su
interfaz hay que agregarlos ahí primero, que es la fuente de verdad de las rutas.

`GET /course/` incorpora `enrolled_count` desde SPEC-004. La definición de
«inscrito vigente» (inscripción visible + colaborador y usuario disponibles) vive
una sola vez en `apps/course/views.py` (`INSCRITO_VIGENTE` / `vigente(prefix)`) y la
comparten el listado, el panel y la lista de inscritos: si el contador dice 3, la
lista trae 3. Al tocar el criterio, cambian los tres juntos.

**Trampa (SPEC-007):** `POST /course/{id}/assign/` ante un par curso-colaborador
**ya existente pero oculto** responde `201` reactivando esa fila, no `400`. La
`UniqueConstraint(course, collaborator)` no filtra por `show`, así que una segunda
fila es imposible; sin la reactivación, desinscribir por error sería irreversible.
Solo el duplicado **visible** responde `400`.

**Trampa:** `GET /course/{id}/collaborators/` **no** exige `is_active=True`, pero
`POST /course/{id}/assign/` **sí** (responde `404`). Es deliberado —uno lee
inscritos existentes, el otro crea un vínculo nuevo— y hay un test que lo fija
(`test_asignar_sigue_rechazando_el_curso_inactivo`). No igualar las dos
condiciones.

**No queda ningún endpoint pendiente del contrato del front**: todo lo declarado en
`apiEndpoints.ts` está implementado.

Header de auth: `Authorization: Token <token>`.
Login inválido responde `400` con `{"text": "Credenciales inválidas"}` — el front
lee exactamente `err.data.text`, mantener esa forma en los errores de auth.

## Tests (TDD: test primero)

`APITestCase` de DRF, un paquete `tests/` por app (`apps/user/tests/`), con
`utils/model_factories.py` para armar el fixture. Las factories son idempotentes
(`get_or_create`) y crean la `Organization` sola si no se le pasa una.

Referirse a las URLs por `reverse("nombre-de-url")`, nunca hardcodeadas — por eso
toda ruta nueva lleva `name=` en `urls.py`.

Todo endpoint nuevo debe traer al menos: el happy path, el **403 con el rol
equivocado** y el **aislamiento entre organizaciones** (un tenant no ve lo del otro).

## Supuestos

**Obligatorio: al cerrar una feature, sus supuestos van a `SUPUESTOS.md` en la
misma rama, antes del merge a `dev`** — nunca en un commit suelto posterior. Acá
bajan los del **contrato de la API**: defaults, validaciones, forma de las
respuestas y reglas de negocio (los de interfaz van al `SUPUESTOS.md` del front).

Se resuelven primero como `PA-*` en el Artículo 8 del spec y bajan una vez cerrada
la feature. Formato: sección `## SPEC-00X — <nombre>`, cada supuesto en negrita
como afirmación, el porqué a continuación y `→ archivo` cuando ayude a ubicarlo.
El porqué es lo que importa: sin él la línea describe el código en vez de explicar
la decisión.

## Bitácora de commits

**Obligatorio: cada commit en este repo se registra acá**, en la misma tanda de
cambios (el archivo va dentro del commit que describe). Formato: fila nueva al
final, más reciente abajo.

Las filas se identifican por **asunto del commit, no por hash**: el archivo viaja
dentro del commit que describe, así que no puede contener su propio hash (y un
`--amend` lo invalidaría). El hash se obtiene con `git log`.

Después de actualizar esta tabla, **replicar la línea** en la bitácora consolidada
de `Proyecto Entrevista/.claude/CLAUDE.md` — el archivo padre es el índice de los
dos repos.

| Fecha | Rama | Commit | Qué cambió |
|---|---|---|---|
| 2026-09-02 | `dev` | *(base de Lifebox)* | Scaffolding Django/DRF/Knox, modelos, login + listados de admin, seeder, tests de auth, README |
| 2026-09-03 | `dev` | Agregar guía de contexto de Claude Code para el repo | Comandos, arquitectura, convenciones y esta bitácora |
| 2026-09-03 | `feature/crear-curso` | Incorporar SPEC-001 (crear curso) al repositorio | El spec SDD pasa a `docs/specs/`, versionado junto al código que especifica |
| 2026-09-03 | `feature/crear-curso` | Agregar tests de creación de curso (SPEC-001) | CA-1..CA-8 como `APITestCase`; rojo (6 fallan con 405, CA-4 y CA-5 ya pasaban) |
| 2026-09-03 | `feature/crear-curso` | Permitir al admin crear cursos vía POST /course/ | `ListCreateAPIView` + serializer de escritura, organización server-side; verde 11/11 |
| 2026-09-03 | `feature/crear-curso` | Identificar la bitácora por asunto en vez de hash | Un archivo no puede contener su propio hash; `--amend` lo invalidaba |
| 2026-09-03 | `dev` | Merge de feature/crear-curso (`--no-ff`) | SPEC-001 cerrado en el backend; suite en verde tras el merge (11/11) |
| 2026-09-03 | `dev` | Documentar los supuestos de SPEC-001 | `SUPUESTOS.md`: transversales (org server-side, soft-delete, sin paginación) y los del crear curso |
| 2026-09-03 | `feature/crear-colaborador` | Incorporar SPEC-002 (crear colaborador) al repositorio | El spec SDD pasa a `docs/specs/`; resuelve la contraseña inicial (generada por el servidor, entregada una sola vez) |
| 2026-09-03 | `feature/crear-colaborador` | Agregar tests de creación de colaborador (SPEC-002) | CA-1..CA-12 como `APITestCase`; rojo (12 de 14 fallan con 405, CA-9 y CA-10 ya pasaban) |
| 2026-09-03 | `feature/crear-colaborador` | Permitir al admin crear colaboradores vía POST /collaborator/ | `ListCreateAPIView` + serializer de escritura; contraseña generada, hasheada y devuelta una sola vez; verde 25/25 |
| 2026-09-03 | `feature/crear-colaborador` | Revertir SPEC-002 (crear colaborador) | Se deshacen los tres commits de arriba: spec, tests y vista vuelven al estado de `dev`, `POST /collaborator/` queda otra vez pendiente. Las filas se conservan porque los commits siguen en el historial de la rama |
| 2026-09-03 | `feature/crear-colaborador` | Incorporar SPEC-002 (crear colaborador) al repositorio — v2 | Rediseño tras el revert: contraseña temporal mostrada una sola vez al crear, sin cifrado ni almacenamiento recuperable; el admin la **regenera** (no la vuelve a ver) vía `POST /collaborator/{id}/reset-password/` |
| 2026-09-03 | `feature/crear-colaborador` | Agregar tests de creación y regeneración de colaborador (SPEC-002 v2) | 23 tests cubren CA-1..CA-20, apellido opcional, aleatoriedad y atomicidad; rojo esperado: creación `405` y ruta de regeneración inexistente |
| 2026-09-03 | `feature/crear-colaborador` | Permitir crear colaboradores y regenerar su contraseña temporal | `ListCreateAPIView` + endpoint de regeneración, tenant server-side, creación atómica y contraseña solo hasheada; suite verde 34/34, sin migraciones |
| 2026-09-03 | `dev` | Merge de feature/crear-colaborador (`--no-ff`) | SPEC-002 cerrada en el backend; suite completa verde 34/34 |
| 2026-09-03 | `feature/asignar-curso` | Incorporar SPEC-003 (asignar curso) al repositorio | Define asignación individual, tenant server-side, duplicados, estados no disponibles y contrato de UI; propuestas aprobadas |
| 2026-09-03 | `feature/asignar-curso` | Agregar tests de asignación de cursos (SPEC-003) | Cobertura estricta de contrato, permisos, tenant, estados, entrada hostil y duplicados visibles/ocultos; rojo esperado por ruta inexistente |
| 2026-09-03 | `feature/asignar-curso` | Permitir asignar cursos a colaboradores vía POST | Endpoint tenant-safe, recursos activos/visibles, duplicados controlados y respuesta anidada; suite completa verde 50/50 |
| 2026-09-03 | `dev` | Merge de feature/asignar-curso (`--no-ff`) | SPEC-003 cerrada en backend; 16 tests específicos y suite completa verde 50/50 |
| 2026-09-03 | `feature/panel-inscripciones` | Incorporar SPEC-004 (panel de inscripciones) al repositorio | Define `GET /course/enrollments/` con una sola agregación, `enrolled_count` aditivo en `GET /course/`, conteo de inscritos vigentes y separación de cursos activos/inactivos; resuelve la numeración ambigua que dejó SPEC-003 |
| 2026-09-03 | `feature/panel-inscripciones` | Agregar tests del panel de inscripciones (SPEC-004) | 20 tests cubren CA-1..CA-16, la reversibilidad de PA-8 y `CaptureQueriesContext` contra el N+1; rojo esperado: ruta inexistente y `enrolled_count` ausente |
| 2026-09-03 | `feature/panel-inscripciones` | Exponer el panel de inscripciones vía GET /course/enrollments/ | `ListAPIView` con `annotate(Count(..., filter=...))`, orden activos→inactivos, y `enrolled_count` aditivo en `GET /course/` con una única definición de «inscrito vigente»; verde 70/70, sin migraciones |
| 2026-09-03 | `feature/panel-inscripciones` | Documentar los supuestos de SPEC-004 y exigirlos antes del merge | Criterio de «inscrito vigente», cursos inactivos visibles, orden server-side y agregación única; el protocolo pasa a obligar que los supuestos se escriban al cerrar la feature |
| 2026-09-03 | `dev` | Merge de feature/panel-inscripciones (`--no-ff`) | SPEC-004 cerrada en backend; 20 tests específicos y suite completa verde 70/70 |
| 2026-09-03 | `feature/inscribir-colaborador` | Incorporar SPEC-005 (inscribir colaborador) al repositorio | Define `GET /course/{id}/collaborators/`, que admite cursos inactivos al revés que el de asignar, y ata la lista al contador de SPEC-004; marca superseded PA-1 de SPEC-003 y RN-11 de SPEC-004 |
| 2026-09-03 | `feature/inscribir-colaborador` | Agregar tests de los inscritos por curso (SPEC-005) | 16 tests cubren CA-1..CA-15, con un test que contrasta este endpoint contra el de asignar en curso inactivo y otro que iguala el largo de la lista al `enrolled_count`; rojo esperado por ruta inexistente |
| 2026-09-03 | `feature/inscribir-colaborador` | Listar los inscritos de un curso vía GET /course/{id}/collaborators/ | `ListAPIView` que admite cursos inactivos (RN-4) y `select_related`; el criterio «inscrito vigente» se factoriza en `vigente(prefix)` y pasa a gobernar contador y lista; verde 86/86, sin migraciones |
| 2026-09-03 | `feature/inscribir-colaborador` | Documentar los supuestos de SPEC-005 | La asimetría entre leer e inscribir en un curso inactivo, la definición única de «inscrito vigente» y el orden por fecha |
| 2026-09-03 | `dev` | Merge de feature/inscribir-colaborador (`--no-ff`) | SPEC-005 cerrada en backend; 16 tests específicos y suite completa verde 86/86 |
| 2026-09-04 | `feature/mis-cursos` | Incorporar SPEC-006 (mis cursos) al repositorio | Define `GET /course-collaborator/my-courses/`, primera vista del lado del colaborador; el colaborador sale del token y el aislamiento se prueba entre pares de la misma organización |
| 2026-09-04 | `feature/mis-cursos` | Agregar tests de mis cursos (SPEC-006) | 15 tests cubren CA-1..CA-14, con Ana y Luis en el mismo tenant para probar el aislamiento entre compañeros y query params que intentan suplantar identidad; estrena `apps/course_collaborator/tests/`; rojo esperado por ruta inexistente |
| 2026-09-04 | `feature/mis-cursos` | Exponer los cursos del colaborador vía GET /course-collaborator/my-courses/ | Estrena `apps/course_collaborator/` con vista, `urls.py` y el `include` que faltaba; primer uso de `IsCollaborator`, colaborador derivado del token; verde 101/101, sin migraciones |
| 2026-09-04 | `feature/mis-cursos` | Documentar los supuestos de SPEC-006 | El colaborador sale del token, el aislamiento entre compañeros, el filtro redundante por organización y por qué PA-8 sigue sin parchear |
| 2026-09-04 | `dev` | Merge de feature/mis-cursos (`--no-ff`) | SPEC-006 cerrada en backend; 15 tests específicos y suite completa verde 101/101. **Con esto no queda ningún endpoint pendiente del contrato del front** |
| 2026-09-04 | `feature/correcciones` | Incorporar SPEC-007 (correcciones) al repositorio | Primer bonus: da al catálogo y a la inscripción las transiciones que les faltaban (corregir, retirar, versionar, desinscribir, dar de baja), todas por borrado lógico. Supersede SPEC-003 RN-6 (la reinscripción ahora reactiva la fila oculta) y SPEC-001 RN-3 (el nombre de curso pasa a exigir 3 caracteres y una letra, también al crear). Suma el rechazo en el login de una cuenta sin perfil, que hoy deja al front rebotando entre `/admin` y `/colaborador` |
| 2026-09-04 | `feature/correcciones` | Agregar tests de correcciones (SPEC-007) | 50 tests nuevos cubren CA-1..CA-44 en cuatro archivos, más las adiciones a `test_create_course.py` y `test_auth.py`; rojo esperado: 59 errores por las rutas inexistentes y 7 fallos de reglas ya probables contra el código actual (6 nombres de curso que hoy se aceptan y el login sin perfil que hoy entrega token) |
| 2026-09-04 | `feature/correcciones` | Permitir corregir, versionar y dar de baja | Cinco endpoints nuevos, todos por borrado lógico: detalle del curso con `PATCH`/`DELETE`, versión nueva, desinscribir y baja de colaborador. La reinscripción pasa a reactivar la fila oculta (supersede SPEC-003 RN-6, y su test se reescribe apuntando a la regla nueva), el nombre de curso gana un piso compartido por crear y editar, y el login rechaza a la cuenta sin perfil. Incluye `SUPUESTOS.md`: el borrado lógico y su razón (los `CASCADE`), la diferencia entre dar de baja y eliminar, por qué versionar no migra inscritos, el piso del nombre y el cierre del hueco que SPEC-006 dejó anotado; verde 151/151, sin migraciones |
| 2026-09-04 | `feature/correcciones` | Registrar los supuestos de SPEC-007 en la bitácora | La fila del commit de implementación no decía que llevaba `SUPUESTOS.md` adentro |
| 2026-09-04 | `dev` | Merge de feature/correcciones (`--no-ff`) | **SPEC-007 cerrada en backend**: correcciones, versionado y bajas, todas por borrado lógico. 50 tests nuevos y suite completa verde 151/151, sin migraciones. Primer bonus de la entrega |
| 2026-09-04 | `dev` | Agregar MEJORAS.md y completar la lista de endpoints | Entregable que faltaba: las ocho mejoras sobre el flujo pedido, cada una con el problema que resuelve. El README listaba endpoints solo hasta SPEC-002; ahora los agrupa por dominio e incluye los de SPEC-003 a SPEC-007 |
| 2026-09-04 | `feature/corregir-version` | Incorporar SPEC-008 (corregir versión) al repositorio | SPEC-007 prohibía editar `version`, y el enunciado pide corregir el tipeo «decía 1.0 y en realidad es 2.0». La distinción que faltaba no es editar vs. versionar, sino si alguien ya se inscribió: sin inscritos la versión es un dato del formulario; con inscritos es parte de lo que esas personas cursaron. Acota SPEC-007 RN-4 y PA-11 sin anularlos |
| 2026-09-04 | `feature/corregir-version` | Agregar tests de corrección de versión (SPEC-008) | 9 tests cubren CA-1..CA-10 en `test_edit_course.py`; rojo esperado (8 fallos): `version` es de solo lectura, así que el `PATCH` la ignora en silencio y responde `200` tanto donde debe corregir como donde debe rechazar |
| 2026-09-04 | `feature/corregir-version` | Permitir corregir la versión de un curso sin inscritos | `version` sale de `read_only_fields` y gana un `validate_version()` que usa el `enrolled_count` ya anotado, sin consulta nueva. El test de SPEC-007 que fijaba la prohibición sin excepción se reescribe apuntando a la regla nueva. Incluye `SUPUESTOS.md`; verde 160/160, sin migraciones |
| 2026-09-04 | `dev` | Merge de feature/corregir-version (`--no-ff`) | **SPEC-008 cerrada en backend**; suite completa verde 160/160 |
| 2026-09-05 | `feature/cambiar-contrasena` | Incorporar SPEC-009 (cambiar contraseña) al repositorio | SPEC-002 dejó un extremo suelto: el colaborador no puede cambiar su contraseña de ninguna forma, y la temporal la conocen dos personas. Define `POST /user/change-password/`, el flag `must_change_password` y un aviso omitible que reaparece. Primera migración del proyecto: `last_login` existe pero nada lo escribe, así que no sirve como señal de primer ingreso |
