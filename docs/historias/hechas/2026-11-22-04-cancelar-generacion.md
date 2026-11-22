# 04 · Cancelar la generación de un resumen o una minuta

> Origen: `BACKLOG.md`, «Backlog» #1 — hallazgo A-04 — carril M. Decisión en `goldfish_review_report.md`: aceptado,
> «`AsistenteIA` ya acepta `cancelar`; falta conectarlo». Reglas de oro 3, 6 y 9 de `AGENTS.md`.
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»).

## Historia

Como usuario, quiero cancelar la generación de un resumen o una minuta, para no tener que cerrar la app cuando el
modelo tarda.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dada una transcripción en pantalla y una minuta en generación cuyo modelo no envía ningún
  dato, cuando pulso «■ Cancelar», el botón que ocupa el sitio de «✨ Generar minuta» (o «↻ Regenerar») en la pestaña
  Minuta mientras dura la generación, entonces en 1 segundo como máximo, aunque la petición a Copilot siga abierta por
  debajo, la línea de estado de la pestaña dice «Generación cancelada», la barra de estado dice «Generación de la
  minuta cancelada», la pestaña Registro anota la cancelación, la transcripción sigue en la pestaña Texto sin cambios,
  «Generar» de las dos pestañas de IA y el selector de modelo de IA quedan habilitados, «Transcribir» vuelve al estado
  que tenía antes de generar, y puedo al momento generar otra vez, cargar otro archivo o abrir una entrada del
  historial sin el aviso «Espera a que termine el proceso en curso.». Lo mismo vale para el resumen, con «Generación
  del resumen cancelada». (antes: no había forma de interrumpir la generación; «Generar» de las dos pestañas,
  «Transcribir» y el selector de modelo quedaban deshabilitados, y cargar otro archivo o abrir el historial avisaba
  «Espera a que termine el proceso en curso.» hasta que Copilot respondía o fallaba: sin límite si el modelo envía
  datos sin parar, y hasta unos 14 minutos por petición si no envía ninguno (30 s de conexión y 180 s sin datos por
  intento, 4 intentos con esperas de 1, 2 y 4 s). «Escape» solo cancela transcripciones)
- [ ] [NUEVO] Dada una entrada del historial abierta en la ventana con una minuta ya guardada (en el historial y en
  `<nombre>_minuta.md` junto al audio), cuando pulso «↻ Regenerar», después «■ Cancelar», y más tarde la petición que
  quedó abierta termina (con una minuta completa, con un error o con un 401), entonces la pestaña Minuta vuelve a
  mostrar la minuta anterior con «↻ Regenerar», «Copiar» y «Guardar como…» habilitados y la línea de estado «Generación
  cancelada · se conserva la minuta anterior»; la entrada del historial y `<nombre>_minuta.md` conservan la minuta
  anterior sin cambios; no aparece ningún diálogo de error ni de inicio de sesión; y Copilot no recibe ninguna petición
  nueva de ese documento después de pulsar «■ Cancelar» (ni de las partes que aún no habían empezado, ni reintentos,
  ni la de completar secciones, ni la revisión de fidelidad). Si era la primera generación de la minuta, la pestaña
  vuelve a su texto inicial con «✨ Generar minuta» y no se guarda ni se exporta nada.
- [ ] [MODIFICA: sin spec] Dada una minuta o un resumen en generación, cuando cierro la ventana, entonces se pregunta
  «Hay una generación de la minuta en curso. ¿Cancelarla y salir?» (o «del resumen»); si respondo que no, la ventana
  sigue abierta y la generación continúa; si respondo que sí, la ventana se cierra y el documento no se guarda en el
  historial ni junto al audio, aunque Copilot lo termine en ese momento. Si la generación ya se había cancelado, la
  ventana se cierra sin preguntar. (antes: la ventana solo preguntaba antes de cerrar si había una transcripción en
  curso; con una generación en curso se cerraba sin preguntar y el documento se perdía sin aviso, con las peticiones
  ya enviadas a Copilot)

Cómo se verifican:

- **Con tests sin red y sin ventana** (httpx simulado, regla 3):
  - El asistente, con la cancelación activada a mitad de una transcripción larga que se procesa en varias partes en
    paralelo, no inicia ninguna petición nueva a `/chat/completions`: ni las partes en cola, ni el reintento que sigue
    a un 429 o a un fallo de conexión, ni la de completar secciones, ni la revisión de fidelidad (criterio 2).
  - Una generación cancelada cuyo asistente simulado termina después (con documento, con error y con 401) no deja
    cambios en un historial temporal ni escribe el documento junto al audio (criterios 2 y 3).
- **Verificación manual** con el guion que conduce la ventana real con un asistente simulado y lento (uno que abre la
  petición y no envía datos, y otro que termina a los pocos segundos de cancelar):
  1. Transcripción en pantalla, «✨ Generar minuta»: el botón pasa a «■ Cancelar». Pulsarlo y comprobar en menos de
     1 s la línea de estado de la pestaña, la barra de estado, la línea en Registro, el texto inicial de la pestaña,
     «Generar» de Resumen y Minuta y el selector de modelo habilitados, «Transcribir» como estaba y la pestaña Texto
     sin cambios (criterio 1).
  2. Sin esperar, generar el resumen, cargar otro archivo y abrir una entrada del historial: ninguno muestra «Espera a
     que termine el proceso en curso.» (criterio 1).
  3. Entrada del historial con minuta: «↻ Regenerar», «■ Cancelar», esperar a que el asistente simulado termine.
     Comprobar que la pestaña muestra la minuta anterior con sus botones, que no hay diálogos, y que el contenido de la
     entrada en el historial y la fecha de modificación de `<nombre>_minuta.md` no cambian (criterio 2).
  4. Repetir el paso 3 con un asistente simulado que termina con un 401: no se abre el diálogo de inicio de sesión
     (criterio 2).
  5. Con una generación en curso, cerrar la ventana: aparece la pregunta. Con «No», la generación sigue; con «Sí», la
     ventana se cierra; al reabrir, el historial no tiene el documento nuevo. Cancelar una generación y cerrar en
     seguida: se cierra sin preguntar (criterio 3).

## Plan

- Cada generación lleva su propia señal de cancelación, que se pasa al asistente; mientras dura, el botón de generar
  de esa pestaña pasa a «■ Cancelar».
- Al pulsarlo, la ventana vuelve en el acto al estado de antes de generar (botones, selector, «Transcribir», documento
  anterior o texto inicial) sin esperar al hilo de fondo. Que haya una generación «en curso» deja de depender de que
  ese hilo siga vivo, para que generar, cargar otro archivo o abrir el historial funcionen al momento.
- La generación cancelada queda abandonada: cuando su hilo termina, con documento, error o 401, el resultado se
  descarta sin tocar la pestaña, el asistente compartido, el historial ni el archivo, y sin abrir diálogos. Guardar y
  cancelar no se pisan: la decisión de guardar se toma en un solo punto que comprueba la cancelación, así que el
  documento o se guarda y se muestra terminado, o se descarta y se muestra cancelado.
- Cerrar la ventana con una generación activa pregunta, como ya hace con la transcripción; si se acepta, se cancela
  antes de cerrar.
- Tests sin red del asistente (ninguna petición nueva tras cancelar) y del punto de decisión (una generación cancelada
  que termina después no guarda nada), con historial temporal y asistente simulado.

## Fuera de alcance

- Conservar las partes ya procesadas o avisar de un documento incompleto (A-11, «Backlog» #3). Cancelar descarta el
  documento entero; las notas de las partes que terminaron pueden quedar en la memoria del asistente, como hoy, pero
  no se muestran ni se guardan.
- Sacar de la clase de la ventana el flujo «generar y persistir» (A-15, «Salud del código» #5): solo se aísla lo
  mínimo para probar el punto de decisión sin ventana.
- El 401 del modo `auto` y el token de `COPILOT_GITHUB_TOKEN` (A-06, A-07, «Salud del código» #7).
- La exclusión de familias de modelos no autorizadas (historia 03).
- Cortar la conexión HTTP que quedó abierta, acortar los timeouts o respetar `Retry-After`: la petición abierta
  termina sola (en el peor caso unos 3,5 minutos: 30 s de conexión, 180 s sin datos y una espera de hasta 8 s antes
  del siguiente intento, que ya no se envía).
- La cancelación de la transcripción, que sigue igual: espera a que termine el segmento y descarta lo transcrito.
- Que «Copiar» y «Guardar como…» sigan activos con el documento anterior mientras se regenera: es el comportamiento
  de hoy y no lo cita la auditoría.
- Un botón para cerrar el programa («Backlog» #4) y la CLI, que no genera documentos.

## Sugerencias

- Dar a cada generación su propio `Event` en vez de reutilizar uno compartido: la transcripción reutiliza
  `cancelar_flag` y lo limpia al empezar (`_iniciar_transcripcion`). Con un evento compartido, la siguiente generación
  «descancelaría» la abandonada y su hilo seguiría enviando peticiones.
- Tomar la decisión de guardar el documento en el hilo principal, al recibir el resultado, en vez de en el hilo de
  fondo: «Cancelar» y guardar quedarían serializados por `_en_ui` sin cerrojos, y guardar una fila en SQLite y un
  `.md` tarda milisegundos. El coste es que deja de parecerse a la transcripción, que guarda en el hilo de fondo; la
  regla 6 (primero el historial, después el archivo) se cumple igual.
- Hacer que «Escape» cancele también la generación, como ya cancela la transcripción. No lo pide la auditoría.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es pulsar «Cancelar» y que la app siga bloqueada, o que acabe guardando el documento
   como si fuera bueno. El criterio 1 fija el límite de 1 segundo con un modelo que no envía datos; el 2, que nada
   de una generación cancelada llega a la pestaña, al historial ni al archivo, aunque la petición termine después.
2. **La cancelación se ve al instante y no espera al hilo**, a diferencia de la transcripción («Cancelando… (termina
   el segmento actual)»). El asistente solo comprueba la señal al empezar cada intento y entre líneas del stream: con
   una petición callada, el hilo puede seguir vivo unos 3,5 minutos después de cancelar, y esperar a que termine
   dejaría la app bloqueada, que es lo que la historia quiere evitar.
3. **Al cancelar una regeneración se vuelve a mostrar el documento anterior**, porque sigue siendo el que hay en el
   historial y junto al audio: lo que se ve coincide con lo guardado. Dejar la pestaña vacía haría creer que se
   perdió.
4. **Se cancela solo desde el botón de la pestaña** que está generando, y al cerrar la ventana. «Escape» queda como
   sugerencia.
5. **Los textos** («Generación cancelada», «Generación de la minuta cancelada», «se conserva la minuta anterior» y la
   pregunta al cerrar) son propuestas que imitan los de la transcripción («Transcripción cancelada», «Hay una
   transcripción en curso. ¿Cancelarla y salir?»), no requisitos de la auditoría.
6. **Si el resultado y la cancelación llegan casi a la vez, gana lo que se procese primero en la ventana**: si se
   pulsó «Cancelar», el documento se descarta; si el documento ya se mostró, el botón ya no es «Cancelar». Nunca se
   muestra «cancelada» con un documento nuevo guardado.
7. **La spec `transcripcion.md` › «Cargar otro archivo»** («Given una transcripción o una generación de documento en
   curso…») no cambia: una generación cancelada deja de estar «en curso». `/cerrar` puede añadirlo como aclaración.
8. **Un 401 de una generación cancelada no abre el login.** El token sí puede quedar invalidado, como hoy, porque el
   rechazo es real; el login se ofrecerá en la próxima generación.

## Cierre

Cerrada con `/cerrar` el 2026-11-22. Tests: `./venv/bin/python -m pytest -q`, 114 pasan. Revisión del orquestador
sobre diseño y código: listo para commit. Deltas aplicados en `docs/specs/documentos-ia.md` (dos comportamientos nuevos)
y `docs/specs/transcripcion.md` (aclaración en «Cargar otro archivo»).

| # | Marca | Criterio | Evidencia con test y `ruta:línea` | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Con un asistente que no envía datos, «■ Cancelar» devuelve la ventana en 1 s o menos, aunque la petición siga abierta; estados, botones, selector y transcripción como se describen | Ninguna petición nueva tras cancelar: `tests/test_asistente_ia.py:263` (partes en cola), `:279` (espera de reintento tras 429), `:298` (reintento tras fallo de conexión), `:317` (revisión de fidelidad). Interfaz: `src/ui.py:839` (`_alternar_documento_ia`), `src/ui.py:939` (`_cancelar_documento_ia`). Tiempos y estados: verificación visual | cumple (tests y verificación visual del 2026-11-22) |
| 2 | [NUEVO] | Regenerar y cancelar: la pestaña conserva el documento anterior; la petición que termina después no cambia el historial ni el archivo, y no abre diálogos | Tests: `tests/test_persistencia.py:111` (`test_documento_de_generacion_cancelada_no_se_guarda_ni_se_exporta`), `:121` (`test_documento_de_generacion_vigente_se_guarda_y_se_exporta`). Punto de decisión: `src/ui.py:914` (`_recibir_documento_ia`), que descarta el resultado cancelado, y `src/persistencia.py:92` (`persistir_documento_si_vigente`). Pestaña, diálogos y archivo: verificación visual | cumple (tests y verificación visual del 2026-11-22) |
| 3 | [MODIFICA: sin spec] | Cerrar la ventana con una generación en curso pregunta; «no» sigue, «sí» cancela, cierra y no guarda | Código: `src/ui.py:495-504` (`_al_cerrar`). Sin test automático de la ventana: verificación visual | cumple (verificación visual del 2026-11-22) |

**Pendientes aceptados:**

- (a) La conexión HTTP de una generación cancelada no se corta: termina sola (en el peor caso unos 3,5 minutos) y su
  resultado se descarta.
- (b) «Escape» no cancela la generación (sugerencia no implementada).
- (c) El botón «■ Cancelar» no cambia de color.

### Verificación visual (2026-11-22)

Hecha por el orquestador sobre la ventana real, con un asistente simulado que ignora la cancelación y termina más
tarde (el peor caso).

- Criterio 1: al generar, el botón pasa a «■ Cancelar». Tras pulsarlo, la ventana queda libre en 31 ms (límite: 1 s):
  la pestaña dice «Generación cancelada», la barra «Generación de la minuta cancelada», «Generar» de las dos pestañas
  y el selector están habilitados, «Transcribir» vuelve a su estado anterior y la transcripción sigue intacta. Sin
  esperar al hilo abandonado se pudo generar el resumen, cargar otro archivo y abrir una entrada del historial, sin el
  aviso «Espera a que termine el proceso en curso.».
- Criterio 2: se regeneró y se canceló. La petición abandonada terminó después con un documento nuevo y, en otra
  pasada, con un 401. La pestaña siguió mostrando la minuta anterior con «↻ Regenerar», «Copiar» y «Guardar como…» y
  el estado «Generación cancelada · se conserva la minuta anterior». El historial y `reunion_minuta.md` (contenido y
  fecha de modificación) no cambiaron, no hubo diálogos ni se abrió el inicio de sesión, y la siguiente generación
  funcionó. En la primera generación cancelada no se guardó ni exportó nada.
- Criterio 3: al cerrar con una generación en curso se preguntó «Hay una generación de la minuta en curso. ¿Cancelarla
  y salir?». Con «No» la generación siguió. Con «Sí» la ventana se cerró y, al terminar la petición abandonada, el
  historial y el archivo quedaron sin cambios.
