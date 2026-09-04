# SPEC-006 — Mis cursos

- **Capacidad:** Acceso del colaborador a sus cursos asignados
- **Feature:** Mis cursos · rama `feature/mis-cursos`
- **Estado:** Aprobada
- **Repos:** `lifebox-backend` (endpoint) · `lifebox-frontend` (interfaz)

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

---

## Artículo 1 — Contexto y encuadre

Es el **objetivo 2 de la entrega** y el único de los tres pasos del flujo core que
todavía no funciona en la interfaz: *«el colaborador debe poder, al iniciar sesión,
ver solo los cursos que le asignaron»*.

Todo lo que hace falta ya existe salvo la vista. `CourseCollaborator` guarda las
inscripciones desde SPEC-003, el admin las crea desde SPEC-005, y el permiso
`IsCollaborator` está escrito y sin uso. Del lado del cliente,
`pages/colaborador/my-courses/index.vue` es un stub «Próximamente» y el layout
`colaborador.vue` ya enlaza a esa ruta.

La app `apps/course_collaborator/` está vacía: tiene modelo pero su `views.py` no
se tocó nunca, y no hay `urls.py` ni paquete de tests. `academy/urls.py` tampoco
monta todavía el prefijo `course-collaborator/`.

Hasta acá toda la autorización se ejerció contra `IsAdmin`. Esta es la **primera
vista del lado del colaborador**, así que también es la primera vez que se prueba
el aislamiento en esa dirección: que una persona vea lo suyo y nada más.

## Artículo 2 — Objetivo

Que un colaborador autenticado vea, al iniciar sesión, la lista de los cursos que
le fueron asignados —y solo esos—, con la información suficiente para saber qué
tiene que hacer.

## Artículo 3 — Alcance

**Dentro de alcance:** endpoint `GET /course-collaborator/my-courses/`; el `include`
que falta en `academy/urls.py`; la pantalla del colaborador con sus cursos, estado
vacío y estado de error.

**Fuera de alcance:** marcar un curso como completado, progreso o avance,
inscribirse por cuenta propia, descargar material, la vista de detalle de un curso,
notificaciones y cualquier acción de escritura por parte del colaborador.

## Artículo 4 — Actores y precondiciones

- **Actor:** colaborador autenticado con `collaborator_profile` y organización.
- **Precondiciones:** token Knox válido. **No tener cursos asignados es un estado
  válido y esperable**: un colaborador recién creado no tiene ninguno.
- Un administrador autenticado NO DEBE poder consultar este endpoint.

## Artículo 5 — Reglas de negocio

- **RN-1.** El sistema DEBE exponer `GET /course-collaborator/my-courses/` para
  `IsCollaborator`. Sin token DEBE responder `401`; con rol admin, `403`.
- **RN-2.** El colaborador DEBE derivarse exclusivamente de
  `request.user.collaborator_profile`. Ningún identificador recibido por query param
  o body —`collaborator`, `collaborator_id`, `organization`— DEBE alterar el
  resultado. **No existe forma de pedir los cursos de otra persona.**
- **RN-3.** La respuesta DEBE contener únicamente inscripciones cuyo `collaborator`
  sea el del usuario autenticado. Un colaborador NO DEBE ver, bajo ninguna
  combinación de parámetros, un curso que no le fue asignado.
- **RN-4.** Solo DEBEN listarse inscripciones con `show=True` y cursos con
  `show=True`. Una inscripción dada de baja desaparece de la lista.
- **RN-5.** Los cursos con `is_active=False` **DEBEN listarse igual**, marcados. Un
  curso retirado no desinscribe a nadie y quien lo tenía asignado conserva la
  obligación de hacerlo; ocultarlo le escondería trabajo pendiente. Es el mismo
  criterio que SPEC-004 RN-3 y SPEC-005 RN-4.
- **RN-6.** El queryset DEBE filtrar además por la organización del colaborador. El
  endpoint de asignación ya impide cruzar tenants, pero el modelo no lo garantiza
  por sí solo; el filtro es defensa en profundidad y no cuesta nada.
- **RN-7.** Cada elemento DEBE incluir el identificador de la inscripción, su
  `assigned_at` y el curso con `id`, `full_name`, `description`, `duration_hours`,
  `version` e `is_active`.
- **RN-8.** La respuesta NO DEBE incluir `enrolled_count` ni ningún dato de otros
  colaboradores. Cuántas personas más están inscritas no es asunto del colaborador.
- **RN-9.** El orden DEBE ser por `assigned_at` descendente —lo recién asignado
  primero— y, ante empate, por `full_name` del curso ascendente.
- **RN-10.** La consulta NO DEBE emitir una consulta por curso; DEBE resolverse con
  `select_related`.
- **RN-11.** La interfaz DEBE mostrar los cursos con su nombre, versión, duración,
  descripción y fecha de asignación, y DEBE distinguir visualmente los inactivos.
- **RN-12.** La interfaz DEBE representar en español los estados de carga, error y
  vacío. El estado vacío NO DEBE ser una pantalla en blanco: DEBE explicar que
  todavía no hay cursos asignados y que los asigna un administrador.

## Artículo 6 — Criterios de aceptación

- **CA-1:** un colaborador con cursos asignados recibe `200` con una fila por
  inscripción vigente.
- **CA-2:** cada fila incluye `id`, `assigned_at` y el curso con los campos de RN-7.
- **CA-3:** un colaborador sin cursos recibe `200` con una lista vacía.
- **CA-4:** un colaborador **no ve** los cursos asignados a otro colaborador, ni
  siquiera de su misma organización.
- **CA-5:** un colaborador de otra organización no aparece ni afecta el resultado.
- **CA-6:** enviar `collaborator`, `collaborator_id` u `organization` por query param
  no altera el resultado.
- **CA-7:** una inscripción con `show=False` no se lista.
- **CA-8:** un curso con `show=False` no se lista.
- **CA-9:** un curso con `is_active=False` **sí** se lista, con su bandera.
- **CA-10:** la respuesta no expone `enrolled_count` ni datos de otros
  colaboradores.
- **CA-11:** el orden es por `assigned_at` descendente y, ante empate, por nombre.
- **CA-12:** un administrador autenticado recibe `403`.
- **CA-13:** una petición sin token recibe `401`.
- **CA-14:** la consulta no crece con la cantidad de cursos asignados.
- **CA-15:** la pantalla muestra los cursos con nombre, versión, duración,
  descripción y fecha, y marca los inactivos.
- **CA-16:** sin cursos asignados, la pantalla explica la situación en vez de
  quedar vacía.

## Artículo 7 — Contrato de interfaz

### `GET /course-collaborator/my-courses/`

**Autenticación:** `Authorization: Token <token>` · permiso `IsCollaborator`.

**Respuesta `200`:**

```json
[
  {
    "id": 15,
    "assigned_at": "2026-09-03T15:30:00Z",
    "course": {
      "id": 3,
      "full_name": "Prevención de riesgos",
      "description": "Curso obligatorio de inducción",
      "duration_hours": 4,
      "version": "1.0",
      "is_active": true
    }
  }
]
```

**Errores:** `401` sin token, `403` con rol admin.

**Frontend:** `pages/colaborador/my-courses/index.vue` reemplaza el stub por una
grilla de tarjetas, una por curso, con nombre, versión, duración, descripción y
fecha de asignación; los inactivos llevan un distintivo. Incluye estados de carga,
error y vacío.

## Artículo 8 — Preguntas abiertas resueltas

- **PA-1:** el colaborador sale del token, nunca de la petición. No hay endpoint
  que permita pedir los cursos de otra persona, ni siquiera para un admin: eso es
  `GET /course/{id}/collaborators/`, que va por curso y exige `IsAdmin`.
- **PA-2:** los cursos inactivos **sí** se muestran, marcados. Quien lo tenía
  asignado conserva la obligación; esconderlo le ocultaría trabajo pendiente.
- **PA-3:** la respuesta anida el curso dentro de la inscripción, en vez de
  devolver cursos planos con un `assigned_at` agregado. Es simétrico a
  `GET /course/{id}/collaborators/`, que anida el colaborador dentro de la
  inscripción: el recurso es la inscripción en los dos casos.
- **PA-4:** no se expone `enrolled_count`. Cuántos compañeros tiene el curso no es
  información del colaborador y su ausencia evita una fuga innecesaria.
- **PA-5:** el orden es por fecha descendente, como en SPEC-005. Lo recién asignado
  es lo que la persona todavía no vio.
- **PA-6:** **el hueco de PA-8 de SPEC-004 sigue fuera de alcance.** Un colaborador
  con `Collaborator.show=False` y `user.is_active=True` podría iniciar sesión y ver
  esta pantalla. La condición ya está fijada allá: la futura capacidad de baja DEBE
  apagar `Collaborator.show` **y** `user.is_active` a la vez, y con eso la persona
  no puede siquiera autenticarse, de modo que esta vista nunca se renderiza. Se
  descartó parchear `IsCollaborator` acá porque hoy **ningún flujo de la API puede
  dar de baja a un colaborador** —no existe el endpoint—, así que sería endurecer un
  camino inalcanzable y dejaría a la persona pudiendo entrar pero recibiendo `403`
  en todas partes, que es un estado peor que el actual.
- **PA-7:** la pantalla no ofrece marcar un curso como completado. El enunciado pide
  ver los cursos asignados; el avance es otra capacidad.

## Artículo 9 — Decisiones, dependencias y referencias

El backend estrena `apps/course_collaborator/views.py` con un `ListAPIView` y su
serializer arriba, siguiendo la convención del repo (sin `serializers.py`). Se crean
`apps/course_collaborator/urls.py` y el paquete `tests/`, y se agrega a
`academy/urls.py` el `include` del prefijo `course-collaborator/`, que era el único
de la tabla de ruteo que faltaba. Se reutilizan `CourseCollaborator`, `Course`,
`TokenAuthentication` y `IsCollaborator` —que hasta ahora estaba escrito y sin
usar—. No se agregan modelos, migraciones, dependencias ni routers.

El frontend reutiliza `layouts/colaborador.vue` (el enlace «Mis cursos» ya existe
en la barra), `useApiEndpoints()` —`myCourses` ya está declarado—, `$apiFetch`,
`useAsyncData` y Vuetify. Depende de SPEC-003 y SPEC-005, que son los que crean las
inscripciones que esta pantalla lee.

Con esta spec quedan cubiertos los tres pasos del flujo core de la entrega.

---

## Anexo A — Tests y verificaciones

Los tests backend se escriben primero en
`apps/course_collaborator/tests/test_my_courses.py` y cubren cada CA. El énfasis
está en el aislamiento, porque es la primera vista del lado del colaborador: dos
colaboradores de la **misma** organización, cada uno con sus cursos, verificando que
ninguno vea los del otro (CA-4); un tercero en otra organización (CA-5); y query
params hostiles que intentan suplantar identidad (CA-6). Se agregan el `403` con rol
admin, el `401` sin token, los estados ocultos e inactivos, el orden y un
`CaptureQueriesContext` para CA-14.

El frontend se verifica con `npm run build` y checklist manual, **iniciando sesión
como colaborador**: ver los cursos propios, comprobar con el segundo colaborador del
seeder que la lista es distinta, un colaborador sin cursos para el estado vacío, y
el curso inactivo marcado.
