# 22 · Avanzado de Transcripción, Historial y Restablecer

> Origen: `BACKLOG.md`, «Backlog» #5 (panel de configuración, carril L), séptima de sus historias — Diseño:
> docs/disenos/06-panel-de-configuracion.md §Historia C2 (con «Plan técnico», 3: `restablecer_formulario`, y 5: tabla de
> campos, `restablecer_configuracion`, `aplicar_guardado` con las partes de C2 y el párrafo de `historial.ruta`;
> «Decisiones tomadas», de producto 2, 3 y 5 y técnicas 2 y 7; CUJ 2 y CUJ 5; alternativa E; «Revisión (2026-11-22)»,
> filas «C demasiado grande» y «Restablecer no olvidaba `_modelo_preferido` ni el asistente») — carril M. Reglas de oro
> 3, 5, 7, 8 y 9 de `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Parte
> del estado que dejan la 17 a la 20 (A1, A2a, A2b y A3, hechas; última: commit `60e9017`) y la 21 (C1, aprobada y en
> implementación en la copia de trabajo, sin commit).

## Historia

Como usuario de la ventana, quiero ajustar desde la vista «⚙ Configuración» los parámetros finos de Whisper (plegados
en «Avanzado» para que no estorben) y el archivo del historial, sabiendo que este último pide reiniciar, y poder volver
de un golpe a los valores del proyecto, incluido el modelo de IA que elegí, para deshacer mis ajustes sin editar
`preferencias.json` a mano.

## Criterios de aceptación

- [ ] [NUEVO] Dado el YAML del proyecto (`transcripcion.beam_size: 5`, `transcripcion.no_speech_threshold: 0.6`) y sin
  `preferencias.json`, cuando se abre «⚙ Configuración», entonces el grupo «Transcripción» muestra sus cuatro campos y
  un «▸ Avanzado» plegado que oculta los siete de decodificación (Haz de búsqueda, Candidatos, Temperatura de Whisper,
  Usar el texto anterior como contexto, Umbral de compresión, Umbral de probabilidad, Umbral de silencio); y si se
  despliega, se escribe `cinco` en «Haz de búsqueda» y `0,5` en «Umbral de silencio» y se pulsa «Guardar», bajo «Haz de
  búsqueda» aparece «`transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «cinco»).», bajo «Umbral de
  silencio» no hay error, el pie dice «No se guardó nada: corrige 1 valor.» y `preferencias.json` no se crea; al
  corregir a `3` y guardar, el pie dice «Configuración guardada» y el archivo es exactamente `{"configuracion":
  {"transcripcion": {"beam_size": 3, "no_speech_threshold": 0.5}}}`.
- [ ] [NUEVO] Dado el grupo «Historial» con «Archivo del historial (relativo a la carpeta del proyecto)» en
  `data/historial.db` y la nota «Se aplica al reiniciar la app.», cuando se cambia a otra ruta válida (por ejemplo
  `data/otro.db` o una ruta absoluta fuera del proyecto) y se pulsa «Guardar», entonces el pie dice «Configuración
  guardada · el historial nuevo se abrirá al reiniciar la app», la vista Historial (`Ctrl+2`) sigue mostrando las
  mismas entradas de la base de antes y lo que se transcriba o genere hasta reiniciar se guarda en ella, y el archivo
  nuevo no se crea; al cerrar y abrir la ventana, el Historial usa la ruta nueva.
- [ ] [NUEVO] Dado un `preferencias.json` con `{"x": 1, "modelo_ia": "claude-sonnet-5.5", "configuracion": {"salida":
  {"formato": "srt"}, "transcripcion": {"beam_size": 50}}}` (la vista muestra arriba el aviso de `beam_size` inválido),
  el modelo de Whisper del lateral cambiado a mano a `tiny` y una generación anterior que dejó notas conservadas, cuando
  se pulsa «Restablecer valores del proyecto» y se confirma el diálogo «Restablecer configuración», entonces el archivo
  queda `{"x": 1}`, el pie dice «Se restablecieron los valores de config/settings.yaml», desaparece el recuadro de
  avisos, los campos muestran los valores del YAML, en el lateral el formato vuelve a `txt` y el modelo de Whisper
  sigue en `tiny`, el selector de modelo de IA y la línea de estado de las pestañas Resumen y Minuta muestran
  `claude-haiku-5.5` (el del YAML), y la siguiente generación vuelve a pedir todas las partes (las notas conservadas se
  pierden, como al cambiar de modelo). Si se responde «No», nada cambia; y si la escritura falla (carpeta de
  preferencias sin permiso de escritura), aparece el diálogo «Configuración» con «No se pudo restablecer la
  configuración: <motivo>.», el archivo no cambia y no cambia nada en la vista, el lateral ni el selector de modelo de IA.

El caso del error está en el criterio 1 (valor inválido) y en el 3 (respuesta «No» y fallo de escritura); el rechazo
de Restablecer durante un proceso y el CUJ 5 (preferencias ilegibles y su aviso, que desaparece al guardar) se
comprueban en el guion y en un test, sin criterio propio (ver «Supuestos», 6).

### Cómo se verifican

**Sin ventana** (con `pytest`, sin red; `RUTA_PREFERENCIAS` aislada por el fixture autouse `preferencias_aisladas` de
`tests/conftest.py:58`; el proyecto sale de `cargar_configuracion` de un YAML en `tmp_path` y `anterior` de
`combinar(proyecto, leer_ajustes())`; los métodos de la ventana se llaman sin enlazar con un `types.SimpleNamespace`
como `self`, como en los tests de C1):

- `tests/test_configuracion.py::test_restablecer_formulario_devuelve_el_yaml_y_sin_modelo` (criterio 3): con el
  `preferencias.json` del criterio 3 y `preferido_anterior="claude-sonnet-5.5"`, `restablecer_formulario(proyecto,
  anterior, preferido_anterior)` devuelve `errores` vacío, `efectiva == proyecto`, `modelo_preferido` `None`, `avisos`
  vacío, `cambiadas == {("salida", "formato"), ("ia", "modelo")}` y el mensaje «Se restablecieron los valores de
  config/settings.yaml»; el archivo queda `{"x": 1}` y el YAML conserva bytes y `st_mtime_ns`. Con
  `historial.ruta` guardado, `cambiadas` lo incluye y el mensaje termina en « · el historial nuevo se abrirá al
  reiniciar la app» (ver «Supuestos», 3). Sin nada guardado y sin modelo: `cambiadas` vacío.
- `tests/test_configuracion.py::test_restablecer_formulario_con_fallo_no_devuelve_efectiva` (criterio 3):
  `configuracion.restablecer_ajustes` parcheado para lanzar `PermissionError(errno.EACCES, "Permission denied")` da
  `efectiva` y `modelo_preferido` `None`, `cambiadas` vacío, mensaje «No se pudo restablecer la configuración:
  Permission denied.», y el archivo conserva sus bytes.
- `tests/test_ui.py::test_campos_avanzados_e_historial` (criterios 1 y 2): `CAMPOS` tiene exactamente las 15 claves de
  `_tabla()` fuera de `ia`, en el orden en que se pintan (las cuatro de Transcripción, las siete de decodificación,
  las tres de Salida y `historial.ruta`); las siete de decodificación con `avanzado=True` y grupo «Transcripción»,
  `condition_on_previous_text` con control «interruptor» y las otras seis «texto»; `historial.ruta` en el grupo
  «Historial», control «texto», `avanzado=False` y nota «Se aplica al reiniciar la app.»; las demás sin nota.
- `tests/test_ui.py::test_campos_de_transcripcion_y_salida` (de C1) **se ajusta**: comprueba las siete claves de C1 entre
  los campos con `avanzado=False` de los grupos «Transcripción» y «Salida», no que `CAMPOS` tenga solo esas siete.
- `tests/test_ui.py::test_restablecer_configuracion_rechazado_o_cancelado_no_escribe` (criterio 3; añadido, ver
  «Supuestos», 6), parametrizado: con `_transcribiendo` → `True`, `messagebox.showwarning` anota («Configuración»,
  «Espera a que termine el proceso en curso.») y no se pregunta; con `askyesno` → `False`, devuelve `None`. En los dos,
  `src.ui.restablecer_formulario` parcheado para fallar si se llama y `preferencias.json` no existe.
- `tests/test_ui.py::test_aplicar_guardado_repone_el_modelo_de_ia_y_olvida_el_asistente` (criterio 3; añadido): con un
  resultado de restablecer (`modelo_preferido` `None`, `("ia", "modelo")` en `cambiadas`) y un `self` doble con
  `_modelo_preferido="claude-sonnet-5.5"`, `var_modelo_ia`, `combo_modelo_ia`, dos `tabs_ia` cuyas etiquetas de estado
  muestran una «Modelo: GitHub Copilot · claude-sonnet-5.5» y otra «Listo en 12 s con …», y un `_documentos` que anota
  `olvidar_asistente`: queda `_modelo_preferido` `None`, `var_modelo_ia` recibe «claude-haiku-5.5», las opciones del
  selector lo incluyen, solo la primera etiqueta cambia (a «Modelo: GitHub Copilot · claude-haiku-5.5») y
  `olvidar_asistente` se llama una vez; con un resultado sin `("ia", "modelo")` en `cambiadas`, nada de eso se toca.
- Siguen pasando sin cambios `test_aplicar_guardado_solo_toca_las_claves_cambiadas`,
  `test_guardar_configuracion_durante_un_proceso_no_escribe` y `test_motivo_para_no_guardar_durante_un_proceso` (C1),
  `test_restablecer_borra_ajustes_y_modelo_y_conserva_lo_demas` (`tests/test_configuracion.py:739`) y los de fallo de
  lectura y escritura parametrizados con `restablecer_ajustes` (`:768`, `:796`).

Paso rojo: con el código de hoy fallan al importar `restablecer_formulario` de `src.configuracion` y
`restablecer_configuracion` de `AppTranscriptor`, y `test_campos_avanzados_e_historial` porque `CAMPOS` solo tiene
siete claves y `Campo` no tiene `nota`.

**Solo en la ventana real:** el bloque plegado y desplegado, la nota del historial, el recuadro de avisos, el diálogo
de confirmación, que el historial abierto no cambie hasta reiniciar y que el lateral y las pestañas de IA se repongan.
Lo ejecuta el orquestador con el guion de abajo.

### Guion de verificación manual (ventana real)

Un script en la carpeta temporal `T` (no en el repo), lanzado desde la raíz con `./venv/bin/python <script>`. Los
diálogos se responden por script: antes de construir la ventana se sustituyen `src.ui.messagebox.askyesno`,
`showwarning` y `showerror` por funciones que anotan `(título, texto)` en una lista `dialogos` y, en `askyesno`,
devuelven la siguiente respuesta de una cola. El script no puede correr como root (el paso 11 depende de los permisos).

1. **Antes de importar `src.ui`:** apunta `src.configuracion.RUTA_PREFERENCIAS` a `T/prefs/preferencias.json` y
   escribe en él `{` (JSON inválido). Parchea `httpx.get`, `httpx.post`, `httpx.stream` y `src.copilot.leer_token`
   con funciones que anotan en `llamadas` y lanzan `AssertionError`. Guarda bytes y `st_mtime_ns` de
   `config/settings.yaml`.
2. Construye la ventana como `ui.main()` (`cargar_configuracion`, `combinar(proyecto, leer_ajustes())`,
   `AppTranscriptor(efectiva, proyecto=proyecto, avisos=avisos)`) y procesa eventos un segundo. **Comprueba:**
   `llamadas == []`; Registro anota «Las preferencias <ruta> no son un JSON válido; se usan los valores de
   config/settings.yaml. Al guardar se reemplazará el archivo.».
3. `Ctrl+3`. **Comprueba:** arriba, un recuadro con ese mismo aviso; en «Transcripción», los cuatro campos de C1 y
   «▸ Avanzado» plegado (los siete campos de decodificación no están mapeados: `winfo_ismapped()` falso, o en una
   captura); «Salida» como en C1; «Historial» con «Archivo del historial (relativo a la carpeta del proyecto)» =
   `data/historial.db`, la clave `historial.ruta` en gris y la nota «Se aplica al reiniciar la app.»; «Restablecer
   valores del proyecto» junto a «Guardar»; `llamadas == []`.
4. Despliega «Avanzado». **Comprueba:** Haz de búsqueda `5`, Candidatos `5`, Temperatura de Whisper `0.0`, Usar el
   texto anterior como contexto apagado, Umbral de compresión `2.4`, Umbral de probabilidad `-1.0`, Umbral de silencio
   `0.6`, cada uno con su clave en gris.
5. Escribe `cinco` en «Haz de búsqueda» y `0,5` en «Umbral de silencio»; «Guardar». **Comprueba:** el error exacto del
   criterio 1 bajo «Haz de búsqueda», nada bajo «Umbral de silencio», pie «No se guardó nada: corrige 1 valor.», el
   archivo sigue siendo `{` y el recuadro de avisos sigue. Pliega «Avanzado» y pulsa «Guardar» otra vez:
   **Comprueba:** «Avanzado» se despliega solo y el error se ve (ver «Supuestos», 4).
6. Cambia «Haz de búsqueda» a `3`; «Guardar». **Comprueba:** pie «Configuración guardada»; el archivo es exactamente
   `{"configuracion": {"transcripcion": {"beam_size": 3, "no_speech_threshold": 0.5}}}`; el recuadro de avisos
   desaparece y `app.avisos_preferencias == []` (CUJ 5); el YAML no cambió.
7. Anota `ruta0 = app.historial.ruta` y, con `Ctrl+2`, cuántas entradas lista el Historial (`len(app.panel_historial._items)`).
   `Ctrl+3`, escribe `src/historial.db` en «Archivo del historial» y «Guardar». **Comprueba:** bajo el campo,
   «`historial.ruta` no puede estar dentro de la carpeta del proyecto salvo en data/ (vale «src/historial.db»).» y pie
   «No se guardó nada: corrige 1 valor.».
8. Escribe `T/otro.db` (ruta absoluta; se usa en lugar de `data/otro.db` para no dejar una base en el repo) y
   «Guardar». **Comprueba:** pie «Configuración guardada · el historial nuevo se abrirá al reiniciar la app»; el
   archivo tiene además `"historial": {"ruta": "T/otro.db"}`; `app.historial.ruta == ruta0`,
   `app._documentos._historial is app.historial` y `app.panel_historial.historial is app.historial`; `Ctrl+2` lista
   las mismas entradas que en el paso 7; `T/otro.db` no existe. Registro anota las claves cambiadas.
9. Cierra (`app.destroy()`) y construye otra ventana como en el paso 2. **Comprueba:** `app.historial.ruta ==
   Path("T/otro.db")` y el archivo existe; `Ctrl+2` lista cero entradas; `llamadas == []`.
10. Prepara Restablecer: edita a mano el archivo para que sea exactamente el del criterio 3 más la clave
    `"historial": {"ruta": "T/otro.db"}` dentro de `configuracion`; cierra y vuelve a construir la ventana (así abre
    con `srt`, el aviso de `beam_size` y `modelo_ia`). En el lateral pon «Modelo» en `tiny` (`app.var_modelo.set`).
    Asigna `app._documentos._asistente = centinela` (un `object()`). **Comprueba:** el selector de modelo de IA y las
    dos pestañas de IA muestran `claude-sonnet-5.5`; `Ctrl+3` muestra el aviso «… `transcripcion.beam_size` debe ser un
    número entero entre 1 y 20 (vale «50») …».
11. Fallo: `os.chmod(T/prefs, 0o500)`, cola de `askyesno` = `[True]`, pulsa «Restablecer valores del proyecto».
    **Comprueba:** `dialogos` tiene («Restablecer configuración», «¿Volver a los valores de config/settings.yaml? Se
    borrarán los cambios guardados en este panel y el modelo de IA elegido.») y después («Configuración», «No se pudo
    restablecer la configuración: <motivo>.»); el pie muestra ese mensaje; el archivo conserva sus bytes y no queda
    `preferencias.json.tmp`; el lateral sigue en `srt` y `tiny`, el selector de IA en `claude-sonnet-5.5` y
    `app._documentos._asistente is centinela`. Devuelve el permiso (`0o700`).
12. Cancelar: cola `[False]`, «Restablecer». **Comprueba:** se preguntó y no hay más diálogos; el archivo no cambió;
    los campos, el lateral y el selector de IA, igual.
13. Durante un proceso: asigna `app.transcripcion_thread = threading.Thread(target=time.sleep, args=(5,),
    daemon=True)` y arráncalo; «Restablecer». **Comprueba:** («Configuración», «Espera a que termine el proceso en
    curso.») sin pregunta previa; el pie muestra ese texto; el archivo no cambió. Espera a que acabe el hilo.
14. Restablecer de verdad: cola `[True]`, «Restablecer». **Comprueba:** el archivo es exactamente `{"x": 1}`; pie «Se
    restablecieron los valores de config/settings.yaml · el historial nuevo se abrirá al reiniciar la app» (la ruta
    del historial también volvió al YAML); no hay recuadro de avisos; los campos muestran el YAML (`beam_size` 5,
    formato `txt`, `data/historial.db`); con `Ctrl+1`, el lateral tiene formato `txt` y «Modelo» sigue en `tiny`; el
    selector de IA muestra `claude-haiku-5.5` y lo tiene entre sus opciones; las dos pestañas de IA dicen «Modelo:
    GitHub Copilot · claude-haiku-5.5»; `app._modelo_preferido is None`; `app._documentos._asistente is None`;
    `app.historial.ruta` sigue siendo `T/otro.db`; el YAML no cambió; `llamadas == []`.
15. Repetir sin nada guardado: `app._documentos._asistente = centinela`, cola `[True]`, «Restablecer». **Comprueba:**
    el archivo sigue `{"x": 1}`; pie «Se restablecieron los valores de config/settings.yaml» (sin la nota de
    reinicio); el asistente sigue siendo `centinela` (el modelo no cambió); el lateral no cambió.
16. Cierra y construye otra ventana. **Comprueba:** el lateral y la vista muestran los valores del YAML, el selector de
    IA `claude-haiku-5.5` y `app.historial.ruta` es la de `data/historial.db`; `llamadas == []`.
17. Al terminar: borra `T`; `git status --short` no lista `config/settings.yaml`, ninguna preferencia ni ninguna base;
    `./venv/bin/python -m pytest -q` pasa.

## Plan

- Restablecer sin ventana: borrar lo guardado con el restablecimiento atómico de A2b (si falla, devolver solo el
  mensaje de error), releer y combinar como al abrir, sin modelo preferido, y devolver el mismo tipo de resultado que
  el guardado, con las claves que cambiaron (más el modelo de IA si cambió el efectivo) y la nota de reinicio si una
  de ellas la pide.
- En la vista: los siete campos de decodificación en un bloque «Avanzado» plegado dentro de Transcripción (se
  despliega solo si uno de ellos trae un error), el grupo Historial con su nota, un recuadro arriba con los avisos de
  las preferencias que se repinta al refrescar, y «Restablecer valores del proyecto» en el pie, que pide a la ventana
  restablecer y, si se hizo, refresca los campos y pinta el mensaje.
- En la ventana: restablecer con el mismo rechazo que Guardar durante un proceso, una confirmación «Restablecer
  configuración», diálogo de error si la escritura falla (sin aplicar nada) y, si va bien, aplicar el resultado como un
  guardado.
- Aplicar un guardado pasa a quedarse con el modelo preferido del resultado y, solo si cambió el modelo de IA
  efectivo: poner el selector lateral de IA en el nuevo (ofreciéndolo en su lista sin familias excluidas), actualizar
  la línea de estado de las pestañas de IA que mostraban el modelo anterior y olvidar el asistente.
- Tests sin ventana de los campos, de restablecer (bien y con fallo), del rechazo y la cancelación en la ventana y de
  la reposición del modelo de IA; el test de campos de C1 se ajusta a la lista completa.

Archivos del `/pair` (lista cerrada, la del diseño): `src/configuracion.py` (`restablecer_formulario`),
`src/ui_configuracion.py` (`Campo` con `nota` y el control «texto»; los ocho campos de C2 en `CAMPOS`; «Avanzado»
plegado; recuadro de avisos en `refrescar`; `_restablecer` en `PanelConfiguracion`), `src/ui.py`
(`restablecer_configuracion`; `aplicar_guardado` con `_modelo_preferido`, `var_modelo_ia`, opciones de
`combo_modelo_ia`, etiquetas de estado de `tabs_ia` y `olvidar_asistente` si cambió el modelo; importar
`restablecer_formulario`), `tests/test_configuracion.py`, `tests/test_ui.py`. Si hace falta otro, se para y se vuelve
al diseño. El delta de spec (`docs/specs/configuracion.md`, y en `docs/specs/documentos-ia.md` la frase de «Fallo de
una parte» sobre cuándo se pierden las notas) y el resto de la documentación los escribe `/cerrar`.

## Fuera de alcance

- **D1 y D2:** el grupo IA del panel (dominio de Enterprise, revisión de fidelidad, «Avanzado» de IA, «Modelo de IA»
  con su «↻»), `argumentos_asistente`, `_epoca_ia`, `aviso_modelo` y los parámetros `consultando_modelos` y
  `login_abierto` de `motivo_para_no_guardar`. En C2 el asistente se olvida solo si cambia el modelo de IA efectivo
  (ver «Supuestos», 5).
- **B, E1 y E2:** la sección «Sesión de GitHub Copilot». Restablecer no toca el token ni la sesión.
- Reabrir el historial al cambiar `historial.ruta` (alternativa E), y botones de restablecer por campo.
- Que «Restablecer» borre otras claves de `preferencias.json` (se conservan, como `"x"`), o que la CLI lea las
  preferencias.
- Cambiar `restablecer_ajustes`, `guardar_formulario`, `validar_formulario`, `valores_laterales` o sus mensajes.

## Sugerencias (a tu criterio)

- «Avanzado» puede ser un `CTkButton` transparente «▸ Avanzado» / «▾ Avanzado» que hace `grid()` / `grid_remove()` de
  un `CTkFrame` con los siete campos, como `_alternar_avanzado` del panel lateral (`src/ui.py`, `_alternar_avanzado`).
  `_construir_campo` de C1 ya sirve si recibe ese marco como padre.
- `restablecer_formulario` puede compartir con `guardar_formulario` el cálculo de `cambiadas` y del mensaje (un
  ayudante privado de tres líneas), porque ya serían dos usos.
- En `aplicar_guardado`, calcular el texto de las pestañas con `_texto_modelo_ia()` **antes** de sustituir
  `configuracion` y `_modelo_preferido`, como hace `_al_cambiar_modelo_ia`.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es que Restablecer deje la ventana a medias: el archivo borrado pero el selector de IA o
   el asistente con el modelo anterior (la siguiente minuta saldría con un modelo que ya no está guardado), o al revés,
   que aplique algo cuando la escritura falló. Lo cubren el criterio 3 (éxito y fallo) y
   `test_aplicar_guardado_repone_el_modelo_de_ia_y_olvida_el_asistente`.
2. **Dependencia de C1 (en implementación).** Se toma del código de la copia de trabajo y de la historia 21:
   `Campo(seccion, clave, etiqueta, control, grupo, avanzado=False, opciones=())` (sin `nota`, que añade C2),
   `CAMPOS`, `motivo_para_no_guardar(transcribiendo, generando)`, `PanelConfiguracion` con `refrescar`, `_guardar` y
   `_pintar`, `AppTranscriptor.guardar_configuracion(valores_widget)` y `aplicar_guardado(resultado)`. El panel pinta
   un encabezado cada vez que cambia `grupo`, así que los campos avanzados van en `CAMPOS` justo después de los cuatro
   de Transcripción. Si C1 se cierra con otros nombres, esta historia sigue a los que queden.
3. **Nota de reinicio también al restablecer.** El diseño da a `restablecer_formulario` el mensaje fijo «Se
   restablecieron los valores de config/settings.yaml», pero restablecer un `historial.ruta` guardado también cambia la
   base solo al reiniciar. Se añade el mismo sufijo que en Guardar cuando `cambiadas ∩ REQUIEREN_REINICIO` no está
   vacío; sin eso, el pie diría que se volvió al YAML mientras el historial sigue en la otra base.
4. **«Avanzado» con un error dentro.** El diseño no dice qué pasa si un campo plegado tiene un error: el pie diría
   «corrige 1 valor» sin que se vea cuál. Se despliega solo al pintar un error en uno de sus campos. Empieza plegado al
   construir la vista; `refrescar` no cambia si está plegado o no.
5. **Modelo de IA y asistente.** `aplicar_guardado` guarda siempre `resultado.modelo_preferido` en `_modelo_preferido`
   (es estado, no un control), pero toca `var_modelo_ia`, las opciones de `combo_modelo_ia`, las etiquetas de estado y
   el asistente **solo si `("ia", "modelo")` está en `cambiadas`** (decisión de producto 3: solo cambia lo que cambió);
   así `test_aplicar_guardado_solo_toca_las_claves_cambiadas` de C1 sigue pasando sin cambios. Las opciones del
   selector se pasan por `copilot.opciones_de_modelo(<las actuales>, <el nuevo>)`: el diseño solo pone
   `var_modelo_ia.set`, pero sin esto el selector mostraría el modelo del YAML sin ofrecerlo en su lista (spec «Lista
   de modelos bajo demanda»: el selector ofrece el configurado), y nunca ofrece una familia excluida (regla 7). El
   asistente se olvida solo si cambió el modelo, como dice el diseño para C2; si `preferencias.json` traía claves de IA
   editadas a mano (`ia.temperatura`, el dominio…), restablecerlas no olvida el asistente hasta D1
   (`argumentos_asistente`).
6. **Sin criterio propio para el rechazo durante un proceso ni para el CUJ 5.** El rechazo de Restablecer es el mismo
   de Guardar (criterio 3 de C1, misma función y mismo texto); el CUJ 5 lo pide la verificación del diseño para C2.
   Los dos van al guion (pasos 2, 3, 6 y 13) y a tests (`test_restablecer_configuracion_rechazado_o_cancelado_no_escribe`,
   añadido a los del diseño). El aviso de `beam_size` inválido del criterio 3 ejercita además el recuadro de avisos.
7. **Restablecer sin nada guardado** escribe igualmente el archivo (si no existía, queda `{}`): es lo que hace hoy
   `restablecer_ajustes` (`src/configuracion.py:251-255`). No cambia nada visible y no se trata como error.
8. **Marcas.** Los tres criterios son `[NUEVO]`: `docs/specs/configuracion.md` no tiene ninguna vista, ni campos
   avanzados, ni restablecer; «Modelo de IA elegido en la ventana» solo dice cómo se guarda y se lee `modelo_ia`, y
   borrarlo es un comportamiento más, no un cambio de esos. Que las notas conservadas se pierdan al restablecer es la
   regla de hoy («se pierden … al cambiar de modelo», `docs/specs/documentos-ia.md`, «Fallo de una parte»); `/cerrar`
   puede nombrarlo allí.
9. **La ruta del historial en el guion** es absoluta en la carpeta temporal en vez de `data/otro.db`, para no dejar
   una base en el repo; las dos son válidas (A2a) y el comportamiento es el mismo.
10. **Líneas** (copia de trabajo sobre `60e9017`, con C1 a medias; manda el nombre de la función): `src/configuracion.py`:
    `_leer_para_escribir` `:197-204`, `restablecer_ajustes` `:251-255`, `_escribir_preferencias_atomico` `:258-269`
    (el diseño la llama `_escribir_preferencias`), `modelo_ia_efectivo` `:272-274`, `claves_cambiadas` `:347-349`,
    `valores_laterales` `:352-368`, `REQUIEREN_REINICIO` `:467`, `ResultadoGuardado` `:470-478`, `guardar_formulario`
    `:481-500`; `src/ui.py`: `AppTranscriptor.__init__` `:90` (`self.historial` `:130`, `self._documentos` `:134`,
    `_modelo_preferido` y `var_modelo_ia` `:144-145`), `combo_modelo_ia` `:268`, etiqueta `estado` de
    `_construir_tab_ia` `:382`, `_transcribiendo` `:576`, `_generando_ia` `:754`, `_modelo_ia_configurado` `:946`,
    `_texto_modelo_ia` `:949`, `_al_cambiar_modelo_ia` `:993-1008`, `mostrar_vista` `:1076`, `guardar_configuracion`
    `:1106`, `aplicar_guardado` `:1124`; `src/ui_configuracion.py`: `Campo` `:17`, `CAMPOS` `:27`, `refrescar`
    `:121`, `_guardar` `:144`, `_pintar` `:150`; `src/historial.py`: `Historial.__init__` `:106-112` (la ruta relativa
    se resuelve contra la raíz del proyecto); `src/flujo_documentos.py`: `GestorDocumentos.__init__` `:113`,
    `olvidar_asistente` `:163`; `src/copilot.py`: `opciones_de_modelo` `:314`.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa (427 tests). Code review: revisión del orquestador, listo para commit; decisiones aceptadas: `_resultado_tras_escribir` compartido por guardar y restablecer, ayudante `_etiqueta_modelo_ia` y `aplicar_guardado` que asigna `_modelo_preferido` siempre. Delta de spec: `docs/specs/configuracion.md`, sección «Vista Configuración» (tres criterios nuevos, con `Origen` en esta historia; la frase de grupos y la de «dos grupos» del criterio 1 de la historia 21 se actualizan). «Preferencias del usuario al abrir la ventana» y «Modelo de IA elegido en la ventana» no quedan contradichas, así que no cambian.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | «Avanzado» plegado con los siete campos de decodificación; con `cinco` y `0,5` guardar muestra el error bajo «Haz de búsqueda», «No se guardó nada: corrige 1 valor.» y no crea el archivo; con `3` guarda el archivo exacto | Campos y plegado: `tests/test_ui.py:99` (`test_campos_avanzados_e_historial`). Pie: `tests/test_configuracion.py:963`. Despliegue con error y pintado: `src/ui_configuracion.py:200` (`_desplegar_avanzado`), `:231` (`_pintar`). Ventana real: verificación manual, pasos 2 a 6 | cumple (tests y verificación en la ventana) |
| 2 | [NUEVO] | Grupo «Historial» con la nota «Se aplica al reiniciar la app.»; cambiar la ruta y guardar da el pie con la nota de reinicio, el historial abierto no cambia y al reiniciar usa la ruta nueva | Grupo, control y nota: `tests/test_ui.py:99`. Pie con la nota: `tests/test_configuracion.py:1014`. Nota bajo el campo: `src/ui_configuracion.py:26` (`Campo.nota`). Ventana real: verificación manual, pasos 7 a 9 | cumple (tests y verificación en la ventana) |
| 3 | [NUEVO] | «Restablecer valores del proyecto» con confirmación borra `configuracion` y `modelo_ia` (el archivo queda `{"x": 1}`), repone campos, lateral y selector de IA, olvida el asistente y muestra el pie; «No» o fallo de escritura no cambian nada; con proceso en curso avisa sin preguntar | Restablecer con éxito: `tests/test_configuracion.py:1056` (`test_restablecer_formulario_devuelve_el_yaml_y_sin_modelo`). Fallo: `tests/test_configuracion.py:1099`. Rechazo y cancelación: `tests/test_ui.py:210`. Reposición del modelo y del asistente: `tests/test_ui.py:246`. Implementación: `src/configuracion.py:495` (`restablecer_formulario`), `src/ui.py:1129` (`restablecer_configuracion`), `:1147` (`aplicar_guardado`), `src/ui_configuracion.py:223` (`_restablecer`). Ventana real: verificación manual, pasos 10 a 15 | cumple (tests y verificación en la ventana) |

**Verificación (2026-11-22):** `./venv/bin/python -m pytest -q` pasa (427). Comprobado por el orquestador en la ventana real (tres arranques, con `httpx` y `copilot.leer_token` interceptados, `RUTA_PREFERENCIAS` temporal, diálogos capturados por script, usuario no root):

- Preferencias `{`: aviso de JSON inválido en Registro y en el recuadro de la vista; «▸ Avanzado» plegado; grupo Historial con `data/historial.db`; botón «Restablecer valores del proyecto».
- Avanzado: `cinco` en «Haz de búsqueda» y `0,5` en «Umbral de silencio», plegado de nuevo y Guardar → error bajo «Haz de búsqueda», nada bajo el umbral, «Avanzado» se despliega solo, pie «No se guardó nada: corrige 1 valor.», el archivo sigue `{`. Con `3`: archivo exactamente `{"configuracion": {"transcripcion": {"beam_size": 3, "no_speech_threshold": 0.5}}}` y recuadro de avisos oculto.
- Historial: `src/historial.db` rechazado con su mensaje. Ruta temporal fuera del repo: pie con la nota de reinicio; el historial abierto sigue en `data/historial.db` (también tras `Ctrl+2`) y el archivo nuevo no existe. Al reiniciar usa la ruta nueva, vacía.
- Restablecer sin permiso de escritura en la carpeta: diálogo de confirmación y después «No se pudo restablecer la configuración: Permission denied.»; archivo idéntico, sin temporal, asistente intacto. «No»: nada cambia. Con transcripción en curso: «Espera a que termine el proceso en curso.» sin pregunta. Sí: archivo `{"x": 1}`, pie con la nota de reinicio, formato `txt`, `tiny` se conserva, selector y pestañas de IA con `claude-haiku-5.5`, modelo preferido `None`, asistente olvidado, historial abierto sin cambiar. Repetir: pie sin la nota de reinicio y el asistente se conserva.
- 0 llamadas de red ni lecturas del token en todo el recorrido.

**Pendientes aceptados:**

- El triángulo «▸/▾» de «Avanzado» se ve muy pequeño. Se revisa en el repaso final del panel.
- El aviso de `preferencias.json` no válido sale dos veces en la consola (WARNING e INFO). Se revisa en el repaso final del panel.
- Restablecer no olvida el asistente si `preferencias.json` traía claves de IA editadas a mano (`ia.temperatura`, dominio…). Se resuelve con D1 (`argumentos_asistente`).
