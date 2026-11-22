# 07 · Avisar de un documento incompleto y conservar las partes ya procesadas

> Origen: `BACKLOG.md`, «Backlog» #3 — hallazgo A-11 (en parte posible) — carril M. Decisión en
> `goldfish_review_report.md`: aceptado, «Parte «posible»: confirmar con una respuesta real antes de planificar».
> Reglas de oro 1, 3, 4, 6 y 10 de `AGENTS.md`. Requiere la historia 06 (nota de la aplicación al final del documento).
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Se toma solo lo que el código
> confirma (escenario A de A-11 y las secciones que faltan); los escenarios B y C, «posibles», quedan como historias
> derivadas.

## Historia

Como usuario, quiero que la app me avise cuando un documento quedó incompleto y que conserve las partes ya procesadas
si una falla, para no pagar de nuevo toda la generación.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dada una transcripción que cabe en una sola parte y un modelo que devuelve la minuta sin
  «## Tareas y pendientes» ni «## Próximos pasos», también cuando la app le pide completarla, cuando genero la minuta,
  entonces el documento que muestra la pestaña Minuta, el que se guarda en el historial y el que se exporta como
  `<nombre>_minuta.md` terminan, tras una línea horizontal, con la nota «> Nota de la aplicación: a este documento le
  faltan secciones obligatorias que Copilot no devolvió ni al pedírselas de nuevo: Tareas y pendientes, Próximos
  pasos. No lo des por completo: vuelve a generarlo o complétalo con la transcripción.». La nota no aparece en ninguna
  petición enviada a Copilot, y no se añade si el documento final (tras completar secciones, la revisión de fidelidad
  y el post-proceso de la minuta) tiene todas las secciones. Lo mismo vale para el resumen con «Resumen», «Puntos
  clave» y «Conclusiones». (antes: si el reintento tampoco traía las secciones, el documento se mostraba, se guardaba
  y se exportaba sin ningún aviso, la línea de estado decía «Listo en … s con …» y solo quedaba un `warning` en el
  log)
- [ ] [MODIFICA: sin spec] Dada una transcripción que se procesa en 8 partes, con `ia.peticiones_paralelas` en 3, en
  la que la petición de notas de la parte 7 recibe 429 en los 4 intentos, cuando genero la minuta, entonces la
  pestaña muestra «No se pudo generar: falló la parte 7 de 8: GitHub Copilot respondió 429: … Se conservan las notas
  de las <N> partes que terminaron; al volver a generar solo se pedirán las que faltan.», el diálogo de error muestra
  el mismo motivo (desde «falló la parte…») y no se envía la petición de redacción. Cuando después pulso
  «✨ Generar minuta» (o genero el resumen) con el mismo modelo y Copilot ya responde, entonces Copilot recibe solo
  las peticiones de notas de las partes que no terminaron (la 7, y la 8 si no había terminado) y la de redacción: ninguna petición contiene el
  texto de las partes 1 a 6, y la petición de redacción lleva las notas de las 8 partes en orden. (antes: las notas
  de las partes que habían terminado se descartaban, también las de las partes que seguían en curso al fallar la 7,
  que se esperaban igual; el error no decía qué parte falló; y volver a generar enviaba otra vez las 8 peticiones de
  notas además de la de redacción)
- [ ] [NUEVO] Dada una transcripción de unos 80 000 caracteres con `ia.max_caracteres_bloque` en 60 000, que se
  procesa en 2 partes, y un modelo que devuelve la minuta sin «## Tareas y pendientes» también cuando se le pide
  completarla, cuando genero la minuta, entonces el documento termina con una sola línea horizontal seguida de dos
  notas de la aplicación separadas por una línea en blanco: primero la de las secciones que faltan («… le faltan
  secciones obligatorias …: Tareas y pendientes. …») y después la de la historia 06 («… la transcripción se procesó
  en 2 partes …»). El título de la línea `# Minuta:`, la línea `**Fecha:**` y las secciones presentes no cambian, y
  ninguna de las dos notas aparece en las peticiones enviadas a Copilot.

Cómo se verifican:

- **Con tests sin red** (`httpx.stream` simulado que guarda el cuerpo de cada petición y decide la respuesta según el
  prompt, regla 3; la espera entre reintentos se anula en el test):
  - Una parte, revisión desactivada, el modelo omite dos secciones en la redacción y en el reintento: se envían 2
    peticiones, ningún cuerpo contiene «Nota de la aplicación» y la minuta termina con la nota que nombra las dos
    secciones. Si el reintento las devuelve, o si la revisión activada las restituye, no hay nota. Lo mismo con el
    resumen (criterio 1).
  - El punto de persistencia, con historial temporal y un documento con la nota de secciones faltantes, la deja
    intacta en la entrada del historial y en el `.md` junto al audio (criterio 1).
  - 8 partes con `peticiones_paralelas` en 1 (orden fijo): la parte 7 responde 429 cuatro veces. La primera
    generación lanza el error con «parte 7 de 8» y el número de partes conservadas, y no envía la redacción. La
    segunda, con el mismo asistente, envía exactamente 3 peticiones (notas de la parte 7, notas de la parte 8 y
    redacción); ningún cuerpo contiene «parte 1 de 8» a «parte 6 de 8», y el de la redacción contiene «Notas de la
    parte 1» a «Notas de la parte 8» en orden. Con `peticiones_paralelas` en 3, las partes que estaban en curso al
    fallar la 7 y terminan bien tampoco se repiten (criterio 2).
  - 2 partes y una sección que falta tras el reintento: una sola línea `---` al final, la nota de secciones antes que
    la de partes, título y fecha iguales, ninguna nota en los cuerpos enviados (criterio 3).
  - Siguen pasando los tests de cancelación (historia 04) y los de la nota de la historia 06.
- **Verificación manual:** con el guion que conduce la ventana real con un asistente simulado, provocar el fallo de
  una parte, volver a generar sin cambiar de modelo y comprobar en Registro que solo se piden las partes que faltan;
  abrir el `<nombre>_minuta.md` incompleto en un visor de Markdown y comprobar que la nota se ve separada por la línea
  horizontal.

## Plan

- Las notas de cada parte quedan en la memoria del asistente en cuanto esa parte termina, asociadas a su posición y a
  la transcripción de la que salen; al generar otra vez solo se piden las que faltan, y el documento se redacta solo
  cuando están todas.
- Si una parte falla, no se lanzan las que aún no empezaron, las que estaban en curso terminan y se conservan, y el
  error dice qué parte falló y cuántas se conservan.
- Después de todas las pasadas del modelo y del post-proceso, en el mismo punto donde la historia 06 añade su nota,
  la app comprueba qué secciones obligatorias faltan en el documento final y, si falta alguna, añade la nota de
  secciones faltantes; las dos notas comparten una sola línea horizontal.
- El documento incompleto se muestra, se guarda en el historial y se exporta como cualquier otro: la pestaña, la
  persistencia y la exportación no cambian.
- Tests sin red del asistente (cuerpos y número de peticiones, orden de las notas, partes conservadas) y uno del
  punto de persistencia con historial temporal.

## Fuera de alcance

- Detectar una respuesta cortada por `finish_reason: length` o `content_filter`, o un stream que termina sin
  `[DONE]` (escenario B de A-11, «posible»), y avisar antes de enviar si las notas superan `max_prompt_tokens`
  (escenario C, «posible»): la decisión de A-11 pide confirmarlos con una respuesta real, y aquí no se puede hacer
  ninguna. Ver «Historias derivadas».
- Respetar `Retry-After` en los 429 (dirección del arreglo de A-11): ver «Historias derivadas».
- Entregar el documento ya redactado cuando falla la pasada de completar secciones o la revisión de fidelidad, en vez
  de un error: ver «Historias derivadas».
- Conservar las notas tras cancelar, tras cambiar de modelo, tras un 401 o al cerrar la app, y guardarlas en disco o
  en el historial: siguen en la memoria del asistente, que hoy se descarta en esos casos.
- Redactar un documento con las notas de solo algunas partes: si falta una parte, no hay documento.
- Cambiar la línea de estado «Listo en … s con …» de un documento incompleto (ver «Sugerencias»).
- Cambios en la cancelación (historia 04): tras cancelar no se inicia nada nuevo y no se guarda nada.
- Soporte de `/responses`, el 401 del modo `auto` («Salud del código» #7), consultar el catálogo una sola vez (#10) y
  revisar contra la transcripción original (historia derivada de la 06).
- La CLI, que no genera documentos.

## Sugerencias

- Detectar antes el fallo de una parte: hoy se recogen los resultados en orden (`[f.result() for f in futuros]` en
  `_notas_por_bloque`), así que si falla la parte 2 mientras la 1 sigue en curso, el ejecutor sigue lanzando las
  partes 4, 5… hasta que la 1 termina. Recogerlos según terminan (`as_completed`) corta antes el envío de partes que
  se pagarían y, con este cambio, se conservarían pero no se habrían pedido aún.
- La clave de cada parte conservada debe incluir su posición y el total, no solo su texto: el prompt de notas dice
  «parte n de total», y la misma frase en otra división daría otro prompt.
- Calcular las secciones que faltan con la función que ya usa el reintento (`secciones_faltantes`), sobre el documento
  final, después de la revisión: la revisión se acepta comparando cuántas secciones faltan, no cuáles, así que puede
  devolver una sección y perder otra.
- Si se quiere que el aviso se vea también sin abrir el documento, cambiar «Listo en …» por «Incompleto en …» en la
  línea de estado. No lo pide la auditoría.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele es doble**: (a) dar por buena una minuta a la que le falta la sección de tareas sin que
   nadie avise, que cubre el criterio 1; y (b) que falle la parte 7 de 8 de una reunión de tres horas y haya que
   pedir otra vez las 8, que cubre el criterio 2. Los dos están confirmados en el código, así que caben en una
   historia sin esperar a una llamada real.
2. **Los escenarios B y C quedan fuera** porque la decisión de A-11 dice «confirmar con una respuesta real antes de
   planificar» y aquí no se puede. El criterio 1 cubre el efecto más visible de una minuta cortada por longitud: si la
   respuesta se corta, las últimas secciones faltan y aparece la nota. No cubre un corte a mitad de la última sección
   ni unas notas de parte cortadas.
3. **Un documento incompleto se guarda en el historial y se exporta, con la nota.** Regla 6: el trabajo no se
   descarta; ya se pagó y puede servir como borrador. La nota viaja con el documento a la pestaña, al historial y al
   `.md`, así que nadie lo recibe sin el aviso. No guardarlo obligaría a pagar otra vez la generación entera para ver
   lo que ya se tenía.
4. **El aviso es una nota de la aplicación al final del documento, con el patrón de la historia 06**: la añade la
   app después de todas las pasadas, ningún prompt la contiene y el modelo no la puede reescribir (regla 4). Va al
   final para no tocar `# Minuta:` (de donde el historial saca el título) ni `**Fecha:**`. Si las dos notas aplican,
   va primero la de secciones que faltan, que es la más grave, y comparten una sola línea horizontal para no partir
   el documento en tres trozos.
5. **Las partes conservadas viven en la memoria del asistente**, como la caché de notas de hoy. Sobreviven a un error
   que no sea un 401 (la ventana conserva el asistente en ese caso) y se pierden al cancelar, al cambiar de modelo,
   tras un 401 o al cerrar la app, porque en todos esos casos la ventana descarta el asistente.
6. **«Pagar» se mide en peticiones.** Según `docs/integracion-copilot.md` (sin verificar), solo las peticiones con
   `x-initiator: user` cuentan como premium, y las de notas de cada parte van como `agent`. Repetirlas cuesta sobre
   todo tiempo, tokens y riesgo de otro 429. El criterio 2 cuenta peticiones porque es lo que se puede comprobar sin
   red.
7. **Los textos** de la nota y del error son propuestas, no requisitos de la auditoría. La nota nombra las secciones
   sin `#` para que se lea como texto.
8. **Una sección se considera ausente con la regla que ya usa el reintento**: ninguna línea empieza por su título. Un
   título escrito de otra forma (por ejemplo «## Tareas») cuenta como ausente, igual que hoy dispara el reintento; la
   nota puede ser un falso positivo en ese caso.
9. **El criterio 3 es [NUEVO] porque la historia 06 aún no está cerrada.** Si `/cerrar` de la 06 llega antes que
   `/pair` de esta, la nota de la 06 sigue igual (sigue cerrando el documento tras la línea horizontal) y el criterio
   solo añade la convivencia; si la revisión de la 06 cambia el formato de su nota, el criterio 3 se adapta.

## Historias derivadas (para el backlog)

- Como usuario, quiero que la app avise en el documento cuando Copilot cortó una respuesta (por longitud, por el
  filtro de contenido o porque el stream terminó sin cierre), también en las notas de una parte, para no dar por
  completo un documento truncado. — hallazgo A-11, escenario B (posible): confirmar antes con una respuesta real qué
  `finish_reason` envía Copilot y cuándo — carril S.
- Como usuario de reuniones muy largas, quiero que la app me avise antes de redactar si las notas de todas las partes
  superan el límite de entrada del modelo, para no pagar las notas y fallar en la redacción. — hallazgo A-11,
  escenario C (posible) — carril M; depende de «Salud del código» #10 (catálogo una sola vez), que es de donde saldría
  `max_prompt_tokens`.
- [🟡] Respetar `Retry-After` en los 429 de Copilot en vez de la espera fija de 2, 4 y 8 s — hallazgo A-11 (dirección
  del arreglo) — carril S.
- Como usuario, quiero que, si falla la pasada de completar secciones o la revisión de fidelidad, la app me entregue
  el documento ya redactado con una nota de la aplicación en vez de un error, para no pagar otra vez la redacción. —
  comportamiento del código (`_generar` no protege esas dos pasadas), relacionado con A-11 — carril S.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 186 tests. Code review: hecho con
contexto limpio; el primer veredicto fue «arreglar antes» con cuatro hallazgos (error de modelo no autorizado envuelto
como fallo de parte; límite de la caché que podía expulsar notas de la generación en curso; faltaban tests con partes
en paralelo; clave de caché con modelo no cadena). Los cuatro se arreglaron y el orquestador lo verificó (186 tests,
estables en 10 ejecuciones seguidas): listo para commit. Delta de spec: `docs/specs/documentos-ia.md`, tres
comportamientos nuevos con `Origen` en esta historia.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Secciones que siguen faltando tras el reintento: la nota nombra las secciones y termina la minuta y el resumen (con el historial y el `.md`), no va a Copilot; sin faltantes, sin nota | Minuta que falta una sección tras el reintento: `tests/test_asistente_ia.py:672` (`test_minuta_a_la_que_le_falta_una_seccion_tras_el_reintento_lleva_la_nota`). No se envía a Copilot: `:686`. Documento completo, sin nota: `:698`. Resumen: `:709`. Historial y `.md` intactos: `tests/test_persistencia.py:362`. Implementación: `src/asistente_ia.py:213` (`notas_de_la_aplicacion`), `:555` y `:581` (secciones que faltan), `:583` (`_con_nota`) | cumple (tests). Pendiente aceptado: verificación manual |
| 2 | [MODIFICA: sin spec] | Parte que falla (7 de 8, 429 en todos los intentos): error con «falló la parte N de M», sin redacción; al volver a generar solo se piden las partes que faltan; familia no autorizada, modelo vacío o `auto` sin modelo válido dan el mismo error que con una parte | Error «falló la parte»: `tests/test_asistente_ia.py:765` (`test_fallo_de_una_parte_dice_cual_y_cuantas_se_conservan`). Solo las partes que faltan: `:781`; notas conservadas para el otro documento: `:808`; partes en curso que terminan no se repiten: `:913`. Con más partes que la caché: `:892`. Frases singular y ninguna: `:979`, `:992`. Error sin partes: `:844`, `:859`, `:873`. El 401 no se envuelve: `:967`. Implementación: `src/asistente_ia.py:458` (`_notas_por_bloque`), `:522` (mensaje de fallo), `:235` (`_frase_de_partes_conservadas`), `:313` (`_modelo_para_peticion`, validación antes de enviar nada) | cumple (tests). Pendiente aceptado: diálogo de error en la ventana real |
| 3 | [MODIFICA: sin spec] | Con 2 partes y una sección que falta: una sola línea horizontal, primero la nota de secciones y después la de partes; título y fecha no cambian | `tests/test_asistente_ia.py:721` (`test_minuta_de_varias_partes_y_seccion_que_falta_lleva_las_dos_notas`) y `:660` (`test_dos_notas_van_bajo_una_sola_linea_horizontal`). Implementación: `src/asistente_ia.py:213` | cumple (tests). Pendiente aceptado: nota al final en la ventana y en el `.md` |

**Pendientes aceptados:**

- Verificación manual en la ventana real, no hecha: ver el diálogo de error «falló la parte N de M…» y la nota al final
  del documento, y abrir un `<nombre>_minuta.md` incompleto en un visor de Markdown para comprobar que la nota queda
  separada por la línea horizontal.
- Las notas conservadas viven en memoria (`src/asistente_ia.py`): se pierden al cancelar, cambiar de modelo, tras un
  401 o al cerrar la app.
- En modo `auto` la caché no distingue qué modelo resolvió Copilot para cada parte.
- Si el documento ya termina con una línea horizontal, la nota añade otra (cosmético).
