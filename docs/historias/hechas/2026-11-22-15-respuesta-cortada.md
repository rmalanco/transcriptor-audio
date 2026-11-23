# 15 · Avisar en el documento cuando Copilot cortó una respuesta

> Origen: `BACKLOG.md`, «Salud del código» #25 — hallazgo A-11, escenario B (antes «posible») — historia derivada de
> `docs/historias/hechas/2026-11-22-07-documento-incompleto.md`. Carril propuesto en el backlog: S; **esta historia lo
> sube a M** (ver «Supuestos», 1). Reglas de oro 1, 3, 4 y 10 de `AGENTS.md`. Confirmación con Copilot real en
> `docs/integracion-copilot.md` §«Comprobado con peticiones reales (2026-11-22)»: una respuesta cortada por longitud
> termina con `finish_reason: "length"` y `data: [DONE]`; una normal, con `"stop"` y `[DONE]`. `content_filter` y un
> stream sin `[DONE]` no están comprobados. Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver
> «Supuestos»).

## Historia

Como usuario, quiero que la app me avise en el documento cuando Copilot cortó una respuesta (por longitud, por el
filtro de contenido o porque la respuesta terminó sin cierre), también en las notas de una parte, para no dar por
completo un documento truncado.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dada una transcripción que cabe en una sola parte, con la revisión de fidelidad desactivada,
  y una respuesta de redacción que trae la minuta con todas sus secciones pero termina con `finish_reason: "length"` y
  `[DONE]`, cuando genero la minuta, entonces el documento que se muestra, se guarda en el historial y se exporta termina,
  tras una línea horizontal, con «> Nota de la aplicación: Copilot cortó su respuesta antes de terminarla (límite de
  longitud del modelo); este documento puede estar incompleto. No lo des por completo:
  vuelve a generarlo o complétalo con la transcripción.». Con `finish_reason: "content_filter"` el paréntesis dice
  «(filtro de contenido de Copilot)»; con un stream que termina sin `[DONE]` y sin ningún `finish_reason`, dice «(la
  respuesta terminó sin la marca de cierre)». La nota no aparece en ninguna petición enviada a Copilot. Con
  `finish_reason: "stop"`, con o sin `[DONE]`, o con `[DONE]` sin `finish_reason`, no hay nota. Lo mismo vale para el
  resumen. (antes: con `"length"` solo quedaba un `warning` en el log; con `"content_filter"` o sin cierre, ni eso; el
  documento se mostraba, guardaba y exportaba sin aviso y la línea de estado decía «Listo en … s con …»)
- [ ] [MODIFICA: sin spec] Dada una transcripción que se procesa en 3 partes y una petición de notas de la parte 2 que
  termina con `finish_reason: "length"`, cuando genero la minuta, entonces el documento termina, tras una línea
  horizontal, con «> Nota de la aplicación: Copilot cortó antes de terminarlas las notas de la parte 2 de 3 (límite de
  longitud del modelo); lo que se dijo en esa parte puede faltar en este documento.», seguida de la nota de las partes
  que ya existe. Esas notas no se conservan: cuando después genero el resumen con el mismo modelo, Copilot recibe otra
  vez la petición de notas de la parte 2 (y no las de las partes 1 y 3) y la de redacción; si esa vez no se corta, el
  resumen no lleva la nota de notas cortadas. Con varias partes cortadas, una sola nota las nombra en orden, cada una
  con su motivo: «… las notas de las partes 2 (límite de longitud del modelo) y 5 (filtro de contenido de Copilot) de
  8 …». (antes: las notas cortadas se usaban y se guardaban en memoria como cualquier otra, se reutilizaban en el
  siguiente documento y el documento no decía nada)
- [ ] [MODIFICA: documentos-ia › Documento entregado aunque falle una pasada posterior] Dada una redacción completa
  (`"stop"`) y la revisión de fidelidad activada, cuando la respuesta de la revisión termina cortada por cualquiera de
  los tres motivos, entonces la revisión se descarta aunque conserve las secciones, el documento que se entrega es el
  redactado y lleva la nota que ya existe «> Nota de la aplicación: la revisión de fidelidad no se pudo completar
  (Copilot cortó la respuesta: límite de longitud del modelo); este documento no está revisado.», sin la nota de
  respuesta cortada del criterio 1. Del mismo modo, si la respuesta a la petición de completar las secciones que
  faltaban llega cortada, se entrega el borrador con «> Nota de la aplicación: no se pudieron pedir de nuevo a Copilot
  las secciones que faltaban (Copilot cortó la respuesta: límite de longitud del modelo).» y, si siguen faltando, la
  nota de secciones sin la frase «que Copilot no devolvió ni al pedírselas de nuevo»; y si el borrador era una
  redacción cortada, lleva también la nota del criterio 1. (antes: una revisión cortada sustituía al documento si
  conservaba sus secciones, y un reintento de secciones cortado lo sustituía si le faltaban menos, en los dos casos sin
  ningún aviso)

**Orden de las notas.** Todas siguen bajo una sola línea horizontal, separadas por una línea en blanco: primero la de
respuesta cortada (criterio 1), después la de notas de partes cortadas (criterio 2) y luego las que ya existen, en su
orden actual (no se pudieron pedir las secciones, secciones que faltan, revisión no completada, partes). El título
`# Minuta:` y la línea `**Fecha:**` no cambian.

Cómo se verifican:

- **Con tests sin red** (`httpx.stream` simulado que guarda el cuerpo de cada petición y decide, según el prompt, el
  contenido, el `finish_reason` y si envía `[DONE]`; regla 3):
  - `test_redaccion_cortada_por_longitud_lleva_la_nota_de_respuesta_cortada`: una parte, minuta con todas las
    secciones y `"length"`; la minuta termina con la nota exacta del criterio 1 y ningún cuerpo enviado contiene
    «Nota de la aplicación» (criterio 1).
  - `test_redaccion_cortada_por_el_filtro_de_contenido_lo_dice` y
    `test_stream_sin_done_ni_finish_reason_cuenta_como_cortado`: el paréntesis cambia según el motivo (criterio 1).
  - `test_respuesta_completa_no_lleva_nota_de_corte`, parametrizado: `"stop"` con `[DONE]`, `"stop"` sin `[DONE]` y
    `[DONE]` sin `finish_reason` no dan nota; también con el resumen (criterio 1).
  - `test_notas_de_una_parte_cortadas_llevan_la_nota_y_no_se_conservan`: 3 partes, `peticiones_paralelas` en 1, la
    parte 2 cortada la primera vez; la minuta lleva la nota de la parte 2 antes de la de partes, y el resumen
    siguiente, con el mismo asistente, envía exactamente 2 peticiones (notas de la parte 2 y redacción) y no lleva la
    nota de notas cortadas (criterio 2).
  - `test_varias_partes_cortadas_se_nombran_en_una_sola_nota`: partes 2 (`"length"`) y 5 (`"content_filter"`) de 8
    (criterio 2).
  - `test_revision_cortada_se_descarta_y_lo_dice` y `test_reintento_de_secciones_cortado_entrega_el_borrador_con_nota`
    (criterio 3).
  - `test_notas_de_corte_van_primero_bajo_una_sola_linea_horizontal`: redacción cortada, una parte cortada y 2 partes;
    una sola línea `---`, las notas en el orden indicado, título y fecha iguales.
  - Siguen pasando los tests de las historias 04, 06 y 07 y los de las pasadas posteriores (#28).
- **Verificación manual:** no se puede forzar un corte desde la ventana sin cambiar el código; basta con los tests. Si
  algún día una minuta real llega cortada, abrir el `.md` en un visor de Markdown y comprobar que la nota se ve
  separada por la línea horizontal.

## Plan

- La lectura de cada respuesta de Copilot distingue tres finales anómalos (corte por longitud, por el filtro de
  contenido, o sin `[DONE]` y sin motivo) y devuelve el texto junto con el motivo del corte, si lo hay; el `warning`
  del log se mantiene para los tres.
- La redacción guarda el motivo del corte junto al texto del documento; si una pasada posterior sustituye al documento,
  el motivo es el de la respuesta que quedó.
- La petición de completar secciones y la revisión de fidelidad tratan una respuesta cortada como un fallo de esa
  pasada, con el mismo camino y las mismas notas que hoy tiene un error recuperable (#28).
- Las notas de una parte cortada se usan para el documento en curso pero no se guardan en la memoria de notas; el
  documento recuerda qué partes se cortaron y por qué.
- Las notas nuevas se añaden en el mismo punto que las existentes, antes que ellas y bajo la misma línea horizontal;
  tests sin red de los tres criterios.

Archivos del `/pair` (lista cerrada): `src/asistente_ia.py`, `tests/test_asistente_ia.py`. El delta de spec lo escribe
`/cerrar` en `docs/specs/documentos-ia.md`.

## Fuera de alcance

- Avisar antes de redactar si las notas superan el límite de entrada del modelo (#26, historia 16).
- Reintentar automáticamente una respuesta cortada, pedir la continuación al modelo o enviar `max_tokens`: el aviso
  basta para no dar el documento por completo, y repetir la petición cuesta otra petición sin garantía de que no se
  vuelva a cortar.
- Cambiar «Listo en … s con …» de la línea de estado de un documento cortado (la sugerencia equivalente de la historia
  07 sigue abierta).
- Revisar contra la transcripción original (#23), el panel de configuración y el soporte de `/responses`.
- Un corte de conexión a mitad de la respuesta que `httpx` reporta como error: ya se reintenta como cualquier fallo de
  conexión y no cambia.
- La CLI, que no genera documentos.

## Sugerencias

- Devolver el motivo del corte junto al texto desde la función que hace las peticiones, en vez de guardarlo en el
  asistente: las partes van en paralelo, y un atributo compartido mezclaría los motivos de partes distintas.
- Reutilizar `_motivo` para el texto entre paréntesis de las pasadas posteriores no hace falta: los tres motivos son
  textos fijos de la app, ya de una sola línea.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **Carril M, no S.** El cambio toca las cuatro clases de respuesta (notas de cada parte, redacción, completar
   secciones y revisión), la memoria de notas conservadas y el bloque de notas de la aplicación, con tres criterios y
   unos diez tests. No es un arreglo de una línea; por eso tiene historia.
2. **El caso que más duele** es una minuta con todas sus secciones cortada a mitad de «Próximos pasos» o de la tabla
   de tareas: el aviso de secciones que faltan (historia 07) no salta, así que hoy nadie se entera. El criterio 1 lo
   cubre con un documento completo en secciones.
3. **`content_filter` y el stream sin cierre no están comprobados** con Copilot real (se forzó solo el corte por
   longitud). Se tratan según la API de OpenAI, con la que Copilot es compatible: `content_filter` es un
   `finish_reason` del último fragmento; un stream normal termina con un `finish_reason` y después `[DONE]`. Si
   Copilot no los envía nunca, esos tests siguen siendo válidos y el código simplemente no se ejerce.
4. **«Sin cierre» es no recibir ni `[DONE]` ni ningún `finish_reason`.** Si llega `"stop"` sin `[DONE]`, el modelo dijo
   que terminó y el contenido está completo: avisar sería una falsa alarma. Si llega `[DONE]` sin `finish_reason`,
   Copilot cerró el stream a propósito: tampoco se avisa. Un corte de red a mitad de la respuesta suele llegar como
   error de `httpx` y ya se reintenta.
5. **Una revisión o un reintento cortados se descartan** en vez de sustituir al documento: ninguno puede mejorar un
   documento si su propia respuesta está incompleta, y reutilizar el camino de error recuperable de #28 da notas que
   ya existen, sin textos nuevos. El documento entregado solo lleva la nota de respuesta cortada si es la redacción la
   que se cortó.
6. **Unas notas cortadas no se conservan**, para que al volver a generar se pidan de nuevo: conservarlas haría que el
   siguiente documento heredara el corte sin poder evitarlo (hoy solo se pierden al cambiar de modelo, cancelar, tras
   un 401 o al cerrar). Pedirlas otra vez cuesta una petición marcada como `agent`.
7. **Las notas nuevas van primero** porque explican por qué el documento puede estar incompleto antes que las que
   describen cómo se hizo (partes, revisión). Comparten la línea horizontal de la historia 07.
8. **Los textos** de las notas son propuestas, en el tono de las existentes; los tests comprueban el texto exacto.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 344 tests. Code review: revisión
del orquestador, listo para commit. Se quitó de la nota de respuesta cortada la coletilla «aunque tenga todas sus
secciones» (era incoherente cuando además faltan secciones) y se acepta el test extra
`test_reintento_completo_sustituye_a_la_redaccion_cortada_y_no_lleva_nota`. Delta de spec: `docs/specs/documentos-ia.md`,
con `Origen` en esta historia.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Redacción cortada por longitud, filtro de contenido o stream sin cierre: la nota dice el motivo y termina el documento (historial y `.md` incluidos); la nota no va a Copilot; respuesta completa, sin nota | Longitud, y ninguna petición contiene la nota: `tests/test_asistente_ia.py:1491`. Filtro de contenido: `:1506`. Stream sin `[DONE]` ni `finish_reason`: `:1516`. Respuestas completas, parametrizado: `:1528`. Implementación: `src/asistente_ia.py:215` (`_motivo_de_corte`), `:604` (`_leer_stream` marca `[DONE]`), `:581` y `:588` (`_completar` marca la respuesta), `:306` (`_nota_de_corte`), `:332` (`notas_de_la_aplicacion`) | cumple (tests). Pendiente aceptado: `content_filter` y stream sin `[DONE]` no comprobados con Copilot real; verificación manual en la ventana |
| 2 | [MODIFICA: sin spec] | Notas de una o varias partes cortadas: la nota nombra cada parte y su motivo; esas notas no se guardan y al volver a generar se piden de nuevo | Una parte, no se conservan y el resumen reenvía 2 peticiones: `tests/test_asistente_ia.py:1537`. Varias partes en una sola nota: `:1568`. Implementación: `src/asistente_ia.py:659` (no se guardan en caché), `:689` y `:690` (`cortes[n]`), `:312` (`_nota_de_cortes_de_partes`), `:333` | cumple (tests). Pendiente aceptado: verificación manual en la ventana |
| 3 | [MODIFICA: documentos-ia › Documento entregado aunque falle una pasada posterior] | Revisión o reintento de secciones cortados cuentan como fallo de esa pasada con el motivo «Copilot cortó la respuesta: <motivo>»; el borrador se entrega con su nota; la nota de respuesta cortada se mantiene si la redacción también se cortó | Revisión cortada, 3 motivos: `tests/test_asistente_ia.py:1595`. Reintento de secciones cortado: `:1608`. Reintento completo que sustituye a la redacción cortada: `:1652`. Orden de las notas, bajo una sola línea horizontal: `:1625`. Implementación: `src/asistente_ia.py:175` (`_sin_cortar`), `:737` y `:762` (llamadas), `:753` y `:779` (el motivo es el de la respuesta que queda), `:324` (`notas_de_la_aplicacion`) | cumple (tests). Pendiente aceptado: verificación manual en la ventana |

**Verificación:** los tests son sin red (`httpx.stream` simulado, regla 3). No hay verificación en la ventana: la nota
viaja en el texto del documento, que la ventana ya muestra, guarda y exporta. Confirmación con Copilot real: una
respuesta cortada por longitud termina con `finish_reason: "length"` y `[DONE]` (`docs/integracion-copilot.md`).

**Pendientes aceptados:**

- `content_filter` y el stream sin `[DONE]` ni `finish_reason` no se han comprobado con Copilot real. Se tratan según la
  API de OpenAI, con la que Copilot es compatible.
- Verificación manual en la ventana y en un visor de Markdown, no hecha: la nota al final del `.md` y su línea
  horizontal.
- La línea de estado «Listo en … s con …» de un documento cortado no cambia (fuera de alcance, sugerencia de la historia 07).
