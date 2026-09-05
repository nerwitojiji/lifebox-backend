# SPEC-010 — Ficha de curso

- **Capacidad:** Contexto del curso para el colaborador
- **Feature:** Ficha de curso · rama `feature/ficha-de-curso`
- **Estado:** Propuesta
- **Repos:** `lifebox-backend` (endpoint) · `lifebox-frontend` (ficha, tarjetas, imagen)
- **Responde a:** enunciado §6.1 — *«No sé bien de qué trata el curso antes de entrar.»*

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

---

## Artículo 1 — Contexto y encuadre

El enunciado, en la sección de feedback de usuarios, dice:

> *«No sé bien de qué trata el curso antes de entrar.»* Los colaboradores sienten
> que un curso es solo un nombre en una lista, sin contexto. Dales más información
> antes de que decidan entrar (puedes apoyarte en una API pública de imágenes, como
> Lorem Picsum, para darle algo visual).

**La queja no es sobre imágenes.** El pedido es *más información antes de entrar*;
la imagen viene entre paréntesis, como sugerencia opcional y explícitamente
decorativa («algo visual»). Confundir las dos cosas convertiría esta feature en lo
que el propio enunciado descarta en §5.4: *«no sólo detalles visuales»*.

Hay además una frase que define la forma de la solución: **«antes de que decidan
entrar»**. Presupone que hay un *entrar* — un lugar al que el curso lleva. Hoy no
existe. Y §6.2 lo confirma desde el otro lado al pedir *«el material del curso, no
solo la ficha»*: nombra la ficha como algo que debería existir.

### Qué hay hoy

SPEC-006 dejó «Mis cursos» como una grilla de tarjetas que ya muestra nombre,
versión, duración, descripción y fecha de asignación. Es más que «un nombre en una
lista», así que parte de la queja está atendida. Lo que falta es:

1. **No hay dónde entrar.** La tarjeta es terminal: muestra lo que muestra y no
   lleva a ninguna parte. Un curso no tiene una página propia, ni una URL propia.
2. **La descripción compite por espacio.** En una tarjeta, una descripción larga
   desbalancea la grilla; se la recorta o se la deja crecer, y las dos opciones son
   malas. Una ficha resuelve eso: la tarjeta muestra el resumen, la ficha el texto
   entero.
3. **Nada distingue un curso de otro a primera vista.** Cuatro tarjetas de texto
   gris se leen como una tabla. Acá es donde la imagen aporta: no informa, pero
   **hace que la lista se recorra con los ojos** en vez de leerse renglón por
   renglón.
4. **El backend no tiene por dónde.** `GET /course/{id}/` existe desde SPEC-007
   pero es `IsAdmin`. El colaborador **no tiene ningún endpoint que le devuelva un
   curso**: solo la lista completa. Una ficha construida con los datos que la lista
   ya trajo se rompe al recargar la página o al abrir el enlace directo.

### La imagen, con nombre y apellido

La imagen que da Lorem Picsum es **decorativa y arbitraria**: una foto de paisaje
sobre «Prevención de riesgos» no dice nada del curso. Esta spec la adopta sabiendo
eso y lo hace explícito en el código, en el `alt` y en `SUPUESTOS.md`. Su función es
dar identidad visual a cada tarjeta, no informar. La información la da la ficha.

## Artículo 2 — Objetivo

Que un colaborador pueda **abrir un curso asignado y ver todo lo que se sabe de él
en una página propia**, con una URL que sobreviva a una recarga, y que la lista de
cursos se distinga de un vistazo en vez de leerse como una tabla.

## Artículo 3 — Alcance

**Dentro de alcance:**

- `GET /course-collaborator/my-courses/{enrollment_id}/` — el detalle de una
  inscripción propia, con el curso adentro.
- La ficha en el frontend: `/colaborador/my-courses/{enrollment_id}`.
- La imagen determinista derivada del curso, con fallback local obligatorio.
- Las tarjetas de «Mis cursos», que pasan a llevar imagen y a enlazar a la ficha.
- La miniatura en el catálogo del admin, con la misma semilla.

**Fuera de alcance:**

- **Subir una imagen propia del curso.** No se agrega ningún campo al modelo. Ver
  PA-1.
- El material del curso — PDF, video, audio. Es SPEC-011, y la ficha le deja el
  lugar sin anunciarlo.
- Una ficha para el administrador. Ver PA-9.
- Progreso, completado, certificados o cualquier noción de avance.
- Que el colaborador vea a sus compañeros inscritos. Ver PA-8.

## Artículo 4 — Actores y precondiciones

- **Actor:** colaborador autenticado con `collaborator_profile` y organización.
- **Precondiciones:** la inscripción existe, es visible, es suya, y su curso es
  visible y del mismo tenant — exactamente las condiciones que ya aplica
  `MyCoursesView` (SPEC-006 RN-2, RN-5, RN-6).
- El administrador **no** es actor de esta spec, salvo por RN-F9.

## Artículo 5 — Reglas de negocio

### Backend

- **RN-1.** DEBE existir `GET /course-collaborator/my-courses/{enrollment_id}/`,
  que responde `200` con **la misma forma que un elemento de la lista** de SPEC-006:
  la inscripción, con su curso anidado. Un cliente que ya sabe leer la lista sabe
  leer la ficha.
- **RN-2.** DEBE exigir `IsCollaborator`. El colaborador DEBE salir del token y de
  ningún otro lado: no se lee identidad de la ruta, del body ni de query params.
- **RN-3.** El queryset DEBE aplicar **exactamente los mismos filtros** que la
  lista: inscripción visible, curso visible y organización del colaborador. Una
  inscripción de otra persona, oculta, o de otro tenant DEBE responder **`404`**.
- **RN-4.** El criterio de RN-3 DEBE declararse **una sola vez** y compartirse entre
  la lista y el detalle. Si divergieran, la ficha podría abrir un curso que la lista
  no muestra —o al revés— y el colaborador vería dos verdades distintas sobre lo
  mismo.
- **RN-5.** `course__is_active` NO DEBE filtrarse, igual que en la lista (SPEC-006
  RN-5): un curso retirado no desinscribe a nadie, y su ficha DEBE poder abrirse
  para leer el aviso.
- **RN-6.** La respuesta NO DEBE incluir `enrolled_count` ni ningún dato de otros
  inscritos. SPEC-006 RN-8 sigue vigente sin excepción.
- **RN-7.** NO se DEBE agregar ningún campo al modelo `Course`, ninguna migración
  ni ninguna dependencia nueva. La imagen **no es un dato del servidor** (PA-1).
- **RN-8.** El endpoint NO DEBE aceptar ningún verbo de escritura. El colaborador
  lee; la escritura es del admin (decisión cerrada del `CLAUDE.md`).

### Interfaz

- **RN-F1.** La imagen de un curso DEBE derivarse de forma **determinista** del
  propio curso, con la forma
  `https://picsum.photos/seed/<semilla>/<ancho>/<alto>`. La misma semilla DEBE
  producir la misma foto en la tarjeta y en la ficha.
- **RN-F2.** La semilla DEBE derivarse de `full_name`: minúsculas, sin acentos, todo
  lo que no sea alfanumérico colapsado a `-`. Si el resultado quedara vacío, DEBE
  caer a `curso-<id>`. Ver PA-2 para por qué el nombre y no el id.
- **RN-F3.** DEBE existir un **fallback local** cuando la imagen no carga —sin red,
  Picsum caído, dominio bloqueado—: un bloque con la inicial del curso sobre el
  color del tema. NO DEBE quedar un ícono roto, un hueco ni un salto de layout.
- **RN-F4.** La imagen DEBE marcarse como decorativa (`alt=""` y oculta al lector
  de pantalla). Describirla sería mentir: no representa el contenido del curso.
- **RN-F5.** Cada tarjeta de «Mis cursos» DEBE llevar a la ficha de esa inscripción,
  y la ficha DEBE ser alcanzable **por URL directa**, sobreviviendo a una recarga.
- **RN-F6.** La ficha DEBE mostrar: imagen, nombre, versión, duración, **descripción
  completa**, fecha de asignación y —si el curso está retirado— el mismo aviso que
  ya muestra la tarjeta.
- **RN-F7.** En la tarjeta, la descripción DEBE recortarse a un máximo fijo de
  líneas para que la grilla no se desbalancee. El texto entero vive en la ficha.
- **RN-F8.** Una ficha inexistente o ajena (`404`) DEBE mostrar un estado explicado
  y un camino de vuelta a «Mis cursos». NO DEBE mostrarse un error crudo.
- **RN-F9.** El catálogo del admin DEBE mostrar la misma imagen en miniatura, con la
  misma semilla: si el admin no ve nunca lo que ve el colaborador, no puede saber
  cómo se ve el curso que creó.
- **RN-F10.** La ficha DEBE usar el layout `colaborador.vue` existente, sin
  reemplazarlo (requisito del enunciado §2).

## Artículo 6 — Criterios de aceptación

### Backend

- **CA-1:** un colaborador pide una inscripción **suya** y recibe `200` con la misma
  forma que trae la lista.
- **CA-2:** pide la inscripción de **otro colaborador de su misma organización** y
  recibe `404`.
- **CA-3:** pide una inscripción de **otro tenant** y recibe `404`.
- **CA-4:** pide una inscripción **desinscrita** (`show=False`) y recibe `404`.
- **CA-5:** pide una inscripción cuyo **curso fue eliminado** (`course.show=False`)
  y recibe `404`.
- **CA-6:** pide una inscripción cuyo curso está **retirado** (`is_active=False`) y
  recibe `200` — el aviso lo da la interfaz, no un error.
- **CA-7:** un **administrador** pide la ruta y recibe `403`.
- **CA-8:** sin token, `401`.
- **CA-9:** la respuesta **no contiene** `enrolled_count` ni ningún dato de otros
  inscritos.
- **CA-10:** un id inexistente responde `404`.
- **CA-11:** `POST`, `PATCH` y `DELETE` sobre la ruta responden `405`.
- **CA-12:** el curso que devuelve la ficha es **idéntico** al que devuelve la lista
  para esa misma inscripción — el mismo criterio, verificado desde los dos lados.

### Interfaz

- **CA-F1:** al hacer clic en una tarjeta de «Mis cursos» se abre la ficha de ese
  curso.
- **CA-F2:** recargar la ficha (F5) la vuelve a mostrar completa, sin pasar por la
  lista.
- **CA-F3:** la imagen de un curso es la misma en la tarjeta y en la ficha, y sigue
  siendo la misma después de recargar.
- **CA-F4:** con la red cortada, la tarjeta y la ficha muestran el bloque de
  respaldo con la inicial, sin íconos rotos ni saltos de layout.
- **CA-F5:** abrir a mano la ficha de una inscripción ajena muestra el estado
  explicado y el enlace de vuelta.
- **CA-F6:** un curso retirado abre su ficha y muestra el aviso.

## Artículo 7 — Contrato de interfaz

### `GET /course-collaborator/my-courses/{enrollment_id}/`

**Respuesta `200`** — idéntica en forma a un elemento de
`GET /course-collaborator/my-courses/`:

```json
{
  "id": 12,
  "assigned_at": "2026-09-05T14:03:11.482Z",
  "course": {
    "id": 4,
    "full_name": "Prevención de riesgos laborales",
    "description": "Fundamentos de identificación de peligros...",
    "duration_hours": 6,
    "version": "1.0",
    "is_active": true
  }
}
```

**`404`** — inscripción inexistente, ajena, oculta o de curso no visible. La
respuesta es la misma en los cuatro casos: una inscripción que no es suya es
indistinguible de una que no existe.

**`403`** — el usuario es administrador. **`401`** — sin token.

### Imagen (solo frontend, sin backend)

```
https://picsum.photos/seed/prevencion-de-riesgos-laborales/800/450   ← tarjeta
https://picsum.photos/seed/prevencion-de-riesgos-laborales/1200/400  ← ficha
```

## Artículo 8 — Preguntas abiertas resueltas

- **PA-1: no se agrega un campo de imagen al modelo.** La alternativa era un
  `image_url` que el admin completa. Se descarta: dejar que alguien pegue la URL de
  una foto aleatoria no agrega información —sigue siendo decoración, ahora con un
  paso manual— y la imagen *real* de un curso es un archivo subido, que es
  exactamente lo que trae SPEC-011. Agregar el campo ahora significaría una
  migración y un formulario que SPEC-011 tendría que reemplazar. Si más adelante el
  curso gana una portada de verdad, la regla RN-F1 se convierte en el **fallback**
  de ese campo, sin tirar nada.
- **PA-2: la semilla sale del nombre, no del id.** Publicar una versión nueva
  (SPEC-007) crea un curso nuevo con id nuevo. Con semilla por id, «Prevención de
  riesgos 2.0» se vería como un curso completamente distinto de la 1.0; con semilla
  por nombre, las dos versiones comparten identidad visual, que es lo que una
  persona espera. El costo es que **renombrar un curso le cambia la imagen** — y eso
  también es razonable: si cambió de nombre, cambió de curso.
- **PA-3: la ruta usa el id de la inscripción, no el del curso.** Es lo que ya
  devuelve la lista como `id`, y hace que «solo lo que me asignaron» sea cierto **por
  construcción**: no hay curso que buscar y después autorizar, se busca directamente
  entre las inscripciones propias. Además el id de inscripción es estable — SPEC-007
  RN-18 reactiva la fila existente en vez de crear otra —, así que el enlace no se
  rompe si alguien desinscribe y vuelve a inscribir.
- **PA-4: `404` y no `403` para una inscripción ajena.** Un `403` confirmaría que la
  inscripción existe. Es el mismo criterio que ya usan todas las vistas del
  proyecto: fuera del tenant o fuera de lo propio, el recurso simplemente no existe.
- **PA-5: la imagen es decorativa y se declara como tal.** `alt=""` y oculta al
  lector de pantalla. Poner `alt="Imagen del curso Prevención de riesgos"` sería
  falso: la foto no tiene relación con el curso. Es preferible que una tecnología de
  asistencia la ignore a que anuncie algo que no es.
- **PA-6: no se hace proxy ni caché de la imagen en el servidor.** Bajar y guardar
  la foto exigiría `MEDIA_ROOT`, un trabajo en segundo plano y una política de
  expiración, todo para una imagen que el propio enunciado propone como decorativa.
  El navegador ya la cachea.
- **PA-7: la dependencia externa se asume, con red de contención.** Si Picsum no
  responde, RN-F3 garantiza que la pantalla se ve completa igual. El riesgo real —una
  demo sin internet— queda cubierto, y anotado en `SUPUESTOS.md`.
- **PA-8: la ficha no muestra a los compañeros inscritos.** SPEC-006 RN-8 lo decidió
  y no hay razón para reabrirlo: cuánta gente más tiene el curso no es información
  del colaborador, y el panel de inscritos es una herramienta de gestión del admin.
- **PA-9: no se agrega una ficha para el administrador.** El admin ya tiene el
  catálogo, el panel y la lista de inscritos por curso: tres vistas que juntas dicen
  más que una ficha. Lo único que le faltaba era ver la imagen que ve el colaborador,
  y eso lo resuelve RN-F9 con una miniatura. Una ficha de admin sería una cuarta
  pantalla sin pregunta propia que responder.
- **PA-10: la ficha no reserva un espacio visible para el material.** SPEC-011 lo
  agregará. Dejar ahora un «Material: próximamente» repetiría el error que el propio
  proyecto ya corrigió al sacar los stubs de «Próximamente» de la interfaz.

## Artículo 9 — Decisiones, dependencias y referencias

**Backend.** El cambio vive en `apps/course_collaborator/`. El filtro que hoy está
escrito dentro de `MyCoursesView.get_queryset()` se factoriza a una función de
módulo —el mismo movimiento que SPEC-005 hizo con `vigente(prefix)`— y la vista
nueva es un `RetrieveAPIView` que la reusa junto al `MyEnrollmentSerializer`
existente. La ruta se agrega a `apps/course_collaborator/urls.py`, después de la
ruta fija de la lista.

**No se agregan modelos, campos, migraciones ni dependencias.** El backend no sabe
nada de la imagen.

**Frontend.** Un componente nuevo, `components/ImagenCurso.vue`, encapsula la
semilla, las medidas y el fallback de RN-F3, y lo usan los tres lugares que muestran
un curso (tarjeta, ficha, catálogo del admin). La ficha es
`pages/colaborador/my-courses/[id].vue`, con el layout `colaborador` existente.
`endpoints/apiEndpoints.ts` suma `myCourse(id)`, y `models/course.ts` no cambia: la
ficha devuelve el mismo `MyEnrollment` que la lista.

**Referencias:** enunciado §6.1 y §5.4 · SPEC-006 (RN-2, RN-5, RN-6, RN-8) ·
SPEC-007 RN-18 · decisión cerrada «el colaborador NO se autoinscribe».

---

## Anexo A — Tests y verificaciones

Los tests se agregan a `apps/course_collaborator/tests/test_my_courses.py`, junto a
los de la lista, porque comparten el criterio que RN-4 obliga a mantener unido.

Tres cargan el peso de la spec:

- **CA-2** —la inscripción de un compañero **de la misma organización** responde
  `404`—, que es el aislamiento que un filtro por tenant solo no da.
- **CA-6** —el curso retirado abre su ficha—, que fija que la asimetría de SPEC-006
  RN-5 se conserva y no se «arregla» filtrando por `is_active`.
- **CA-12** —el curso de la ficha es idéntico al de la lista—, que es la prueba
  ejecutable de RN-4: si alguien cambia un filtro en un solo lado, este test cae.

Se verifica que la suite completa siga verde (**173 tests** antes de esta feature) y
que `makemigrations --check` no detecte cambios. En el frontend, `npm run build`.

---

# Enmienda 1 — La imagen pasa a depender del tema del curso

- **Estado:** Aprobada e implementada
- **Rama:** `feature/ficha-de-curso` (la misma; SPEC-010 no había llegado a `main`)
- **Reemplaza:** RN-F1, RN-F2 y PA-5 · **Agrega:** RN-F11 · **Acota:** PA-7
- **Repos:** solo `lifebox-frontend`. El backend no cambia.

## Artículo 1 — Por qué

SPEC-010 adoptó Lorem Picsum **sabiendo** que la imagen era arbitraria, y lo dejó
escrito en PA-5. Puesta en pantalla, la decisión falló por una razón que el spec no
anticipó.

«Inducción de seguridad» quedó ilustrado con **un faro sobre el mar**. «Curso de
grappling», con **un chico sentado en una ruina**. El problema no es que la imagen
no informe: es que **contradice** al curso. Una foto adentro de la tarjeta de un
curso se lee como si dijera algo de ese curso — nadie sabe, ni tiene por qué saber,
que es un placeholder. Y una foto que contradice no se lee como decoración: se lee
como un error del sistema.

La premisa de PA-5 era que una imagen decorativa es inofensiva mientras no pretenda
informar. La pantalla mostró que **sí pretende**, por dónde está puesta.

Hay un segundo problema, del mismo momento: la grilla era `md=6` fija, dos tarjetas
por fila desde 960px, siempre. En un monitor ancho eso daba imágenes de ~900px, y la
tarjeta **no reaccionaba a cuántos cursos hay**.

## Artículo 2 — Objetivo

Que la imagen de un curso tenga algo que ver con su tema, y que la grilla se
densifique cuando hay ancho para hacerlo.

## Artículo 3 — Alcance

**Dentro:** el origen de la imagen y la derivación de la etiqueta desde el nombre
del curso; los breakpoints de la grilla de «Mis cursos».

**Fuera:** subir una imagen propia (sigue siendo SPEC-011); que el administrador
elija la portada; la ficha, el endpoint y cualquier cosa del backend.

## Artículo 5 — Reglas de negocio

- **RN-F1 (reemplaza).** La imagen DEBE pedirse a
  `https://loremflickr.com/<ancho>/<alto>/<etiqueta>?lock=<n>`.
- **RN-F2 (reemplaza).** DEBE viajar **una sola etiqueta**: la última palabra
  significativa del nombre, sin acentos y en minúsculas, descartando las palabras
  vacías del castellano, las genéricas de catálogo, los números y las de dos
  caracteres o menos.
  «Inducción de seguridad» → `seguridad`; «Curso de grappling» → `grappling`;
  «Prevención de riesgos laborales» → `laborales`; «Ergonomía en oficina` →
  `oficina`.
- **RN-F2b.** Si el filtrado no deja ninguna palabra, DEBE usarse la última palabra
  con letras del nombre. Si el nombre no deja ninguna, **NO DEBE pedirse imagen**:
  va directo el respaldo local.
- **RN-F2c.** El `lock` DEBE derivarse determinísticamente del nombre y **DEBE
  acotarse al rango 0-9**. Ver PA-E8.
- **RN-F2d.** Tarjeta, ficha y miniatura del admin DEBEN compartir etiqueta y
  `lock`; lo único que puede diferir es el tamaño pedido.
- **RN-F3 (se conserva, y pesa más).** El respaldo local ahora cubre también el
  caso de que no exista ninguna foto para esa etiqueta, no solo la falta de red.
- **RN-F4 (se conserva).** La imagen sigue con `alt=""` y `aria-hidden`. Ver PA-E4.
- **RN-F11 (nueva).** La grilla de «Mis cursos» DEBE ser
  `cols="12" sm="6" lg="4" xl="3"`.

## Artículo 6 — Criterios de aceptación

- **CA-E1:** «Inducción de seguridad» pide la imagen con `seguridad`.
- **CA-E2:** «Curso de grappling» pide `grappling` — ni «curso» ni «de» viajan.
- **CA-E3:** la misma tarjeta pide **la misma URL** en dos cargas seguidas.
- **CA-E4:** tarjeta y ficha del mismo curso comparten etiqueta y `lock`, y solo se
  diferencian en el tamaño.
- **CA-E5:** un curso llamado «1234» no dispara ningún pedido de red y muestra el
  respaldo local.
- **CA-E6:** en `xl` entran cuatro tarjetas por fila; en `sm`, dos; en `xs`, una.
- **CA-E7:** sin red, tarjeta y ficha siguen mostrando el respaldo local sin íconos
  rotos ni saltos de layout (CA-F4 sigue valiendo tal cual).

## Artículo 8 — Preguntas abiertas resueltas

- **PA-E1: se usa LoremFlickr y no Unsplash.** `source.unsplash.com`, que era la
  opción sin credenciales, fue dada de baja; la API oficial exige una clave que quien
  evalúe no tiene y que no corresponde versionar. LoremFlickr sirve por etiqueta, sin
  clave, y `?lock=` lo hace determinista.
- **PA-E2 (corregida al implementar): va UNA etiqueta, no todas.** El spec aprobado
  decía mandarlas todas separadas por coma, asumiendo que LoremFlickr buscaría por
  cualquiera de ellas. **Medido: la coma es AND.** `seguridad` devuelve fotos, pero
  `induccion,seguridad` no devuelve ninguna — exige que la foto tenga las dos
  etiquetas a la vez, y casi ninguna las tiene. Se corrigió antes de cerrar la
  feature.
- **PA-E3: se elige la última palabra significativa, no la primera.** En castellano
  el tema suele cerrar la frase: «Inducción de SEGURIDAD», «Curso de GRAPPLING»,
  «Ergonomía en OFICINA». La primera daría `induccion`, que es la forma del curso y
  no su tema. Y «curso» se elimina siempre: está en el nombre de casi todos y haría
  que todos tiraran hacia la misma clase de foto.
- **PA-E4: la imagen sigue siendo decorativa, con `alt=""`.** Que la foto se
  relacione con el tema no la convierte en información: **nadie la eligió para este
  curso**, y puede seguir siendo desatinada.
- **PA-E5: el contenido no está garantizado, y se asume como límite conocido.** Las
  fotos salen de Flickr por etiqueta, no de un catálogo curado: esta enmienda mejora
  la probabilidad de acertar, no la certeza. Para un producto real la respuesta
  correcta es la portada elegida por el administrador o subida como archivo
  (SPEC-011). Se acepta acá porque el enunciado propone explícitamente apoyarse en
  una API pública de imágenes, y porque el respaldo local cubre el caso de que no
  haya foto.
- **PA-E6: la tarjeta se achica con el ancho de la ventana, no con la cantidad de
  cursos.** Dimensionar según cuántos hay haría que la misma pantalla se viera
  distinta según a quién le asignaron más cursos, y que agregar una inscripción
  encogiera las demás.
- **PA-E7: no se encadena Picsum como segundo intento.** Si LoremFlickr no responde,
  el respaldo local ya deja la pantalla completa; encadenar dos servicios externos
  duplicaría la superficie de falla para ganar una foto que, otra vez, no tendría que
  ver con el curso.
- **PA-E8 (nueva): el `lock` se acota a 0-9, y aun así queda un hueco medido.** El
  `lock` no es una semilla: es un **índice sobre el resultado de la búsqueda**. Con
  un número alto y una etiqueta de pocas fotos, LoremFlickr se queda sin resultado y
  sirve **su propia imagen por defecto** — y lo hace con **HTTP 200**, así que el
  `@error` que dispara el respaldo local **no se entera**. Medido sobre las etiquetas
  reales del proyecto: con el hash completo, `auxilios` caía siempre; en el rango 0-9
  acierta 48 de 50. El hueco que queda es doble y se asume: hay pares
  (etiqueta, lock) sin resultado, y en frío la primera petición puede devolver el
  placeholder y la segunda la foto. **No se puede detectar desde el cliente**: la
  respuesta es una imagen válida servida desde otro origen. La solución real es la
  portada elegida por el administrador; queda anotada como el próximo paso si la
  calidad visual pesa más que la ausencia de un campo en el modelo.

## Artículo 9 — Decisiones, dependencias y referencias

Toca **dos archivos del frontend**: `components/ImagenCurso.vue` (la construcción de
la URL, la derivación de la etiqueta y el rango del `lock`) y
`pages/colaborador/my-courses/index.vue` (los breakpoints de RN-F11). La lista de
palabras vacías se declara **una sola vez**, en el componente.

**El backend no cambia.** Sigue sin saber nada de la imagen, así que los 185 tests
siguen valiendo tal cual y no hay migraciones. La verificación del frontend sigue
siendo `npm run build`.
