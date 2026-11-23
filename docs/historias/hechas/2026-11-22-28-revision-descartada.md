# 28 · Una revisión descartada no cuenta como revisada

> Origen: `BACKLOG.md`, «Salud del código» #23 (carril L), historia R1 del diseño (carril S, la primera de la serie
> R1 → R4 → R6 → R2a → R2b → R3). Cierra el pendiente aceptado de `docs/historias/hechas/2026-11-22-06-revision-de-fidelidad.md`
> («La frase sobre la revisión aparece siempre que la revisión de fidelidad está activada, aunque su resultado se
> descartara por perder secciones»). Reglas de oro 3 y 4 de `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin
> usuario al otro lado: un orquestador aprueba en su nombre (ver «Supuestos»).
>
> — Diseño: docs/disenos/07-revision-contra-el-original.md §R1

Líneas citadas: las de `8ded42a` (el código y los tests no cambian hasta `HEAD`, `1b480d9`). Si se mueven, manda el
nombre de la función.

## Historia

Como usuario que activa la revisión de fidelidad, quiero que el documento me diga cuándo la app descartó la revisión y
por qué, y que en ese caso no diga que se revisó, para no dar por revisado un documento que no tiene ninguna
corrección de la revisión.

## Qué hace hoy el código

- `AsistenteIA._generar` (`src/asistente_ia.py:763-787`): si la revisión no se acepta (deja más secciones sin cubrir
  que el borrador, o, en la minuta, menos filas en la tabla de tareas o menos viñetas en Acuerdos, según
  `contar_filas_tareas` y `contar_vinetas_acuerdos`, regla #24), se conserva el documento anterior **sin registrar
  nada**. `_Documento` (`:197-205`) no tiene dónde guardarlo.
- `AsistenteIA._con_nota` (`:825-831`) calcula `revisado = self.revision_fidelidad and not d.error_revision`: una
  revisión descartada cuenta como revisada.
- Con varias partes, `notas_de_la_aplicacion` (`:327-357`) llama a `_cita_de_partes(partes, revisado)` (`:300-306`),
  que añade «La revisión de fidelidad se hizo contra esas notas, no contra la transcripción.» aunque se descartara. Con
  una sola parte, el documento no lleva ninguna nota y el usuario no sabe nada.

## Criterios de aceptación

Nota de revisión descartada (literal del diseño, punto 4), con `{motivo}` = «quitaba secciones obligatorias» o
«quitaba tareas o acuerdos»:
«> Nota de la aplicación: la revisión de fidelidad se descartó porque {motivo}; este documento no está revisado.»

- [ ] [MODIFICA: sin spec] Dada la revisión de fidelidad activada, una transcripción de una sola parte y una revisión
  de resumen que devuelve el documento sin «### Puntos clave» ni «### Conclusiones», cuando genero el resumen, entonces
  el resumen empieza por el redactado (con todas sus secciones, sin ninguna corrección de la revisión) y contiene, tras
  «\n---\n\n», «> Nota de la aplicación: la revisión de fidelidad se descartó porque quitaba secciones obligatorias;
  este documento no está revisado.». La nota no se envía a Copilot. (antes: se entregaba el redactado sin ninguna
  nota, igual que si la revisión no hubiera encontrado nada que corregir; `test_revision_que_pierde_secciones_se_descarta`
  lo fija con `==`)
- [ ] [MODIFICA: documentos-ia › Revisión de fidelidad contra las notas] Dada la revisión de fidelidad activada, una
  transcripción de 2 partes (`TEXTO2`, `max_caracteres_bloque=900`) y una revisión de minuta que pierde «## Próximos
  pasos», cuando genero la minuta, entonces la minuta lleva la nota «… se descartó porque quitaba secciones
  obligatorias; este documento no está revisado.» **antes** que la de las partes, ambas bajo una sola línea
  horizontal, y la de las partes es la de hoy sin frase de revisión: termina en «…antes de darlo por bueno.» y la
  minuta no contiene «La revisión de fidelidad se hizo». La línea de estado sigue diciendo «Revisando fidelidad con las
  notas de las 2 partes…». (antes: la nota de las partes añadía «La revisión de fidelidad se hizo contra esas notas, no
  contra la transcripción.» aunque la revisión se hubiera descartado)
- [ ] [MODIFICA: documentos-ia › Revisión de fidelidad que borra tareas o acuerdos] Dada la revisión de fidelidad
  activada y una minuta de una parte: si la revisión pierde una sección **y** una fila de tareas, el motivo es
  «quitaba secciones obligatorias» (precedencia de secciones); si solo pierde una fila de tareas (o una viñeta de
  Acuerdos), la minuta conserva la anterior a la revisión, con esa fila, y lleva la nota con «quitaba tareas o
  acuerdos» (provisional: R4 sustituye este caso por «se aplica y se repone marcado»); si la revisión se acepta, no hay
  nota de revisión descartada. En el resumen la regla de tareas no aplica: una revisión que quita una viñeta de
  «### Puntos clave» se acepta sin nota. (antes: la minuta anterior se conservaba sin ninguna nota)

**Orden de las notas** (diseño, punto 4): respuesta cortada, notas de partes cortadas, secciones que no se pudieron
pedir de nuevo, secciones que faltan, revisión no completada **o** descartada (nunca las dos: una revisión que falla o
llega cortada no llega a compararse), y la última, la de las partes. Los tests nuevos comprueban con `in` y el orden
relativo (`index`), no con `endswith`, salvo donde se diga.

## Cómo se verifican

Todo con tests sin red en `tests/test_asistente_ia.py` (regla 3): `_completar` parcheado con un iterador de
respuestas, o `_simular_chat` (`:777`) con `_prohibir_red` (`:45`), cuya función `respuesta` mira primero si el último
mensaje contiene «DOCUMENTO:» (la revisión) y después `_es_prompt_de_notas` (`:787`). Minutas con `_minuta` (`:195`) o
`MINUTA_MODELO` (`:791`); `TEXTO2 = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))`, que con
`max_caracteres_bloque=900` da 2 partes (el texto que ya usan `:654`, `:814` y `:873`).

- **Rojos** (fallan antes del cambio):
  - `test_revision_que_pierde_secciones_lo_dice_y_no_cuenta_como_revisada` (criterio 1): resumen de una parte;
    `resumen.startswith(completo)`, la nota exacta tras «\n---\n\n» con `in`, y ninguna petición enviada contiene
    «Nota de la aplicación».
  - `test_revision_descartada_con_varias_partes_no_dice_que_se_reviso` (criterio 2): `TEXTO2`, revisión =
    `MINUTA_MODELO` sin «## Próximos pasos»; nota de descartada antes de la de partes (`index`), una sola «\n---\n»,
    la minuta termina en «…antes de darlo por bueno.» y no contiene «La revisión de fidelidad se hizo».
  - `test_revision_que_pierde_secciones_y_tareas_da_el_motivo_de_secciones` (criterio 3): minuta de una parte con
    dos tareas; la revisión trae una tarea y no trae «## Próximos pasos»; el motivo es el de secciones y la minuta no
    contiene «quitaba tareas o acuerdos». Sobrevive a R4.
  - `test_revision_descartada_por_tareas_lo_dice` (criterio 3, **provisional**: R4 lo sustituye): la revisión solo
    quita una fila; la fila sigue en la minuta y la nota dice «quitaba tareas o acuerdos».
- **Guarda** (pasan antes y después):
  - `test_revision_aceptada_no_lleva_nota_de_descartada` (criterio 3): test nuevo, verde ya antes del cambio; revisión
    que corrige una frase y conserva tareas y acuerdos; la corrección está y no hay «se descartó».
  - `test_revision_de_fidelidad_reemplaza_documento` (`:174`), `test_revision_de_minuta_que_conserva_tareas_y_acuerdos_se_acepta`
    (`:246`), `test_nota_de_notas_dice_el_numero_de_partes` y `test_nota_de_notas_con_revision_anade_la_frase_de_la_revision`
    (`:751-763`): los del diseño.
  - Además (no los lista el diseño, pero fijan bordes de R1): `test_revision_de_minuta_que_borra_una_tarea_se_descarta`
    (`:222`) y `..._un_acuerdo_se_descarta` (`:234`) (siguen conservando la fila; comprueban con `in`);
    `test_revision_de_resumen_no_aplica_la_regla_de_tareas` (`:258`, el último punto del criterio 3);
    `test_revision_que_restituye_la_seccion_no_lleva_nota` (`:1285`) y
    `test_seccion_recuperada_por_la_revision_no_deja_nota_de_secciones` (`:1363`, con `==`: una revisión aceptada no
    añade nota); `test_fallo_en_la_revision_con_varias_partes_no_dice_que_se_reviso` (`:654`) y
    `test_revision_cortada_se_descarta_y_lo_dice` (`:1595`, con `==`: una revisión fallida o cortada lleva solo «no se
    pudo completar», nunca también «se descartó»); `test_revision_con_varias_partes_dice_que_revisa_contra_las_notas`
    (`:873`) y `test_una_sola_parte_no_lleva_nota_y_revisa_contra_la_transcripcion` (`:892`); y los de
    `notas_de_la_aplicacion` con argumentos posicionales (`:929-952`), que no cambian porque el parámetro nuevo es solo
    por palabra clave.
- **Se ajusta:** `test_revision_que_pierde_secciones_se_descarta` (definido en `:187`; el `==` está en `:192`) pasa a
  `resumen.startswith(completo)` y la nota con `in`.
- Suite completa: `./venv/bin/python -m pytest -q` en verde (hoy 501 tests; 505 tras esta historia).
- **Verificación manual:** no hace falta generar de verdad: todo lo observable (texto del documento y peticiones
  enviadas) lo cubren los tests con `httpx` simulado. No hay peticiones reales autorizadas para esto. Opcional, sin red:
  copiar la salida del test del criterio 2 a un `.md` temporal fuera del repo y abrirlo en un visor de Markdown para ver
  las dos notas bajo una sola línea horizontal.

## Plan

- El resultado interno de cada generación recuerda, además del fallo de la revisión, si se descartó y con qué motivo
  (secciones antes que tareas o acuerdos).
- Al decidir si se acepta la revisión, la rama que hoy conserva el documento anterior en silencio anota ese motivo; la
  aceptación y su regla no cambian.
- El bloque de notas de la aplicación recibe el motivo (parámetro nuevo solo por palabra clave, con valor por defecto,
  firma fijada en el punto 7 del diseño) y escribe la nota de revisión descartada en el lugar de la de revisión no
  completada.
- Una revisión descartada deja de contar como revisada al montar las notas, así que la nota de las partes vuelve a la
  de hoy sin frase de revisión.
- Tests rojos de los tres criterios primero; luego el ajuste del test que hoy compara con `==`.

Archivos del `/pair` (lista cerrada, la del diseño): `src/asistente_ia.py` (`_Documento.revision_descartada:
Optional[str] = None`, al final de los campos; `AsistenteIA._generar`; `notas_de_la_aplicacion(..., *,
revision_descartada: Optional[str] = None)`; `AsistenteIA._con_nota`, con `revisado = self.revision_fidelidad and not
d.error_revision and not d.revision_descartada`), `tests/test_asistente_ia.py`. Si hace falta otro archivo, se para y
se vuelve al diseño.

Documentación que cambia (`/cerrar`):

- `docs/specs/documentos-ia.md`: «Notas de la aplicación juntas» (`:157-166`, añadir «revisión descartada» junto a
  «revisión no completada»), «Revisión de fidelidad contra las notas» (`:210-217`, la descartada no dice que se
  revisó) y «Revisión de fidelidad que borra tareas o acuerdos» (`:219-223`, ahora con la nota; ver «Discrepancias»,
  2); el criterio 1 crea el comportamiento «Revisión que pierde secciones» (hoy sin spec).
- `src/EGM.md`, «Documentos generados» (`:297-305`: también la regla de aceptación de `:304-305`).
- Historia 06, «Pendientes aceptados»: el de la frase de revisión, cerrado.
- `BACKLOG.md` #23 sigue abierto (🟡) hasta R3.

## Fuera de alcance

- **R4:** reponer marcadas con «[comprobar]» las tareas y acuerdos que la revisión quitó, el nuevo `PROMPT_REVISION`
  y la nota de lo repuesto. Hasta entonces, quitar una tarea descarta la revisión entera (con la nota provisional de
  esta historia).
- **R6:** `CARACTERES_POR_TOKEN` a 2,3 y `estimar_tokens`.
- **R2a:** `_ConsultaDeLimite` y `_limite_del_modelo` (una consulta al catálogo por generación).
- **R2b:** revisar contra la transcripción completa cuando cabe, `fuente_revision` y la frase «lo contrastó después».
- **R3:** el motivo de por qué la revisión fue contra las notas (`motivo_notas`).
- Cambiar la regla de aceptación (qué se descarta), los textos de las demás notas, la línea de estado, el valor por
  defecto de `revision_fidelidad` (D6) o la CLI.

## Supuestos

1. El orquestador aprobó los criterios, los textos y el plan del diseño en nombre del usuario; esta historia no
   pregunta y no añade requisitos. «El caso que dolería» se toma del diseño: una minuta de varias partes que diga «La
   revisión de fidelidad se hizo…» sin estar revisada (criterio 2).
2. El criterio 1 usa los dos títulos que pierde el test de hoy (`"## Resumen\nsolo esto"`); basta con perder uno.

## Discrepancias entre diseño y código

1. **Línea del test que se ajusta.** El diseño cita `:187`, que es la definición; el `==` está en `:192`. Sin efecto.
2. **Documentación de `/cerrar` incompleta en el diseño.** La lista de R1 no incluye la spec «Revisión de fidelidad que
   borra tareas o acuerdos» (`docs/specs/documentos-ia.md:219-223`), que R1 cambia (el descarte por tareas pasa a
   llevar nota, provisional hasta R4), ni la regla de aceptación de `src/EGM.md:304-305` (cita `:297-302`). Se añaden
   arriba; no contradicen el diseño.
3. **Guardas que el diseño no lista.** Los tests de `:222`, `:234`, `:258`, `:654`, `:873`, `:892`, `:1285`, `:1363`
   y `:1595` ya fijan bordes de R1 (descartes por tareas que conservan la fila, resumen sin regla de tareas,
   revisión que restituye una sección, revisión fallida o cortada sin doble nota). Se añaden como guarda.
4. **Filas de relleno.** Hoy `contar_filas_tareas` cuenta «Sin tareas» y `contar_vinetas_acuerdos` cuenta «Sin
   acuerdos explícitos». Una revisión que solo quita ese relleno se descarta (en silencio hoy) y, con R1, llevará
   «quitaba tareas o acuerdos». Es el comportamiento provisional que el diseño acepta entre R1 y R4 (R4 excluye el
   relleno); no se corrige aquí.
5. `test_revision_aceptada_no_lleva_nota_de_descartada` figura en el diseño como «guarda» siendo nuevo: es un test
   nuevo que ya pasa antes del cambio. Sin contradicción.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 506 tests (501 de antes más 5 nuevos; la historia decía 505 por error de cuenta). Code review: revisión del orquestador, listo para commit. Ajuste previsto en la historia: `test_revision_que_pierde_secciones_se_descarta` pasa de `==` a `startswith` más la nota con `in`.

Delta de spec (`docs/specs/documentos-ia.md`, con `Origen` en esta historia):

- «Revisión que pierde secciones»: comportamiento nuevo (criterio 1, `[MODIFICA: sin spec]`; hoy no tenía spec).
- «Revisión de fidelidad contra las notas» (criterio 2) y «Revisión de fidelidad que borra tareas o acuerdos» (criterio 3): [MODIFICA]. Sus viñetas dicen ahora la versión nueva, con la nota de la revisión descartada.
- «Notas de la aplicación juntas»: la revisión descartada ocupa el lugar de la no completada en el orden.
- `src/EGM.md`, «Documentos generados»: regla de aceptación, `_Documento.revision_descartada` y `notas_de_la_aplicacion(..., *, revision_descartada=None)`.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Revisión de resumen que pierde secciones: el resumen empieza por el redactado y lleva la nota de descartada tras «\n---\n\n»; la nota no se envía a Copilot | `tests/test_asistente_ia.py:187`, `:198` (`test_revision_que_pierde_secciones_lo_dice_y_no_cuenta_como_revisada`); `src/asistente_ia.py:795`, `:355`, `:840` | cumple |
| 2 | [MODIFICA: documentos-ia › Revisión de fidelidad contra las notas] | Minuta de 2 partes con revisión descartada: la nota de descartada va antes que la de las partes, bajo una sola línea horizontal, y la minuta no dice que se revisó | `tests/test_asistente_ia.py:300` (`test_revision_descartada_con_varias_partes_no_dice_que_se_reviso`); `src/asistente_ia.py:355-357`, `:840-842` | cumple |
| 3 | [MODIFICA: documentos-ia › Revisión de fidelidad que borra tareas o acuerdos] | Minuta: pierde sección y tarea, gana el motivo de secciones (`:321`); pierde solo una tarea, se descarta con nota («quitaba tareas o acuerdos», `:335`); revisión aceptada sin nota (`:287`). Resumen: la regla de tareas no aplica, así que una viñeta menos se acepta sin nota (`:275` comprueba la aceptación; la ausencia de nota la fija el código, `src/asistente_ia.py:788`, que solo activa la regla en la minuta, `:857`) | `tests/test_asistente_ia.py:321`, `:335`, `:287`, `:275`; `src/asistente_ia.py:791-797` | cumple (el motivo de tareas es provisional hasta R4) |

**Verificación:** `./venv/bin/python -m pytest -q` pasa (506). No hizo falta verificación en ventana ni petición real: lo observable es el texto del documento y las peticiones enviadas, y los tests lo cubren con `httpx` simulado (regla 3).

**Pendientes aceptados:**

- El motivo «quitaba tareas o acuerdos» es provisional hasta R4 (test `:335`). R4 lo sustituye por la reposición marcada con «[comprobar]».
- Las filas de relleno «Sin tareas» y «Sin acuerdos explícitos» cuentan como fila y como viñeta. Hasta R4, una revisión que solo quita ese relleno se descarta con la nota «quitaba tareas o acuerdos».
