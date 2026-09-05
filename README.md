# Backend — Lifebox Academy

API Django + DRF + Knox para la plataforma de cursos de ejemplo.

## Requisitos (entorno vacío)

Instala estas herramientas de sistema **antes** de clonar o correr el proyecto. El proyecto usa SQLite en disco, pero eres libre de usar otra base de datos si lo prefieres.

### 1. Git

Necesario para clonar el repositorio.

| OS | Instalación |
|----|-------------|
| macOS | `xcode-select --install` (incluye Git y make) |
| Linux (Debian/Ubuntu) | `sudo apt update && sudo apt install git` |
| Windows | [Git for Windows](https://git-scm.com/download/win) o `winget install Git.Git` |

### 2. Python 3.11+

Incluye `pip` y el módulo `venv`. Verifica con `python3 --version` (debe ser ≥ 3.11).

| OS | Instalación |
|----|-------------|
| macOS | `brew install python@3.11` o [python.org](https://www.python.org/downloads/) |
| Linux (Debian/Ubuntu) | `sudo apt install python3.11 python3.11-venv python3-pip` |
| Windows | Instalador desde [python.org](https://www.python.org/downloads/) (marca “Add python.exe to PATH”) |

### 3. make

Usado por los comandos del `Makefile` (`make migrate`, `make runserver`, etc.).

| OS | Instalación |
|----|-------------|
| macOS | Ya viene con `xcode-select --install`; si falta: `brew install make` |
| Linux (Debian/Ubuntu) | `sudo apt install make` |
| Windows | `choco install make`, o usa [WSL](https://learn.microsoft.com/windows/wsl/) y sigue los pasos de Linux |

### Resumen rápido (copiar/pegar)

**macOS**

```bash
xcode-select --install
brew install python@3.11   # si no tienes Python 3.11+
```

**Linux (Debian/Ubuntu)**

```bash
sudo apt update
sudo apt install git make python3.11 python3.11-venv python3-pip
```

**Windows**

1. Instala [Git](https://git-scm.com/download/win) y [Python 3.11+](https://www.python.org/downloads/).
2. Instala `make` (`choco install make`) o trabaja desde WSL.

## Setup

```bash
git clone <url-del-repo>
cd Backend

python3.11 -m venv .venv
source .venv/bin/activate   # Windows (cmd): .venv\Scripts\activate
                            # Windows (PowerShell): .venv\Scripts\Activate.ps1

pip install -r requirements.txt
cp .env.example .env
make migrate
make seed
make runserver
```

API en `http://127.0.0.1:8000`.

Dependencias Python (se instalan con `pip install -r requirements.txt`):

- Django 4.2
- djangorestframework
- django-rest-knox
- django-cors-headers
- python-dotenv
- pypdf 6.17.0 (validación de PDFs)

Base de datos: SQLite por defecto (`db.sqlite3`, se crea al migrar). No es obligatorio usar PostgreSQL, Redis u otros servicios, pero puedes hacerlo si lo prefieres.

## Usuarios de prueba (seeder)

| Rol | Email | Password |
|-----|-------|----------|
| Admin | `admin@lifebox.test` | `password123` |
| Colaborador | `colaborador1@lifebox.test` | `password123` |
| Colaborador | `colaborador2@lifebox.test` | `password123` |

## Demostrar el flujo en 5 pasos

Con este API corriendo (`make runserver`) y el Frontend en `http://localhost:3000`
(ver su README). El recorrido completo se hace por la interfaz.

1. **Entrar como administrador**: `admin@lifebox.test` / `password123`.
2. **Crear un curso** en **Cursos → Nuevo curso**, con nombre, descripción, duración
   aproximada en horas y versión (por ejemplo `1.0.1`).
3. **Subirle material**: abrir el nombre del curso en la tabla (o **Ver ficha**) y
   usar **Agregar PDF**, un archivo por operación. Hay dos de ejemplo listos en
   [`docs/demo/`](docs/demo/): [la guía](docs/demo/guia-del-curso.pdf) y
   [la actividad](docs/demo/actividad-de-repaso.pdf). Máximo 10 MiB, sin cifrado.
4. **Crear un colaborador** en **Colaboradores → Nuevo colaborador**, con nombre y
   correo. El servidor genera su contraseña temporal y la muestra **una sola vez**:
   copiarla antes de cerrar el diálogo. Si se pierde, el admin la regenera desde la
   misma pantalla — ver [SUPUESTOS.md](SUPUESTOS.md).
5. **Inscribirlo** en **Inscripciones → Inscribir colaborador**, eligiendo el curso y
   la persona. Esa misma pantalla es el panel: nombre, versión y cantidad de
   inscritos por curso, todo junto, sin entrar curso por curso. Después, **cerrar
   sesión e ingresar como ese colaborador** con su contraseña temporal (o con
   `colaborador1@lifebox.test` / `password123`): en **Mis cursos** ve solo los cursos
   que le asignaron y, al abrir la tarjeta, lee y descarga los PDFs del paso 3.

Probado en **Windows**, con Python 3.13.3 y SQLite.

El resto del bonus —reemplazar y quitar documentos, corregir la versión, dar de
baja— está en [Demostrar el material PDF](#demostrar-el-material-pdf-bonus) y
enumerado en [MEJORAS.md](MEJORAS.md).

## Endpoints disponibles

Header de autenticación: `Authorization: Token <token>`.
La organización nunca viaja en la petición: se deriva del usuario autenticado.

### Sesión

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/user/login/` | No | Login → `{ token, user }`. Rechaza una cuenta sin perfil asociado |
| POST | `/user/verify-token/` | Token | Verifica sesión |
| GET | `/user/me/` | Token | Usuario actual |
| POST | `/user/change-password/` | Token | Cambia la propia contraseña. Exige la actual, invalida los demás tokens y apaga `must_change_password` |

### Cursos

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/course/` | Admin | Lista los cursos de la organización, con `enrolled_count` y `materials` |
| POST | `/course/` | Admin | Crea un curso |
| GET | `/course/{id}/` | Admin | Detalle de un curso |
| PATCH | `/course/{id}/` | Admin | Corrige nombre, descripción y duración; da de baja o reactiva (`is_active`) |
| DELETE | `/course/{id}/` | Admin | Elimina (borrado lógico). Responde `400` si el curso tiene inscritos |
| POST | `/course/{id}/new-version/` | Admin | Publica una versión nueva y deja la anterior dada de baja |

### Inscripciones

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/course/enrollments/` | Admin | Resumen por curso: nombre, versión y cantidad de inscritos |
| GET | `/course/{id}/collaborators/` | Admin | Inscritos vigentes de un curso |
| POST | `/course/{id}/assign/` | Admin | Inscribe a un colaborador. Reactiva la inscripción si estaba desinscrito |
| DELETE | `/course/{id}/collaborators/{enrollment_id}/` | Admin | Desinscribe (borrado lógico) |
| GET | `/course-collaborator/my-courses/` | Colaborador | Los cursos asignados a quien está autenticado |
| GET | `/course-collaborator/my-courses/{enrollment_id}/` | Colaborador | La ficha de un curso propio. El id es el de la **inscripción**, no el del curso; lo ajeno responde `404` |

### Colaboradores

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/collaborator/` | Admin | Lista colaboradores de la organización |
| POST | `/collaborator/` | Admin | Crea un colaborador y entrega su contraseña temporal una sola vez |
| POST | `/collaborator/{id}/reset-password/` | Admin | Regenera la contraseña temporal |
| DELETE | `/collaborator/{id}/` | Admin | Da de baja: pierde el acceso, conserva su historial |

## Estructura

```
apps/
  user/                 # User, Admin, Collaborator, login
  organization/         # Organization
  course/               # Course, CourseMaterial, gestión de cursos y PDFs
  course_collaborator/  # Inscripciones propias, fichas y lectura privada de PDFs
utils/                  # BaseAbstractModel, permissions, factories
docs/FILES.md           # Guía de archivos locales (media)
```

## Tests

```bash
make test
```

## Archivos locales

Ver [docs/FILES.md](docs/FILES.md) para `MEDIA_ROOT` y uploads.

## Demostrar el material PDF (bonus)

Tras actualizar el repositorio, ejecutar `pip install -r requirements.txt` y
`python manage.py migrate`. La nueva tabla es `CourseMaterial`; los archivos
persisten en `media/`, fuera de Git. No requiere servicios externos.

1. Con ambos servidores abiertos, ingresar como admin, crear un curso y abrir su
   nombre desde **Cursos**.
2. Usar **Agregar PDF** para subir [la guía](docs/demo/guia-del-curso.pdf) y
   [la actividad](docs/demo/actividad-de-repaso.pdf), uno por operación.
3. Inscribir al colaborador desde **Inscripciones**. Ingresar con esa cuenta y
   abrir el curso en **Mis cursos**: seleccionar, leer y descargar los PDFs.
4. Volver como admin, reemplazar o quitar un PDF desde su menú; actualizar la ficha
   del colaborador. Una versión nueva comienza sin material.

Límite: 10 MiB por documento, sin cifrado. API y almacenamiento privado:
[docs/FILES.md](docs/FILES.md). Probado en **Windows, Python 3.13.3 y SQLite**.
La suite de backend incluye **213 tests**, 28 específicos de material PDF.
