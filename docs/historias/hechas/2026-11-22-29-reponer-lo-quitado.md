# 29 · La revisión quita tareas y acuerdos; la app los repone marcados

> Origen: `BACKLOG.md`, «Salud del código» #23 (carril L), historia R4 del diseño (carril M, la segunda de la serie
> R1 → R4 → R6 → R2a → R2b → R3; depende de R1, `docs/historias/28-revision-descartada.md`). Decisión D4 del diseño
> («corregir y reponer marcado»), que sustituye a la del punto #24 de «Salud del código» **solo para tareas y
> acuerdos**. Reglas de oro 3 y 4 de `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin usuario al otro lado: un
> orquestador aprueba en su nombre (ver «Supuestos»).
>
> — Diseño: docs/disenos/07-revision-contra-el-original.md §R4

Líneas citadas: las de la copia de trabajo del 2026-11-22 con R1 en curso (sin commit sobre `1b480d9`). Si se mueven,
manda el nombre de la función.

## Historia

Como usuario que activa la revisión de fidelidad, quiero que la revisión pueda corregir una minuta aunque quiera quitar
una tarea o un acuerdo, y que la app me devuelva lo quitado marcado con «[comprobar]» y listado en una nota, para tener
las correcciones de la revisión sin que ninguna fila desaparezca sin que yo lo vea.

## Qué hace hoy el código

- `PROMPT_REVISION` (`src/asistente_ia.py:97-115`) pide corregir «Datos que no aparecen en la transcripción (nombres,
  fechas, cifras, tareas)» y a la vez «no elimines secciones ni tareas»: contradictorio, y no dice qué acuerdos o
  tareas son legítimos aunque se deduzcan (los que `PROMPT_MINUTA`, `:63-95`, obliga a convertir en tarea).
- `AsistenteIA._generar` (`:708`; regla de aceptación en `:784-797`): en la minuta (`conservar_tareas_y_acuerdos=True`,
  que pasa `generar_minuta`, `:848`), si la revisión deja menos filas según `contar_filas_tareas` (`:151`) o menos
  viñetas según `contar_vinetas_acuerdos` (`:158`), se descarta entera y se conserva la minuta anterior (regla #24).
  Con R1, además, `revision_descartada = "quitaba tareas o acuerdos"` (`:797`, provisional) y la minuta lleva «> Nota
  de la aplicación: la revisión de fidelidad se descartó porque quitaba tareas o acuerdos; este documento no está
  revisado.». Se pierden también las correcciones buenas de esa revisión.
- Los dos contadores cuentan las filas de relleno: la fila «Sin tareas» y la viñeta «Sin acuerdos explícitos». No hay
  emparejamiento: comparan solo números.
- `notas_de_la_aplicacion` (`:328`) no tiene nota de lo repuesto; `_Documento` (`:197`) no tiene campo `repuestas`.
- `normalizar_tabla_tareas` (`:279`), en el post-proceso de `generar_minuta`, ya quita la fila «Sin tareas» cuando la
  tabla tiene tareas reales y cambia «No asignado» por «Sin fecha» en la columna de fecha.

## Criterios de aceptación

Textos literales del diseño (puntos 4 y 5). Marca: `MARCA_REPUESTA = "[comprobar]"`. Nota de lo repuesto, con
`{lista}` = los elementos entre «», 1 → «A»; 2 → «A» y «B»; de 3 a 5 → «A», «B», «C» y «D»; más de 5 → los 5 primeros
y « y {n} más»:
«> Nota de la aplicación: la revisión de fidelidad quiso quitar de la minuta lo siguiente por no encontrarlo en la
transcripción; la app lo ha repuesto marcado con «[comprobar]»: {lista}. Compruébalo con la transcripción y bórralo si
no se dijo.»

- [ ] [MODIFICA: documentos-ia › Revisión de fidelidad que borra tareas o acuerdos] Dada la revisión de fidelidad
  activada y una minuta de una parte con las tareas «Enviar las cifras de octubre | Ana» y «Revisar el plan | Ana», el
  acuerdo «Se aprueba el presupuesto» y la frase «la entrega está sujeta a validación», cuando la revisión devuelve la
  minuta sin la fila «Enviar las cifras de octubre» y con la frase «la entrega llega si me llegan los datos», entonces
  la minuta contiene la frase corregida (la revisión se aplica), la línea «| Revisar el plan | Ana | Sin fecha |»
  seguida de «| Enviar las cifras de octubre [comprobar] | Ana | Sin fecha |» al final de la tabla, y bajo la línea
  horizontal la nota de lo repuesto con la lista «Enviar las cifras de octubre (Ana)»; no contiene «se descartó» ni
  «quitaba tareas o acuerdos». Igual con los acuerdos: dados «- Se aprueba el presupuesto» y «- Se contrata a Ana» y
  una revisión que solo trae «* Se aprueba el presupuesto.», la minuta lleva «- Se contrata a Ana [comprobar]» tras la
  última viñeta de Acuerdos. Dada una revisión que cambia la única tarea por la fila «Sin tareas», la tarea vuelve
  marcada y la fila «Sin tareas» desaparece. La petición de revisión pide quitar «Tareas o acuerdos que nada de la
  transcripción respalda» salvo los que se deducen de lo dicho, y ya no dice «no elimines secciones ni tareas».
  (antes: la revisión que dejaba menos filas de tareas o menos viñetas de acuerdos se descartaba entera, con sus
  correcciones, y se conservaba la minuta anterior; con R1, con la nota «…se descartó porque quitaba tareas o
  acuerdos; este documento no está revisado.», que deja de existir)
- [ ] [MODIFICA: documentos-ia › Revisión de fidelidad que borra tareas o acuerdos] Solo se repone cuando una sección
  **baja** de número y solo lo que falta: dada una revisión que conserva las 2 filas de tareas pero reescribe la
  primera celda de una, la minuta lleva la revisión sin ningún «[comprobar]» ni nota de lo repuesto; dada una que
  reescribe «Enviar el informe» como «Enviar el informe final» y quita «Revisar el contrato» (de 3 filas a 2), solo
  vuelve «| Revisar el contrato [comprobar] | Ana | Sin fecha |» y la nota lista solo «Revisar el contrato (Ana)»;
  dada una revisión que pierde «## Próximos pasos» **y** una tarea, la minuta es la anterior con la nota de R1
  «…se descartó porque quitaba secciones obligatorias…» y sin ningún «[comprobar]»; en el resumen no se repone nada
  (una revisión que quita una viñeta de «### Puntos clave» se acepta sin marca ni nota). (antes: los dos primeros
  casos con 3 → 2 filas se descartaban; el de mismo número de filas ya se aceptaba, y el de secciones y el del resumen
  no cambian)
- [ ] [MODIFICA: documentos-ia › Notas de la aplicación juntas] Dado el bloque de notas con lo repuesto, cuando se
  monta, entonces con 1 elemento la lista es «A»; con 2, «A» y «B»; con 6, «A», «B», «C», «D», «E» y 1 más (todas las
  filas vuelven a la minuta, el tope es solo de la nota); un elemento de 200 caracteres sale con sus 120 primeros
  caracteres y «…», y uno corto que acaba en punto lo conserva («Se contrata a Ana.»); una tarea cuyo responsable es
  «No asignado» o está vacío sale sin paréntesis; con la lista vacía no hay nota (sin nada más que avisar, el bloque es
  `""`). La nota va después de la de secciones que faltan y de la de revisión no completada, y antes de la de las
  partes, que sigue diciendo «La revisión de fidelidad se hizo contra esas notas, no contra la transcripción.» (lo
  repuesto cuenta como revisado); nunca coincide con la de revisión descartada. Ni la marca ni la nota llegan a
  ninguna petición a Copilot. (antes: el orden era respuesta cortada, notas de partes cortadas, secciones que no se
  pudieron pedir de nuevo, secciones que faltan, revisión no completada o descartada y la de las partes, sin nota de
  lo repuesto)

**Caso que dolería** (del diseño, regla 4): una tarea real que la revisión quitó y que desaparece de la minuta sin que
el usuario lo vea. Lo cubren los criterios 1 y 2: toda fila que falta vuelve completa y marcada, y una tarea reescrita
no se confunde con una quitada.

## Cómo se verifican

Todo con tests sin red en `tests/test_asistente_ia.py` (regla 3): `_completar` parcheado con un iterador de
respuestas, o `_simular_chat` (`:857`) con `_prohibir_red` (`:45`), cuya función `respuesta` mira primero si el último
mensaje contiene «DOCUMENTO:» (la revisión). Minutas con `_minuta` (`:212`, responsable «Ana» y «Sin fecha» en todas
las filas) o `MINUTA_MODELO` (`:871`); `TEXTO2` = `"\n".join(f"Segmento {i:03d} con algo de contenido." for i in
range(40))`, 2 partes con `max_caracteres_bloque=900`. Los tests de notas comprueban con `in` y el orden relativo
(`index`), salvo los de `notas_de_la_aplicacion`, que comparan el texto exacto.

- **Rojos** (fallan antes del cambio):
  - `test_revision_que_quita_una_tarea_se_aplica_y_la_repone_marcada` (criterio 1): el escenario literal; frase
    corregida, las dos líneas consecutivas de la tabla, nota con «Enviar las cifras de octubre (Ana)», sin «se
    descartó».
  - `test_acuerdo_quitado_se_repone_marcado` (criterio 1): revisión con «* Se aprueba el presupuesto.»; «- Se contrata
    a Ana [comprobar]» y una sola «[comprobar]».
  - `test_tarea_cambiada_por_sin_tareas_se_repone` (criterio 1): la tarea vuelve marcada y no queda ninguna fila «Sin
    tareas».
  - `test_prompt_de_revision_permite_quitar_solo_lo_no_respaldado` (criterio 1): `PROMPT_REVISION` contiene «no
    elimines secciones.» y «un acuerdo con responsable también es una tarea», y no contiene «ni tareas».
  - `test_tarea_reescrita_y_otra_quitada_solo_repone_la_quitada` (criterio 2): solo «Revisar el contrato
    [comprobar]»; «Enviar el informe final» sin marca y «Enviar el informe» sin reponer.
  - `test_reponer_lo_quitado_sin_bajar_no_cambia_nada` (criterio 2): función pura `reponer_lo_quitado(antes,
    despues)` con el mismo número de filas y una celda reescrita → `(despues, [])`.
  - `test_nota_de_lo_repuesto_formato_y_tope` (criterio 3): `notas_de_la_aplicacion([], 1, True, repuestas=…)` con
    1, 2 y 6 elementos, uno de 200 caracteres, uno que acaba en punto y `repuestas=[]` → `""`; y con
    `notas_de_la_aplicacion(["## Próximos pasos"], 2, True, repuestas=["A"])`, el orden secciones que faltan → lo
    repuesto → partes con «La revisión de fidelidad se hizo contra esas notas».
  - `test_lo_repuesto_no_se_envia_a_copilot` (criterio 3): `TEXTO2` con `_simular_chat`; la revisión quita la fila de
    `MINUTA_MODELO`; la minuta lleva la marca y la nota, ninguna petición contiene «[comprobar]» ni «quiso quitar», y
    se enviaron 4 peticiones (2 notas, la minuta y la revisión). El diseño lo llama «guarda desde que existe»: es rojo
    al escribirlo porque comprueba que la marca está (ver «Discrepancias», 5).
- **Renombrados y ampliados** (rojos tras ampliarlos):
  - `test_revision_de_minuta_que_borra_una_tarea_se_descarta` (`:239`) → `test_revision_de_minuta_que_borra_una_tarea_se_repone_marcada`:
    comprueba también «| Revisar el contrato [comprobar] | Ana | Sin fecha |».
  - `test_revision_de_minuta_que_borra_un_acuerdo_se_descarta` (`:251`) → `test_revision_de_minuta_que_borra_un_acuerdo_se_repone_marcado`:
    comprueba «- Se contrata a Ana [comprobar]».
- **Sustituido:** `test_revision_descartada_por_tareas_lo_dice` (`:335`, de R1, provisional) se borra; el motivo
  «quitaba tareas o acuerdos» deja de existir en `_generar` (búsqueda inversa: `grep -n "quitaba tareas" src/` sin
  resultados).
- **Guarda** (pasan antes y después):
  - `test_revision_que_pierde_secciones_y_tareas_da_el_motivo_de_secciones` (`:321`, de R1; criterio 2): se le añade
    `assert "[comprobar]" not in minuta`, que pasa antes y después.
  - `test_revision_de_resumen_no_aplica_la_regla_de_tareas` (`:275`, criterio 2), `test_las_notas_nuevas_no_se_envian_a_copilot`
    (`:776`), `test_revision_de_minuta_que_conserva_tareas_y_acuerdos_se_acepta` (`:263`),
    `test_revision_aceptada_no_lleva_nota_de_descartada` (`:287`), `test_revision_descartada_con_varias_partes_no_dice_que_se_reviso`
    (`:300`), `test_revision_que_restituye_la_seccion_no_lleva_nota` (`:1365`: la tabla aparece, no baja),
    `test_contar_filas_de_tareas` (`:225`) y `test_contar_vinetas_de_acuerdos` (`:232`) (las funciones se quedan; ver
    «Discrepancias», 3), los de `notas_de_la_aplicacion` con argumentos posicionales (`:1009-1032`) y
    `test_nota_de_notas_*` (`:831-843`): el parámetro nuevo es solo por palabra clave.
- Suite completa: `./venv/bin/python -m pytest -q` en verde (506 con R1 en la copia de trabajo; 513 tras esta
  historia si R1 queda como está: 8 nuevos, 1 borrado).
- **Verificación manual** (la del diseño, «Verificación común», sin red): copiar la salida de
  `test_revision_que_quita_una_tarea_se_aplica_y_la_repone_marcada` a un `.md` temporal fuera del repo y abrirlo en un
  visor de Markdown: la tabla sigue siendo una tabla, «[comprobar]» se ve como texto y la cola de notas sigue bajo una
  sola línea horizontal. No hay peticiones reales autorizadas para esto.

## Plan

- La petición de revisión pasa a ser el texto completo del diseño: puede quitar tareas o acuerdos que nada respalda,
  pero no los que se deducen de lo dicho ni secciones.
- La revisión se acepta o se descarta solo por las secciones (R1 intacto); el descarte por tareas o acuerdos y su
  motivo provisional desaparecen.
- Una función pura compara la minuta antes y después de la revisión: solo si la tabla de tareas o la lista de acuerdos
  baja de número (sin contar el relleno), empareja filas por similitud uno a uno, repone al final las que quedan sin
  pareja, completas y marcadas, y devuelve la lista para la nota. Se aplica antes del post-proceso, que ya quita la
  fila «Sin tareas» sobrante.
- El resultado de cada generación guarda esa lista (cuenta como revisada) y el bloque de notas la escribe con su
  formato y tope, entre la de revisión no completada y la de las partes.
- Tests rojos de los tres criterios primero; después los renombrados, el borrado del provisional de R1 y la guarda
  ampliada.

Archivos del `/pair` (lista cerrada, la del diseño): `src/asistente_ia.py` (`PROMPT_REVISION`; `MARCA_REPUESTA =
"[comprobar]"`; `reponer_lo_quitado(antes: str, despues: str) -> tuple[str, list[str]]` y sus auxiliares privadas;
`_Documento.repuestas: list[str] = field(default_factory=list)`, al final, tras `revision_descartada`;
`AsistenteIA._generar`; `notas_de_la_aplicacion(..., *, revision_descartada=None, repuestas: Optional[list[str]] =
None)`; `AsistenteIA._con_nota`), `tests/test_asistente_ia.py`. Si hace falta otro archivo, se para y se vuelve al
diseño.

Detalles del diseño que el `/pair` sigue al pie de la letra (punto 5): normalización (sin marcador de viñeta,
minúsculas, espacios colapsados, sin punto final; celdas unidas por « | »); similitud `difflib.SequenceMatcher(None, a,
b).ratio()`, pares ordenados por (similitud descendente, índice de antes, índice de después); relleno = fila cuya
primera celda es «Sin tareas» y viñeta «Sin acuerdos explícitos» (sin mayúsculas ni punto final); sin tabla en
`despues`, se insertan la cabecera y el separador de `PROMPT_MINUTA` bajo el título; la viñeta «Sin acuerdos
explícitos» se quita si se repone un acuerdo; elementos de la nota en una línea y recortados con `MAX_MOTIVO_NOTA`
(120) **sin** `_motivo`; primero tareas, después acuerdos. El motivo de corte (`corte = _corte(revisado)`) se toma de
la respuesta de Copilot antes de reponer, porque el texto repuesto ya no es un `_TextoDeCopilot`.

Documentación que cambia (`/cerrar`):

- `docs/specs/documentos-ia.md`: «Revisión de fidelidad que borra tareas o acuerdos» (`:219-223`: se aplica y se
  repone marcado, con la nota; decisión D4 en vez del punto #24 para tareas y acuerdos) y «Notas de la aplicación
  juntas» (`:157-166`: «lo repuesto» entre la revisión no completada o descartada y la de las partes), sobre el texto
  que deje `/cerrar` de R1.
- `src/EGM.md`, «Documentos generados» (`:297-305`; la regla de aceptación está en `:304-305`) y la lista de
  constantes de `:120` (`MARCA_REPUESTA`).
- `BACKLOG.md` #23 sigue abierto (🟡) hasta R3; el #24 sigue ✅ (su regla queda sustituida por D4, se dice en la spec).

## Fuera de alcance

- Reponer o avisar de secciones: una revisión que pierde secciones se sigue descartando entera (R1).
- Tareas que la minuta omite (la revisión no añade lo que falta), y comparar celdas cuando el número de filas no baja.
- Cambiar `PROMPT_MINUTA`, `PROMPT_SISTEMA`, el resumen (no tiene tabla ni acuerdos), la línea de estado o el valor
  por defecto de `revision_fidelidad` (D6).
- **R6, R2a, R2b, R3:** relación caracteres/token, consulta única al catálogo, revisión contra la transcripción
  completa (`fuente_revision`, la frase «lo contrastó después») y el motivo de revisar contra las notas
  (`motivo_notas`).
- Quitar `contar_filas_tareas` y `contar_vinetas_acuerdos` (ver «Discrepancias», 3).
- Verificación sin IA (D5) y limitar los reintentos de `_completar` (riesgo 7).

## Supuestos

1. El orquestador aprobó los criterios, los textos y el plan del diseño en nombre del usuario; esta historia no
   pregunta y no añade requisitos. «El caso que dolería» se toma de la regla 4 y del diseño (riesgo 5).
2. Se parte de R1 tal como está en la copia de trabajo (diff sin commit sobre `1b480d9`, 506 tests): `_Documento`
   ya tiene `revision_descartada`, `notas_de_la_aplicacion` ya tiene `*, revision_descartada`, `_generar` asigna
   «quitaba secciones obligatorias» o «quitaba tareas o acuerdos» y existen sus cinco tests. Si R1 cambia antes de su
   commit, mandan los nombres de la historia 28 y las líneas se recalculan.
3. Los criterios usan `_minuta` tal como está (responsable «Ana», fecha «Sin fecha»), y por eso las líneas esperadas
   terminan en «| Ana | Sin fecha |».

## Discrepancias entre diseño y código

1. **Título de sección ausente tras una revisión aceptada (hueco del diseño).** La revisión se acepta si no deja
   **más** secciones sin cubrir que el borrador (`_generar`, `conserva_secciones`, comparación `<=`). Si al borrador le
   faltaba, por ejemplo, «## Acuerdos» y la revisión la trae pero pierde «## Tareas y pendientes», se acepta y no hay
   título bajo el que reponer las filas. El diseño solo cubre «`despues` sin tabla» (con título). Es raro (exige una
   redacción incompleta tras el reintento de secciones) y no entra en los criterios; el `/pair` no lo improvisa: si
   aparece, se para y el orquestador decide (por ejemplo, tratarlo como «pierde secciones» o añadir la sección al
   final). Recomendación: enmienda de una línea en el punto 5 del diseño.
2. **Líneas de documentación.** El diseño cita `src/EGM.md:297-302`; la regla de aceptación que cambia está en
   `:304-305` (la misma discrepancia que en R1). Se añade también `src/EGM.md:120` (lista de constantes) para
   `MARCA_REPUESTA`.
3. **Contadores que quedan sin uso.** Tras R4, `_generar` deja de usar `contar_filas_tareas` y
   `contar_vinetas_acuerdos` (las únicas llamadas, `:788-790`), que cuentan el relleno que R4 excluye. El diseño no dice
   si se quitan. Se quedan (públicas, con sus tests `:225` y `:232` como guarda) para no ampliar la historia;
   `reponer_lo_quitado` usa su propio recuento sin relleno. Quitarlas sería un carril S aparte.
4. **Recorte con un punto final.** El criterio 3 del diseño dice «el largo acaba en los 120 primeros caracteres + «…»
   (un punto final se conserva)». Con 200 caracteres el punto queda fuera del recorte; lo que se conserva es el punto
   de un elemento corto (no se aplica `_motivo`, que lo quita). El criterio 3 lo separa en los dos casos.
5. **`test_lo_repuesto_no_se_envia_a_copilot` como guarda.** El diseño lo pone en «Guarda» con «nuevo, guarda desde que
   existe». Sin reposición no hay nada que no enviar, así que, para no ser trivial, comprueba también que la marca y la
   nota están en la minuta: es rojo al escribirlo y guarda después. Además, la revisión es la última petición de la
   generación, así que hoy ninguna petición puede llevar lo repuesto; el test protege contra cambios futuros.
6. **Orden de las notas con partes.** El diseño fija el orden (punto 4) pero no lo pone en ningún test de R4; se
   comprueba en `test_nota_de_lo_repuesto_formato_y_tope` con la función pura (secciones que faltan, lo repuesto,
   partes con frase de revisión).
7. **`normalizar_tabla_tareas` y el relleno.** Solo quita «Sin tareas» en filas de 3 columnas y cuando hay más de dos
   filas de 3 columnas en el documento (cabecera incluida): con cabecera, «Sin tareas» y una fila repuesta son 3, así
   que funciona para el criterio 1. Una fila «Sin tareas» de otra forma (una sola celda) no se quitaría; el diseño lo
   delega en esta función y no se cambia aquí.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 514 tests (la historia decía 513; el noveno test nuevo, `test_sin_la_seccion_donde_reponer_se_descarta`, lo pidió el orquestador). Code review: revisión del orquestador, listo para commit.

Decisión del orquestador sobre el hueco de «Discrepancias», 1: si hay filas o viñetas que reponer y la revisión ya no tiene el título de su sección, la revisión se descarta con «quitaba secciones obligatorias» (nota de R1); nada desaparece sin que el usuario lo vea.

Delta de spec (`docs/specs/documentos-ia.md`, con `Origen` en esta historia):

- «Revisión de fidelidad que borra tareas o acuerdos»: [MODIFICA]. La revisión se aplica y lo quitado se repone marcado con «[comprobar]» y listado en una nota; se descarta solo si no hay título donde reponer. Sale el motivo provisional «quitaba tareas o acuerdos» de R1.
- «Notas de la aplicación juntas»: [MODIFICA]. La nota de lo repuesto va entre la de revisión descartada y la de las partes, con su formato y tope.
- `src/EGM.md`, «Documentos generados» y constantes: regla de aceptación, `reponer_lo_quitado`, `_Documento.repuestas`, `notas_de_la_aplicacion(..., *, repuestas=...)` y `MARCA_REPUESTA`.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: documentos-ia › Revisión de fidelidad que borra tareas o acuerdos] | Revisión que quita una fila de tareas o una viñeta de acuerdos: se aplica y la fila o viñeta vuelve al final, marcada; la frase corregida entra; la nota lista lo repuesto; sin «se descartó». La tarea reescrita por «Sin tareas» vuelve marcada | `tests/test_asistente_ia.py:449` (`test_revision_que_quita_una_tarea_se_aplica_y_la_repone_marcada`), `:409` (`test_acuerdo_quitado_se_repone_marcado`), `:395` (`test_tarea_cambiada_por_sin_tareas_se_repone`); `src/asistente_ia.py:98` (`PROMPT_REVISION`), `:976` (`reponer_lo_quitado`) | cumple |
| 2 | [MODIFICA: documentos-ia › Revisión de fidelidad que borra tareas o acuerdos] | Solo se repone lo que falta y donde la tabla o la lista bajan de número; sin título de sección donde reponer, la revisión se descarta con el motivo de secciones; en resúmenes no aplica (una viñeta de «### Puntos clave» se acepta sin marca) | `tests/test_asistente_ia.py:379` (`test_tarea_reescrita_y_otra_quitada_solo_repone_la_quitada`), `:372` (`test_reponer_lo_quitado_sin_bajar_no_cambia_nada`), `:431` (`test_sin_la_seccion_donde_reponer_se_descarta`), `:322` (`test_revision_que_pierde_secciones_y_tareas_da_el_motivo_de_secciones`), `:276` (`test_revision_de_resumen_no_aplica_la_regla_de_tareas`); `src/asistente_ia.py:294` (`_sin_donde_reponer`), `:971-972` | cumple |
| 3 | [MODIFICA: documentos-ia › Notas de la aplicación juntas] | Nota de lo repuesto: formato con 1, 2 y 6 elementos, vacío, recorte a 120 caracteres, «No asignado» sin paréntesis, orden de las notas; sin marca ni nota en las peticiones a Copilot | `tests/test_asistente_ia.py:356` (`test_nota_de_lo_repuesto_formato_y_tope`), `:337` (`test_lo_repuesto_no_se_envia_a_copilot`); `src/asistente_ia.py:483` (`_recortado`), `:489` (`_lista_entre_comillas`), `:498` (`_cita_de_lo_repuesto`), `:536` (la nota en `notas_de_la_aplicacion`) | cumple |

**Verificación:**

- `./venv/bin/python -m pytest -q`: 514 pasan.
- Comprobación con mutante (orquestador): con la reposición desactivada fallan los 7 tests que dependen de ella. Los de formato y «sin bajar no cambia nada» siguen en verde, como deben.
- Desviaciones aceptadas por el orquestador: código escrito en dos bloques (varios tests verdes al primer intento, comprobados con el mutante); conteo de marcas por línea en los tests, no por apariciones; `reponer_lo_quitado` no valida el título, lo garantiza `_generar`.
- Verificación manual del diseño (copiar la salida a un `.md` y abrirla en un visor) no hecha en este cierre. Lo observable está cubierto con `httpx` simulado.

**Pendientes aceptados:**

- `contar_filas_tareas` y `contar_vinetas_acuerdos` quedan sin uso en `_generar`, con sus tests (`test_contar_filas_de_tareas`, `test_contar_vinetas_de_acuerdos`) como guarda. Quitarlas sería un carril S aparte.
- `normalizar_tabla_tareas` solo quita «Sin tareas» en tablas de 3 columnas. Es el comportamiento de antes; con R4 basta para el criterio 1.
- `reponer_lo_quitado` llamada a mano con un `despues` sin el título de su sección falla con `TypeError`. `_generar` lo evita con `_sin_donde_reponer`.
