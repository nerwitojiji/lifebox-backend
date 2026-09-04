# SPEC-008 — Corregir la versión de un curso

- **Capacidad:** Ciclo de vida del catálogo
- **Feature:** Corregir versión · rama `feature/corregir-version`
- **Estado:** Aprobada
- **Repos:** `lifebox-backend` (endpoint) · `lifebox-frontend` (interfaz)
- **Supersede:** SPEC-007 RN-4 y PA-11

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

---

## Artículo 1 — Contexto y encuadre

SPEC-007 resolvió que la versión de un curso **no se edita**: cambia publicando
una versión nueva, que crea un curso nuevo y retira el anterior (RN-4, PA-11). El
razonamiento era correcto y sigue siéndolo: la versión es parte de la identidad de
lo que alguien cursó, y editarla en su lugar haría que los inscritos de la 1.0
pasaran a figurar como inscritos de la 2.0.

Pero el enunciado nombra un caso que esa regla no cubre:

> *«Puse mal la versión del curso: decía 1.0 y en realidad es 2.0.»*

Eso **no es versionar, es corregir un tipeo**. El curso siempre fue la 2.0; el
administrador escribió mal al crearlo. Con la regla actual, la única salida es
publicar una versión nueva — y esa persona termina con **dos cursos donde quería
uno corregido**, más el original dado de baja. La corrección de un error de tipeo
produce basura en el catálogo.

La distinción que faltaba no es entre «editar» y «versionar»: es **si alguien ya
se inscribió**.

- **Sin inscritos**, la versión es un dato del formulario como cualquier otro.
  Nadie la cursó, nada la referencia, corregirla no le miente a nadie.
- **Con inscritos**, la versión es parte de lo que esas personas recibieron.
  Cambiarla reescribiría su historial, y ahí el único camino honesto sigue siendo
  publicar una versión nueva.

Esta spec agrega esa condición. No reabre la puerta que SPEC-007 cerró: la
entreabre exactamente donde no hay nada que romper.

### Qué queda superseded

**SPEC-007 RN-4** («`version` NO DEBE editarse por `PATCH`») y **PA-11** («un solo
camino por operación») quedan **acotados, no anulados**. El principio de un solo
camino se conserva donde importaba: mientras haya inscritos, publicar una versión
nueva sigue siendo el único camino. RN-1 de esta spec define la excepción.

## Artículo 2 — Objetivo

Que un administrador pueda corregir la versión que escribió mal, mientras nadie se
haya inscrito todavía, sin ensuciar el catálogo con un curso duplicado.

## Artículo 3 — Alcance

**Dentro de alcance:** `version` como campo editable de `PATCH /course/{id}/` bajo
la condición de RN-1; el campo de versión en el diálogo de edición del frontend,
con la explicación de cuándo se puede y cuándo no.

**Fuera de alcance:** cambiar el comportamiento de `POST /course/{id}/new-version/`,
que no se toca; migrar inscritos entre versiones; un historial de versiones
anteriores de un mismo curso; y corregir la versión de un curso que ya tuvo
inscritos y fue vaciado a propósito para saltarse la regla (ver PA-3).

## Artículo 4 — Actores y precondiciones

- **Actor:** administrador autenticado con `admin_profile` y organización.
- **Precondiciones:** el curso pertenece a su tenant y es visible (SPEC-007 RN-2).
- Todo lo demás de `PATCH /course/{id}/` —permisos, tenant, `404`— sigue igual.

## Artículo 5 — Reglas de negocio

- **RN-1.** `PATCH /course/{id}/` DEBE aceptar `version` **solo si el curso no
  tiene ningún inscrito vigente** (`enrolled_count == 0`, con el criterio único de
  SPEC-004 RN-5). Con al menos un inscrito, enviar una `version` **distinta de la
  actual** DEBE responder `400` bajo `version`, explicando que se publique una
  versión nueva.
- **RN-2.** Enviar la **misma** `version` que el curso ya tiene NO DEBE dar error,
  aunque haya inscritos: no es un cambio, y un cliente que reenvía el objeto
  completo no tiene por qué fallar. La comparación DEBE hacerse sobre el texto ya
  recortado.
- **RN-3.** La `version` recibida DEBE pasar la misma validación que en
  `POST /course/{id}/new-version/` (SPEC-007 RN-8): máximo 20 caracteres y al menos
  un carácter alfanumérico tras recortar espacios. Esa validación DEBE seguir
  declarada una sola vez.
- **RN-4.** La `version` corregida NO DEBE coincidir con la de otro curso visible
  del mismo tenant que comparta `full_name`, por la misma razón que RN-10 de
  SPEC-007: «cursó la 2.0» tiene que identificar un contenido. En caso contrario,
  `400` bajo `version`.
- **RN-5.** Corregir la versión NO DEBE tocar ningún otro campo, ni el estado del
  curso, ni crear cursos nuevos. Es una edición, no una publicación.
- **RN-6.** El mensaje del `400` de RN-1 DEBE decir **por qué** no se puede —el
  curso ya tiene inscritos— y **qué hacer** —publicar una versión nueva—, no
  limitarse a «no permitido».

### Interfaz

- **RN-F1.** El diálogo de edición DEBE volver a mostrar el campo **Versión**, que
  SPEC-007 había quitado.
- **RN-F2.** El campo DEBE estar habilitado solo cuando el curso no tiene
  inscritos. Con inscritos DEBE mostrarse **deshabilitado y con la explicación**,
  no oculto: esconderlo dejaría al administrador sin saber por qué a veces puede y
  a veces no.
- **RN-F3.** El texto de ayuda DEBE nombrar la cantidad de inscritos y remitir a
  «Nueva versión», que es la acción que sí resuelve el caso.

## Artículo 6 — Criterios de aceptación

- **CA-1:** `PATCH` con una `version` nueva sobre un curso **sin inscritos**
  responde `200` y persiste el cambio.
- **CA-2:** `PATCH` con una `version` distinta sobre un curso **con un inscrito
  vigente** responde `400` bajo `version` y no cambia nada.
- **CA-3:** `PATCH` con la **misma** `version` sobre un curso con inscritos
  responde `200` y no da error.
- **CA-4:** `PATCH` con `version` vacía, `"."` o `"--"` responde `400` bajo
  `version`, tenga o no inscritos.
- **CA-5:** `PATCH` con una `version` que ya usa otro curso visible del mismo
  nombre responde `400` bajo `version`.
- **CA-6:** un curso cuyo único inscrito fue **desinscrito** vuelve a admitir la
  corrección de versión.
- **CA-7:** un curso cuyo único inscrito fue **dado de baja** también la admite:
  el criterio es el mismo «inscrito vigente» que usa el contador.
- **CA-8:** corregir la versión no altera `full_name`, `description`,
  `duration_hours` ni `is_active`, y no crea ningún curso nuevo.
- **CA-9:** `POST /course/{id}/new-version/` sigue comportándose exactamente igual
  que en SPEC-007, incluso sobre un curso sin inscritos.
- **CA-10:** el mensaje del `400` de CA-2 menciona los inscritos y la publicación
  de una versión nueva.
- **CA-F1:** el diálogo de edición muestra el campo de versión habilitado en un
  curso sin inscritos, y deshabilitado con explicación en uno que los tiene.

## Artículo 7 — Contrato de interfaz

### `PATCH /course/{id}/` — campo nuevo

```json
{ "version": "2.0" }
```

**Respuesta `200`:** el curso, con la misma forma que en SPEC-007.

**Error `400`** cuando el curso tiene inscritos:

```json
{
  "version": [
    "Este curso ya tiene 3 inscritos, así que su versión no se puede corregir. Publica una versión nueva."
  ]
}
```

El resto de los `400` —versión inválida, versión ya usada— conserva la forma de
SPEC-007.

## Artículo 8 — Preguntas abiertas resueltas

- **PA-1:** la condición es **«sin inscritos vigentes»** y no «recién creado» ni
  «dentro de los primeros N minutos». Una ventana de tiempo es arbitraria y falla
  justo cuando el error se descubre tarde; «nadie se inscribió todavía» es la
  condición real que hace inofensivo el cambio, y ya está calculada.
- **PA-2:** se reutiliza el criterio de «inscrito vigente» de SPEC-004 en vez de
  contar filas de `CourseCollaborator`. Así, un curso cuyos inscritos fueron
  desinscritos o dados de baja vuelve a admitir la corrección — que es lo correcto:
  si el contador dice 0, no hay historial que proteger.
- **PA-3:** no se impide vaciar un curso a propósito —desinscribir a todos— para
  poder corregir la versión. Sería una defensa contra un administrador que ya tiene
  permiso para hacer las dos cosas por separado, y exigiría un rastro de auditoría
  que esta entrega no lleva. Queda anotado como límite conocido.
- **PA-4:** enviar la misma versión no es un error (RN-2). Un cliente que hace
  `PATCH` con el objeto completo es un uso legítimo, y fallar ahí convertiría una
  regla de negocio en una trampa de integración.
- **PA-5:** el campo se muestra **deshabilitado** en vez de oculto cuando hay
  inscritos. Ocultarlo haría que el diálogo cambiara de forma según el curso, sin
  decir por qué; deshabilitado con explicación enseña la regla en el momento en que
  aplica.
- **PA-6:** `POST /course/{id}/new-version/` **no** se restringe a cursos con
  inscritos. Publicar la 2.0 de un curso que nadie tomó es legítimo —el contenido
  cambió— y ahora hay dos caminos válidos ahí: corregir el número o publicar una
  versión. La diferencia la sabe el administrador, no el sistema.

## Artículo 9 — Decisiones, dependencias y referencias

El cambio vive en `CourseDetailSerializer` (`apps/course/views.py`): `version` sale
de `read_only_fields` y pasa a declararse con el validador `validar_version()` que
SPEC-007 ya dejó a nivel de módulo, más un `validate_version()` que consulta el
`enrolled_count` ya anotado en el queryset de la vista. No hace falta una consulta
nueva: la anotación existe desde SPEC-004.

**No se agregan modelos, campos, migraciones ni dependencias.** El endpoint de
publicar versión no se toca.

En el frontend, `pages/admin/courses/index.vue` recupera el campo de versión en su
diálogo de edición y lo condiciona a `course.enrolled_count`, que ya viaja en
`GET /course/`.

---

## Anexo A — Tests y verificaciones

Los tests se agregan a `apps/course/tests/test_edit_course.py`, junto al resto del
`PATCH`. Dos cargan el peso de la spec: **CA-2**, que fija que con inscritos la
versión no se toca —es la regla de SPEC-007 que se conserva—, y **CA-6**, que fija
que desinscribir devuelve la posibilidad de corregir, que es lo que prueba que la
condición es «hay historial que proteger» y no «el curso es nuevo».

Se verifica que la suite completa siga verde (151 tests antes de esta feature) y
que `makemigrations --check` no detecte cambios.
