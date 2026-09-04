# SPEC-007 — Correcciones: reasignar, versionar y dar de baja

- **Capacidad:** Ciclo de vida del catálogo y de las inscripciones
- **Feature:** Correcciones · rama `feature/correcciones`
- **Estado:** Aprobada
- **Repos:** `lifebox-backend` (endpoints) · `lifebox-frontend` (interfaz)
- **Supersede:** SPEC-003 RN-6 y CA-10 · SPEC-001 RN-3

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

---

## Artículo 1 — Contexto y encuadre

Las specs 001 a 006 construyeron un sistema que **solo sabe crear**. Se crea un
curso, se crea un colaborador, se inscribe a alguien; nada de eso se puede
deshacer ni corregir desde la aplicación. Un curso con el nombre mal escrito queda
mal escrito, una inscripción equivocada queda para siempre, y un curso que la
organización dejó de dictar sigue ofreciéndose como si nada.

Eso ya dejó marcas en el código. `is_active` existe en `Course` desde el
scaffolding y **nada lo pone en `False`**: SPEC-004 ordena el panel separando
activos de inactivos y SPEC-006 marca los cursos retirados en la vista del
colaborador, pero ese estado hoy solo se puede alcanzar por el admin de Django o
por el seeder. Lo mismo con `show`: la regla de arquitectura manda borrado lógico
y todavía no hay una sola operación que borre.

Esta spec cierra esa mitad faltante. No agrega un dominio nuevo: da a los objetos
que ya existen las tres transiciones que les faltan —**corregir**, **retirar** y
**versionar**— y hace lo propio con la inscripción, que hoy solo nace.

Al diseñar la baja de un colaborador apareció un agujero contiguo. En este
proyecto **el rol no es un campo: es la existencia del perfil** `admin_profile` o
`collaborator_profile`. Un usuario que se quede sin ninguno de los dos —hoy solo
alcanzable borrando el perfil desde el `/admin/` de Django, que es el único
borrado físico que el proyecto deja abierto— autentica bien, recibe `role: null`
y entonces el middleware del front lo manda de `/admin` a `/colaborador` y de
vuelta, porque `isAdmin` e `isCollaborator` son las dos falsas. No es una cuenta
inútil: es una cuenta que rompe la aplicación para quien la tenga. RN-24 lo
ataja en el único lugar donde esa persona puede leer una explicación: el login.

### Qué queda superseded

**SPEC-003 RN-6 y CA-10** establecían que un par curso-colaborador ya existente
responde `400` **incluso si está oculto**, con la nota explícita «esta spec NO
reactiva inscripciones». Esa regla era correcta mientras nada podía ocultar una
inscripción. Al introducir la desinscripción como borrado lógico deja de serlo:
desinscribir a alguien por error y no poder volver a inscribirlo —recibiendo
«Este colaborador ya está inscrito en el curso», que sería falso— convierte una
corrección en un callejón sin salida. RN-18 de esta spec la reemplaza. El resto de
SPEC-003 sigue vigente sin cambios.

**SPEC-001 RN-3** exigía que `full_name` fuera «obligatorio y no vacío», y eso es
todo lo que valida hoy: `"."`, `".."` y `"a"` son nombres de curso aceptados. Solo
`""` —y los espacios en blanco, que DRF recorta— y los nombres de más de 255
caracteres se rechazan. Un catálogo donde el colaborador abre «Mis cursos» y ve un
punto no cumple el objetivo de que sepa qué va a cursar. RN-5 de esta spec la
reemplaza por una regla con piso real, y **la aplica también a la creación**: si
solo valiera al editar, se seguiría pudiendo crear `"."` y el `PATCH` sería el
único en quejarse.

## Artículo 2 — Objetivo

Que un administrador pueda **corregir lo que ya creó**: arreglar los datos de un
curso, retirarlo de circulación, publicar una versión nueva, mover a un
colaborador de un curso a otro y dar de baja a quien ya no está en la
organización — todo sin perder el historial de lo que pasó antes.

## Artículo 3 — Alcance

**Dentro de alcance:**

- `PATCH /course/{id}/` — corregir nombre, descripción, duración y estado.
- `DELETE /course/{id}/` — eliminar (borrado lógico) un curso creado por error.
- `POST /course/{id}/new-version/` — publicar una versión nueva de un curso.
- `DELETE /course/{id}/collaborators/{enrollment_id}/` — desinscribir.
- `DELETE /collaborator/{id}/` — dar de baja a un colaborador.
- Reactivación de una inscripción oculta al volver a inscribir (RN-18).
- `GET /course/{id}/` como retrieve simple, que la vista de detalle trae consigo.
- Un piso de validación para `full_name` y `version`, **compartido con
  `POST /course/`**, que hoy acepta `"."` como nombre de curso (RN-5, RN-8).
- El rechazo, en el login, de una cuenta sin ningún perfil asociado (RN-24).

**Fuera de alcance:** editar colaboradores (nombre, correo), reactivar
colaboradores dados de baja, migrar inscritos de una versión a la siguiente,
historial de auditoría de quién corrigió qué, cambios masivos, un endpoint
dedicado de «reasignar» (ver PA-6), la imagen del curso y el material
(SPEC-008 y SPEC-009), y toda la interfaz, que se implementa después del backend.

## Artículo 4 — Actores y precondiciones

- **Actor:** administrador autenticado con `admin_profile` y organización.
- **Precondiciones:** token Knox válido. Los recursos existen y pertenecen al
  tenant del administrador.
- Un colaborador autenticado NO DEBE poder ejecutar ninguna de estas operaciones.
- Ninguna operación de esta spec DEBE borrar filas físicamente.

## Artículo 5 — Reglas de negocio

### Corregir y retirar un curso

- **RN-1.** El sistema DEBE exponer `GET`, `PATCH` y `DELETE` en
  `/course/{id}/` para `IsAdmin`. Sin token DEBE responder `401`; con rol
  colaborador, `403`.
- **RN-2.** El curso DEBE pertenecer a `request.user.admin_profile.organization` y
  tener `show=True`. En caso contrario —otro tenant, oculto o inexistente— DEBE
  responder `404`, sin revelar su existencia. La organización NO DEBE leerse del
  body ni de query params.
- **RN-3.** `PATCH` DEBE aceptar únicamente `full_name`, `description`,
  `duration_hours` e `is_active`. Cualquier otro campo del body —`version`,
  `organization`, `organization_id`, `show`, `created_at`, `enrolled_count`— DEBE
  ignorarse sin alterar el curso.
- **RN-4.** `version` NO DEBE editarse por `PATCH`. La versión cambia solo
  publicando una versión nueva (RN-8): si se pudiera editar en su lugar, existirían
  dos caminos para lo mismo y el de `PATCH` perdería el curso anterior.
- **RN-5.** `full_name` DEBE tener, **tras recortar los espacios de los extremos,
  al menos 3 caracteres, y DEBE contener al menos una letra**. Quedan rechazados
  `"."`, `".."`, `"---"`, `"12"` y `"a"`. Esta regla NO DEBE valer solo al editar:
  DEBE declararse **una sola vez** y aplicarse por igual en `PATCH /course/{id}/` y
  en `POST /course/` — supersede SPEC-001 RN-3, que solo exigía «no vacío». Los
  cursos ya guardados con nombres que no la cumplen NO DEBEN modificarse: no hay
  migración de datos, la regla rige de aquí en adelante.
- **RN-5b.** `PATCH` DEBE conservar el resto de las validaciones de SPEC-001:
  `duration_hours` entero mayor o igual a 1 y `full_name` de a lo más 255
  caracteres. Un valor inválido DEBE responder `400` bajo la clave del campo y
  NO DEBE modificar el curso.
- **RN-6.** `is_active` DEBE poder ponerse en `False` (dar de baja) y volver a
  `True` (revertir una baja equivocada). Dar de baja un curso NO DEBE tocar sus
  inscripciones: quien lo tenía asignado lo conserva, marcado como retirado
  (SPEC-006 RN-5), y sigue contando en el panel (SPEC-004 RN-3).
- **RN-7.** `DELETE /course/{id}/` DEBE ser borrado lógico (`show=False`) y
  responder `204`. Un curso con al menos un **inscrito vigente** (SPEC-004 RN-5)
  NO DEBE poder eliminarse: DEBE responder `400` explicando que primero se dé de
  baja el curso o se desinscriba a su gente. Eliminar existe para el curso creado
  por error, no para hacer desaparecer historial. Un curso eliminado DEBE dejar de
  aparecer en todos los listados y responder `404` en las rutas que lo pidan.

### Versionar

- **RN-8.** El sistema DEBE exponer `POST /course/{id}/new-version/` para
  `IsAdmin`, que recibe `version` (texto obligatorio, máximo 20 caracteres, que
  tras recortar espacios DEBE contener **al menos un carácter alfanumérico**).
  Quedan rechazados `""`, `"."` y `"--"`; siguen siendo válidos `"1.0"`, `"2"`,
  `"v3"` y `"2026.1"`.
- **RN-9.** El curso de origen DEBE pertenecer al tenant, tener `show=True` e
  `is_active=True`. En caso contrario DEBE responder `404`. Versionar un curso ya
  retirado NO DEBE permitirse: la versión nueva sucede a la que está vigente.
- **RN-10.** La `version` recibida DEBE ser distinta de la del curso de origen y
  NO DEBE coincidir con la de ningún otro curso visible del mismo tenant que
  comparta `full_name`. En caso contrario DEBE responder `400` bajo `version`.
- **RN-11.** Publicar una versión DEBE crear un **curso nuevo** copiando
  `full_name`, `description` y `duration_hours` del de origen, con la `version`
  recibida, `is_active=True`, `show=True` y la organización del administrador. La
  respuesta DEBE ser `201` con el curso nuevo.
- **RN-12.** En la misma operación, el curso de origen DEBE quedar
  `is_active=False`. Las dos escrituras DEBEN ser atómicas: si algo falla, NO DEBE
  quedar ni el curso nuevo ni el viejo retirado.
- **RN-13.** Los inscritos del curso de origen NO DEBEN migrarse a la versión
  nueva. Quedan donde estaban, que es lo que hace auditable «esta persona cursó la
  1.0». Inscribir en la versión nueva es una acción aparte y explícita.

### Desinscribir y reinscribir

- **RN-14.** El sistema DEBE exponer
  `DELETE /course/{id}/collaborators/{enrollment_id}/` para `IsAdmin`, que DEBE
  poner `show=False` en la inscripción y responder `204`.
- **RN-15.** La inscripción DEBE pertenecer al curso de `{id}`, y el curso al
  tenant del administrador. Una inscripción de otro curso, de otro tenant,
  inexistente o **ya oculta** DEBE responder `404`.
- **RN-16.** Al curso NO DEBE exigírsele `is_active=True`: corregir una
  inscripción de un curso retirado DEBE ser posible, por la misma razón que
  `GET /course/{id}/collaborators/` los admite (SPEC-005 RN-4).
- **RN-17.** Desinscribir DEBE hacer bajar el `enrolled_count` del curso y sacar a
  la persona de `GET /course/{id}/collaborators/` y de sus «mis cursos», porque el
  criterio de «inscrito vigente» ya exige `show=True` en la inscripción. NO DEBE
  agregarse una segunda definición de vigencia.
- **RN-18.** `POST /course/{id}/assign/` DEBE **reactivar** una inscripción oculta
  del mismo par curso-colaborador —poniendo `show=True`— y responder `201` con
  ella, en vez del `400` que ordenaba SPEC-003 RN-6. Una inscripción **visible**
  DEBE seguir respondiendo `400` como hasta ahora.
- **RN-19.** Al reactivar, `assigned_at` DEBE conservar su valor original: es la
  fecha en que se asignó, no la de la corrección.

### Dar de baja a un colaborador

- **RN-20.** El sistema DEBE exponer `DELETE /collaborator/{id}/` para `IsAdmin`,
  que DEBE responder `204`. El colaborador DEBE pertenecer al tenant y tener
  `show=True`; si no, `404`.
- **RN-21.** Dar de baja DEBE poner `show=False` en el `Collaborator` **y**
  `is_active=False` en su `User`, en una sola transacción. Sin lo segundo, alguien
  dado de baja seguiría iniciando sesión y viendo sus cursos.
- **RN-22.** Dar de baja NO DEBE borrar sus inscripciones. Dejan de contar y de
  listarse por el criterio de «inscrito vigente», que ya exige
  `collaborator__show=True` y el usuario activo; el vínculo histórico permanece en
  la base.
- **RN-23.** Un administrador NO DEBE poder darse de baja a sí mismo por esta ruta:
  el endpoint opera sobre `Collaborator`, y un admin no lo es.

### Cuentas sin perfil

- **RN-24.** `POST /user/login/` DEBE rechazar con `400` a un usuario que
  autentique correctamente pero **no tenga ni `admin_profile` ni
  `collaborator_profile`**, sin entregar token. El error DEBE usar la forma de los
  errores de auth ya existente —`{"text": "..."}`, que es la única que el front
  lee— y DEBE decir que la cuenta no tiene un perfil asociado, en vez de mentir con
  «Credenciales inválidas»: quien llega hasta acá ya demostró ser el dueño de la
  cuenta, así que no hay nada que ocultarle.
- **RN-25.** Esta regla NO DEBE alcanzar a los colaboradores dados de baja por
  RN-20: la baja deja el perfil en su lugar (`show=False`), así que a ellos los
  rechaza `is_active=False` por el camino de siempre. Las dos causas DEBEN quedar
  distinguibles en los tests.

## Artículo 6 — Criterios de aceptación

**Corregir un curso**

- **CA-1:** `PATCH` con nombre, descripción y duración válidos responde `200` con
  el curso actualizado y persiste el cambio.
- **CA-2:** `PATCH` con `version` en el body no cambia la versión del curso.
- **CA-3:** `PATCH` con `organization`, `organization_id`, `show` o `created_at` en
  el body no altera ninguno de esos campos.
- **CA-4:** `PATCH` con `full_name` vacío, `"."`, `".."`, `"---"`, `"12"` o `"a"`
  responde `400` bajo `full_name` y no modifica el curso.
- **CA-5:** `PATCH` con `duration_hours` igual a 0 o negativo responde `400` bajo
  `duration_hours`.
- **CA-6:** `PATCH` sobre un curso de otro tenant, oculto o inexistente responde
  `404`.
- **CA-7:** `PATCH` con `is_active=false` retira el curso, y con `is_active=true`
  lo reactiva.
- **CA-8:** dar de baja un curso no cambia la cantidad de sus inscritos ni lo saca
  de «mis cursos» del colaborador.
- **CA-9:** `GET /course/{id}/` responde `200` con el curso y su `enrolled_count`.

**Eliminar un curso**

- **CA-10:** `DELETE` sobre un curso sin inscritos vigentes responde `204`, deja
  `show=False` y no borra la fila.
- **CA-11:** el curso eliminado desaparece de `GET /course/`, de
  `GET /course/enrollments/` y responde `404` en `GET /course/{id}/`.
- **CA-12:** `DELETE` sobre un curso con un inscrito vigente responde `400` y el
  curso sigue visible.
- **CA-13:** `DELETE` sobre un curso cuyo único inscrito fue desinscrito sí
  responde `204`.

**Versionar**

- **CA-14:** `POST /course/{id}/new-version/` con una versión nueva responde `201`
  con un curso distinto, activo, con el mismo nombre, descripción y duración.
- **CA-15:** tras versionar, el curso de origen queda `is_active=False` y sigue
  visible.
- **CA-16:** los inscritos del curso de origen siguen en él y la versión nueva
  nace con `enrolled_count` en 0.
- **CA-17:** versionar con la misma `version` del origen responde `400` bajo
  `version`.
- **CA-18:** versionar con una `version` que ya usa otro curso del mismo nombre
  responde `400` bajo `version`.
- **CA-19:** omitir `version`, o mandarla vacía, `"."` o `"--"`, responde `400`
  bajo `version`.
- **CA-20:** versionar un curso inactivo, oculto, de otro tenant o inexistente
  responde `404`.
- **CA-21:** un `400` al versionar no crea el curso nuevo ni retira el de origen.

**Desinscribir y reinscribir**

- **CA-22:** `DELETE` de una inscripción vigente responde `204` y la deja
  `show=False` sin borrar la fila.
- **CA-23:** tras desinscribir, el `enrolled_count` del curso baja en uno y la
  persona no aparece en `GET /course/{id}/collaborators/`.
- **CA-24:** tras desinscribir, el curso desaparece de «mis cursos» de esa
  persona.
- **CA-25:** `DELETE` de una inscripción ya oculta responde `404`.
- **CA-26:** `DELETE` de una inscripción que pertenece a otro curso responde `404`
  y no la modifica.
- **CA-27:** `DELETE` de una inscripción de otro tenant responde `404`.
- **CA-28:** desinscribir de un curso inactivo responde `204`.
- **CA-29:** volver a inscribir a una persona desinscrita responde `201`, deja la
  inscripción visible otra vez y no crea una segunda fila.
- **CA-30:** al reactivar, `assigned_at` conserva su valor original.
- **CA-31:** inscribir a alguien ya inscrito y visible sigue respondiendo `400`.

**Dar de baja a un colaborador**

- **CA-32:** `DELETE /collaborator/{id}/` responde `204`, deja `show=False` en el
  colaborador e `is_active=False` en su usuario.
- **CA-33:** el colaborador dado de baja desaparece de `GET /collaborator/` y ya
  no cuenta en el `enrolled_count` de los cursos donde estaba.
- **CA-34:** sus inscripciones siguen existiendo en la base.
- **CA-35:** dar de baja a un colaborador de otro tenant, ya oculto o inexistente
  responde `404`.
- **CA-36:** un colaborador dado de baja no puede iniciar sesión.

**Permisos, transversal a todo el artículo**

- **CA-37:** cada uno de los cinco endpoints de administración responde `401` sin
  token. El login queda fuera: es público y no tiene permiso que probar.
- **CA-38:** cada uno de esos cinco endpoints responde `403` con rol colaborador.

**La validación del nombre alcanza también a la creación**

- **CA-39:** `POST /course/` con `full_name` igual a `"."`, `".."`, `"---"`, `"12"`
  o `"a"` responde `400` bajo `full_name` y no crea el curso. Es el mismo listado
  de CA-4: si alguno de los dos endpoints acepta lo que el otro rechaza, la regla
  se declaró dos veces.
- **CA-40:** `POST /course/` con `"  Prevención de riesgos  "` crea el curso; el
  nombre se guarda recortado y el largo mínimo se mide sobre el texto recortado.
- **CA-41:** un curso ya guardado con un nombre que no cumple la regla se sigue
  listando y se puede dar de baja; la regla no lo vuelve inaccesible.

**Cuentas sin perfil**

- **CA-42:** un usuario con contraseña correcta pero sin `admin_profile` ni
  `collaborator_profile` recibe `400` al iniciar sesión, con la clave `text`, y no
  obtiene token.
- **CA-43:** un colaborador dado de baja con `DELETE /collaborator/{id}/` conserva
  su `collaborator_profile`; su login falla por `is_active=False` (CA-36) y no por
  CA-42. Las dos causas son distintas y el test lo verifica sobre el perfil, no
  sobre el mensaje.
- **CA-44:** un admin y un colaborador normales siguen iniciando sesión igual que
  antes.

## Artículo 7 — Contrato de interfaz

### `GET | PATCH | DELETE /course/{id}/`

**Autenticación:** `Authorization: Token <token>` · permiso `IsAdmin`.

`PATCH` — body parcial, todos los campos opcionales:

```json
{
  "full_name": "Prevención de riesgos",
  "description": "…",
  "duration_hours": 8,
  "is_active": false
}
```

**Respuesta `200`:**

```json
{
  "id": 3,
  "full_name": "Prevención de riesgos",
  "description": "…",
  "duration_hours": 8,
  "version": "1.0",
  "is_active": false,
  "created_at": "2026-09-04T12:00:00Z",
  "enrolled_count": 4
}
```

`DELETE` — sin body. **Respuesta `204`** sin contenido, o `400`:

```json
{
  "detail": [
    "No se puede eliminar un curso con inscritos. Da de baja el curso o desinscribe a sus colaboradores."
  ]
}
```

### `POST /course/{id}/new-version/`

```json
{ "version": "2.0" }
```

**Respuesta `201`:** el curso nuevo, con la misma forma que el `200` de arriba
(`enrolled_count` en 0). **Errores:** `400` bajo `version`, `404` si el curso de
origen no está disponible.

### `DELETE /course/{id}/collaborators/{enrollment_id}/`

**Respuesta `204`** sin contenido. **Errores:** `404` si la inscripción no existe,
ya está oculta, es de otro curso o de otro tenant.

### `DELETE /collaborator/{id}/`

**Respuesta `204`** sin contenido. **Errores:** `404` si el colaborador no
pertenece al tenant o ya está dado de baja.

### `POST /user/login/` — cambio de comportamiento

Sin cambios en la firma. Una cuenta con credenciales válidas pero **sin ningún
perfil** deja de recibir token y responde `400`:

```json
{ "text": "Tu cuenta no tiene un perfil asociado. Contacta al administrador." }
```

### `POST /course/{id}/assign/` — cambio de comportamiento

Sin cambios en la firma. Ante un par curso-colaborador con inscripción **oculta**,
ahora responde `201` reactivándola en vez de `400` (RN-18).

**Frontend (se implementa después del backend):** la pantalla de cursos suma
editar, versionar y eliminar por curso; el panel de inscripciones suma
desinscribir en cada fila expandida; la pantalla de colaboradores suma dar de
baja. Cada acción destructiva DEBE pedir confirmación y decir qué consecuencia
tiene. El detalle de esta interfaz se fija al implementarla.

## Artículo 8 — Preguntas abiertas resueltas

- **PA-1:** versionar **crea un curso nuevo** y retira el anterior, en vez de
  editar el campo `version`. La versión es parte de la identidad de lo que alguien
  cursó: si se edita en su lugar, los inscritos de la 1.0 pasan a figurar como
  inscritos de la 2.0 y se pierde el registro de qué contenido recibieron. Es
  además la lectura que ya asumía SPEC-005 PA-7 al justificar por qué un curso
  retirado conserva su lista de inscritos.
- **PA-2:** los inscritos **no se migran** a la versión nueva. Migrarlos diría que
  esas personas cursaron algo que todavía no existía. Quien deba rehacer el curso
  se inscribe explícitamente en la versión nueva.
- **PA-3:** el curso de origen queda **inactivo, no oculto**. Debe seguir viéndose
  en el panel —con sus inscritos— porque esa es justamente la información que el
  versionado quiere preservar.
- **PA-4:** «dar de baja» y «eliminar» son operaciones distintas y las dos se
  implementan. Dar de baja (`is_active=False`) retira el curso de circulación
  conservándolo a la vista; eliminar (`show=False`) es para el curso creado por
  error, y por eso RN-7 lo prohíbe cuando hay gente inscrita. Ofrecer solo una de
  las dos obligaría a elegir entre no poder deshacer un error de tipeo o poder
  borrar historial.
- **PA-5:** desinscribir es **borrado lógico**, como manda la regla de
  arquitectura. La fila queda como rastro de que la inscripción existió.
- **PA-6:** **no** se agrega un endpoint de «reasignar». Mover a alguien de un
  curso a otro es desinscribir de uno e inscribir en otro, dos operaciones que ya
  existen y que la interfaz compone. Un endpoint propio sería una tercera forma de
  escribir lo mismo, con sus propias reglas de tenant que mantener.
- **PA-7:** volver a inscribir a alguien desinscrito **reactiva** la fila existente
  en vez de crear una nueva. La restricción única `(course, collaborator)` no
  filtra por `show`, así que crear otra fila sería imposible; y reactivar mantiene
  una sola verdad por par.
- **PA-8:** al reactivar se conserva el `assigned_at` original en vez de
  actualizarlo. La fecha responde «desde cuándo tiene este curso asignado»; una
  desinscripción por error no cambia esa respuesta. El costo es que no queda
  registro de la interrupción, y se acepta: esta entrega no lleva auditoría.
- **PA-9:** dar de baja a un colaborador **también desactiva su usuario**. Un
  colaborador oculto que igual puede iniciar sesión es un agujero, no una
  simplificación.
- **PA-10:** no se ofrece reactivar a un colaborador dado de baja. La baja de una
  persona es un hecho administrativo poco frecuente y su reverso pide decidir qué
  pasa con sus inscripciones históricas; queda para una spec propia antes que
  resuelto a medias acá.
- **PA-11:** `PATCH` no acepta `version` aunque el campo sea editable en el modelo.
  Un solo camino por operación (RN-4).
- **PA-12:** reactivar un curso retirado por un versionado **se permite** sin
  chequear si su sucesor está activo. La organización puede tener dos versiones
  vigentes a propósito —una en curso y otra nueva— y el sistema no tiene por qué
  decidir eso por ella.
- **PA-13:** el piso del nombre es **3 caracteres y al menos una letra**, y no un
  número mayor. Se eligió el mínimo que rechaza la basura evidente (`"."`, `"---"`,
  `"12"`, `"a"`) sin ponerse a juzgar la calidad editorial de un nombre que
  escribe un administrador autenticado. **El costo aceptado es una sigla real de
  dos caracteres**: «5S» —la metodología de orden y limpieza— hay que escribirla
  «5S — Orden y limpieza». Se prefiere ese falso positivo, que tiene una salida
  obvia, antes que dejar pasar `"ab"`.
- **PA-14:** la regla **no se aplica retroactivamente**. No hay migración que
  renombre los cursos ya guardados: reescribir el dato de una organización para
  satisfacer una regla nueva es peor que convivir con él. Un curso viejo con
  nombre inválido se sigue listando y se puede dar de baja; solo se le exige el
  nombre nuevo si alguien va a editarlo (CA-41).
- **PA-15:** la validación vive en **un único validador compartido** por la
  creación y la edición, no duplicada en cada serializer. Dos copias de la misma
  regla se separan a la primera corrección, y entonces `POST` y `PATCH` empiezan a
  aceptar cosas distintas.
- **PA-16:** el login rechaza a la cuenta sin perfil **con un mensaje propio**, no
  con «Credenciales inválidas». En ese punto la contraseña ya se validó: la
  persona es dueña de la cuenta y no hay enumeración que evitar. Mentirle solo
  lograría que reintente su contraseña, que está bien.
- **PA-17:** el efecto secundario de RN-24 es que **un superusuario creado con
  `createsuperuser` deja de poder loguearse por la API**, porque no tiene perfil.
  Se acepta a propósito: ese usuario existe para entrar por `/admin/` con sesión
  de Django, y por la API no tendría ninguna operación disponible de todos modos
  —`IsAdmin` mira `admin_profile`, no `is_superuser`—. Lo único que cambia es que
  ahora se lo dicen en vez de dejarlo entrar a una interfaz que rebota.
- **PA-18:** no se agrega limpieza ni detección de usuarios huérfanos. El agujero
  se cierra impidiendo que entren, no persiguiendo filas: mientras la API no borre
  físicamente, el huérfano solo lo puede fabricar alguien con acceso al `/admin/`
  de Django, que ya sabe lo que está haciendo.

## Artículo 9 — Decisiones, dependencias y referencias

El backend reutiliza `Course`, `CourseCollaborator`, `Collaborator`, `User`,
`TokenAuthentication`, `IsAdmin`, `with_enrolled_count()` y el criterio
`vigente()` que SPEC-004 y SPEC-005 dejaron en `apps/course/views.py`; RN-7 y
RN-17 se apoyan en ese criterio en vez de definir el suyo. Las vistas nuevas son
genéricas de DRF —`RetrieveUpdateDestroyAPIView` para el detalle del curso,
`GenericAPIView` para versionar, `DestroyAPIView` para la inscripción y para el
colaborador— en los `views.py` que ya existen. Las operaciones de RN-12 y RN-21
usan `transaction.atomic()`.

La validación de RN-5 y RN-8 se escribe como funciones de validación a nivel de
módulo en `apps/course/views.py` —donde ya viven los serializers de este dominio—
y `CourseCreateSerializer` las adopta junto con los serializers nuevos. Es el
único punto de esta spec que modifica código de SPEC-001.

RN-24 toca `LoginView` en `apps/user/views.py`, que es código del scaffolding
base: se agrega una comprobación después de autenticar y antes de emitir el token,
usando el mismo `hasattr(user, "…_profile")` con que ya se deriva el rol en
`UserSerializer.get_role()`. No se toca el front: el mensaje viaja bajo la clave
`text`, que la pantalla de login ya sabe mostrar.

**No se agregan modelos, campos, migraciones ni dependencias.** Todo el estado que
esta spec manipula —`show` de `BaseAbstractModel`, `is_active` de `Course` y de
`User`— ya existe en la base y hasta ahora no tenía quién lo escribiera.

`GET /course/{id}/` nace acá como retrieve simple porque la vista de detalle lo
trae consigo y `PATCH` necesita devolver el objeto igual. SPEC-009 lo extenderá
con la imagen y la ficha; esta spec no lo diseña para eso.

Depende de SPEC-001 (validaciones del curso), SPEC-003 (endpoint de asignación,
cuyo comportamiento ante un duplicado oculto se modifica), SPEC-004 (criterio de
inscrito vigente y panel), SPEC-005 (lista de inscritos) y SPEC-006 (mis cursos,
que refleja las desinscripciones sin cambiar).

---

## Anexo A — Tests y verificaciones

Los tests se escriben primero, repartidos por dominio:
`apps/course/tests/test_edit_course.py` (CA-1..CA-13),
`apps/course/tests/test_course_version.py` (CA-14..CA-21),
`apps/course/tests/test_unenroll.py` (CA-22..CA-31) y
`apps/user/tests/test_deactivate_collaborator.py` (CA-32..CA-36), con los CA-37 y
CA-38 de permisos repetidos en cada archivo para su propia ruta. CA-39 y CA-40
van en `apps/course/tests/test_create_course.py`, junto a los tests de SPEC-001
que ya viven ahí: la regla es de la creación tanto como de la edición, y el test
tiene que estar donde alguien la vaya a buscar. CA-42, CA-43 y CA-44 van en
`apps/user/tests/test_auth.py`, por la misma razón.

Cinco grupos de tests cargan el peso de las decisiones de esta spec y no deben
ablandarse: **CA-12**, que impide borrar un curso con gente inscrita; **CA-16**,
que fija que versionar no migra inscritos; **CA-29 y CA-30**, que verifican que la
reinscripción reactiva la fila original conservando su fecha; **CA-36**, que
comprueba que un colaborador dado de baja no puede iniciar sesión; y el par
**CA-4 y CA-39**, que corren la misma lista de nombres inválidos contra editar y
contra crear — si uno de los dos se ablanda, la regla dejó de estar declarada una
sola vez.

Se verifica además que la suite completa siga verde (101 tests antes de esta
feature) y que `python manage.py makemigrations --check` no detecte cambios
pendientes.
