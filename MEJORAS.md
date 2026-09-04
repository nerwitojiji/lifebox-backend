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

---

## Cómo está construido esto

**Se reutilizó lo que ya existía, no se impuso una arquitectura nueva.** Todas las
vistas nuevas son genéricas de DRF sobre los permisos `IsAdmin` / `IsCollaborator`
que venían en el repo; los serializers viven en el mismo `views.py`, como el resto;
y el estado que se manipula —`show` de `BaseAbstractModel`, `is_active`— ya estaba
en los modelos base sin que nada lo escribiera. **Estas ocho mejoras no agregaron
un solo modelo, campo, migración ni dependencia.**

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
suite completa está en **151 tests**.
