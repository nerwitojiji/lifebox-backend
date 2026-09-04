# Supuestos — Backend

Decisiones tomadas donde el enunciado o el spec dejaban espacio, con el porqué y
dónde se ven en el código. Los supuestos se confirman en el Artículo 8 del spec
correspondiente (`docs/specs/`) y bajan acá una vez cerrados.

## Transversales

**La organización nunca viaja en la petición.** Se deriva siempre del perfil del
usuario autenticado (`request.user.admin_profile.organization`). Si un cliente
manda `organization` u `organization_id` en el body, se ignora en silencio en vez
de responder `400`: el campo no forma parte del contrato de entrada, así que
tratarlo como error revelaría que el servidor lo mira. El aislamiento entre
organizaciones se hace valer filtrando el queryset, nunca confiando en el front.

**Baja lógica, no física.** Todo modelo hereda `show` de `BaseAbstractModel` y los
listados filtran `show=True`. Dar de baja será marcar `show=False`; no se borran
filas.

**Los listados no están paginados.** `GET /course/` y `GET /collaborator/`
devuelven un array plano, no un objeto `{count, results}`. No se configuró
`DEFAULT_PAGINATION_CLASS` porque el volumen esperado es de decenas de registros,
y el frontend tipa las respuestas como arreglos. Si el volumen creciera, agregar
paginación es un cambio que rompe el contrato con el front.

**Los mensajes de error los traduce DRF.** Con `LANGUAGE_CODE = "es-cl"` y
`USE_I18N = True`, los errores de validación salen en español sin trabajo extra.
Por eso los tests asertan sobre el status y la clave del campo, nunca sobre el
texto del mensaje: cambiar de idioma no debe romper la suite.

## SPEC-001 — Crear curso

**`duration_hours` es opcional, con default 1, y se valida `>= 1`.**
El modelo usa `PositiveIntegerField`, que **acepta 0** — un curso de cero horas no
tiene sentido, así que el mínimo es validación añadida en el serializer, no del
modelo. Si se omite, aplica el default del modelo.
→ `CourseCreateSerializer.duration_hours` en `apps/course/views.py`.

**La duración se modela en horas enteras.** El enunciado pide "duración
aproximada" sin unidad. Horas enteras es lo bastante fino para un curso corporativo
y evita decimales sin significado. El label en la UI dice "Duración aproximada
(horas)" para que la unidad sea explícita.

**`version` es texto libre con default `"1.0"`.** El modelo es `CharField(20)` y
el enunciado habla de una "versión corta". No se valida semver: forzar un formato
sería una restricción que nadie pidió, y el campo es informativo.

**`is_active` nace en `true` y no se puede elegir al crear.** Un curso recién
creado está disponible; activarlo o desactivarlo es otra acción, fuera del alcance
de esta spec. El campo se expone en la respuesta pero es de solo lectura.

**El `201` devuelve el curso completo, incluidos los campos de solo lectura.**
`id`, `is_active` y `created_at` forman parte de la respuesta porque el contrato
(Artículo 7) los exige y el frontend necesita el `id`. Por eso el serializer de
escritura los declara en `fields` y los marca en `read_only_fields`, en vez de
listar solo los campos escribibles.

**Una sola vista para `GET` y `POST`.** `ListCreateAPIView` con
`get_serializer_class()`, en lugar de dos vistas separadas: el frontend ya apuntaba
ambos verbos a `/course/`, y separar habría duplicado el permiso y el filtro por
organización. El serializer de escritura sí es una clase aparte, para que la
creación no acepte campos que solo tienen sentido al leer.

## SPEC-002 — Crear colaborador

**La contraseña temporal la genera el servidor y se muestra una sola vez.** El
admin no elige la contraseña: recibe `temporary_password` únicamente en el `201`
de creación. En la base solo queda el hash producido por `set_password`; el valor
en claro no se cifra, guarda ni puede recuperarse después.

**Una contraseña perdida se regenera, no se revela.** El admin puede llamar
`POST /collaborator/{id}/reset-password/`. La respuesta muestra una nueva
contraseña una sola vez y el hash anterior se reemplaza inmediatamente. El
queryset del endpoint está limitado a la organización del admin y a perfiles con
`show=True`; un colaborador de otro tenant se comporta como inexistente (`404`).

**La contraseña tiene 12 caracteres sin símbolos ambiguos.** Se genera con
`django.utils.crypto.get_random_string` y un alfabeto que excluye `0/O` y
`1/l/I`. Esto facilita copiarla o dictarla sin introducir una dependencia ni
reducirla a una constante predecible.

**No se fuerza cambio en el primer login ni se envía correo.** El colaborador
puede entrar inmediatamente con la contraseña temporal vigente. Obligar a
cambiarla y entregar credenciales por email pertenecen a features posteriores.

**El correo es único en todo el sistema.** `User.email` ya tiene `unique=True`,
por lo que tampoco se reutiliza un correo de otro tenant o de un perfil dado de
baja. La reactivación queda fuera de SPEC-002.

## SPEC-003 — Asignar curso

**La asignación es individual.** `POST /course/{id}/assign/` recibe un único
`collaborator_id`. Una operación por inscripción mantiene errores precisos y
evita introducir semántica parcial para lotes dentro del flujo core.

**Solo se asignan recursos disponibles.** El curso debe estar visible y activo;
el perfil colaborador y su usuario deben estar visibles, y el usuario activo. Un
recurso inexistente, no disponible o ajeno al tenant responde `404` para no filtrar
su existencia.

**Los duplicados son error y no reactivan.** Si el par curso-colaborador ya existe,
incluso con `show=False`, la API responde `400` bajo `collaborator_id`. Reactivar
una inscripción es una corrección explícita fuera de SPEC-003. La validación previa
mejora el mensaje y la restricción única sigue protegiendo carreras concurrentes.

**La respuesta contiene un resumen anidado.** El `201` incluye la inscripción,
el nombre/versión del curso y el nombre/correo del colaborador. Así el cliente puede
confirmar la operación sin otra consulta y sin exponer objetos completos.

## SPEC-004 — Panel de inscripciones

**«Inscrito vigente» mide personas que hoy tienen el curso, no historial.** El
conteo excluye las inscripciones con `show=False` y las de colaboradores dados de
baja (`Collaborator.show`, `User.show`, `User.is_active`), con el mismo criterio de
disponibilidad que SPEC-003 usa para admitirlos. La alternativa —contar todo lo
histórico— daría un número que no responde cuánta gente tiene el curso ahora.
→ `VIGENTE` y `with_enrolled_count()` en `apps/course/views.py`.

**La definición vive en un solo lugar y la comparten dos endpoints.** El panel y
`GET /course/` usan la misma anotación, de modo que sus conteos no puedan divergir.
Al cambiar el criterio, cambian los dos juntos.

**Dar de baja a un colaborador es reversible; ocultar una inscripción no.** La baja
del colaborador solo lo saca del conteo: la fila de `CourseCollaborator` sigue
existiendo y reactivarlo restituye el número sin intervención. Ocultar la
inscripción, en cambio, es definitivo (SPEC-003 no la reactiva).

**Esto asume que dar de baja apagará ambos estados a la vez.** Hoy
`IsCollaborator` no verifica `show`, así que un colaborador con
`Collaborator.show=False` y `user.is_active=True` quedaría invisible para el admin
pero podría seguir entrando y viendo sus cursos, y el panel informaría menos
inscritos de los que en la práctica acceden. La futura capacidad de baja debe
apagar `Collaborator.show` **y** `user.is_active` juntos; con esa condición el
criterio se sostiene sin tocar los permisos.

**Los cursos inactivos aparecen; los ocultos no.** `is_active=False` y
`show=False` no son lo mismo: el primero cierra la puerta a inscripciones nuevas,
el segundo saca el registro de circulación. Un curso desactivado conserva a sus
inscritos, así que esconderlo del panel ocultaría inscripciones vivas. Hoy ningún
flujo de la API produce `is_active=False` —el campo es de solo lectura al crear y
no hay endpoint de edición—, pero el panel define su postura porque el modelo lo
permite.

**El orden lo fija el servidor, no el cliente.** `-is_active`, luego
`-enrolled_count`, luego `full_name`. La lista llega ya agrupada para que sea
legible aun sin separarla, y para que un curso inactivo con muchos inscritos no se
cuele antes de uno activo. No se ofrece ordenamiento configurable.

**El conteo se resuelve en una sola consulta agregada.** `annotate(Count(...,
filter=Q(...)))` en vez de contar en Python o por curso. Un test compara el número
de consultas con uno y con siete cursos para que el N+1 no pueda reaparecer.

**La respuesta es una lista plana, sin envoltorio.** No se devuelve
`{ "active": [], "inactive": [] }`: la separación entre activos e inactivos es de
presentación, y un envoltorio habría roto la convención de los demás listados.
Los totales los deriva la interfaz.

**`enrolled_count` en `GET /course/` es un cambio aditivo.** Los campos previos
conservan nombre, tipo y orden; solo se suma uno. Se prefirió extender ese endpoint
antes que hacer que la pantalla de cursos consumiera el panel y cruzara dos listas
por `id`.

## SPEC-005 — Inscribir y ver inscritos

**Leer los inscritos de un curso inactivo SÍ se permite; inscribir en él NO.**
`GET /course/{id}/collaborators/` no exige `is_active=True`, mientras que
`POST /course/{id}/assign/` responde `404`. La asimetría es deliberada y responde a
que son operaciones distintas: una **crea** un vínculo —y un curso retirado no debe
admitir gente nueva— y la otra solo **lee** los que ya existen —y un curso retirado
conserva a los suyos, que es justamente el caso de uso al versionar—. Está
comentada en el código y fijada por
`test_asignar_sigue_rechazando_el_curso_inactivo`, que ejerce los dos endpoints
sobre el mismo curso en la misma prueba. **No igualar las dos condiciones.**
→ `CourseCollaboratorsView.get_course()` vs `CourseAssignView.get_course()` en
`apps/course/views.py`.

**Una sola definición de «inscrito vigente» gobierna tres lugares.** El criterio se
factorizó en `vigente(prefix)`: sin prefijo filtra `CourseCollaborator` directo, y
con `course_collaborators__` se lo mira desde `Course`. Lo usan el
`annotate(Count(...))` del panel, el `enrolled_count` del listado de cursos y el
filtro de esta lista. Si el contador dice 3, la lista trae 3 — y hay un test que lo
compara para que no puedan separarse.

**El orden es por fecha descendente, no alfabético.** Lo recién inscrito aparece
primero, porque el uso inmediato del endpoint es confirmar a quien se acaba de
inscribir. El desempate sí es por nombre.

**La lista no expone al colaborador completo.** Se devuelve `id`, `full_name` y
`email` reutilizando el serializer que ya usaba la asignación, en vez del objeto
entero. Es lo que la interfaz necesita y no filtra más de lo debido.
