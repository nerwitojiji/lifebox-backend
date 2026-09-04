# SPEC-005 — Inscribir y ver inscritos desde el panel

- **Capacidad:** Gestión de inscripciones del administrador
- **Feature:** Inscribir colaborador · rama `feature/inscribir-colaborador`
- **Estado:** Aprobada
- **Repos:** `lifebox-backend` (endpoint) · `lifebox-frontend` (interfaz)
- **Supersede:** SPEC-003 PA-1 · SPEC-004 RN-11 y Artículo 7 (frontend)

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

---

## Artículo 1 — Contexto y encuadre

SPEC-004 dejó el panel de inscripciones mostrando nombre, versión y cantidad de
inscritos por curso. Esas columnas son un **subconjunto** de las que ya muestra la
grilla de cursos, de modo que las dos pantallas dicen casi lo mismo.

La causa fue SPEC-004 PA-5: al agregar `enrolled_count` a `GET /course/` para que
asignar produjera un cambio visible, se trasladó a la grilla de cursos la única
información que el panel tenía en exclusiva.

El problema no se arregla repartiendo datos, sino **responsabilidades**:

- **Cursos** es el catálogo. Crear y, más adelante, editar, versionar, dar de baja
  y subir material. Gira en torno al curso.
- **Inscripciones** es el vínculo curso↔persona. Inscribir y ver quién está en qué.

Esto además cierra el problema de origen: hoy se inscribe desde Cursos y la única
señal del resultado es un mensaje que se desvanece. Inscribiendo dentro de
Inscripciones, la persona aparece en la lista de esa misma pantalla.

### Qué queda superseded

- **SPEC-003 PA-1** («la asignación se realiza desde una acción por curso en la
  pantalla de cursos») queda **sin efecto**. La acción se muda a Inscripciones. El
  endpoint `POST /course/{id}/assign/` y todas sus reglas de negocio (RN-1 a RN-8)
  **siguen vigentes sin cambios**: se muda quién lo llama, no qué hace.
- **SPEC-004 RN-11 y su Artículo 7 (frontend)** describían un panel de solo
  lectura. Esta spec lo convierte en la pantalla operativa. La separación entre
  cursos activos e inactivos, los totales de RN-12 y todo el backend de SPEC-004
  **se conservan**.

## Artículo 2 — Objetivo

Que un administrador inscriba colaboradores y vea quiénes están inscritos en cada
curso desde una sola pantalla, dejando la grilla de cursos dedicada al catálogo.

## Artículo 3 — Alcance

**Dentro de alcance:** endpoint `GET /course/{id}/collaborators/`; traslado de la
acción de inscribir desde la pantalla de cursos al panel; filas expandibles con los
inscritos de cada curso; limpieza de la pantalla de cursos.

**Fuera de alcance:** mis cursos, desinscribir, reactivar inscripciones ocultas,
inscripciones masivas, notificaciones, paginación, búsqueda dentro de la lista de
inscritos y la vista inversa (un colaborador y sus cursos).

## Artículo 4 — Actores y precondiciones

- **Actor:** administrador autenticado con `admin_profile` y organización.
- **Precondiciones:** token Knox válido. Un curso sin inscritos es un estado válido
  y representable.
- Un colaborador autenticado NO DEBE poder consultar los inscritos de un curso.

## Artículo 5 — Reglas de negocio

- **RN-1.** El sistema DEBE exponer `GET /course/{id}/collaborators/` para
  `IsAdmin`. Sin token DEBE responder `401`; con rol colaborador, `403`.
- **RN-2.** La organización DEBE derivarse de
  `request.user.admin_profile.organization`. Un curso de otro tenant, oculto o
  inexistente DEBE responder `404`, sin revelar su existencia.
- **RN-3.** El curso DEBE tener `show=True` para responder.
- **RN-4.** El curso **NO DEBE** exigirse `is_active=True`. Un curso retirado
  conserva a sus inscritos y sigue siendo auditable (SPEC-004 RN-3), así que su
  lista DEBE poder consultarse. **Esto diverge a propósito de
  `POST /course/{id}/assign/`, que sí responde `404` ante un curso inactivo**: allí
  se crea un vínculo nuevo, acá solo se leen los existentes. La divergencia es
  deliberada y NO DEBE «corregirse» igualándolas.
- **RN-5.** La lista DEBE usar el mismo criterio de «inscrito vigente» que el
  contador de SPEC-004 (RN-5): inscripción con `show=True` cuyo colaborador tenga
  `show=True`, `user.show=True` y `user.is_active=True`. La cantidad de elementos
  devueltos DEBE ser igual al `enrolled_count` del mismo curso; ese criterio DEBE
  declararse una sola vez en el código y compartirse.
- **RN-6.** Cada elemento DEBE incluir el identificador de la inscripción, su
  `assigned_at` y el `id`, `full_name` y `email` del colaborador.
- **RN-7.** El orden DEBE ser por `assigned_at` descendente —lo más reciente
  primero, que es lo que el admin acaba de hacer— y, ante empate, por nombre
  ascendente.
- **RN-8.** La consulta NO DEBE emitir una consulta por colaborador; DEBE resolverse
  con `select_related` sobre el usuario.
- **RN-9.** La interfaz DEBE ofrecer una única acción «Inscribir colaborador» que
  pida curso y colaborador. El selector de cursos DEBE ofrecer **solo cursos
  activos**, porque los inactivos no admiten inscripciones (SPEC-003 RN-4).
- **RN-10.** Tras inscribir con éxito, la interfaz DEBE reflejar el cambio sin
  recargar: el contador del curso sube **y** la persona aparece en su lista.
- **RN-11.** Los inscritos DEBEN pedirse **solo al expandir** un curso, no al cargar
  la pantalla. Cada fila DEBE representar sus estados de carga, error y vacío.
- **RN-12.** La pantalla de cursos NO DEBE seguir ofreciendo la acción de asignar.
  DEBE conservar la columna «Inscritos», que es contexto del catálogo y no una
  acción.

## Artículo 6 — Criterios de aceptación

- **CA-1:** un curso con inscritos responde `200` con una fila por inscrito vigente.
- **CA-2:** cada fila incluye `id`, `assigned_at` y el colaborador con `id`,
  `full_name` y `email`.
- **CA-3:** un curso sin inscritos responde `200` con una lista vacía.
- **CA-4:** un curso con `is_active=False` devuelve su lista igual (RN-4).
- **CA-5:** un curso con `show=False` responde `404`.
- **CA-6:** un curso de otra organización responde `404`.
- **CA-7:** un curso inexistente responde `404`.
- **CA-8:** una inscripción con `show=False` no se lista.
- **CA-9:** una inscripción cuyo colaborador tiene `show=False` no se lista.
- **CA-10:** una inscripción cuyo usuario tiene `show=False` o `is_active=False` no
  se lista.
- **CA-11:** la cantidad devuelta coincide con el `enrolled_count` que informa
  `GET /course/enrollments/` para ese curso.
- **CA-12:** el orden es por `assigned_at` descendente y, ante empate, por nombre.
- **CA-13:** un colaborador autenticado recibe `403`.
- **CA-14:** una petición sin token recibe `401`.
- **CA-15:** la consulta no crece con la cantidad de inscritos.
- **CA-16:** la pantalla de inscripciones permite inscribir eligiendo curso y
  colaborador, y ofrece solo cursos activos.
- **CA-17:** tras inscribir, el contador sube y la persona aparece en la lista del
  curso sin recargar.
- **CA-18:** expandir un curso pide sus inscritos en ese momento y muestra carga,
  error o vacío según corresponda.
- **CA-19:** la pantalla de cursos ya no ofrece asignar y conserva «Inscritos».

## Artículo 7 — Contrato de interfaz

### `GET /course/{id}/collaborators/`

**Autenticación:** `Authorization: Token <token>` · permiso `IsAdmin`.

**Respuesta `200`:**

```json
[
  {
    "id": 15,
    "assigned_at": "2026-09-03T15:30:00Z",
    "collaborator": { "id": 7, "full_name": "Ana Pérez", "email": "ana@acme.cl" }
  }
]
```

**Errores:** `401` sin token, `403` con rol colaborador, `404` para un curso
inexistente, oculto o de otro tenant.

**Frontend:**

- `pages/admin/enrollments/index.vue` incorpora el botón «Inscribir colaborador»
  —diálogo con selector de curso (solo activos) y de colaborador, que reutiliza
  `POST /course/{id}/assign/`— y vuelve expandible cada fila para mostrar los
  inscritos con nombre, correo y fecha de inscripción.
- `pages/admin/courses/index.vue` pierde el diálogo de asignación, su selector y su
  columna de acciones; conserva «Inscritos».

## Artículo 8 — Preguntas abiertas resueltas

- **PA-1:** la acción de inscribir vive en Inscripciones, no en Cursos. Cada
  pantalla queda con un sustantivo y un trabajo.
- **PA-2:** la acción es un botón único que pide curso y colaborador, en vez de una
  acción por fila. Sirve tanto para «inscribir a alguien en este curso» como para
  «inscribir a esta persona», sin duplicar interfaz.
- **PA-3:** la columna «Inscritos» **se queda** en la pantalla de cursos. Un número
  sin acción asociada es contexto del catálogo, no una duplicación de la otra
  pantalla; y `enrolled_count` ya viaja en `GET /course/`.
- **PA-4:** los inscritos se ven como fila expandible dentro del panel, no en una
  página de detalle. El objetivo 3 de la entrega pide el resumen «todo junto», y una
  página aparte lo partiría en dos navegaciones.
- **PA-5:** un colaborador dado de baja **no aparece** en la lista. Se prefiere que
  el número y la lista siempre coincidan antes que la trazabilidad de quién estuvo
  inscrito; mostrarlo marcado obligaría a explicar en pantalla por qué hay cuatro
  filas y el contador dice tres.
- **PA-6:** los inscritos se piden al expandir, no al cargar. Cargar los N cursos de
  entrada haría N peticiones para mostrar algo que el admin quizá no abra.
- **PA-7:** este endpoint admite cursos inactivos aunque el de asignar no. Leer
  quiénes quedaron dentro de un curso retirado es justamente el caso de uso del
  versionado.

## Artículo 9 — Decisiones, dependencias y referencias

El backend reutiliza `Course`, `CourseCollaborator`, `Collaborator`,
`TokenAuthentication`, `IsAdmin` y el criterio `VIGENTE` que SPEC-004 dejó en
`apps/course/views.py`. Ese criterio se factoriza para servir a la vez al
`annotate(Count(...))` del panel y al filtro de esta lista, de modo que una sola
definición gobierne el contador y la lista. El serializer anidado reutiliza
`AssignedCollaboratorSerializer`, que ya existe desde SPEC-003. La vista es un
`ListAPIView` en el mismo `views.py`; no se agregan modelos, migraciones,
dependencias ni routers.

El frontend reutiliza `useApiEndpoints()` —`courseCollaborators` ya está
declarado—, `$apiFetch`, `useAsyncData` y Vuetify. Depende de SPEC-003 (el endpoint
de asignación, que no cambia) y de SPEC-004 (el panel y el contador).

---

## Anexo A — Tests y verificaciones

Los tests backend se escriben primero en
`apps/course/tests/test_course_collaborators.py` y cubren cada CA, con énfasis en
tres: **CA-4**, que fija que un curso inactivo sí devuelve su lista y protege la
divergencia deliberada de RN-4; **CA-11**, que compara el largo de la lista con el
`enrolled_count` del panel e impide que las dos definiciones se separen; y
**CA-15**, que verifica que la consulta no crece con la cantidad de inscritos.

El frontend se verifica con `npm run build` y checklist manual: inscribir y ver
subir el contador y aparecer la persona, expandir un curso vacío, expandir con
error de red, comprobar que el selector no ofrece cursos inactivos, y que la
pantalla de cursos ya no ofrece asignar pero conserva «Inscritos».
