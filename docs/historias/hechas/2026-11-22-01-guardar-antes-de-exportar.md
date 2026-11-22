# 01 · Guardar en el historial antes de exportar

> Origen: `BACKLOG.md`, «Salud del código» #1 — hallazgos A-01 y A-25 — carril M. Regla de oro 6 de `AGENTS.md`.
> Refinada con `/story` el 2026-11-22. Esta historia cubre A-01; A-25 se propone como historia aparte (ver
> «Historias derivadas»).

## Historia

Como usuario que transcribe reuniones largas, quiero que la transcripción, el resumen y la minuta queden guardados
en el historial antes de exportarlos junto al audio, y que un fallo al escribir ese archivo me avise sin descartar
el resultado, para no perder horas de transcripción ni pagar de nuevo una generación en Copilot.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dado un audio de una reunión de 90 minutos guardado en una carpeta donde no se puede
  escribir, cuando termina la transcripción, entonces la transcripción aparece en el historial con su texto y sus
  segmentos, se ve en la pestaña Texto con «Copiar», «Guardar como…» y los botones de generar resumen y minuta
  habilitados, y un aviso dice que no se pudo exportar `<nombre>_transcripcion.<formato>` y el motivo.
  (antes: el archivo se escribía antes de guardar en el historial; si la escritura fallaba, la transcripción no
  llegaba al historial, el estado decía «Error en la transcripción» con un diálogo de error, y aunque los segmentos
  seguían en pantalla, «Copiar», «Guardar como…» y los botones de IA quedaban deshabilitados: el resultado se
  perdía)
- [ ] [MODIFICA: sin spec] Dada una transcripción cuyo audio está en una carpeta donde no se puede escribir, cuando
  se pide la minuta y Copilot la devuelve, entonces la minuta queda guardada en esa entrada del historial (con el
  modelo usado y, si el título no se editó a mano, con el título que da la minuta), se muestra en la pestaña Minuta
  con «Copiar» y «Guardar como…» habilitados, y la línea de estado de la pestaña avisa que no se pudo exportar
  `<nombre>_minuta.md` y el motivo, sin pedir otra generación. Lo mismo vale para el resumen y `<nombre>_resumen.md`.
  (antes: el `.md` se escribía antes de guardar en el historial; si la escritura fallaba, el documento ya generado
  se descartaba: la pestaña mostraba «No se pudo generar: <error>», salía un diálogo de error, el historial no lo
  guardaba y había que volver a pedirlo a Copilot)
- [ ] [MODIFICA: sin spec] Dado que el historial no está disponible (no se pudo abrir al arrancar o falla al
  guardar, por ejemplo con el disco lleno) y tampoco se puede escribir junto al audio, cuando termina la
  transcripción, entonces la transcripción sigue en pantalla con «Copiar» y «Guardar como…» habilitados y un aviso
  dice que no quedó guardada en ningún sitio y que se use «Guardar como…». (antes: sin historial, la exportación
  era el único guardado; si fallaba, la transcripción se perdía como en el primer criterio, y un fallo del
  historial solo se anotaba en la pestaña Registro)

Cómo se verifican:

- **Con tests sin interfaz:** en los tres criterios, qué queda guardado (entrada del historial con texto, segmentos,
  documento, modelo y título) y que el fallo de exportación o de historial se devuelve como aviso con el nombre del
  archivo y el motivo, en vez de lanzarse. Con un historial temporal y un destino que falla al escribir.
- **Verificación manual:** que el aviso se ve en la ventana, que los botones quedan habilitados y que la pestaña
  Minuta o Resumen muestra el documento. Se prueba con un audio en una carpeta de solo lectura.

## Plan

- Sacar a funciones sin interfaz solo el paso de persistir de cada flujo: guardar en el historial, si lo hay, y
  después exportar. Cada una devuelve lo guardado y los avisos (exportación fallida, historial fallido) en vez de
  lanzar el error. No incluyen transcribir ni llamar a Copilot: eso sigue siendo el punto 5 del backlog.
- Transcripción: el guardado en el historial pasa al hilo de fondo, antes de exportar, como ya hace el documento. La
  ventana recibe el resultado, la entrada creada (o ninguna) y los avisos, y termina siempre por el camino de éxito:
  muestra el resultado y habilita los botones.
- Documentos: invertir el orden (historial y después archivo). Un fallo de exportación o de historial deja la
  pestaña con el documento y el aviso en su línea de estado. Solo un fallo de Copilot sigue por el camino de error
  de hoy.
- Avisos: en la transcripción, diálogo de advertencia y una línea en la pestaña Registro con el archivo y el motivo; en los documentos, la línea de estado de la pestaña y una línea en Registro, sin diálogo. Si no quedó guardado
  en ningún sitio, el texto lo dice y remite a «Guardar como…». «Abrir carpeta» queda deshabilitado si no se
  exportó nada.
- Tests de las funciones de persistir con historial temporal: exportación que falla, historial que falla y los dos
  a la vez, para la transcripción y para un documento.

## Fuera de alcance

- No sobrescribir sin aviso cuando dos audios con el mismo nombre comparten carpeta (A-25): pasa a una historia
  aparte porque exige elegir entre cambiar el nombre de los archivos o preguntar antes de sobrescribir.
- Regenerar un resumen o una minuta reemplaza al anterior en el historial y en el archivo, sin aviso. Es el
  comportamiento de hoy y no lo cita la auditoría.
- Conservar la transcripción parcial al cancelar: hoy se descarta (A-22 lo documenta como comportamiento conocido).
- Errores de «Guardar como…», que solo van a `stderr` (A-27, «Salud del código» #17).
- Cargar otro archivo sin invalidar el resultado anterior (A-02, #3): los documentos siguen exportándose con el
  nombre del archivo cargado.
- Sacar de la clase Tk los flujos completos de transcribir y generar (A-15, #5): aquí solo se extrae el paso de
  persistir, lo mínimo para probar sin ventana.
- Cancelar la generación de IA (A-04) y el aviso de documento incompleto (A-11).
- La CLI: no usa el historial y su exportación tiene su propio hallazgo (A-10, #9).
- `pytest` no está instalado ni declarado (A-16, #2): hay que instalarlo a mano para correr los tests de esta
  historia.

## Sugerencias

- Hacer «Salud del código» #17 (A-27) justo después: esta historia convierte «Guardar como…» en la vía para
  recuperar un resultado que no se exportó, y hoy sus errores no se ven en la ventana.
- La función de persistir de la transcripción es la primera pieza de «transcribir y persistir» del punto 5 (A-15).
  Conviene darle la forma que ese punto vaya a reutilizar, sin adelantar el resto de la extracción.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es perder la transcripción de una reunión larga porque falló la escritura del archivo
   (carpeta de solo lectura, medio de solo lectura o disco lleno, los escenarios de A-01). Lo cubre el primer
   criterio con una reunión de 90 minutos; el tercero cubre el disco lleno, donde también puede fallar el
   historial.
2. **A-25 no cabe en esta historia** y se propone aparte. La auditoría da dos soluciones (incluir la extensión de
   origen en el nombre o avisar antes de sobrescribir) y elegir es decisión del usuario. La revisión dice «se
   resuelve con A-01», pero arreglar el orden de guardado no cambia los nombres de los archivos ni evita la
   colisión.
3. **Un fallo del historial no impide exportar.** La regla 6 dice que primero se guarda en el historial y después
   el archivo; si el historial falla se exporta igual, con aviso. Para el documento, el plan lo trata igual que
   para la transcripción, aunque solo el tercer criterio lo fija, y solo para la transcripción.
4. **Cuando falla el historial y la exportación funciona**, se avisa del fallo del historial. Hoy, en la
   transcripción, ese fallo solo se anota en la pestaña Registro, y el usuario cree que quedó guardada.
5. **«Abrir carpeta» queda deshabilitado** si la exportación falló: hoy abre la carpeta del archivo exportado, y
   sin archivo no hay carpeta que mostrar.
6. **La forma del aviso** (diálogo de advertencia y línea en Registro, o solo la línea de estado de la pestaña en
   los documentos) es la más cercana a lo que la app ya hace con los errores. No es un requisito de la auditoría.

## Historias derivadas (para el backlog)

- Como usuario que guarda varias grabaciones con el mismo nombre en una carpeta (`reunion.m4a` y `reunion.mp4`),
  quiero que la app no sobrescriba sin aviso la transcripción, el resumen o la minuta de otra grabación, para no
  perder documentos ya exportados. — hallazgo A-25 — carril S si se incluye la extensión de origen en el nombre, M
  si se pregunta antes de sobrescribir. Decisión previa: cuál de las dos. Si cambian los nombres, comprobar que los
  patrones de `.gitignore` de «Salud del código» #4 (`*_resumen.md`, `*_minuta.md`) siguen cubriéndolos.

## Cierre

Cerrada con `/cerrar` el 2026-11-22. Tests: `./venv/bin/python -m pytest -q`, 85 pasan. Code review: «arreglar antes»
con 6 hallazgos; 5 arreglados y verificados por el orquestador; el restante queda en «Pendientes aceptados».

| # | Marca | Criterio | Evidencia con test y `ruta:línea` | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Transcripción en el historial con texto y segmentos; pestaña Texto con «Copiar», «Guardar como…» y botones de IA habilitados; aviso con `<nombre>_transcripcion.<formato>` y el motivo si falla la exportación | Tests: `tests/test_persistencia.py:39` (`test_transcripcion_exportacion_fallida_deja_entrada_en_historial`), `:193` (`test_transcripcion_error_inesperado_al_exportar_no_lanza`). Código: `src/persistencia.py:30` (`persistir_transcripcion`), `src/ui.py:661` (`_finalizar_ok`), `src/ui.py:703` (diálogo) | cumple (persistencia); ventana: verificación manual pendiente |
| 2 | [MODIFICA: sin spec] | Minuta (y resumen) en el historial con modelo y título; pestaña con «Copiar» y «Guardar como…» habilitados; aviso en la línea de estado con el archivo y el motivo, sin otra generación | Tests: `tests/test_persistencia.py:101` (`test_documento_exportacion_fallida_conserva_contenido_y_modelo`), `:113` (`test_documento_minuta_sin_titulo_editado_toma_titulo_de_la_minuta`), `:128` (`test_documento_historial_fallido_exporta_y_avisa`). Código: `src/persistencia.py:55` (`persistir_documento`), `src/ui.py:837`, `src/ui.py:848` (`_finalizar_documento_ia`) | cumple (persistencia); ventana: verificación manual pendiente |
| 3 | [MODIFICA: sin spec] | Historial no disponible y carpeta no escribible: la transcripción sigue en pantalla con «Copiar» y «Guardar como…», y el aviso dice que no quedó guardada en ningún sitio | Tests: `tests/test_persistencia.py:70` (`test_transcripcion_sin_historial_ni_exportacion_no_guarda_en_ningun_sitio`), `:142` (`test_documento_ambos_fallan_devuelve_los_dos_motivos`), `:157` (`test_aviso_sin_guardado_remite_a_guardar_como`). Código: `src/persistencia.py:84` (`texto_sin_guardado`) | cumple (persistencia); ventana: verificación manual pendiente |

**Verificación manual pendiente** (la parte visual de los tres criterios; con un audio en una carpeta de solo lectura):

- [ ] Transcribir en carpeta de solo lectura: aparece el diálogo con el archivo y el motivo; la transcripción queda en la pestaña Texto con los botones habilitados; «Abrir carpeta» deshabilitado.
- [ ] Historial no disponible y carpeta de solo lectura: la transcripción sigue en pantalla y el aviso dice que no quedó guardada en ningún sitio y remite a «Guardar como…».
- [ ] Minuta en carpeta de solo lectura: la pestaña Minuta muestra el documento con «Copiar» y «Guardar como…»; la línea de estado avisa del archivo y del motivo; no aparece diálogo.
- [ ] Resumen en carpeta de solo lectura: lo mismo que la minuta, con `_resumen.md`.
- [ ] Historial que falla con exportación correcta: el archivo existe junto al audio y el aviso dice que no se guardó en el historial.
- [ ] Flujo normal (carpeta escribible, historial disponible): sin diálogos de aviso; el archivo y la entrada del historial aparecen.

**Pendientes aceptados:**

- Verificación manual de la parte visual de los tres criterios (lista de arriba).
- Del code review: si se elimina la entrada del historial mientras Copilot genera un documento, la ventana dice «guardado en el historial» aunque no exista la fila. Pasa al punto 3 de «Salud del código» de `BACKLOG.md`.
- `src/persistencia.py` arrastra `faster_whisper` al importarse por `src/__init__.py`. Pasa al punto 5 de «Salud del código» de `BACKLOG.md`.
