# 06 · Advertir de que el documento se redactó a partir de notas

> Origen: `BACKLOG.md`, «Salud del código» #8 — hallazgo A-05 — carril M. Decisión en `goldfish_review_report.md`:
> aceptado, «Afecta a la regla de fidelidad de la minuta». Reglas de oro 1, 2, 3, 4 y 10 de `AGENTS.md`.
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). De las dos salidas que ofrece el
> backlog se elige la segunda, advertir; la primera queda como historia derivada.

## Historia

Como usuario que genera la minuta o el resumen de una reunión larga, quiero que el documento diga que se redactó a
partir de notas intermedias y no de la transcripción completa, y que la app no presente como «revisado contra la
transcripción» lo que solo se contrastó con esas notas, para no dar por bueno un dato que nadie dijo.

## Criterios de aceptación

- [ ] [NUEVO] Dada una transcripción de unos 80 000 caracteres con `ia.max_caracteres_bloque` en 60 000, que se
  procesa en 2 partes, cuando genero la minuta, entonces el documento que muestra la pestaña Minuta, el que se guarda
  en el historial y el que se exporta como `<nombre>_minuta.md` terminan, tras una línea horizontal, con la nota
  «> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento se redactó a partir de notas
  extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, cifras y condiciones con la
  transcripción antes de darlo por bueno.». La nota no aparece en ninguna petición enviada a Copilot, y el título, la
  fecha y las secciones de la minuta no cambian. Lo mismo vale para el resumen, también cuando reutiliza las notas ya
  extraídas para la minuta sin pedir notas nuevas.
- [ ] [MODIFICA: sin spec] Dada la transcripción del criterio 1, `ia.revision_fidelidad: true` y una nota de parte que
  atribuye a Ana una tarea que nadie dice en la transcripción, cuando genero la minuta y la revisión la deja igual,
  entonces mientras dura la revisión la línea de estado de la pestaña dice «Revisando fidelidad con las notas de las 2
  partes…», la petición de revisión lleva como fuente esas notas y no el texto de la transcripción, y la nota del
  criterio 1 añade al final «La revisión de fidelidad se hizo contra esas notas, no contra la transcripción.».
  (antes: la línea de estado decía «Revisando fidelidad con la transcripción…» aunque la fuente fueran las notas, y el
  documento no llevaba ninguna advertencia, así que la tarea inventada quedaba en la minuta como si se hubiera
  revisado contra la transcripción)
- [ ] [NUEVO] Dada una transcripción de exactamente 60 000 caracteres con `ia.max_caracteres_bloque` en 60 000 y la
  revisión activada, cuando genero la minuta, entonces el documento no lleva la nota, la línea de estado dice
  «Revisando fidelidad con la transcripción…» y la petición de revisión lleva la transcripción completa. Con 60 001
  caracteres la transcripción se procesa en 2 partes y el documento termina con la nota del criterio 1, que dice «en 2
  partes».

Cómo se verifican:

- **Con tests sin red** (`httpx.stream` simulado que guarda el cuerpo de cada petición, regla 3):
  - Transcripción de 2 partes: ningún cuerpo enviado contiene «Nota de la aplicación»; la minuta devuelta termina con
    la nota; su título (el de la línea `# Minuta:`), la línea `**Fecha:**` y las secciones de `SECCIONES_MINUTA` son
    los mismos que sin la nota. Después, el resumen con el mismo asistente no envía peticiones de notas y también
    termina con la nota (criterio 1).
  - Con la revisión activada y respuestas simuladas en las que las notas y el documento atribuyen a Ana una tarea que
    no está en la transcripción: los mensajes de progreso incluyen «Revisando fidelidad con las notas de las 2
    partes…»; el cuerpo de la petición de revisión contiene «Notas de la parte 1» y no contiene ninguna línea de la
    transcripción; la minuta termina con la nota y la frase de la revisión (criterio 2).
  - Límite: 60 000 caracteres dan una sola parte, sin nota, con el mensaje «Revisando fidelidad con la transcripción…»
    y la transcripción completa en el cuerpo de la revisión; 60 001 dan 2 partes y la nota (criterio 3).
  - El punto de persistencia, con historial temporal y asistente simulado que devuelve un documento con la nota, la
    deja intacta en la entrada del historial y en el `.md` junto al audio (criterio 1).
  - Siguen pasando los tests de cancelación: tras cancelar no se inicia la revisión y no se devuelve ningún documento,
    así que tampoco se añade la nota.
- **Verificación manual:** abrir el `<nombre>_minuta.md` exportado en un visor de Markdown y comprobar que la nota se
  ve separada por la línea horizontal y que la última línea de «Próximos pasos» no se convierte en un título.

## Plan

- El asistente ya sabe en cuántas partes dividió la transcripción. Cuando son 2 o más, al final, después de todas
  las pasadas del modelo (redacción, completar secciones, revisión y post-proceso de la minuta), la app añade la nota
  al documento. Así ningún modelo la ve ni la puede reescribir, como la fecha.
- La frase sobre la revisión se añade solo si la revisión de fidelidad está activada y hubo más de una parte.
- El mensaje de progreso de la revisión nombra la fuente real: la transcripción o las notas de N partes.
- La pestaña, el historial y la exportación no cambian: ya guardan y muestran el texto que devuelve el asistente.
- Tests sin red del asistente (cuerpos de las peticiones, mensajes de progreso, límite de 60 000 y 60 001 caracteres
  y notas reutilizadas) y uno del punto de persistencia con historial temporal.

## Fuera de alcance

- Revisar contra la transcripción original (la otra salida del backlog): ver «Historias derivadas» y «Supuestos» 2.
- Que la revisión se acepte solo contando secciones, de modo que una revisión que borre tareas o acuerdos pasa (la
  segunda mitad del escenario de A-05, que el punto #8 del backlog no recoge): ver «Historias derivadas».
- Cambiar qué texto recibe la revisión, o si se hace, con más de una parte: sigue revisando contra las notas, que
  aún detecta errores introducidos al redactar desde ellas.
- Cambiar los prompts. En particular, que los de minuta y resumen llamen «Transcripción» a las notas, y el de revisión
  «TRANSCRIPCIÓN» (ver «Sugerencias»).
- El valor por defecto de `revision_fidelidad` (`false` en el YAML, `True` en el código) y el comentario del YAML
  «2.ª pasada contra la transcripción»: los lleva la historia 05 (módulo de configuración, «Salud del código» #6),
  que tiene esa decisión pendiente y está editando `config/settings.yaml`.
- Avisar de un documento incompleto o truncado y conservar las partes ya procesadas (A-11, «Backlog» #3).
- Marcar los documentos en la lista del historial o en la línea «Listo en … s con …»: la nota ya viaja con el
  documento a los tres sitios.
- Añadir la nota a documentos generados antes de este cambio.
- Soporte de `/responses`, familias no autorizadas (historia 03) y cancelación (historia 04): no cambian.
- La CLI, que no genera documentos.

## Sugerencias

- Añadir la nota en un solo punto de `AsistenteIA._generar`, justo antes de devolver el documento, y que
  `generar_minuta` aplique su post-proceso sobre el documento sin la nota, o comprobar que ese post-proceso no la
  toca: `normalizar_tabla_tareas` solo mira líneas con `|` y el `re.sub` de la fecha solo la primera `**Fecha:**`,
  así que hoy no la tocaría. Lo más simple es que `_generar` reciba el post-proceso o que la nota se añada en los dos
  `generar_*`; decidirlo en `/pair` según lo que quede más corto.
- Dejar una línea en blanco antes de `---`: si la línea horizontal va pegada a un párrafo, Markdown convierte ese
  párrafo en un título (encabezado setext).
- Cuando la historia 05 libere `config/settings.yaml`, corregir el comentario de `revision_fidelidad` para que diga
  que, con más de una parte, la pasada es contra las notas.
- Señal concreta para más adelante: con más de una parte, `PROMPT_MINUTA` y `PROMPT_RESUMEN` presentan las notas
  bajo «Transcripción:», y `PROMPT_REVISION` bajo «TRANSCRIPCIÓN». Llamarlas «Notas de la transcripción» sería más
  honesto con el modelo, pero cambia el texto que recibe y no lo pide la auditoría.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es que la minuta de una reunión larga afirme algo que nadie dijo y que la app lo
   presente como revisado contra la transcripción, cuando solo se comparó con unas notas que ya traían el error. El
   criterio 2 lo cubre: el progreso nombra la fuente real y el documento lo dice por escrito.
2. **Se elige advertir (B) y no revisar contra el original (A)**, con estos números, calculados con el código
   (`dividir_texto`, longitudes de los prompts) para una reunión de 90 minutos de ~80 000 caracteres y
   `max_caracteres_bloque` 60 000. La transcripción se divide en 2 partes de ~40 000 (40 091 y 39 909 con líneas de
   40 a 110 caracteres). Los prompts fijos miden: sistema 1 030, notas 335, minuta 1 244, resumen 498 y revisión 707
   caracteres. Se suponen ~8 000 caracteres de notas por parte (no medido) y una minuta de ~5 000.
   - **Hoy, con la revisión activada:** 4 peticiones (5 si hay que completar secciones). Notas: 2 × ~41 400; redacción:
     ~18 300; revisión contra las notas: ~22 700. En total, ~124 000 caracteres. Con el YAML versionado
     (`revision_fidelidad: false`) son 3 peticiones y ~101 000, sin ninguna revisión.
   - **A en una petición:** la revisión pasa a ~86 700 caracteres (+~64 000 frente a la de hoy) y manda 80 000 de
     transcripción en una sola petición, por encima del límite que el usuario configura justo para eso. Con 3 horas
     (~160 000, que hoy son 3 partes de ~53 300) serían ~167 000 caracteres en una petición, unos 40 000–55 000
     tokens a 3–4 caracteres por token (estimación). No se sabe si cabe: el código no consulta `max_prompt_tokens`
     (A-11, escenario C) y no hay llamadas reales para comprobarlo.
   - **A por partes:** 2 revisiones de ~46 700 caracteres (+1 petición y +~71 000 caracteres), en serie y no en
     paralelo, porque cada una corrige el documento que deja la anterior. Con 3 horas, 3 de ~60 000. Y no resuelve el
     caso que duele: quien revisa la parte 1 no ve la 2. Con el prompt actual («Datos que no aparecen en la
     transcripción») borraría datos ciertos de la otra parte, lo que va contra la regla 4. Si se le dice que ignore lo
     que no está en su fragmento, ya no puede detectar un dato inventado. Hacerlo bien exige un diseño (carril L).
   - **B:** 0 peticiones y 0 caracteres más; vale también con la revisión desactivada, que es como viene el YAML
     desde el primer commit, y se comprueba entera con tests sin red.
3. **La advertencia la pone la app dentro del documento, al final, en una cita que empieza por «Nota de la
   aplicación:»**, porque es lo único que viaja a los tres sitios donde se lee la minuta: pestaña, historial y `.md`
   exportado. La línea de estado es efímera. Al añadirse después de todas las pasadas, el modelo no la ve ni la puede
   confundir con contenido de la reunión, como pasa con la fecha (regla 4). Va al final y no arriba para no tocar la
   línea `# Minuta:`, de la que el historial saca el título (`titulo_desde_minuta`), ni la de `**Fecha:**`.
4. **Los textos** de la nota y del mensaje de progreso son propuestas, no requisitos de la auditoría. La nota dice el
   número de partes porque es un dato que la app conoce y que explica el motivo.
5. **Con una sola parte no hay nota**: el documento ya se redacta y se revisa contra la transcripción completa, que
   es lo que el criterio 3 fija como límite. No se inventa un umbral distinto de `max_caracteres_bloque`.
6. **Las notas reutilizadas cuentan como notas**: la segunda generación (por ejemplo, el resumen después de la
   minuta) no pide notas nuevas, pero también se redacta a partir de ellas, así que lleva la nota.
7. **La revisión contra las notas se conserva** con más de una parte: aún corrige reformulaciones introducidas al
   redactar desde las notas. Quitarla sería otro cambio de comportamiento que el backlog no pide.

## Historias derivadas (para el backlog)

- Como usuario que genera la minuta de una reunión larga, quiero que la revisión de fidelidad contraste el documento
  con la transcripción original y no con las notas, para que un dato o una tarea que se coló al extraer las notas no
  pase como revisado. — hallazgo A-05 (salida «revisar contra el original») — carril L: revisar por partes no detecta
  datos inventados y una sola petición supera `max_caracteres_bloque` (ver «Supuestos» 2).
- [🟡] Aceptar la revisión de fidelidad solo si conserva las tareas y los acuerdos del documento, no solo sus
  secciones, para que una revisión que borra tareas no sustituya a la minuta — hallazgo A-05 (segunda mitad del
  escenario) — carril S.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 159 tests. Code review: revisión
del orquestador (cambio acotado a una función pura y al final de `generar_minuta`/`generar_resumen`; ningún test
existente se tocó), listo para commit. Delta de spec: `docs/specs/documentos-ia.md`, dos comportamientos nuevos con
`Origen` en esta historia.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Con 2 partes, la nota termina la minuta y el resumen (también con notas reutilizadas), no va a Copilot y no cambia título, fecha ni secciones | Minuta: `tests/test_asistente_ia.py:532` (`test_minuta_de_varias_partes_termina_con_la_nota_de_la_aplicacion`). No se envía a Copilot: `:550`. Resumen con notas reutilizadas: `:573`. Historial y `.md` exportado intactos: `tests/test_persistencia.py:346`. Implementación: `src/asistente_ia.py:203` (`nota_de_notas`), `:510` (`_con_nota`) | cumple (tests). Pendiente aceptado: visor de Markdown |
| 2 | [MODIFICA: sin spec] | Con la revisión activada y 2 partes: la línea de estado nombra las notas, la petición de revisión lleva las notas y el documento añade la frase sobre la revisión | Progreso: `src/asistente_ia.py:502-503`; `tests/test_asistente_ia.py:591` (`test_revision_con_varias_partes_dice_que_revisa_contra_las_notas`). Frase: `:477` (`test_nota_de_notas_con_revision_anade_la_frase_de_la_revision`) y `:591`. Sin revisión, sin frase: `:637` | cumple |
| 3 | [NUEVO] | Una sola parte: sin nota, progreso «con la transcripción» y revisión con el texto completo; un carácter más del límite: 2 partes y nota | Una parte: `tests/test_asistente_ia.py:610` (`test_una_sola_parte_no_lleva_nota_y_revisa_contra_la_transcripcion`). Límite + 1: `:625` (`test_un_caracter_mas_del_limite_se_procesa_en_dos_partes_y_lleva_la_nota`). Los tests usan un límite de 900 caracteres en lugar de 60 000; la lógica de `dividir_texto` es la misma | cumple (tests) |

**Pendientes aceptados:**

- Verificación manual, no hecha: abrir un `<nombre>_minuta.md` exportado en un visor de Markdown y comprobar que la nota
  queda separada por la línea horizontal y que la última línea de «Próximos pasos» no se convierte en un título. Los
  tests comprueban que el bloque empieza con línea en blanco antes de `---`.
- La frase sobre la revisión aparece siempre que la revisión de fidelidad está activada, aunque su resultado se
  descartara por perder secciones (`src/asistente_ia.py:515`).
- Decisión del usuario: se eligió advertir en vez de revisar contra la transcripción original (supuesto 2 de esta
  historia, con los números). La alternativa queda como punto 23 del backlog.
