# Mejoras — Backend

Lo que se construyó **además** del flujo pedido en la sección 3 del enunciado, y
qué problema resuelve cada cosa. El flujo core —crear curso, crear colaborador,
asignar, mis cursos y panel de inscripciones— no está acá: eso es la entrega, no
una mejora.

Cada mejora está especificada en `docs/specs/` y tiene tests. La decisión y su
porqué están en `SUPUESTOS.md`.

---

## 1. Corregir un curso ya creado

**Problema:** el sistema solo sabía crear. Un curso con el nombre mal escrito
quedaba mal escrito para siempre, y no había forma de arreglarlo desde la
aplicación.

`PATCH /course/{id}/` corrige nombre, descripción y duración.

## 2. Dar de baja un curso, sin perder a quienes lo cursaron

**Problema:** un curso que la organización dejó de dictar seguía ofreciéndose como
si nada. `Course.is_active` existía desde el scaffolding y **ninguna operación lo
escribía**: solo se podía cambiar desde el admin de Django.

Dar de baja retira el curso de circulación pero lo conserva a la vista, con sus
inscritos, en el panel. Quien lo tenía asignado lo sigue viendo marcado como
retirado: un curso que se retira no cancela la obligación de quien ya lo tenía.

## 3. Eliminar un curso creado por error — y solo ese

**Problema:** «dar de baja» y «eliminar» no son lo mismo, y ofrecer una sola de
las dos obliga a elegir entre no poder deshacer un error de tipeo o poder borrar
historial.

`DELETE /course/{id}/` hace borrado lógico, pero **responde `400` si el curso
tiene inscritos vigentes**, con la instrucción de darlo de baja o desinscribir
primero. Eliminar existe para el curso creado por error, no para hacer desaparecer
el registro de quién cursó qué.

## 4. Publicar una versión nueva de un curso

**Problema:** el enunciado pide que el curso tenga versión, pero nada permitía
avanzarla. Y la salida obvia —editar el campo `version`— es incorrecta: los
inscritos de la 1.0 pasarían a figurar como inscritos de la 2.0, y se perdería el
registro de qué contenido recibió cada persona.

`POST /course/{id}/new-version/` crea un curso nuevo con el mismo contenido y deja
el anterior dado de baja, en una sola operación atómica. **Los inscritos no se
migran**: quien cursó la 1.0 sigue en la 1.0, que es lo que hace auditable la
capacitación.

## 5. Desinscribir, y poder volver a inscribir

**Problema:** una inscripción equivocada era permanente. El enunciado lo nombra
literal: *«Me equivoqué al inscribir a Ana en el curso, era para Bruno»*.

`DELETE /course/{id}/collaborators/{enrollment_id}/` desinscribe con borrado
lógico. Reasignar es desinscribir de un curso e inscribir en otro, dos operaciones
que ya existen; no se agregó un endpoint de «reasignar» que sería una tercera
forma de escribir lo mismo.

**El detalle que hacía falta:** la restricción única `(course, collaborator)` no
filtra por `show`, así que volver a inscribir a alguien desinscrito chocaba contra
una fila que nadie ve y respondía «este colaborador ya está inscrito» — falso, y
sin salida. Ahora la reinscripción **reactiva** esa fila y conserva su fecha
original: desinscribir por error dejó de ser irreversible.

## 6. Dar de baja a un colaborador

**Problema:** el enunciado lo nombra literal: *«Contratamos a alguien, pero ya no
trabaja con nosotros»*. No había forma de reflejarlo.

`DELETE /collaborator/{id}/` oculta el perfil **y desactiva su usuario**, en una
sola transacción. Las dos cosas juntas, porque un colaborador oculto que igual
puede iniciar sesión es un agujero, no una simplificación. Sus inscripciones no se
borran: dejan de contar en el panel, pero el registro de qué cursó se conserva.

## 7. El nombre de un curso ahora tiene un piso

**Problema:** la única validación era «no vacío», así que `"."` era un nombre de
curso perfectamente válido. El colaborador que abre «Mis cursos» y ve un punto no
sabe qué va a cursar — que es justo el problema que el enunciado describe en su
sección 6.1.

Un nombre debe tener al menos 3 caracteres y contener alguna letra. La regla se
declara **una sola vez** y rige tanto al crear como al editar: si viviera solo en
la edición, se seguiría pudiendo crear `"."` y el `PATCH` sería el único en
quejarse. No se aplica retroactivamente: reescribir el dato ya guardado de una
organización es peor que convivir con él.

## 8. Una cuenta sin perfil ya no rompe la aplicación

**Problema (encontrado, no reportado):** en este proyecto el rol no es un campo,
se deriva de la existencia de `admin_profile` o `collaborator_profile`. Un usuario
sin ninguno de los dos autenticaba bien, recibía `role: null`, y entonces el
middleware del frontend lo mandaba de `/admin` a `/colaborador` y de vuelta,
porque `isAdmin` e `isCollaborator` eran las dos falsas. No era una cuenta inútil:
era una cuenta que dejaba la aplicación en un bucle de redirecciones.

El login ahora la rechaza con un mensaje propio —no con «credenciales
inválidas»—, porque en ese punto la persona ya acertó su contraseña: es su cuenta
y no hay nada que ocultarle. El efecto secundario aceptado es que un superusuario
de `createsuperuser` deja de poder entrar por la API; para eso está `/admin/`.

## 9. Cambiar la propia contraseña

**Problema:** el colaborador recibía una contraseña temporal al ser creado y **no
tenía ninguna forma de cambiarla**. La única salida era pedirle al administrador
que la regenerara, y eso entregaba otra temporal: la contraseña de esa persona la
conocían siempre dos personas.

`POST /user/change-password/` la cambia exigiendo la actual, e **invalida los demás
tokens** de esa cuenta para que una sesión abierta en otro lado no sobreviva al
cambio. El campo `User.must_change_password` marca que la contraseña la eligió el
servidor: se enciende al crear un colaborador y al regenerarle la contraseña, y se
apaga cuando la persona pone la suya. Fue **la primera migración funcional de la entrega**, y
hizo falta porque `last_login` nunca se escribe —el login usa `authenticate()` y
Knox, no `django.contrib.auth.login()`—, así que no distingue el primer ingreso del
décimo.

## 10. El colaborador puede abrir la ficha de un curso suyo

**Problema:** el colaborador solo tenía la lista completa de sus cursos. No existía
ningún endpoint que le devolviera **un** curso, así que una pantalla de detalle no
podía sobrevivir a una recarga ni a un enlace directo. `GET /course/{id}/` no
servía: es `IsAdmin`.

`GET /course-collaborator/my-courses/{enrollment_id}/` devuelve una inscripción
propia con su curso, en la misma forma que una fila de la lista. Se busca por id de
**inscripción** y no de curso, así «solo lo que me asignaron» es cierto **por
construcción**: no existe el momento intermedio en que un curso ajeno está
encontrado pero todavía no rechazado. Lo ajeno, oculto o de otro tenant responde
`404` y nunca `403`, porque un `403` confirmaría que existe.

El filtro que define «lo mío» se declara una sola vez y lo comparten la lista y la
ficha: si divergieran, la ficha podría abrir un curso que la lista no muestra.

## 11. Varios PDFs privados por curso

**Problema:** la ficha describía un curso, pero no entregaba su material. El admin
ahora agrega, reemplaza y quita documentos individuales que el colaborador puede
leer después. Ambos reciben los mismos metadatos y bytes, con permisos propios.

El modelo `CourseMaterial` conserva archivo, nombre, tamaño y páginas. pypdf valida
el formato real, máximo 10 MiB y sin cifrado. Las vistas filtran rol, organización
y pertenencia; se retira la ruta pública `/media/`. El reemplazo conserva el PDF
anterior si falla el guardado y evita sobrescribir otros archivos. La nueva versión
comienza sin material; los inscritos de la anterior conservan sus documentos.

---

## Cómo está construido esto

**Se reutilizó lo que ya existía, no se impuso una arquitectura nueva.** Todas las
vistas nuevas son genéricas de DRF sobre los permisos `IsAdmin` / `IsCollaborator`
que venían en el repo; los serializers viven en el mismo `views.py`, como el resto;
y el estado que se manipula —`show` de `BaseAbstractModel`, `is_active`— ya estaba
en los modelos base sin que nada lo escribiera. Nueve de estas once mejoras no
agregaron modelos, campos, migraciones ni dependencias. SPEC-009 incorpora
`User.must_change_password`; SPEC-011 incorpora `CourseMaterial`, su migración
y pypdf para validar el contenido de los documentos.

**La definición de «inscrito vigente» vive una sola vez.** El contador del panel,
la lista de inscritos y el filtro de mis cursos la comparten: si el contador dice
3, la lista trae 3. Desinscribir a alguien o darlo de baja hace bajar el número sin
tocar ninguna de las tres consultas.

**Todo es borrado lógico.** No por seguir una convención, sino porque todas las FK
del proyecto son `on_delete=CASCADE`: un borrado físico de un curso se llevaría en
silencio sus inscripciones, que es exactamente el registro que el panel y el
versionado existen para conservar.

**Cada mejora se especificó antes de escribirse** (`docs/specs/SPEC-00X-*.md`,
nueve artículos con vocabulario RFC 2119) y se implementó con tests primero. La
suite completa está en **213 tests**.
