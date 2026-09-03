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
