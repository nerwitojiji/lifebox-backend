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

## SPEC-006 — Mis cursos

**El colaborador sale del token y de ningún otro lado.** La vista no lee nada de
la petición: ni body, ni query params, ni URL. No existe forma de pedir los cursos
de otra persona, porque no hay parámetro que lo permita. El aislamiento no depende
de validar una entrada, sino de que esa entrada no exista.
→ `MyCoursesView.get_queryset()` en `apps/course_collaborator/views.py`.

**El aislamiento se prueba entre compañeros, no solo entre organizaciones.** Todas
las suites anteriores miraban el lado del admin, donde el riesgo es cruzar tenants.
Acá el riesgo es otro: que Ana vea los cursos de Luis siendo los dos de la misma
empresa. Por eso el fixture pone a dos colaboradores en la misma organización.

**Se filtra igual por organización, aunque sea redundante.** La asignación ya
impide cruzar tenants, pero el modelo `CourseCollaborator` no lo garantiza por sí
solo —nada a nivel de base impide una fila que enlace un colaborador con un curso
ajeno—. El filtro extra no cuesta nada y evita que un dato inconsistente se
convierta en una fuga.

**Los cursos inactivos se listan; los ocultos no.** Mismo criterio que SPEC-004 y
SPEC-005: `is_active=False` es un curso retirado que conserva a sus inscritos —y
quien lo tenía asignado conserva la obligación—, mientras que `show=False` es un
borrado lógico. Esconder un curso retirado le taparía trabajo pendiente a la
persona.

**La respuesta no expone `enrolled_count` ni datos de otros inscritos.** Cuántos
compañeros tiene el curso no es información del colaborador. El serializer es una
clase aparte precisamente para que el campo del panel no se filtre acá por
herencia.

**El curso va anidado dentro de la inscripción.** Simétrico a
`GET /course/{id}/collaborators/`, que anida el colaborador: en los dos casos el
recurso es la inscripción, y `assigned_at` pertenece a ella, no al curso.

**El hueco de PA-8 sigue sin parchear, y es deliberado.** Un colaborador con
`Collaborator.show=False` y `user.is_active=True` podría iniciar sesión y ver esta
pantalla. No se endureció `IsCollaborator` porque hoy **ningún flujo de la API
puede dar de baja a un colaborador** —no existe el endpoint—, y el parche dejaría a
esa persona pudiendo entrar pero recibiendo `403` en todas partes, que es peor que
el estado actual. La condición para que el criterio se sostenga sigue siendo la
misma: la capacidad de baja debe apagar `Collaborator.show` **y** `user.is_active`
a la vez, con lo cual la persona no puede ni autenticarse.

> **Cerrado por SPEC-007.** `DELETE /collaborator/{id}/` apaga los dos campos en
> una sola transacción (RN-21), que es exactamente la condición que este supuesto
> exigía. El hueco dejó de existir sin tener que endurecer `IsCollaborator`.

## SPEC-007 — Correcciones: reasignar, versionar y dar de baja

**Ningún endpoint borra filas: todos escriben `show`.** Es la regla de
arquitectura del repo, confirmada por quien entregó la base, y acá tiene una razón
concreta: **todas las FK del proyecto son `on_delete=CASCADE`**. Un
`curso.delete()` no borra un curso, borra el curso *y todas sus inscripciones* en
silencio — justo el registro de quién lo cursó, que es lo que el panel y el
versionado existen para conservar. La operación que el admin cree hacer y la que
la base hace no serían la misma. Con `show=False` el borrado es local y
reversible.
→ `CourseDetailView.perform_destroy()`, `CourseUnenrollView.perform_destroy()` y
`CollaboratorDeactivateView.perform_destroy()`.

**«Dar de baja» y «eliminar» son dos operaciones distintas, y las dos existen.**
Dar de baja un curso (`is_active=False`, vía `PATCH`) lo retira de circulación
pero lo deja a la vista con sus inscritos; eliminarlo (`show=False`, vía `DELETE`)
lo hace desaparecer. Ofrecer solo una obligaba a elegir entre no poder deshacer un
error de tipeo o poder borrar historial. Por eso **`DELETE` responde `400` si el
curso tiene inscritos vigentes**: eliminar es para el curso creado por error, y
quien quiera retirar uno que ya se dictó tiene la baja.

**Versionar crea un curso nuevo y retira el anterior; no edita el campo
`version`.** La versión es parte de la identidad de lo que alguien cursó: si se
editara en su lugar, los inscritos de la 1.0 pasarían a figurar como inscritos de
la 2.0 y se perdería el registro de qué contenido recibieron. Por la misma razón
**los inscritos no se migran** a la versión nueva: migrarlos afirmaría que esas
personas cursaron algo que todavía no existía. El curso de origen queda
**inactivo, no oculto**, porque su lista de inscritos es justamente la información
que el versionado quiere preservar.
→ `CourseNewVersionView.post()`.

**`PATCH` no acepta `version` aunque el campo sea editable en el modelo.** Un solo
camino por operación: si se pudiera editar, existirían dos formas de cambiar la
versión y la del `PATCH` perdería el curso anterior.

**Reinscribir a alguien desinscrito reactiva su fila en vez de crear una nueva, y
conserva la fecha original.** Esto **supersede SPEC-003 RN-6**, que devolvía `400`
ante un par ya existente aunque estuviera oculto. La `UniqueConstraint(course,
collaborator)` no filtra por `show`, así que una segunda fila es imposible y el
`400` habría dicho «ya está inscrito» sobre algo que nadie ve: desinscribir por
error habría sido irreversible. `assigned_at` no se toca porque responde «desde
cuándo tiene este curso asignado», y una desinscripción equivocada no cambia esa
respuesta; el costo aceptado es que no queda registro de la interrupción.
→ `CourseAssignView.post()`.

**Desinscribir se permite en un curso inactivo, aunque inscribir no.** Misma
asimetría deliberada que SPEC-005 documentó para la lista de inscritos: crear un
vínculo nuevo en un curso retirado no tiene sentido, corregir uno existente sí.

**No hay endpoint de «reasignar».** Mover a alguien de un curso a otro es
desinscribir de uno e inscribir en otro, dos operaciones que ya existen. Un
endpoint propio sería una tercera forma de escribir lo mismo, con sus propias
reglas de tenant que mantener en sincronía.

**El nombre de un curso exige 3 caracteres y al menos una letra, al crear y al
editar.** Hasta esta feature `"."` era un nombre de curso válido: lo único que se
validaba era «no vacío» (SPEC-001 RN-3, ahora superseded). El colaborador que abre
«Mis cursos» tiene que entender qué va a cursar. El piso es el mínimo que rechaza
la basura evidente (`"."`, `"---"`, `"12"`, `"a"`) sin ponerse a juzgar la calidad
editorial de lo que escribe un administrador autenticado; **el costo aceptado es
una sigla real de dos caracteres**, como «5S», que hay que escribir «5S — Orden y
limpieza». La regla se declara **una sola vez** y la comparten los dos serializers:
duplicada, `POST` y `PATCH` se separarían a la primera corrección.
→ `validar_nombre_de_curso()` en `apps/course/views.py`.

**La regla del nombre no se aplica retroactivamente.** No hay migración que
renombre los cursos ya guardados: reescribir el dato de una organización para
satisfacer una regla nueva es peor que convivir con él. Un curso viejo con nombre
inválido se sigue listando y se puede dar de baja; solo se le exige el nombre
nuevo a quien vaya a editarlo.

**El login rechaza a una cuenta sin ningún perfil.** El rol no es un campo: se
deriva de la existencia de `admin_profile` o `collaborator_profile`. Un usuario sin
ninguno de los dos autentica bien, recibe `role: null`, y el middleware del front
lo manda de `/admin` a `/colaborador` y de vuelta, porque `isAdmin` e
`isCollaborator` son las dos falsas. No es una cuenta inútil: es una cuenta que
rompe la aplicación. Se le responde `400` con un mensaje propio y no con
«Credenciales inválidas», porque en ese punto ya acertó su contraseña: es su
cuenta y no hay enumeración que evitar.
→ `LoginView.post()` en `apps/user/views.py`.

**Un superusuario de `createsuperuser` deja de poder entrar por la API.** Es el
efecto secundario de lo anterior y se acepta a propósito: ese usuario existe para
`/admin/` con sesión de Django, y por la API no tendría ninguna operación
disponible de todos modos —`IsAdmin` mira `admin_profile`, no `is_superuser`—. Lo
único que cambia es que ahora se lo dicen en vez de dejarlo entrar a una interfaz
que rebota.

**No se detectan ni se limpian usuarios huérfanos.** El agujero se cierra
impidiendo que entren, no persiguiendo filas. Mientras la API no borre
físicamente, un huérfano solo lo puede fabricar alguien con acceso al `/admin/` de
Django, que es también la única puerta que queda para una purga real —por ejemplo,
un derecho a supresión de la Ley 19.628— y que está fuera del alcance del uso
normal a propósito.

## SPEC-008 — Corregir la versión de un curso

**La versión se puede corregir, pero solo mientras nadie se haya inscrito.**
SPEC-007 la había hecho de solo lectura, con un buen argumento: la versión es
parte de la identidad de lo que alguien cursó. Pero eso deja sin respuesta el
caso que el enunciado nombra —«puse mal la versión: decía 1.0 y en realidad es
2.0»—, que no es versionar sino corregir un tipeo: obligaba a publicar una
versión nueva y dejaba dos cursos donde se quería uno corregido. La distinción
que faltaba no era «editar vs. versionar», sino **si hay historial que
proteger**. Con al menos un inscrito, la prohibición de SPEC-007 sigue intacta.
→ `CourseDetailSerializer.validate_version()` en `apps/course/views.py`.

**La condición es «sin inscritos vigentes», no «recién creado».** Una ventana de
tiempo —editable los primeros N minutos— es arbitraria y falla justo cuando el
error se descubre tarde. «Nadie se inscribió todavía» es la condición real que
hace inofensivo el cambio, y ya venía calculada en el `enrolled_count` que anota
el queryset: la regla no cuesta una consulta nueva.

**Un curso cuyos inscritos fueron desinscritos o dados de baja vuelve a admitir
la corrección.** Es consecuencia de reutilizar el criterio de «inscrito vigente»
en vez de contar filas, y es lo correcto: si el contador dice 0, no hay a quién
mentirle. El precio es que un administrador puede vaciar un curso a propósito
para cambiarle la versión. **No se bloquea**: sería una defensa contra alguien
que ya tiene permiso para hacer las dos operaciones por separado, y exigiría un
rastro de auditoría que esta entrega no lleva. Queda como límite conocido, no
como olvido.

**Reenviar la misma versión nunca falla, ni siquiera con inscritos.** No es un
cambio, y un cliente que hace `PATCH` con el objeto completo es un uso legítimo.
Fallar ahí convertiría una regla de negocio en una trampa de integración.

**`POST /course/{id}/new-version/` no se restringió a cursos con inscritos.**
Publicar la 2.0 de un curso que nadie tomó es legítimo —el contenido cambió— así
que ahí conviven dos caminos válidos: corregir el número o publicar una versión.
Cuál corresponde lo sabe el administrador, no el sistema.

## SPEC-009 — Cambiar la contraseña

**Se exige la contraseña actual aunque la persona ya esté autenticada.** El token
pudo quedar abierto en un equipo prestado; sin ese segundo factor, apropiarse de
la cuenta sería trivial para quien lo tenga. El costo es un campo más en el
formulario y vale la pena.

**Al cambiarla se invalidan los demás tokens del usuario, y solo sobrevive el de
la petición.** Esta es la razón de seguridad de toda la feature: la contraseña
temporal la generó el servidor pero **la vio el administrador** y viajó por algún
canal. Si alguien abrió sesión con ella, esa sesión muere en el momento del
cambio. El token actual se conserva para no expulsar a quien acaba de hacer lo
correcto.
→ `ChangePasswordView.post()` en `apps/user/views.py`.

**La fuerza de la contraseña la deciden los `AUTH_PASSWORD_VALIDATORS` que ya
estaban en `settings.py`,** no una regla nueva. Ya gobernaban la contraseña
temporal generada; que gobiernen también la elegida mantiene un solo criterio y
evita que la validación del cambio y la de la generación se separen.

**El endpoint sirve a cualquier usuario autenticado, administradores incluidos.**
Opera sobre `request.user` y nunca sobre un identificador, así que restringirlo a
colaboradores costaría código extra para excluir a quien más lo necesita: el admin
entra con la contraseña del seeder y no tiene a nadie por encima a quien pedirle
una regeneración.

**El flag `must_change_password` vive en `User` y no en `Collaborator`.** La
contraseña es del usuario, no del perfil. Ponerlo en el perfil obligaría a
preguntar por el rol antes de saber si hay que avisar, y dejaría fuera a un
administrador al que alguna vez se le entregue una temporal.

**Hizo falta una migración porque `last_login` no sirve como señal de primer
ingreso.** La columna existe —viene de `AbstractBaseUser`— pero **nada la
escribe**: el login usa `authenticate()` y Knox, y nunca llama a
`django.contrib.auth.login()`, que es quien la actualizaría. Se queda en `NULL`
para siempre y no distingue el primer ingreso del décimo.

**Regenerar la contraseña vuelve a encender el aviso.** Sin eso, el flag se
apagaría para siempre después del primer cambio y la persona no se enteraría de
que la temporal nueva también conviene cambiarla.

**No hay recuperación autogestionada por correo, y es una decisión, no una
omisión.** El proyecto no tiene ningún backend de correo configurado, y las tres
salidas posibles son peores que el estado actual: un proveedor real exige
credenciales que quien evalúe no tiene; el backend de consola deja el enlace en la
terminal del servidor, donde no le llega a nadie; y mostrarlo en pantalla le
regala el acceso a cualquiera que escriba un correo conocido. El camino real ya
existe —lo regenera el administrador— y la pantalla de login lo explica.

**No hay límite de intentos sobre `current_password`.** Es una defensa real contra
fuerza bruta, pero exige almacenar intentos o configurar un throttle, y ninguno de
los dos existe en el proyecto. Queda como límite conocido.
