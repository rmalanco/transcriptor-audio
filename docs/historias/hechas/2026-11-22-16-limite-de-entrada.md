# 16 · Avisar antes de redactar si las notas no caben en el modelo

> Origen: `BACKLOG.md`, «Salud del código» #26 — hallazgo A-11, escenario C (antes «posible») — historia derivada de
> `docs/historias/hechas/2026-11-22-07-documento-incompleto.md` — carril M. Reglas de oro 1, 3, 4, 7 y 10 de
> `AGENTS.md`. Confirmación con Copilot real en `docs/integracion-copilot.md` §«Comprobado con peticiones reales
> (2026-11-22)»: `GET /models` trae `capabilities.limits.max_prompt_tokens` por modelo (ese día, 936 000 en
> `claude-haiku-5.5` y `claude-sonnet-5.5`, 128 000 en `claude-haiku-4.5`, 64 000 en `gpt-4.1`). No se comprobó qué
> responde Copilot cuando una petición los supera. Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver
> «Supuestos» y «Decisiones para el usuario»).

## Historia

Como usuario de reuniones muy largas, quiero que la app me avise antes de redactar si las notas de todas las partes
superan el límite de entrada del modelo, para no enviar una redacción que Copilot va a rechazar y saber qué hacer.

## Criterios de aceptación

- [ ] [NUEVO] Dada una transcripción que se procesa en 3 partes, `ia.modelo` en `gpt-4.1`, un catálogo de Copilot que
  da a `gpt-4.1` `max_prompt_tokens` 64 000 y unas notas de 100 000 caracteres por parte (unos 76 000 tokens estimados
  con la petición de redacción entera), cuando genero la minuta, entonces Copilot recibe las 3 peticiones de notas y una
  consulta del catálogo, no recibe la petición de redacción, y la pestaña muestra «No se pudo generar: las notas de las
  3 partes suman unos <N> tokens y el modelo «gpt-4.1» admite como máximo 64000 tokens de entrada, así que no se envió
  la redacción. Elige en el selector un modelo con más contexto y vuelve a generar; con otro modelo se pedirán de nuevo
  las notas de todas las partes.» (el diálogo de error muestra el mismo motivo), donde <N> es la estimación, sin
  separador de miles. Cuando después genero el resumen con el mismo modelo, Copilot no recibe ninguna petición: ni de
  notas, ni del catálogo, ni de redacción, y aparece el mismo error.
- [ ] [NUEVO] Dada la misma transcripción de 3 partes y un catálogo que da a `gpt-4.1` 64 000, cuando las notas suman
  60 000 caracteres por parte (unos 46 000 tokens), entonces Copilot recibe una consulta del catálogo y la redacción se
  envía como hoy; y cuando las notas son cortas (por debajo de unos 32 000 tokens en total) o la transcripción cabe en
  una sola parte, entonces no se consulta el catálogo y la redacción se envía como hoy. Generar después el otro
  documento con el mismo asistente no vuelve a consultar el catálogo.
- [ ] [NUEVO] Dadas unas notas de unos 76 000 tokens, cuando la consulta del catálogo falla (error de conexión, 401,
  500 o una respuesta con formato inesperado), o el catálogo no trae el modelo, o el modelo no trae
  `capabilities.limits.max_prompt_tokens` o no es un entero positivo, entonces la redacción se envía como hoy, no
  aparece ningún error nuevo y la pestaña Registro anota que no se pudo comprobar el límite de entrada. Si la consulta
  falló, la siguiente generación con el mismo asistente puede volver a intentarla (una vez por generación).

Cómo se verifican:

- **Con tests sin red** (`httpx.stream` simulado que decide la respuesta según el prompt y cuenta las peticiones;
  `httpx.get` del catálogo simulado con `capabilities.limits` y contado; regla 3):
  - `test_notas_que_superan_el_limite_no_envian_la_redaccion`: 3 partes, notas de 100 000 caracteres, límite 64 000;
    3 peticiones de chat (todas de notas), 1 de catálogo, el error dice el modelo, el límite y «no se envió la
    redacción», y ningún cuerpo es el de redacción (criterio 1).
  - `test_repetir_con_el_mismo_modelo_no_pide_nada_y_repite_el_error`: el resumen con el mismo asistente no hace
    ninguna petición de chat ni de catálogo (criterio 1).
  - `test_notas_que_caben_consultan_el_catalogo_una_vez_y_redactan`: 60 000 caracteres por parte; 1 consulta de
    catálogo en total para la minuta y el resumen, y las dos redacciones se envían (criterio 2).
  - `test_notas_cortas_o_una_sola_parte_no_consultan_el_catalogo`: con `httpx.get` que hace fallar el test si se
    llama (criterio 2).
  - `test_sin_limite_conocido_se_redacta_como_hoy`, parametrizado: conexión caída, 401, 500, `data` inesperado, modelo
    ausente, sin `capabilities.limits`, `max_prompt_tokens` 0, negativo o texto; la redacción se envía y hay un
    `warning` en el log (criterio 3).
  - En `tests/test_copilot.py`, `test_limites_de_entrada_del_catalogo` comprueba que se lee `max_prompt_tokens` de
    cada modelo y se ignoran los que no lo traen o no es un entero positivo.
  - Siguen pasando, sin cambios, los tests de varias partes que hoy prohíben cualquier `GET` (sus notas son cortas y no
    llegan al umbral) y los de las historias 04, 06 y 07.
- **Verificación manual:** opcional. Con la sesión propia y texto sintético (nunca una transcripción, regla 2),
  generar con `gpt-4.1` y un `ia.max_caracteres_bloque` bajo sobre un texto que produzca notas largas, y comprobar en
  Registro que se consulta el catálogo una vez y que el error aparece sin enviar la redacción.

## Plan

- La parte de Copilot ofrece la lectura del límite de entrada de cada modelo a partir del catálogo, con los mismos
  errores controlados que el resto de consultas del catálogo.
- Antes de enviar la redacción de un documento de varias partes, la app estima los tokens de la petición entera
  (instrucciones del sistema, plantilla y notas) como caracteres entre 4, redondeado hacia arriba.
- Solo si esa estimación supera el umbral de 32 000 tokens se pide el límite: el catálogo se consulta una vez por
  asistente y se recuerda; una consulta fallida no se recuerda y se anota en el log.
- Si la estimación supera el límite del modelo que se va a usar (en `auto`, el que resolvió la sesión), no se envía la
  redacción y el error lo dice; las notas siguen conservadas para ese modelo, como tras el fallo de una parte.
- Tests sin red del asistente y de la lectura del catálogo, y la frase de tráfico de red del diseño actual al día.

Archivos del `/pair` (lista cerrada): `src/copilot.py`, `src/asistente_ia.py`, `tests/test_asistente_ia.py`,
`tests/test_copilot.py`, `docs/disenos/00-actual.md` (solo la viñeta «Cuándo hay tráfico de red»: generar un
documento de varias partes con notas largas añade como mucho un `GET /models`). El delta de spec lo escribe `/cerrar`
en `docs/specs/documentos-ia.md`.

## Fuera de alcance

- Avisar antes de pedir las notas: su tamaño no se conoce hasta que Copilot las devuelve (ver «Supuestos», 2).
- Comprobar el límite en la petición de una sola parte, en la de completar secciones o en la revisión de fidelidad.
  La revisión lleva las notas y el documento, así que puede superar el límite aunque la redacción quepa: hoy Copilot
  la rechazaría y, desde #28, el documento se entrega con la nota «la revisión de fidelidad no se pudo completar (…)».
- Sugerir en el error qué modelos de la cuenta tienen contexto suficiente (opción C de «Decisiones para el usuario»).
- Conservar las notas al cambiar de modelo: hoy cambiar de modelo descarta el asistente y sus notas; cambiarlo es otra
  historia.
- Contar tokens con el tokenizador real de cada modelo o con una librería nueva.
- Avisar de una respuesta cortada (#25, historia 15), revisar contra la transcripción original (#23), el panel de
  configuración y el soporte de `/responses`.
- La CLI, que no genera documentos.

## Sugerencias

- En modo `auto` la sesión ya lee el catálogo entero al abrirse (para saber qué modelos admiten `/chat/completions`) y
  hoy solo guarda los endpoints. Guardar ahí también los límites evitaría la consulta extra en `auto`. No es
  necesario para los criterios, que usan un modelo fijo.
- Leer el límite del catálogo sin el filtro de modelos habilitados de la lista del selector: el modelo con el que se
  generó ya está en uso y basta con encontrar su `id`.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es una reunión de muchas horas con un modelo de contexto pequeño (`gpt-4.1`, 64 000) en
   la que, tras varios minutos de notas, la redacción falla con un 400 de Copilot que no dice qué hacer. El criterio 1
   lo sustituye por un error claro, sin enviar la redacción.
2. **La comprobación va entre las notas y la redacción**, no antes de las notas, aunque el backlog diga «para no pagar
   las notas». El tamaño de las notas no se conoce hasta tenerlas; estimarlo como una fracción de la transcripción
   daría falsas alarmas o ninguna. Las notas ya obtenidas siguen en memoria para ese modelo; lo que se evita es enviar
   una redacción que se va a rechazar y el error opaco.
3. **Tokens ≈ caracteres / 4, sin margen añadido y redondeado hacia arriba**, sobre la petición de redacción entera.
   Para texto en español con los tokenizadores de GPT la cuenta suele estar cerca; con los de Claude suele quedarse
   corta (hay más tokens que caracteres / 4). Se elige que el error se equivoque hacia «no avisar»: si la estimación
   se queda corta, Copilot rechaza la redacción como hoy; si se pasara, la app bloquearía una redacción que habría
   funcionado, sin forma de saltarse el aviso. Por eso no se resta ni se suma margen.
4. **Umbral de 32 000 tokens estimados (unos 128 000 caracteres) para consultar el catálogo**, la mitad del límite más
   bajo visto (64 000 en `gpt-4.1`). Por debajo no se consulta nada: la mayoría de las reuniones no generan ninguna
   consulta extra (el punto #10 pidió no añadir tráfico), y los tests de varias partes que hoy prohíben cualquier `GET`
   siguen igual. Un modelo con un límite por debajo de 32 000 no se comprobaría y fallaría como hoy.
5. **Una consulta del catálogo por asistente**, bajo demanda: el asistente vive mientras no se cambia de modelo, no se
   cancela, no hay un 401 y no se cierra la app. Si la consulta falla no se recuerda el fallo, para que la siguiente
   generación pueda comprobarlo; es como mucho una consulta por generación que supere el umbral.
6. **Sin límite conocido, se sigue como hoy**: el aviso es una ayuda, no un requisito de cumplimiento, y bloquear por
   no poder leer el catálogo dejaría sin documento a quien hoy lo obtiene.
7. **El consejo del error es solo «elige un modelo con más contexto».** Bajar `ia.max_caracteres_bloque`, que era una
   de las salidas propuestas, suele empeorarlo: más partes dan más notas en total. Subirlo da menos notas, pero cada
   petición de notas crece y depende del mismo límite; no se aconseja en el error.
8. **Probabilidad baja con los modelos actuales.** Con partes de 60 000 caracteres, superar 64 000 tokens de notas
   exige del orden de decenas de partes (decenas de horas de audio) o notas muy extensas. El criterio se mantiene
   porque `ia.max_caracteres_bloque` y el modelo son configurables y el catálogo cambia.
9. **El texto del error** es una propuesta, en el tono del de «falló la parte N de M», y empieza en minúscula porque la
   pestaña lo muestra tras «No se pudo generar: ».

## Decisiones para el usuario

Qué hace la app cuando la estimación supera el límite del modelo:

1. **(Recomendada) No enviar la redacción y mostrar el error del criterio 1.** Es lo menos sorprendente: el usuario ve
   por qué y qué hacer, y no se envía una petición que Copilot rechazaría. Riesgo: si la estimación se pasara, se
   bloquearía una redacción posible; por eso la estimación se equivoca hacia no avisar (Supuestos 3).
2. **Enviar la redacción igualmente y, si Copilot la rechaza, explicar el motivo con el límite del catálogo.** No
   bloquea nunca por una estimación, pero envía siempre la petición y depende de una respuesta de error de Copilot que
   no se ha comprobado.
3. **Como la 1, y además nombrar en el error los modelos de la cuenta con contexto suficiente** (autorizados y
   compatibles con `/chat/completions`). Más útil, pero el texto depende del catálogo de cada cuenta y añade un
   criterio; podría ser una historia aparte.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa (359 tests). Code review: revisión del
orquestador, listo para commit. El orquestador añadió `test_si_el_catalogo_falla_se_vuelve_a_consultar_en_la_siguiente_generacion`
(criterio 3: un fallo del catálogo no se guarda y se reintenta en la siguiente generación). Delta de spec:
`docs/specs/documentos-ia.md`, comportamiento «Notas que no caben en el modelo», con `Origen` en esta historia.

**Decisión del usuario** (cuestionario del 2026-11-22): opción 1 de «Decisiones para el usuario». Si las notas superan el
límite, no se envía la redacción y se explica el motivo; no se añaden modelos sugeridos al error (opción 3) ni se envía
la redacción igualmente (opción 2).

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Notas que superan el límite del modelo: no se envía la redacción, el error nombra modelo, límite y estimación; repetir con el mismo modelo no consulta nada más | Notas que superan, 3 peticiones de notas y 1 consulta, sin redacción: `tests/test_asistente_ia.py:1705`. Repetir sin peticiones ni consultas: `:1724`. Lectura del límite: `tests/test_copilot.py:177`. Implementación: `src/asistente_ia.py:795` (`_comprobar_limite_de_entrada`), `:733` (llamada), `:819` (error), `src/copilot.py:264` (`limites_de_entrada`), `:251` (`_catalogo`) | cumple (tests). Pendiente aceptado: no se comprobó qué responde Copilot a una petición que supera el límite (ya no se envía) |
| 2 | [NUEVO] | Notas que caben, una sola parte o notas por debajo del umbral: se redacta como hoy; por debajo del umbral no se consulta el catálogo; una consulta por asistente | Notas cortas o una parte, con `httpx.get` prohibido: `tests/test_asistente_ia.py:1687`. Notas que caben, 1 consulta para minuta y resumen: `:1743`. Implementación: `src/asistente_ia.py:799` (`estimado`), `:732` (solo con más de una parte), `:806` (`self._limites`, una vez por asistente) | cumple (tests). Pendiente aceptado: la estimación `caracteres / 4` es aproximada |
| 3 | [NUEVO] | Catálogo no disponible, sin el modelo o sin límite válido: se redacta como hoy, con aviso en el log; un fallo no se guarda y se vuelve a consultar | Catálogo caído, 401, 500, formato inesperado, modelo ausente, sin límite, cero, negativo o texto, parametrizado: `tests/test_asistente_ia.py:1767`. Fallo seguido de consulta en la siguiente generación: `:1780`. Implementación: `src/asistente_ia.py:809` (el fallo no se guarda), `:811` y `:816` (`log.warning`) | cumple (tests). Pendiente aceptado: no hay verificación en la ventana |

**Verificación:** tests sin red (`httpx.get` y `httpx.stream` simulados, regla 3). No hay verificación manual en la ventana:
el error viaja por el camino de error de siempre («No se pudo generar: …»). Confirmación con Copilot real del campo
`capabilities.limits.max_prompt_tokens` en `docs/integracion-copilot.md`.

**Pendientes aceptados:**

- No se comprobó qué responde Copilot si se le envía una petición que supera `max_prompt_tokens`. Ya no se envía en este
  flujo.
- La estimación de tokens (caracteres / 4, sin margen) es aproximada; con los tokenizadores de Claude suele quedarse corta.
  Si se queda corta, Copilot rechaza la redacción por el camino de error de siempre.
- Sin verificación en la ventana: el error llega por el camino de error de siempre.
