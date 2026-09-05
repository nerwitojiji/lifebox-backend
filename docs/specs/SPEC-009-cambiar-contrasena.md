# SPEC-009 — Cambiar la contraseña

- **Capacidad:** Ciclo de vida de la cuenta
- **Feature:** Cambiar contraseña · rama `feature/cambiar-contrasena`
- **Estado:** Aprobada
- **Repos:** `lifebox-backend` (endpoint) · `lifebox-frontend` (interfaz)
- **Supersede:** nada. Completa SPEC-002.

> Vocabulario normativo (RFC 2119): **DEBE / NO DEBE / DEBERÍA / PODRÍA**.

---

## Artículo 1 — Contexto y encuadre

SPEC-002 resolvió la contraseña inicial: el servidor la genera, se muestra al
administrador una sola vez y no queda recuperable. Si se pierde, el admin la
**regenera** (`POST /collaborator/{id}/reset-password/`) y entrega otra temporal.

Ese diseño dejó un extremo suelto: **el colaborador no tiene ninguna forma de
cambiar su contraseña**. No es que no se le pida en el primer ingreso — es que la
operación no existe en el sistema. Su única salida es pedirle al admin que la
regenere, y lo que recibe es *otra contraseña temporal*. Nunca llega a tener una
que solo él conozca.

Eso importa por algo concreto: la contraseña temporal **la vio el administrador**
y viajó por algún canal —correo, chat, un papel—. Mientras no se cambie, la cuenta
la conocen dos personas y el rastro queda en ese canal. Cambiarla es lo único que
corta eso, y hoy es imposible.

Esta spec agrega la operación que faltaba y avisa a quien la necesita en el
momento en que le sirve: al entrar con una contraseña que no eligió.

### Lo que esta spec NO hace

**No agrega recuperación autogestionada** («olvidé mi contraseña» por correo). El
proyecto no tiene ningún backend de correo configurado, y las tres salidas
posibles son malas: un proveedor real exige credenciales que quien evalúe no
tiene; el backend de consola deja el enlace en la terminal del servidor, donde no
le llega a nadie; y mostrar el enlace en pantalla le regala el acceso a cualquiera
que escriba un correo conocido. El camino de recuperación **ya existe y es el
correcto para este producto**: lo regenera el administrador. RN-11 se limita a
decirlo en la pantalla donde la persona se queda trabada.

## Artículo 2 — Objetivo

Que cualquier persona con cuenta pueda cambiar su propia contraseña, y que quien
recibió una temporal se entere de que puede hacerlo, sin quedar obligada a
hacerlo en ese momento.

## Artículo 3 — Alcance

**Dentro de alcance:** `POST /user/change-password/`; el campo
`must_change_password` en `User` y quién lo enciende y lo apaga; el aviso omitible
al ingresar; el acceso permanente a la acción desde los dos layouts; y la nota de
recuperación en el login.

**Fuera de alcance:** recuperación por correo, expiración de contraseñas,
autenticación en dos pasos, historial de contraseñas usadas, límite de intentos
(ver PA-6) y cambiar la contraseña de otra persona, que ya resuelve el endpoint de
regeneración del administrador.

## Artículo 4 — Actores y precondiciones

- **Actor:** cualquier usuario autenticado, con o sin perfil de administrador.
- **Precondiciones:** token Knox válido. La persona conoce su contraseña actual.
- El endpoint NO DEBE recibir el identificador de un usuario: opera siempre sobre
  quien está autenticado.

## Artículo 5 — Reglas de negocio

### El cambio

- **RN-1.** El sistema DEBE exponer `POST /user/change-password/` para cualquier
  usuario autenticado. Sin token DEBE responder `401`.
- **RN-2.** El body DEBE traer `current_password` y `new_password`, los dos
  obligatorios. Faltar alguno DEBE responder `400` bajo la clave que falte.
- **RN-3.** `current_password` DEBE verificarse contra la contraseña vigente. Si no
  coincide, DEBE responder `400` bajo `current_password` y NO DEBE cambiar nada.
  Exigirla es lo que impide que un token robado se apropie de la cuenta.
- **RN-4.** `new_password` DEBE pasar los validadores de `AUTH_PASSWORD_VALIDATORS`
  que ya están configurados —largo mínimo y similitud con los datos del usuario—
  mediante `django.contrib.auth.password_validation.validate_password`. La regla de
  fuerza NO DEBE reescribirse acá: ya está declarada en `settings.py`.
- **RN-5.** `new_password` NO DEBE ser igual a `current_password`; en ese caso,
  `400` bajo `new_password`.
- **RN-6.** Un cambio válido DEBE guardar la contraseña **hasheada** y responder
  `200`. La respuesta NO DEBE incluir ninguna contraseña.
- **RN-7.** Tras el cambio, los **demás tokens** del usuario DEBEN invalidarse y el
  token de la petición actual DEBE seguir sirviendo. La contraseña temporal la
  conocía otra persona: si abrió sesión con ella, esa sesión tiene que morir acá.

### El aviso

- **RN-8.** `User` DEBE tener `must_change_password` (booleano, por defecto
  `False`). Esto exige una migración.
- **RN-9.** El campo DEBE ponerse en `True` al **crear un colaborador**
  (SPEC-002) y al **regenerar su contraseña**, y en `False` cuando la persona la
  cambia por la suya. Un administrador creado por el seeder o por
  `createsuperuser` DEBE nacer en `False`: nunca recibió una contraseña temporal.
- **RN-10.** `UserSerializer` DEBE exponer `must_change_password`, de modo que
  viaje en `POST /user/login/`, `GET /user/me/` y `POST /user/verify-token/`. El
  frontend NO DEBE inferirlo de ningún otro dato.

### Interfaz

- **RN-11.** La pantalla de login DEBE ofrecer «¿Olvidaste tu contraseña?» que
  explique el camino real: pedirle al administrador que la regenere. NO DEBE
  prometer un correo de recuperación que el sistema no puede enviar.
- **RN-12.** Al entrar a la aplicación con `must_change_password` en `True`, la
  interfaz DEBE mostrar un aviso que ofrezca cambiarla, con una salida explícita
  para hacerlo después. **Omitir DEBE ser posible**, y el aviso DEBE volver a
  aparecer en el siguiente ingreso: se puede postergar, no desaparecer.
- **RN-13.** La acción DEBE estar disponible de forma permanente desde los dos
  layouts, junto a «Cerrar sesión», y no solo desde el aviso. Quien la omitió tiene
  que poder volver sin cerrar sesión.
- **RN-14.** El formulario DEBE pedir la contraseña actual y la nueva, y DEBE
  mostrar los errores del servidor por campo. NO DEBE validar la fuerza por su
  cuenta: la regla vive en el backend y duplicarla las separa.
- **RN-15.** Tras un cambio exitoso, la sesión DEBE seguir abierta —el token actual
  sigue vigente por RN-7— y el aviso NO DEBE volver a aparecer.

## Artículo 6 — Criterios de aceptación

- **CA-1:** un cambio válido responde `200`; la contraseña nueva permite iniciar
  sesión y la anterior deja de servir.
- **CA-2:** tras el cambio, `must_change_password` queda en `False`.
- **CA-3:** una `current_password` incorrecta responde `400` bajo esa clave y no
  cambia la contraseña.
- **CA-4:** una `new_password` que no pasa los validadores —demasiado corta, o
  parecida al correo— responde `400` bajo `new_password`.
- **CA-5:** una `new_password` igual a la actual responde `400`.
- **CA-6:** omitir cualquiera de los dos campos responde `400` bajo esa clave.
- **CA-7:** una petición sin token responde `401`.
- **CA-8:** un administrador también puede cambiar la suya.
- **CA-9:** tras el cambio, un token emitido antes deja de servir y el token con el
  que se hizo la petición sigue sirviendo.
- **CA-10:** un colaborador recién creado llega con `must_change_password` en
  `True`.
- **CA-11:** tras `POST /collaborator/{id}/reset-password/`, vuelve a `True`.
- **CA-12:** el admin del seeder tiene `must_change_password` en `False`.
- **CA-13:** `login`, `me` y `verify-token` incluyen el campo en el usuario.
- **CA-14:** la respuesta del cambio no contiene ninguna contraseña.
- **CA-F1:** al ingresar con el campo en `True`, aparece el aviso; se puede omitir;
  vuelve a aparecer en el siguiente ingreso.
- **CA-F2:** tras cambiarla, el aviso no reaparece y la sesión sigue abierta.
- **CA-F3:** la acción está disponible desde los dos layouts sin depender del
  aviso.
- **CA-F4:** el login explica cómo recuperar la contraseña sin prometer un correo.

## Artículo 7 — Contrato de interfaz

### `POST /user/change-password/`

**Autenticación:** `Authorization: Token <token>` · cualquier usuario autenticado.

```json
{ "current_password": "…", "new_password": "…" }
```

**Respuesta `200`:**

```json
{ "detail": "Tu contraseña fue actualizada." }
```

**Errores `400`:** `{ "current_password": ["La contraseña actual no es correcta."] }`
· `{ "new_password": ["…"] }` con el texto de los validadores de Django o
«La contraseña nueva debe ser distinta de la actual.»

### `UserSerializer` — campo nuevo

`must_change_password` (booleano, solo lectura) se suma al objeto `user` que
devuelven `login`, `me` y `verify-token`.

## Artículo 8 — Preguntas abiertas resueltas

- **PA-1:** el aviso es **omitible**, no bloqueante. Bloquear la navegación hasta
  el cambio es lo más seguro, pero arruina la demo: quien evalúe entra con
  `colaborador1@lifebox.test` y no quiere que lo obliguen a nada. El costo
  aceptado es que una contraseña temporal puede vivir indefinidamente; se
  compensa con que el aviso **reaparece en cada ingreso** y la acción queda
  siempre a mano. Se puede postergar, no esconder.
- **PA-2:** el flag vive en `User` y no en `Collaborator`. La contraseña es del
  usuario, no del perfil; ponerlo en el perfil obligaría a preguntar por el rol
  antes de saber si hay que avisar, y dejaría fuera a un administrador al que
  alguna vez se le entregue una contraseña temporal.
- **PA-3:** se exige la **contraseña actual** aunque la persona ya esté
  autenticada. El token puede haber quedado en un equipo prestado; sin este
  segundo factor, tomar la cuenta sería trivial para quien lo tenga.
- **PA-4:** se **invalidan los demás tokens** (RN-7). Es el punto del cambio: la
  contraseña temporal la conocía el administrador, y si abrió sesión con ella, esa
  sesión debe morir. El token actual se conserva para no expulsar a quien acaba de
  hacer lo correcto.
- **PA-5:** la fuerza de la contraseña la deciden los `AUTH_PASSWORD_VALIDATORS`
  que ya están en `settings.py`, no una regla nueva. Ya gobiernan la contraseña
  temporal generada; que gobiernen también la elegida mantiene un solo criterio.
- **PA-6:** no se agrega límite de intentos sobre este endpoint. Es una defensa
  real contra fuerza bruta sobre `current_password`, pero exige almacenamiento de
  intentos o un throttle configurado, y ninguno de los dos existe en el proyecto.
  Queda anotado como límite conocido, no como olvido.
- **PA-7:** no hay recuperación por correo, y el login lo dice en vez de callarlo.
  Un enlace «¿Olvidaste tu contraseña?» que no lleva a ninguna parte es peor que
  uno que explica a quién pedirle ayuda.
- **PA-8:** el administrador **no** ve el aviso salvo que alguien le haya
  regenerado la contraseña. Nace en `False` porque eligió la suya al crearse la
  organización o al correr el seeder.

## Artículo 9 — Decisiones, dependencias y referencias

El backend reutiliza `TokenAuthentication` de Knox, `UserSerializer` y el endpoint
de regeneración de SPEC-002, que pasa a encender el flag. La vista es un
`GenericAPIView` en `apps/user/views.py`, con su serializer arriba, como el resto
del repo. La invalidación de tokens usa el `auth_token_set` que Knox ya expone y
excluye `request.auth`.

**Esta spec sí agrega un campo y una migración** —la primera del proyecto sobre
los modelos base—, porque no hay forma honesta de derivar «esta persona nunca
eligió su contraseña» de los datos actuales: `last_login` existe en la tabla pero
**nada lo escribe**, ya que el login usa `authenticate()` + Knox y nunca llama a
`django.contrib.auth.login()`, que es quien lo actualizaría. Se queda en `NULL`
para siempre y no distingue el primer ingreso del décimo.

El frontend reutiliza `stores/userStore.ts` —que ya persiste el usuario— y
`$apiFetch`. El aviso se resuelve en los layouts para no repetirlo por página.

---

## Anexo A — Tests y verificaciones

Los tests van en `apps/user/tests/test_change_password.py`, más las adiciones a
`test_create_collaborator.py` para CA-10 y CA-11, que son del dominio de SPEC-002.

Tres cargan el peso de esta spec: **CA-1**, que verifica el cambio contra el login
real y no solo contra el hash; **CA-9**, que fija la invalidación de los otros
tokens, que es la razón de seguridad de toda la feature; y **CA-11**, que ata la
regeneración del administrador al aviso, sin la cual el flag se apagaría para
siempre después del primer cambio.

Se verifica que la suite completa siga verde (160 tests antes de esta feature) y
que `makemigrations --check` quede limpio **después** de generar la migración.
