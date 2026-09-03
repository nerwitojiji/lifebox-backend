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
| `/course-collaborator/` | *(falta)* | hay que agregar el `include` para `my-courses/`; `apps/course_collaborator/` no tiene `urls.py` todavía |

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

Pendiente (gap contra el front):

| Método | Ruta | Notas |
|---|---|---|
| POST | `/collaborator/` | idem en `collaborator_views.py`; definir cómo se setea la contraseña inicial y **documentarlo en `SUPUESTOS.md`** |
| POST | `/course/{id}/assign/` | crea `CourseCollaborator`; validar que curso y colaborador sean del mismo tenant |
| GET | `/course/{id}/collaborators/` | inscritos de un curso |
| GET | `/course/enrollments/` | panel: por curso `full_name`, `version` y cantidad de inscritos, resuelto con `annotate(Count(...))` en un solo queryset — no contar en Python |
| GET | `/course-collaborator/my-courses/` | cursos del colaborador logueado; permiso `IsCollaborator`, vista en `apps/course_collaborator/views.py` |

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
