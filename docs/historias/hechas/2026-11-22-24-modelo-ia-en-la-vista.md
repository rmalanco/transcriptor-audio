# 24 · El modelo de IA en la vista Configuración

> Origen: `BACKLOG.md`, «Backlog» #5 (panel de configuración, carril L), novena de sus historias; punto 22 de la
> sección «Backlog» — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia D2 (con «Plan técnico», 5: tabla de
> campos, fila D2, `motivo_para_no_guardar` y `aviso_modelo`, y `guardar_configuracion`; 6: «Grupo IA», viñeta D2;
> «Decisiones tomadas», de producto 3 y técnicas 2 y 7; «Requisitos no funcionales», «Cumplimiento (regla 7)»;
> «Verificación común»; «Revisión (2026-11-22)», filas «Carrera de «↻» con login, logout y cambio de dominio»,
> «Guardado no atómico; `_al_cambiar_modelo_ia` antes de guardar», «Regla 7 en el guardado» y «Literales sueltos») —
> carril M. Reglas de oro 1, 3, 5, 7 y 9 de `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin usuario al otro lado
> (ver «Supuestos»). Parte de lo que dejan la 17 a la 22 (A1, A2a, A2b, A3, C1 y C2, hechas; último commit `3d0f477`)
> y la 23 (D1, aprobada y aún sin implementar).

## Historia

Como usuario de la ventana, quiero elegir el modelo de IA en la vista «⚙ Configuración», con la misma lista que el
selector del lateral, y guardarlo junto con el resto de los valores de un solo golpe, sin que la vista me deje guardar
un modelo no autorizado ni guardar mientras la lista de modelos o el inicio de sesión siguen a medias, para tener todos
los valores por defecto en un único sitio sin que se mezclen con una consulta que aún no ha terminado.

## Criterios de aceptación

- [ ] [NUEVO] Dado el YAML del proyecto (`ia.modelo: "claude-haiku-5.5"`, `salida.formato: "txt"`), sin
  `preferencias.json`, con sesión de Copilot y una generación anterior que dejó creado el asistente, cuando se abre
  «⚙ Configuración», el grupo «IA» empieza con «Modelo de IA» (clave `ia.modelo` en gris) en `claude-haiku-5.5`, que
  ofrece lo mismo que el selector del lateral (`auto` y `claude-haiku-5.5`), y se pulsa su «↻», entonces el campo y el
  selector del lateral pasan a ofrecer la misma lista (`auto`, `gpt-4.1`, `claude-haiku-5.5`), sin perder lo que el
  formulario tuviera escrito sin guardar; y si se elige `gpt-4.1` en el campo, se cambia «Formato de salida» a `srt` y
  se pulsa «Guardar», el pie dice «Configuración guardada», `preferencias.json` queda exactamente `{"modelo_ia":
  "gpt-4.1", "configuracion": {"salida": {"formato": "srt"}}}` en **una sola** escritura, el selector del lateral
  muestra `gpt-4.1`, la línea de estado de Resumen y de Minuta dice «Modelo: GitHub Copilot · gpt-4.1», Registro anota
  «Configuración guardada: ia.modelo, salida.formato» y no «Modelo de IA: gpt-4.1» (la línea del selector lateral), la
  siguiente generación crea un asistente nuevo con `gpt-4.1` y `config/settings.yaml` no cambia. Elegir un modelo en el
  campo sin guardar no cambia el lateral ni el archivo, y al volver a la vista el campo muestra otra vez el guardado.
- [ ] [NUEVO] Dado un modelo efectivo de una familia no autorizada (`modelo_ia: "Mistral-Large-3"` en
  `preferencias.json`, o `ia.modelo: "Mistral-Large-3"` en el YAML sin preferencia), cuando se abre la vista, entonces
  bajo «Modelo de IA» aparece en rojo «El modelo configurado «Mistral-Large-3» es de la familia «mistral», que no está
  autorizada por la empresa: no se enviará. Elige otro.», el campo muestra `Mistral-Large-3` pero no lo ofrece entre sus
  opciones (ni antes ni después de «↻») y no admite texto libre; si se pulsa «Guardar» sin cambiarlo, bajo el campo
  aparece «El modelo «Mistral-Large-3» es de la familia «mistral», que no está autorizada por la empresa. Elige otro
  modelo.», el pie dice «No se guardó nada: corrige 1 valor.» y `preferencias.json` no cambia; al elegir `auto` y
  guardar, el archivo tiene `"modelo_ia": "auto"`, el lateral muestra `auto` y el aviso rojo desaparece. Con un modelo
  autorizado no hay aviso.
- [ ] [MODIFICA: configuracion › Vista Configuración] Dado «↻» (del lateral o de la vista) consultando todavía la
  lista de modelos, o el diálogo «Iniciar sesión en GitHub Copilot» abierto, y «Formato de salida» cambiado a `srt` en
  la vista, cuando se pulsa «Guardar» o «Restablecer valores del proyecto», entonces aparece el diálogo «Configuración»
  con «Espera a que termine la consulta de modelos de IA.» o «Termina o cancela el inicio de sesión en GitHub Copilot.»
  (sin preguntar antes «Restablecer configuración»), el pie muestra ese texto, `preferencias.json` no cambia (ni se
  crea), el lateral y el selector de modelo de IA no cambian; mientras «↻» consulta, el «↻» de la vista está
  deshabilitado como el del lateral; con una transcripción o una generación en curso a la vez, el texto es «Espera a
  que termine el proceso en curso.»; y en cuanto llega la lista (o falla) o se cierra el diálogo, «Guardar» funciona
  como en el criterio 1. (antes: Guardar y Restablecer solo se rechazan durante una transcripción o una generación; con
  «↻» en curso guardan, y si lo guardado cambia el dominio de GitHub Enterprise la lista que llega después se descarta
  —historia 23, criterio 3—; con el diálogo de inicio de sesión abierto, `guardar_configuracion` tampoco lo comprueba,
  aunque el diálogo es modal y con el ratón no se llega al botón)

El caso del error está en el criterio 2 (modelo no autorizado) y en el 3 (rechazo con consulta o inicio de sesión a
medias); el límite «un proceso y una consulta a la vez» también en el 3.

### Cómo se verifican

**Sin ventana** (con `pytest`, sin red: `httpx` nunca se llama; `RUTA_PREFERENCIAS` aislada por el fixture autouse
`preferencias_aisladas` de `tests/conftest.py:58`; los métodos de la ventana y del panel se llaman sin enlazar con un
`types.SimpleNamespace` como `self`, como en C1, C2 y D1):

- `tests/test_ui.py::test_aviso_modelo_solo_para_familias_excluidas` (criterio 2; del diseño): `aviso_modelo
  ("Mistral-Large-3")` es exactamente el texto rojo del criterio 2; `aviso_modelo("kimi-k3-mini")` nombra la familia
  `kimi`; `gpt-4.1`, `auto` y `claude-haiku-5.5` dan `None`.
- `tests/test_ui.py::test_motivo_para_no_guardar_con_consulta_o_login` (criterio 3; del diseño): con
  `consultando_modelos=True` da «Espera a que termine la consulta de modelos de IA.»; con `login_abierto=True`,
  «Termina o cancela el inicio de sesión en GitHub Copilot.»; con un proceso y cualquiera de los dos, «Espera a que
  termine el proceso en curso.» (el proceso manda); con los dos nuevos a la vez, el de la consulta; sin nada, `None`.
  `test_motivo_para_no_guardar_durante_un_proceso` (C1, `tests/test_ui.py:128`) sigue pasando sin cambios (los dos
  parámetros nuevos valen `False` por defecto).
- `tests/test_ui.py::test_campos_cubren_las_21_claves` (criterio 1; del diseño): `CAMPOS` tiene exactamente las 21
  claves de `configuracion._tabla()`; `ia.modelo` es el primer campo del grupo «IA», con la etiqueta «Modelo de IA»,
  `avanzado=False` y sin nota. Sustituye a `test_campos_de_ia_sin_modelo` (D1), que afirma que no hay `ia.modelo`.
- `tests/test_ui.py::test_guardar_configuracion_pasa_el_modelo_en_la_misma_escritura` (criterio 1; sustituye al test
  de `test_configuracion.py` del diseño, ver «Supuestos», 5): `AppTranscriptor.guardar_configuracion(app,
  {("salida", "formato"): "srt"}, "gpt-4.1")` sin enlazar, con el `guardar_formulario` real, `configuracion.
  _escribir_preferencias_atomico` envuelto en un espía que cuenta las llamadas, `app.aplicar_guardado` que anota el
  resultado y `app._al_cambiar_modelo_ia` que lanza `AssertionError`: una sola escritura; el archivo es el del
  criterio 1; `aplicar_guardado` recibe un resultado con `("ia", "modelo")` y `("salida", "formato")` en `cambiadas` y
  `modelo_preferido == "gpt-4.1"`. Con `"Mistral-Large-3"`: ninguna escritura, `aplicar_guardado` no se llama y el
  resultado trae el error de la regla 7 en `("ia", "modelo")`.
- `tests/test_ui.py::test_guardar_y_restablecer_rechazados_con_consulta_o_login` (criterio 3; añadido), parametrizado
  por `_consultando_modelos` y `_login_abierto`: `guardar_configuracion` y `restablecer_configuracion` sin enlazar, con
  `ui.guardar_formulario`, `ui.restablecer_formulario` y `messagebox.askyesno` que fallan si se llaman: el diálogo
  anota («Configuración», <texto del criterio 3>), el resultado trae ese texto como `mensaje` y `efectiva` `None`, y
  `preferencias.json` no existe.
- `tests/test_ui.py::test_login_abierto_mientras_el_dialogo_existe` (criterio 3; añadido): `ui.DialogoLoginCopilot`
  parcheado con un doble que guarda `al_terminar`; tras `AppTranscriptor._iniciar_sesion_copilot(app, al_conectar)`,
  `app._login_abierto` es `True`; `al_terminar(False)` lo deja en `False` (y la barra de estado dice «Inicio de sesión en
  GitHub Copilot cancelado», como hoy); con `al_terminar(True)`, `al_conectar` ya lo ve en `False` (así el «↻» que
  relanza tras iniciar sesión no queda bloqueado por su propio diálogo).
- `tests/test_ui.py::test_lista_de_modelos_llega_tambien_al_campo_de_la_vista` (criterio 1; añadido): `_mostrar_modelos_ia
  (opciones, epoca)` con la época vigente y un `panel_configuracion` doble anota las mismas opciones en el campo
  «Modelo de IA» y vuelve a habilitar su «↻»; con `panel_configuracion` `None`, hace lo de hoy sin error; con una
  época vieja (D1), ni el lateral ni el campo cambian.
- `tests/test_ui.py::test_guardar_del_panel_pasa_el_modelo_aparte` (criterio 1; añadido): `PanelConfiguracion._guardar`
  sin enlazar, con variables dobles para cada campo de `CAMPOS` (`ia.modelo` → `gpt-4.1`) y un `app` que anota los
  argumentos de `guardar_configuracion`: los valores no llevan `("ia", "modelo")` y `modelo_ia == "gpt-4.1"`.
- Se ajustan sin cambiar lo que afirman: `test_guardar_configuracion_durante_un_proceso_no_escribe` (`:139`) y
  `test_restablecer_configuracion_rechazado_o_cancelado_no_escribe` (`:210`), cuyos dobles ganan `_consultando_modelos`
  y `_login_abierto` en `False`. Siguen pasando sin cambios `test_validar_formulario_subconjunto_errores_en_orden_y_regla_7`
  (`tests/test_configuracion.py:567`), `test_guardar_ajustes_con_modelo_en_una_sola_escritura` (`:693`),
  `test_guardar_ajustes_rechaza_modelo_excluido_sin_escribir` (`:722`) y `test_guardar_formulario_devuelve_cambiadas_avisos_y_mensaje`
  (`:993`), que ya prueban la escritura única, la regla 7 y `cambiadas` con el modelo en la capa sin ventana.

Paso rojo: con el código de hoy (más D1) fallan al importar `aviso_modelo`; `motivo_para_no_guardar` no acepta
`consultando_modelos` ni `login_abierto`; `guardar_configuracion` no acepta `modelo_ia`; `CAMPOS` no tiene
`ia.modelo`; `_iniciar_sesion_copilot` no pone `_login_abierto`; `_mostrar_modelos_ia` no toca el panel.

**Solo en la ventana real:** el campo con su «↻» y su lista compartida con el lateral, el aviso rojo, el error bajo el
campo, el lateral y las pestañas de IA tras guardar, los dos rechazos con su diálogo, el «↻» de la vista deshabilitado
durante la consulta y la «Verificación común» del diseño (abrir la ventana y la vista sin red y sin leer el token). Lo
ejecuta el orquestador con el guion de abajo.

### Guion de verificación manual (ventana real)

Un script en una carpeta temporal `T` (no en el repo), lanzado desde la raíz con `./venv/bin/python <script>`.
`bombear(s)` llama a `app.update()` durante `s` segundos; `registro()` es `app.text_log.get("1.0", "end")`; `panel` es
`app.panel_configuracion`; «pulsar» un botón es su `.invoke()` (o `_guardar()` / `_restablecer()` del panel).

1. **Antes de importar `src.ui`:** `src.configuracion.RUTA_PREFERENCIAS` → `T/prefs/preferencias.json` (no existe).
   `httpx.get`, `httpx.post` y `httpx.stream` → funciones que anotan en `llamadas` y lanzan `AssertionError`.
   `src.copilot.leer_token` → anota su argumento en `dominios` y devuelve `None` si `sin_sesion[0]` es `True` o, si no,
   `copilot.Sesion("tok-prueba", dominio, "prueba")`. `src.copilot.cargar_opciones_de_modelo(sesion, actual)` → espera
   el `threading.Event` `soltar_lista` (máx. 10 s) y devuelve `copilot.opciones_de_modelo(["auto", "gpt-4.1",
   "claude-haiku-5.5", "Mistral-Large-3"], actual)` (el filtro real de la regla 7). `src.configuracion.
   _escribir_preferencias_atomico` → envoltorio que suma 1 a `escrituras[0]` y llama al original. Guarda bytes y
   `st_mtime_ns` de `config/settings.yaml`.
2. Importa `src.ui`. Sustituye `ui.AsistenteIA` por `AsistenteAnotador` (el de la historia 23: anota sus `kw` en
   `creados`; `generar_resumen` / `generar_minuta` devuelven `"# Documento\n\nTexto."` al momento).
   `ui.messagebox.showwarning`, `showerror` y `showinfo` anotan `(título, texto)` en `dialogos`; `askyesno` anota y
   devuelve el siguiente valor de la cola `respuestas`. `ui.DialogoLoginCopilot` → clase doble `(master,
   enterprise_url, al_terminar)` que se añade a `logins` y no hace nada más.
3. Construye la ventana como `ui.main()` y `bombear(1)`. **Comprueba:** `llamadas == []`, `dominios == []`,
   `escrituras == [0]`, `creados == []`.
4. Asistente previo: `app.resultado_actual` = un `ResultadoTranscripcion` de dos segmentos, `app.archivo_actual =
   str(T / "reunion.m4a")` (no existe: solo historial); `app._generar_documento_ia("resumen")`, `bombear(1)`.
   **Comprueba:** `len(creados) == 1`, `creados[0]["modelo"] == "claude-haiku-5.5"`.
5. `Ctrl+3`. **Comprueba:** el grupo «IA» empieza con «Modelo de IA», la clave `ia.modelo` en gris y un «↻» al lado;
   el campo dice `claude-haiku-5.5` y sus opciones son `["auto", "claude-haiku-5.5"]`, iguales a
   `app.combo_modelo_ia.cget("values")`; no hay texto rojo bajo el campo; `dominios == []` y `llamadas == []`
   (Verificación común).
6. **Rechazo con «↻» en curso:** `soltar_lista.clear()`; pulsa el «↻» de la vista; `bombear(0.3)`. **Comprueba:** el «↻»
   de la vista y `app.btn_cargar_modelos_ia` están `disabled`; `dominios == [None]`. Elige `srt` en «Formato de salida»
   y pulsa «Guardar». **Comprueba:** `dialogos[-1] == ("Configuración", "Espera a que termine la consulta de modelos de
   IA.")`, el pie muestra ese texto, `T/prefs/preferencias.json` no existe, `escrituras == [0]`, `app.var_formato.get()
   == "txt"`. Pulsa «Restablecer valores del proyecto». **Comprueba:** el mismo diálogo y `respuestas` sin consumir (no
   se preguntó).
7. `soltar_lista.set()`, `bombear(1)`. **Comprueba:** las opciones del campo y de `app.combo_modelo_ia` son `["auto",
   "gpt-4.1", "claude-haiku-5.5"]` (sin `Mistral-Large-3`); los dos «↻» en `normal`; el campo sigue en
   `claude-haiku-5.5` y «Formato de salida» sigue en `srt` (lo no guardado no se pierde).
8. **Guardar el modelo:** elige `gpt-4.1` en el campo. Ve a `Ctrl+1`: **comprueba** que el selector del lateral sigue en
   `claude-haiku-5.5` y que el archivo no existe; vuelve con `Ctrl+3`: el campo vuelve a `claude-haiku-5.5` y el formato
   a `txt`. Elige otra vez `gpt-4.1` y `srt`; «Guardar». **Comprueba:** pie «Configuración guardada»; el archivo, cargado
   con `json`, es `{"modelo_ia": "gpt-4.1", "configuracion": {"salida": {"formato": "srt"}}}`; `escrituras == [1]`;
   `app.var_modelo_ia.get() == "gpt-4.1"` y `app.var_formato.get() == "srt"`; las etiquetas de estado de Resumen y
   Minuta que mostraban el modelo dicen «Modelo: GitHub Copilot · gpt-4.1»; `registro()` contiene «Configuración
   guardada: ia.modelo, salida.formato» y no contiene «Modelo de IA: gpt-4.1»; el YAML conserva bytes y `st_mtime_ns`.
9. `app._generar_documento_ia("minuta")`, `bombear(1)`. **Comprueba:** `len(creados) == 2` y `creados[1]["modelo"] ==
   "gpt-4.1"` (el asistente se olvidó).
10. **Rechazo con el inicio de sesión abierto:** `sin_sesion[0] = True`; pulsa el «↻» de la vista; `bombear(0.5)`.
    **Comprueba:** `len(logins) == 1`; los dos «↻» en `normal`. Elige `vtt` en «Formato de salida» y pulsa «Guardar».
    **Comprueba:** `dialogos[-1] == ("Configuración", "Termina o cancela el inicio de sesión en GitHub Copilot.")`, el
    pie lo muestra, el archivo no cambió, `escrituras == [1]`. «Restablecer»: el mismo diálogo, sin pregunta.
11. `logins[0]._al_terminar(False)` (o el argumento guardado), `bombear(0.3)`. **Comprueba:** la barra de estado dice
    «Inicio de sesión en GitHub Copilot cancelado». «Guardar» con `vtt`. **Comprueba:** pie «Configuración guardada»,
    el archivo tiene `"formato": "vtt"` y sigue con `"modelo_ia": "gpt-4.1"`, `escrituras == [2]`. `sin_sesion[0] =
    False`.
12. **Proceso y consulta a la vez:** `soltar_lista.clear()`; pulsa «↻»; asigna `app.transcripcion_thread =
    threading.Thread(target=time.sleep, args=(3,), daemon=True)` y arráncalo; «Guardar». **Comprueba:** `dialogos[-1]
    == ("Configuración", "Espera a que termine el proceso en curso.")`. Espera a que acabe el hilo; `soltar_lista.set()`,
    `bombear(1)`.
13. **Modelo no autorizado (preferencia):** `app.destroy()`; escribe el archivo como `{"modelo_ia": "Mistral-Large-3"}`;
    construye otra ventana y `Ctrl+3`. **Comprueba:** bajo «Modelo de IA», en rojo, el texto exacto del aviso del
    criterio 2; el campo dice `Mistral-Large-3` y sus opciones son `["auto"]` (como el lateral); el campo es un menú (no
    se puede escribir en él). «Guardar». **Comprueba:** bajo el campo, «El modelo «Mistral-Large-3» es de la familia
    «mistral», que no está autorizada por la empresa. Elige otro modelo.»; pie «No se guardó nada: corrige 1 valor.»; el
    archivo no cambió; `escrituras` no cambió. Pulsa «↻», `bombear(1)`: las opciones son `["auto", "gpt-4.1",
    "claude-haiku-5.5"]`, sin `Mistral-Large-3`. Elige `auto`, «Guardar». **Comprueba:** el archivo es `{"modelo_ia":
    "auto"}`; `app.var_modelo_ia.get() == "auto"`; el aviso rojo ya no está.
14. **Modelo no autorizado (YAML):** `app.destroy()`; borra el archivo; copia `config/settings.yaml` a `T/settings.yaml`
    con `ia.modelo: "Mistral-Large-3"` y construye la ventana con `cargar_configuracion(T / "settings.yaml")` (el resto
    como `ui.main()`); `Ctrl+3`. **Comprueba:** el mismo aviso; «Guardar» sin cambiarlo da el mismo error y el archivo no
    se crea. No se edita el YAML del repo.
15. Cierra y construye otra ventana con el YAML del repo. **Comprueba:** `Ctrl+3` muestra el modelo guardado (no hay
    preferencia: `claude-haiku-5.5`); `llamadas == []` en todo el guion; `config/settings.yaml` no cambió.
16. Al terminar: borra `T`; `git status --short` no lista `config/settings.yaml` ni preferencias;
    `./venv/bin/python -m pytest -q` pasa.

Opcional, con una sesión real y sin parches (lo pide la verificación del diseño): «↻» de la vista carga la misma lista
que el del lateral. No es necesario para dar la historia por cumplida (regla 3: los tests no hacen red).

## Plan

- Sin ventana: el motivo para no guardar aprende dos causas nuevas, después de la del proceso en curso (la consulta de
  modelos y el inicio de sesión abierto), y un aviso para un modelo efectivo de familia no autorizada, en el mismo
  módulo de la vista.
- En la vista: «Modelo de IA» como primer campo del grupo IA, un menú sin texto libre con su propio valor (el modelo
  efectivo de la ventana) y las opciones del selector del lateral, un «↻» que lanza la misma consulta de la ventana, y
  el aviso rojo bajo el campo; al refrescar se repone valor, opciones y aviso; al guardar, el modelo va aparte del
  resto de valores.
- En la ventana: guardar acepta el modelo y lo pasa al guardado de siempre (una sola escritura, sin pasar por el
  cambio del selector lateral); guardar y restablecer comprueban también la consulta en curso y el inicio de sesión
  abierto.
- La ventana sabe si el inicio de sesión está abierto: lo marca al abrir el diálogo y lo quita al terminar, antes de
  seguir con lo que tocara.
- Cuando llega la lista de «↻», también la recibe el campo de la vista si existe; el «↻» de la vista se deshabilita y
  habilita a la vez que el del lateral.

Archivos del `/pair` (lista cerrada, la del diseño): `src/ui_configuracion.py` (campo `ia.modelo` en `CAMPOS`, su
menú y su «↻» en `PanelConfiguracion`, `refrescar` con el modelo efectivo, sus opciones y el aviso, `_valores_formulario`
sin `ia.modelo`, `_guardar` con `modelo_ia`, `aviso_modelo`, `motivo_para_no_guardar` con los dos parámetros nuevos),
`src/ui.py` (`_login_abierto` en `AppTranscriptor.__init__` y en `_iniciar_sesion_copilot`; `guardar_configuracion`
con `modelo_ia` y los cuatro motivos; `restablecer_configuracion` con los cuatro motivos; `_mostrar_modelos_ia` actualiza
el menú del panel; el «↻» del panel en `_cargar_modelos_ia` y sus tres respuestas), `tests/test_ui.py`,
`tests/test_configuracion.py` (en la lista del diseño; no se espera tocarlo, ver «Supuestos», 5). Si hace falta otro, se
para y se vuelve al diseño. El delta de spec (`docs/specs/configuracion.md`, «Vista Configuración» y «Modelo de IA
elegido en la ventana»; `docs/specs/documentos-ia.md`, «Lista de modelos bajo demanda» si D1 dejó allí la respuesta
vieja de «↻») y el resto de la documentación los escribe `/cerrar`.

## Fuera de alcance

- **B, E1 y E2:** la sección «Sesión de GitHub Copilot» de la vista, iniciar o cerrar sesión desde ella, `estado_sesion`
  y subir la época u olvidar el asistente al iniciar o cerrar sesión. D2 solo pone `_login_abierto`, que E2 usará.
- Cambiar `src/configuracion.py` (`guardar_formulario`, `guardar_ajustes`, `validar_formulario` y sus mensajes ya
  guardan el modelo en la misma escritura y aplican la regla 7), `src/copilot.py` (`opciones_de_modelo`,
  `familia_excluida`, `FAMILIAS_EXCLUIDAS`), `src/ui_copilot.py` o la defensa en el envío
  (`AsistenteIA._modelo_para_peticion`).
- Texto libre en el campo del modelo, o cambiar cómo funciona el selector del lateral (`_al_cambiar_modelo_ia` sigue
  guardando al instante en `modelo_ia`).
- Rechazar las acciones de sesión o la generación mientras «↻» consulta (alternativa I): solo se rechazan Guardar y
  Restablecer.
- Actualizar el aviso rojo mientras se elige otro modelo sin guardar: describe el modelo efectivo y se repone al
  refrescar (al guardar o al volver a la vista).
- Recargar sola la lista de modelos, o abrir y reutilizar sesiones `auto`.

## Sugerencias (a tu criterio)

- En `Campo`, un control propio para el modelo (por ejemplo `control="modelo_ia"`) en vez de reutilizar «lista» con
  opciones vacías: `refrescar`, `_valores_formulario` y la construcción ya tienen que tratarlo aparte (valor de
  `_modelo_ia_configurado()`, opciones de `combo_modelo_ia`, sin entrar en `valores_widget`), y así se ve dónde.
- Si D1 deja el ayudante de las tres respuestas de «↻» que sugiere (`_respuesta_de_modelos(epoca)`), habilitar el «↻»
  del panel ahí; si no, son tres copias de una línea más y vale la pena extraerlo ahora.
- En `_iniciar_sesion_copilot`, poner `_login_abierto = True` después de construir el diálogo (si el constructor
  lanza, la marca no se queda puesta para siempre) y quitarlo en la primera línea de `al_terminar`.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es que la vista guarde lo que la empresa no autoriza o que guardar deje el modelo a medias:
   un modelo de familia excluida en `modelo_ia`, o el archivo con el modelo nuevo y el lateral, las pestañas o el
   asistente con el anterior (la siguiente minuta saldría con otro modelo sin que se note). Lo cubren los criterios 1
   y 2, `test_guardar_configuracion_pasa_el_modelo_en_la_misma_escritura` y los pasos 8, 9 y 13 del guion.
2. **Dependencia de D1 (aprobada, sin implementar).** Se toma de `docs/historias/23-grupo-ia.md`: existen
   `_consultando_modelos` (lo pone `_cargar_modelos_ia` y lo quitan sus tres respuestas) y `_epoca_ia`; las tres
   respuestas reciben la época; `aplicar_guardado` olvida el asistente si cambian `argumentos_asistente`, comparando el
   modelo con `modelo_ia_efectivo` de cada lado (decisión del orquestador para D1), lo que ya cubre el cambio de modelo
   que añade D2; al descartar una lista vieja la barra de estado vuelve a «Listo» (decisión del orquestador para D1);
   el grupo «IA» va entre «Salida» e «Historial» con un «Avanzado» propio. Si D1 se cierra con otros nombres, esta
   historia sigue a los que queden. `aplicar_guardado` no debería necesitar cambios en D2 (C2 ya repone
   `var_modelo_ia`, las opciones del lateral y las etiquetas cuando `("ia", "modelo")` está en `cambiadas`); el panel
   toma valor y opciones del lateral en `refrescar`, que `_guardar` llama tras guardar.
3. **Restablecer también se rechaza** con consulta o inicio de sesión a medias. El diseño solo pone los cuatro motivos
   en `guardar_configuracion` (decisión técnica 7: «Guardar se rechaza además…»), pero Restablecer usa el mismo
   `motivo_para_no_guardar` y también cambia `modelo_ia` y el selector, con la misma carrera contra la lista que llega;
   el encargo de la historia lo pide.
4. **El «↻» de la vista se deshabilita mientras consulta.** El diseño solo dice que llama a `app._cargar_modelos_ia`.
   Sin esto, una segunda pulsación lanzaría otra consulta y la primera respuesta quitaría `_consultando_modelos` con la
   segunda aún en vuelo, y Guardar dejaría de estar protegido. Es el mismo comportamiento que el «↻» del lateral.
5. **El test de `test_configuracion.py` del diseño** (`test_guardar_formulario_con_modelo_cambia_cambiadas_y_modelo_preferido`)
   pasaría antes de implementar: la parte `con_modelo` de `test_guardar_formulario_devuelve_cambiadas_avisos_y_mensaje`
   (`tests/test_configuracion.py:993`, de A3) ya lo comprueba, y `test_guardar_ajustes_con_modelo_en_una_sola_escritura`
   (`:693`) prueba la escritura única. Se sustituye por `test_guardar_configuracion_pasa_el_modelo_en_la_misma_escritura`,
   que falla hoy (la ventana no acepta `modelo_ia`), como hizo la Revisión con otros tests que pasaban antes de tiempo.
   `tests/test_configuracion.py` queda en la lista por si hace falta, pero no se espera tocarlo.
6. **El criterio 1 del diseño se reescribe para que sea observable.** «`_al_cambiar_modelo_ia` no se llamó» se ve en
   Registro (no aparece «Modelo de IA: gpt-4.1», la línea que escribe ese método) y en el test con un doble que falla si
   se llama; «una sola escritura» se cuenta con un espía en el guion y en el test. Se añaden la lista compartida tras
   «↻» y que elegir sin guardar no cambia nada (decisión de producto 3).
7. **Mensajes y orden.** `aviso_modelo` (vista, «… no se enviará. Elige otro.») y el error de `validar_formulario`
   («… que no está autorizada por la empresa. Elige otro modelo.», sin cambios) son textos distintos del diseño y se
   conservan así. En `motivo_para_no_guardar`, el proceso en curso manda; entre consulta e inicio de sesión (que no
   coinciden: `_sin_sesion_para_modelos` quita la marca de consulta antes de abrir el diálogo), la consulta. El error
   de la regla 7 bajo el campo sustituye al aviso rojo hasta el siguiente refresco; el diseño no dice si conviven.
8. **Inicio de sesión abierto y modalidad.** `DialogoLoginCopilot` hace `grab_set` a los 100 ms
   (`src/ui_copilot.py:58`), así que con el ratón no se llega a «Guardar» mientras está abierto; la comprobación de
   `_login_abierto` cubre esos 100 ms, el error del device flow que deja el diálogo abierto con su mensaje y las
   llamadas por programa. El guion pulsa por programa por eso. `al_terminar` solo se llama al terminar bien, al pulsar
   «Cancelar» o al cerrar con la «X» (`_terminar`, `_cerrar`); si el device flow falla, el diálogo sigue abierto y la
   marca también, que es lo correcto.
9. **Marcas.** El 1 y el 2 son `[NUEVO]`: la spec «Vista Configuración» dice que IA «llega con otras historias» y no hay
   campo del modelo en la vista; «Modelo de IA elegido en la ventana» habla del selector lateral, que no cambia. El 3 es
   `[MODIFICA: configuracion › Vista Configuración]`: cambia el rechazo de Guardar (hoy solo con un proceso) y deja sin
   camino desde Guardar el escenario del criterio 3 de D1 (lista vieja tras guardar el dominio con «↻» en curso), como
   ya anunciaba su Supuesto 9; la época sigue sirviendo a E2. Si `/cerrar` de D1 llevó ese escenario a
   `documentos-ia › Lista de modelos bajo demanda`, el `/cerrar` de D2 lo reescribe allí.
10. **Líneas** (de `3d0f477`, sin D1; D1 cambia `src/ui.py` y `src/ui_configuracion.py`, manda el nombre de la
    función): `src/ui.py`: `AppTranscriptor.__init__` `:95` (`panel_configuracion` `:131`, `_documentos` `:139`,
    `_modelo_preferido` y `var_modelo_ia` `:149-150`), `combo_modelo_ia` `:273-277` (sus opciones pasan por
    `copilot.opciones_de_modelo`), `btn_cargar_modelos_ia` `:278`, `_transcribiendo` `:581`, `_generando_ia` `:759`,
    `_crear_asistente` `:815`, `_generar_documento_ia` `:827` (deshabilita el selector `:849`),
    `_restaurar_controles_ia` `:904`, `_modelo_ia_configurado` `:951`, `_texto_modelo_ia` `:954`, `_cargar_modelos_ia`
    `:957-977`, `_sin_sesion_para_modelos` `:979`, `_fallo_cargar_modelos_ia` `:984`, `_mostrar_modelos_ia` `:989-996`,
    `_al_cambiar_modelo_ia` `:998-1013` (escribe «Modelo de IA: <m>» en Registro), `_iniciar_sesion_copilot`
    `:1015-1024`, `mostrar_vista` `:1081` (refresca el panel al volver), `guardar_configuracion` `:1111-1127` (pasa
    `None` como `modelo_ia`), `restablecer_configuracion` `:1129-1145`, `aplicar_guardado` `:1147-1171`, `_en_ui`
    `:1308`, `main` `:1342`; `src/ui_configuracion.py`: `Campo` `:18`, `CAMPOS` `:29`, `motivo_para_no_guardar` `:51`,
    `PanelConfiguracion` `:58`, `_construir` `:76`, `_crear_control` `:162`, `refrescar` `:173` (lee
    `app.configuracion[sección][clave]`: para `ia.modelo` daría el del YAML, no el efectivo), `_valores_formulario`
    `:209`, `_guardar` `:217`, `_pintar` `:231`; `src/ui_copilot.py`: `DialogoLoginCopilot.__init__` `:23`,
    `grab_set` `:58`, `_terminar` `:91`, `_cerrar` `:100`; `src/configuracion.py`: `guardar_ajustes` `:207` (modelo y
    `configuracion` en una escritura; rechaza un modelo excluido), `_escribir_preferencias_atomico` `:258`,
    `modelo_ia_efectivo` `:272`, `validar_formulario` `:440` (regla 7 `:457-463`; `ia.modelo` en los valores es
    `ValueError`), `ResultadoGuardado` `:471`, `guardar_formulario` `:481`, `_resultado_tras_escribir` `:507`
    (`("ia", "modelo")` en `cambiadas` si cambia el efectivo); `src/copilot.py`: `FAMILIAS_EXCLUIDAS` `:305`,
    `familia_excluida` `:308`, `opciones_de_modelo` `:314`, `cargar_opciones_de_modelo` `:349`.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa (484 tests). Code review: revisión del orquestador, listo para commit. Decisiones del pair aceptadas: `_panel_de_modelos` con `getattr` (los dobles de test de la ventana no siempre tienen `panel_configuracion`) y `_refrescar_modelo` fija el «↻» de la vista según `_consultando_modelos`. Arreglo del orquestador tras la revisión: sin error en «Modelo de IA», `PanelConfiguracion._pintar` vuelve a poner bajo el campo el aviso del modelo no autorizado (antes desaparecía tras un «Guardar» rechazado por una consulta o un inicio de sesión); cubierto por `test_rechazo_sin_error_del_modelo_conserva_el_aviso_de_familia_excluida` (`tests/test_ui.py:833`).

Delta de spec (`docs/specs/configuracion.md`, con `Origen` en esta historia):

- «Modelo de IA en la vista Configuración» (criterio 1) y «Modelo no autorizado en la vista Configuración» (criterio 2): [NUEVO].
- «Vista Configuración», bullet del rechazo de «Guardar» (criterio 3): [MODIFICA], con la nota `(antes: …)`. La frase de grupos ya dice que IA tiene «Modelo de IA» primero.
- «Grupo IA de la vista Configuración»: se quita la frase «no hay campo Modelo de IA» y se remite a la sección nueva.
- «Cambio del dominio de GitHub Enterprise en la vista»: el primer bullet se reescribe (con «↻» en curso no se guarda el dominio); la lista descartada queda como protección para el inicio y el cierre de sesión desde la vista (E2, pendiente).

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | «Modelo de IA» primero del grupo IA con `claude-haiku-5.5` y las opciones del lateral; su «↻» comparte la lista con el lateral sin perder lo escrito; Guardar con `gpt-4.1` y `srt` escribe una sola vez, repone lateral, pestañas y Registro, y no se aplica nada sin guardar | Campo y orden: `tests/test_ui.py:326` (`test_campos_cubren_las_21_claves`); `src/ui_configuracion.py:47` (`CAMPOS`), `:179` (`btn_cargar_modelos_ia`), `:214` (`_refrescar_modelo`). Lista compartida: `tests/test_ui.py:771` (`test_lista_de_modelos_llega_tambien_al_campo_de_la_vista`); `src/ui.py:1019` (`_mostrar_modelos_ia`). Una escritura y sin `_al_cambiar_modelo_ia`: `tests/test_ui.py:637` (`test_guardar_configuracion_pasa_el_modelo_en_la_misma_escritura`), `:800` (`test_guardar_del_panel_pasa_el_modelo_aparte`); `src/ui.py:1148` (`guardar_configuracion`) | cumple (tests y ventana) |
| 2 | [NUEVO] | Modelo de familia no autorizada: aviso rojo bajo el campo, sin ofrecerlo entre las opciones, Guardar rechazado con el error de la regla 7 y pie «No se guardó nada: corrige 1 valor.»; con `auto` se guarda y el aviso desaparece | `tests/test_ui.py:607` (`test_aviso_modelo_solo_para_familias_excluidas`), `:637` (parte de Mistral), `:833` (`test_rechazo_sin_error_del_modelo_conserva_el_aviso_de_familia_excluida`); `src/ui_configuracion.py:70` (`aviso_modelo`), `:284` (`_pintar`) | cumple (tests; ventana con la preferencia guardada. El caso del YAML sin preferencia, solo con tests: misma ruta de `_modelo_ia_configurado`, sin copia del YAML en ventana) |
| 3 | [MODIFICA: configuracion › Vista Configuración] | «Guardar» y «Restablecer» se rechazan con proceso en curso, consulta de modelos o inicio de sesión abierto, cada uno con su texto, sin preguntar y sin escribir; «↻» de la vista deshabilitado durante la consulta | `tests/test_ui.py:129` (`test_motivo_para_no_guardar_durante_un_proceso`), `:140`, `:212`, `:621` (`test_motivo_para_no_guardar_con_consulta_o_login`), `:691` (`test_guardar_y_restablecer_rechazados_con_consulta_o_login`), `:723` (`test_login_abierto_mientras_el_dialogo_existe`). Código: `src/ui_configuracion.py:58` (`motivo_para_no_guardar`), `src/ui.py:65` (`_marcar_cargar_modelos`), `:1053` y `:1061` (`_login_abierto`), `:1148` y `:1168` (`guardar_configuracion`, `restablecer_configuracion`) | cumple (tests y ventana) |

**Verificación (2026-11-22):** `./venv/bin/python -m pytest -q` pasa (484). Comprobado por el orquestador en la ventana real, con dos arranques, `httpx` interceptado, `copilot.leer_token` y `copilot.cargar_opciones_de_modelo` falsos (el segundo bloqueable y pasando por el filtro real de la regla 7), un espía de `_escribir_preferencias_atomico`, `ui.DialogoLoginCopilot` sustituido por un doble, diálogos por script y preferencias temporales:

- Al abrir y con `Ctrl+3`: 0 llamadas de red y 0 lecturas del token; «Modelo de IA» con `claude-haiku-5.5` y opciones `auto` y `claude-haiku-5.5`, sin aviso.
- «↻» de la vista consultando: los dos «↻» deshabilitados; «Guardar» y «Restablecer» responden «Espera a que termine la consulta de modelos de IA.» sin preguntar y sin escribir. Al llegar la lista, vista y lateral ofrecen `auto`, `gpt-4.1` y `claude-haiku-5.5` (Mistral-Large-3 llegó en la respuesta y no se ofreció).
- `gpt-4.1` con formato `srt` y «Guardar»: pie «Configuración guardada»; `preferencias.json` queda exactamente `{"configuracion": {"salida": {"formato": "srt"}}, "modelo_ia": "gpt-4.1"}` con una sola escritura; lateral y pestañas de Resumen y Minuta con `gpt-4.1`; Registro «Configuración guardada: ia.modelo, salida.formato»; asistente olvidado.
- Inicio de sesión abierto: «Guardar» y «Restablecer» responden «Termina o cancela el inicio de sesión en GitHub Copilot.» y el archivo no cambia. Al cancelar el diálogo, la marca se quita, la barra dice «Inicio de sesión en GitHub Copilot cancelado» y «Guardar» funciona. Proceso y consulta a la vez: «Espera a que termine el proceso en curso.».
- Con `modelo_ia` `Mistral-Large-3` guardado: el campo muestra el aviso rojo, no lo ofrece antes ni después de «↻»; «Guardar» da el error de la regla 7, pie «No se guardó nada: corrige 1 valor.» y 0 escrituras. Con `auto` se guarda `{"modelo_ia": "auto"}`, el aviso desaparece y el lateral muestra `auto`.
- 0 llamadas de red en todo el recorrido.

**Pendientes aceptados:**

- Con el diálogo de inicio de sesión abierto, `_consultando_modelos` ya es False (la consulta terminó antes de abrirlo), así que un segundo «↻» podría abrir otro diálogo de inicio de sesión. El diálogo es modal (`grab_set` a los 100 ms) y con el ratón no se alcanza; solo lo lograría una llamada por programa.
- El caso de un modelo no autorizado en una copia del YAML (sin preferencia) no se verificó en ventana; está cubierto por el de la preferencia (misma ruta de `_modelo_ia_configurado`) y por los tests.
- E2 (sesión de Copilot en la vista) sigue fuera de esta historia; `_login_abierto` ya está preparado para ella.
