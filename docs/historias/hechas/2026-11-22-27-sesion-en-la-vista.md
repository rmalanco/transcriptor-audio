# 27 · La sesión de GitHub Copilot en la vista Configuración

> Origen: `BACKLOG.md`, «Backlog» #6 (sesión de GitHub Copilot desde el panel, carril M), tercera y última de sus
> historias; punto 25 de la sección «Backlog» — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia E2 (con
> «Plan técnico», 5: `PanelConfiguracion.refrescar` «y, en E2, la sección Sesión»; 7: tabla de siete textos de
> `describir_sesion` y viñetas «Mostrar», «Dominio editado sin guardar», «Iniciar sesión», «Cerrar sesión» e «Hilos»;
> «Decisiones tomadas», técnicas 7, 8, 9 y 10; CUJ 3 y CUJ 4; «Verificación común»; alternativas F, G e I;
> «Requisitos no funcionales», «Privacidad y secretos», «Red» e «Hilos»; «Revisión (2026-11-22)», filas «E mezclaba
> lógica y vista», «Carrera de «↻» con login, logout y cambio de dominio», «Sesión: token propio corrupto, `repr` del
> token, textos incompletos» y «Asistente olvidado de más») — carril M. Reglas de oro 1, 3, 5, 8 y 9 de `AGENTS.md`.
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»).
>
> **Requires: #24 (E1) — cumplido** (commit `1ea7185`, `docs/historias/hechas/2026-11-22-26-cerrar-solo-la-sesion-propia.md`).
> **Requires: #22 (D2) — en implementación** en la copia de trabajo (`docs/historias/24-modelo-ia-en-la-vista.md`, sin
> commit). Esta historia parte del código de esa copia de trabajo (ver «Supuestos», 2) y no empieza su `/pair` hasta
> que D2 esté cerrada: las dos tocan `src/ui.py`, `src/ui_configuracion.py` y `tests/test_ui.py`.

## Historia

Como usuario de la ventana, quiero ver en la vista «⚙ Configuración» de dónde sale mi sesión de GitHub Copilot y
poder iniciarla o cerrar la que guardó la app con un botón, para activar o desactivar la IA sin esperar a generar un
documento ni usar la terminal, sin que la app toque la sesión de opencode ni la variable de entorno.

## Criterios de aceptación

- [ ] [MODIFICA: configuracion › Vista Configuración] Dado la ventana recién abierta (abrirla no lee el token ni hace
  red, como hoy) y cada una de estas sesiones, cuando se abre «⚙ Configuración» (`Ctrl+3`), entonces al principio del
  grupo «IA», antes de «Modelo de IA», hay una sección «Sesión de GitHub Copilot» con el texto y los dos botones de la
  fila que toca de la tabla del diseño («Plan técnico», 7), y mostrarla lee la sesión del disco una vez y no hace
  ninguna petición de red:

  | Sesión | Texto | «Iniciar…» | «Cerrar sesión» |
  |---|---|---|---|
  | ninguna | «No has iniciado sesión en GitHub Copilot.» | «Iniciar sesión», habilitado | deshabilitado |
  | solo opencode | «Se usa la sesión de opencode. La app no la cierra: ciérrala desde opencode. La sesión se comprueba al usarla.» | «Iniciar sesión con la app», habilitado | deshabilitado |
  | `COPILOT_GITHUB_TOKEN` y archivo propio | «Se usa el token de la variable de entorno COPILOT_GITHUB_TOKEN. La app no puede cerrarlo: quita la variable para usar otra sesión. Hay además una sesión guardada por la app que ahora no se usa. La sesión se comprueba al usarla.» | deshabilitado | habilitado |

  Y si, sin guardar, se escribe `empresa.ghe.com` en «Dominio de GitHub Enterprise», los dos botones se deshabilitan y
  el texto termina en «Guarda primero el dominio.»; al borrar lo escrito (el campo vuelve al dominio guardado) o al ir
  a Transcribir y volver, la sección vuelve a ser la de la tabla. Ningún texto contiene el token. (antes: la vista no
  tenía sección de sesión y abrirla no hacía ninguna petición de red ni leía el token — `docs/specs/configuracion.md`,
  «Vista Configuración», primer criterio; `src/ui_configuracion.py:195`, `PanelConfiguracion.refrescar`, solo pone
  valores, el modelo y los avisos.)
- [ ] [NUEVO] Dado «No has iniciado sesión en GitHub Copilot.» y una generación anterior que dejó creado el asistente,
  cuando se pulsa «Iniciar sesión», se abre el diálogo «Iniciar sesión en GitHub Copilot» de siempre y se autoriza,
  entonces (CUJ 3) la sección dice «Sesión iniciada con la app. La sesión se comprueba al usarla.», «Iniciar sesión»
  queda deshabilitado y «Cerrar sesión» habilitado, Registro anota «Sesión de GitHub Copilot iniciada», la siguiente
  generación crea un asistente nuevo (las notas conservadas de un fallo anterior se pierden) y una lista de «↻» pedida
  antes de iniciar sesión, si llega después, se descarta; el selector de modelo no se recarga solo. Si en cambio se
  cancela el diálogo, la sección no cambia, la barra de estado dice «Inicio de sesión en GitHub Copilot cancelado», el
  asistente sigue siendo el mismo y no se crea el archivo de sesión.
- [ ] [NUEVO] Dado un archivo de sesión propio y una sesión de opencode, cuando se pulsa «Cerrar sesión» y se responde
  «Sí» al diálogo «Cerrar sesión» («¿Cerrar la sesión de GitHub Copilot guardada por la app? La de opencode y la
  variable de entorno no se tocan.»), entonces (CUJ 4) el archivo propio deja de existir, el de opencode queda igual
  (mismos bytes y misma fecha de modificación), la sección dice «Se usa la sesión de opencode. La app no la cierra:
  ciérrala desde opencode. La sesión se comprueba al usarla.» con «Cerrar sesión» deshabilitado e «Iniciar sesión con
  la app» habilitado, el selector de modelo del lateral y el campo «Modelo de IA» ofrecen solo `auto` y el modelo
  configurado, la siguiente generación crea un asistente nuevo, una lista de «↻» en vuelo se descarta al llegar y
  Registro anota «Sesión de GitHub Copilot cerrada». Si se responde «No», nada cambia. Si el archivo no se puede
  borrar (carpeta sin permiso de escritura), aparece el diálogo «Sesión de GitHub Copilot» con «No se pudo cerrar la
  sesión:» y el motivo, y el archivo, la sección, el selector y el asistente no cambian. Y durante una transcripción o
  una generación, pulsar cualquiera de los dos botones muestra el diálogo «Sesión de GitHub Copilot» con «Espera a que
  termine el proceso en curso.», sin preguntar, sin borrar nada y sin abrir el inicio de sesión.

Los casos de error, límite y acción repetida están en los criterios: el dominio sin guardar (1), el diálogo cancelado
(2), la respuesta «No», el `OSError` y el rechazo durante un proceso (3), y la respuesta vieja de «↻» (2 y 3). El caso
que más dolería (ver «Supuestos», 1) es el criterio 3.

### Cómo se verifican

**Sin ventana** (con `pytest`, sin red; `RUTA_PREFERENCIAS` aislada por el fixture autouse `preferencias_aisladas` de
`tests/conftest.py:58`; los métodos de la ventana y del panel se llaman sin enlazar con un `types.SimpleNamespace` como
`self`, como en C1, C2, D1 y D2). `rutas_aisladas` es local de `tests/test_copilot.py:15`: **todo test de
`tests/test_ui.py` que llegue a `estado_sesion` o a `cerrar_sesion_propia` reales aísla él mismo `copilot.RUTA_TOKEN` y
`copilot.RUTA_AUTH_OPENCODE` en `tmp_path` y quita `COPILOT_GITHUB_TOKEN` con `monkeypatch`**, o parchea esas funciones;
nunca se lee ni se borra la sesión real.

- `tests/test_ui.py::test_cerrar_sesion_copilot_olvida_el_asistente_y_avanza_la_epoca` (criterio 3; del diseño):
  `AppTranscriptor._cerrar_sesion_copilot(app)` sin enlazar, con `ui.messagebox.askyesno` que anota y devuelve `True`
  y `copilot.cerrar_sesion_propia` parcheada para devolver `EstadoSesion("opencode", False)`: anota el título y el
  texto exactos de la pregunta, llama a `olvidar_asistente` una vez, `_epoca_ia` sube en 1, `combo_modelo_ia` recibe
  `["auto", <configurado>]` (y el campo del panel doble, las mismas opciones), Registro anota «Sesión de GitHub
  Copilot cerrada» y devuelve el estado. `cerrar_sesion_propia` recibe el dominio guardado (`None` si está vacío).
- `tests/test_ui.py::test_cerrar_sesion_copilot_con_oserror_no_aplica_nada` (criterio 3; del diseño):
  `cerrar_sesion_propia` lanza `PermissionError("sin permiso")`: `showerror("Sesión de GitHub Copilot", "No se pudo
  cerrar la sesión:\nsin permiso")`, devuelve `None`, `olvidar_asistente` no se llama, la época y el selector no
  cambian.
- `tests/test_ui.py::test_acciones_de_sesion_rechazadas_o_canceladas_no_cambian_nada` (criterio 3; añadido),
  parametrizado: con `_transcribiendo` o `_generando_ia` verdadero, `_cerrar_sesion_copilot` y la acción de iniciar
  sesión de la vista muestran `showwarning("Sesión de GitHub Copilot", "Espera a que termine el proceso en curso.")`,
  no llaman a `askyesno`, ni a `cerrar_sesion_propia`, ni construyen `ui.DialogoLoginCopilot` (dobles que fallan si se
  llaman); con `askyesno` que devuelve `False`, `cerrar_sesion_propia` no se llama y devuelve `None`.
- `tests/test_ui.py::test_iniciar_sesion_desde_la_vista_avanza_la_epoca_y_olvida_el_asistente` (criterio 2; añadido):
  `ui.DialogoLoginCopilot` parcheado con un doble que guarda `al_terminar` (como
  `test_login_abierto_mientras_el_dialogo_existe`, `tests/test_ui.py:723`); tras la acción de iniciar de la vista,
  `al_terminar(True)` sube `_epoca_ia` en 1, llama a `olvidar_asistente` y pide repintar la sección; el selector no
  cambia. `al_terminar(False)` no cambia la época, ni el asistente, ni la sección.
- `tests/test_ui.py::test_seccion_de_sesion_segun_el_estado_y_el_dominio_escrito` (criterio 1; añadido): la función
  sin Tk de `src/ui_configuracion.py` que decide texto y estado de los botones a partir de `describir_sesion` y del
  dominio escrito y el guardado (ver «Sugerencias»): las tres filas del criterio 1; con el dominio escrito distinto
  del guardado (sin contar espacios), los dos botones deshabilitados y el texto con « Guarda primero el dominio.» al
  final; con `"  "` frente a `""`, igual que sin escribir.
- `tests/test_ui.py::test_refrescar_sesion_lee_el_disco_sin_red` (criterio 1; añadido): `PanelConfiguracion.
  refrescar_sesion` sin enlazar, con etiqueta y botones dobles, rutas aisladas en `tmp_path`, una sesión de opencode
  escrita a mano, `copilot.httpx.get` y `copilot.httpx.post` que lanzan `AssertionError` y `copilot.leer_token`
  envuelta para contar: una lectura con el dominio guardado (`None` si es `""`), el texto de la fila «solo opencode» y
  el estado de los botones; `tmp_path` no cambia.
- Siguen pasando sin cambios `tests/test_copilot.py` (en especial los de B y E1: `test_describir_sesion_texto_y_botones`,
  `test_cerrar_sesion_propia_no_toca_opencode`) y los de D2 en `tests/test_ui.py`
  (`test_login_abierto_mientras_el_dialogo_existe`, `test_guardar_y_restablecer_rechazados_con_consulta_o_login`,
  `test_cargar_modelos_ia_descarta_si_cambia_la_epoca_durante_la_consulta`, `:561`).
- `./venv/bin/python -m pytest -q` en verde (regla 5).

Paso rojo: hoy no existen `AppTranscriptor._cerrar_sesion_copilot`, la acción de iniciar sesión de la vista, la
función de la sección ni `PanelConfiguracion.refrescar_sesion`.

**Solo en la ventana real:** la sección pintada al principio del grupo IA, el estado real de los botones, el
`<KeyRelease>` del dominio, el diálogo de login de verdad abriéndose desde la vista, el repintado tras iniciar y cerrar,
el lateral y el campo del modelo tras cerrar, y la «Verificación común» del diseño (abrir la ventana: 0 lecturas del
token; mostrar la vista: 1 lectura y 0 peticiones). Lo ejecuta el orquestador con el guion de abajo.

### Guion de verificación manual (ventana real)

Un script en una carpeta temporal `T` dentro del scratchpad de la sesión (no en el repo), lanzado desde la raíz con
`./venv/bin/python <script>`. Nunca usa la sesión real ni imprime un token: solo tokens de prueba en `T`. `bombear(s)`
llama a `app.update()` durante `s` segundos; `registro()` es `app.text_log.get("1.0", "end")`; `panel` es
`app.panel_configuracion`; `seccion()` devuelve el texto de la sección y el `state` y el texto de sus dos botones;
«pulsar» es `.invoke()` del botón (o llamar a su `command` si está deshabilitado y se prueba el rechazo).

1. **Antes de importar `src.ui`:** `os.environ.pop("COPILOT_GITHUB_TOKEN", None)`. `src.copilot.RUTA_TOKEN` →
   `T/app/copilot.json`; `src.copilot.RUTA_AUTH_OPENCODE` → `T/oc/auth.json`; `src.configuracion.RUTA_PREFERENCIAS` →
   `T/prefs/preferencias.json` (ninguno existe). `httpx.get`, `httpx.post` y `httpx.stream` → funciones que anotan en
   `llamadas` y lanzan `AssertionError`. `src.copilot.leer_token` → envoltorio que anota el dominio en `lecturas` y
   llama a la original (así `estado_sesion`, que la busca en el módulo, también cuenta). `src.copilot.
   cargar_opciones_de_modelo(sesion, actual)` → espera el `threading.Event` `soltar_lista` (máx. 10 s) y devuelve
   `copilot.opciones_de_modelo(["auto", "gpt-4.1", "claude-haiku-5.5"], actual)`. Guarda bytes y `st_mtime_ns` de
   `config/settings.yaml`.
2. Importa `src.ui`. `ui.AsistenteIA` → `AsistenteAnotador` (el de `tests/test_ui.py:378`: anota sus `kw` en `creados`
   y devuelve un documento al momento; no lee el token). `ui.messagebox.showwarning`, `showerror` y `showinfo` anotan
   `(título, texto)` en `dialogos`; `askyesno` anota y devuelve el siguiente valor de la cola `respuestas`.
   `ui.DialogoLoginCopilot` → doble `(master, enterprise_url, al_terminar)` que se añade a `logins` y no hace nada más.
   `autorizar(d)` = `copilot.guardar_token("tok-prueba", d.enterprise_url)` y `d.al_terminar(True)`.
3. Construye la ventana como `ui.main()` y `bombear(1)`. **Comprueba:** `llamadas == []`, `lecturas == []`.
4. `Ctrl+3`. **Comprueba:** en el grupo «IA», la sección «Sesión de GitHub Copilot» va antes de «Modelo de IA»;
   `seccion()` es la fila «ninguna» del criterio 1; `lecturas == [None]`; `llamadas == []`.
5. **Dominio sin guardar:** escribe `empresa.ghe.com` en el dominio (inserta en el `Entry` y genera `<KeyRelease>`
   sobre él). **Comprueba:** los dos botones `disabled` y el texto termina en «Guarda primero el dominio.». Borra lo
   escrito y genera `<KeyRelease>`: vuelve la fila «ninguna». Escríbelo otra vez, `Ctrl+1`, `Ctrl+3`: el dominio está
   vacío y la sección es la de «ninguna». `T/prefs/preferencias.json` no existe.
6. **Asistente previo:** `app.resultado_actual` = un `ResultadoTranscripcion` de dos segmentos, `app.archivo_actual =
   str(T / "reunion.m4a")`; `app._generar_documento_ia("resumen")`, `bombear(1)`. **Comprueba:** `len(creados) == 1`.
7. **Cancelar el inicio:** `Ctrl+3`; pulsa «Iniciar sesión». **Comprueba:** `len(logins) == 1`,
   `logins[0].enterprise_url is None`, `app._login_abierto` es `True`. `logins[0].al_terminar(False)`, `bombear(0.3)`.
   **Comprueba:** la barra dice «Inicio de sesión en GitHub Copilot cancelado»; `seccion()` sigue en «ninguna»;
   `T/app/copilot.json` no existe; `app._epoca_ia` no cambió.
8. **Iniciar:** anota `e = app._epoca_ia` y `v = app.combo_modelo_ia.cget("values")`; pulsa «Iniciar sesión» y
   `autorizar(logins[1])`, `bombear(0.3)`. **Comprueba:** texto «Sesión iniciada con la app. La sesión se comprueba al
   usarla.», «Iniciar sesión» `disabled`, «Cerrar sesión» `normal`; `registro()` contiene «Sesión de GitHub Copilot
   iniciada»; `app._epoca_ia == e + 1`; `app.combo_modelo_ia.cget("values") == v`; `llamadas == []`.
   `app._generar_documento_ia("minuta")`, `bombear(1)`: `len(creados) == 2`.
9. **Cerrar con opencode, «No» primero:** escribe `T/oc/auth.json` con `{"github-copilot": {"refresh": "tok-oc",
   "enterpriseUrl": null}}` y guarda su `sha256` y `st_mtime_ns`. `soltar_lista.clear()`; pulsa el «↻» de la vista,
   `bombear(0.3)` (consulta en vuelo). `respuestas = [False]`; pulsa «Cerrar sesión». **Comprueba:** `dialogos` (o la
   anotación de `askyesno`) tiene `("Cerrar sesión", "¿Cerrar la sesión de GitHub Copilot guardada por la app? La de
   opencode y la variable de entorno no se tocan.")`; `T/app/copilot.json` sigue; `seccion()` no cambió.
10. **Cerrar, «Sí»:** anota `e = app._epoca_ia`; `respuestas = [True]`; pulsa «Cerrar sesión». **Comprueba:**
    `T/app/copilot.json` no existe; `T/oc/auth.json` con el mismo `sha256` y `st_mtime_ns`; `seccion()` es la fila
    «solo opencode» del criterio 1; `app._epoca_ia == e + 1`; `app.combo_modelo_ia.cget("values")` y las opciones del
    campo «Modelo de IA» son `["auto", "claude-haiku-5.5"]`; `registro()` contiene «Sesión de GitHub Copilot
    cerrada». `soltar_lista.set()`, `bombear(1)`: el selector sigue con esas dos opciones, los dos «↻» en `normal` y
    `registro()` contiene «Se descarta una lista de modelos de una sesión o un dominio anteriores».
    `app._generar_documento_ia("resumen")`, `bombear(1)`: `len(creados) == 3`.
11. **Fallo al borrar** (si el script corre como root, se salta: el permiso no falla): `copilot.guardar_token
    ("tok-prueba")`; `Ctrl+1`, `Ctrl+3` (fila «app»); `os.chmod(T / "app", 0o500)`; `respuestas = [True]`; pulsa
    «Cerrar sesión». **Comprueba:** `dialogos[-1][0] == "Sesión de GitHub Copilot"` y su texto empieza por «No se pudo
    cerrar la sesión:\n»; el archivo sigue; `seccion()` sigue en «app»; la época no cambió. `os.chmod(T / "app",
    0o700)`.
12. **Rechazo durante un proceso:** `copilot.guardar_token("tok-otro", "empresa.ghe.com")` (sesión propia de otro
    dominio con opencode: los dos botones habilitados); `Ctrl+1`, `Ctrl+3`. Asigna `app.transcripcion_thread =
    threading.Thread(target=time.sleep, args=(3,), daemon=True)` y arráncalo. Pulsa «Iniciar sesión con la app» y
    «Cerrar sesión». **Comprueba:** dos `("Sesión de GitHub Copilot", "Espera a que termine el proceso en curso.")`
    en `dialogos`; `respuestas` sin consumir (pon `[True]` antes); `len(logins)` no cambió; `T/app/copilot.json` sigue.
    Espera a que acabe el hilo.
13. **Variable de entorno:** `os.environ["COPILOT_GITHUB_TOKEN"] = "tok-var"`; `Ctrl+1`, `Ctrl+3`. **Comprueba:**
    `seccion()` es la fila «`COPILOT_GITHUB_TOKEN` y archivo propio» del criterio 1 (Iniciar `disabled`, Cerrar
    `normal`); ninguna línea de `registro()` ni de la sección contiene `tok-`. Quita la variable.
14. Al terminar: `llamadas == []` en todo el guion; `config/settings.yaml` con los mismos bytes y `st_mtime_ns`; borra
    `T`; `git status --short` no lista preferencias, tokens ni el YAML; `./venv/bin/python -m pytest -q` pasa.

Opcional, con una cuenta real y fuera de este guion (lo pide la verificación del diseño): CUJ 3 y CUJ 4 de verdad,
`sha256sum ~/.local/share/opencode/auth.json` igual antes y después. No hace falta para dar la historia por cumplida.
`python -m src.main --copilot-logout` no cambia (esta historia no toca `src/main.py` ni `copilot.cerrar_sesion`).

## Plan

- En la vista, una sección al principio del grupo IA (texto y dos botones) que se repinta desde el estado de la sesión
  leído del disco con el dominio guardado: al mostrar o refrescar la vista, y tras iniciar o cerrar sesión. Una
  función sin Tk decide el texto y el estado de los botones a partir de la descripción de la sesión y del dominio
  escrito frente al guardado.
- El campo del dominio, al soltar una tecla, compara su texto sin espacios con el guardado y, si difieren, deshabilita
  los dos botones y añade «Guarda primero el dominio.»; refrescar la vista lo deshace.
- Iniciar: la ventana rechaza durante una transcripción o generación; si no, abre el inicio de sesión de siempre y, al
  terminar bien, avanza la época de la IA, olvida el asistente y repinta la sección; no recarga la lista de modelos.
- Cerrar: la ventana rechaza durante un proceso, pregunta, cierra solo la sesión propia y, si va bien, avanza la
  época, olvida el asistente, repone el selector del lateral y el campo del modelo a `auto` y el configurado, lo anota
  en Registro y devuelve el estado para que la vista lo pinte; si el borrado falla, avisa y no cambia nada.
- Tests primero (paso rojo), con las rutas de sesión aisladas en cada test que llegue al disco y la red parcheada para
  que falle.

Archivos del `/pair` (lista cerrada, la del diseño): `src/ui_configuracion.py` (sección «Sesión de GitHub Copilot» al
principio del grupo IA en `PanelConfiguracion._construir`, `refrescar_sesion` llamado desde `refrescar`, el
`<KeyRelease>` del campo `ia.copilot_enterprise_url` y la función sin Tk de la sección), `src/ui.py`
(`AppTranscriptor._cerrar_sesion_copilot`; la acción de iniciar de la vista con su rechazo y su `al_conectar` que
avanza `_epoca_ia`, llama a `self._documentos.olvidar_asistente()` y repinta la sección, sobre
`_iniciar_sesion_copilot`, `src/ui.py:1049`, sin cambiarlo), `tests/test_ui.py`. Si hace falta otro, se para y se vuelve
al diseño. El delta de spec y el resto de la documentación los escribe `/cerrar`: `docs/specs/configuracion.md`
(«Vista Configuración», que hoy dice «Abrirla no hace ninguna petición de red ni lee el token» y «el resto (… la sesión
de GitHub Copilot) llega con otras historias»; y un comportamiento nuevo para la sección), `docs/specs/documentos-ia.md`
(«Fallo de una parte», último punto: las notas conservadas se pierden también al iniciar o cerrar sesión desde la
vista), `docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md`, `AGENTS.md`, `.context/*` y `README.md`.

## Fuera de alcance

- Cambiar `src/copilot.py` (`estado_sesion`, `describir_sesion`, `cerrar_sesion_propia`, `leer_token`: B y E1),
  `src/ui_copilot.py` (`DialogoLoginCopilot` sigue igual) o `src/main.py` (`--copilot-login` y `--copilot-logout` no
  cambian).
- Comprobar la sesión contra GitHub al mostrar la vista (alternativa F): el texto dice «se comprueba al usarla».
- Cerrar la sesión de opencode o tocar la variable de entorno (alternativa G).
- Rechazar iniciar o cerrar sesión mientras «↻» consulta (alternativa I): basta la época.
- Recargar sola la lista de modelos tras iniciar sesión; abrir o reutilizar sesiones `auto`.
- Repintar la sección cuando el inicio de sesión lo abre otra acción (una generación sin sesión, o «↻» sin sesión, también
  el de la vista, vía `_sin_sesion_para_modelos`, `src/ui.py:1007`), ni avanzar la época u olvidar el asistente en esos
  caminos: el diseño lo pone solo en el `al_conectar` de la vista. La sección se pone al día al volver a mostrar la
  vista (ver «Supuestos», 4).
- Calcular la sesión al abrir la ventana o con un temporizador (decisión técnica 8).

## Sugerencias (a tu criterio)

- Una función pura en `src/ui_configuracion.py`, por ejemplo `seccion_de_sesion(descripcion, dominio_escrito,
  dominio_guardado) -> (texto, iniciar_habilitado, cerrar_habilitado, texto_iniciar)`, como ya hay
  `motivo_para_no_guardar` y `aviso_modelo` en ese módulo: concentra la regla del dominio sin guardar y se prueba sin
  Tk; `refrescar_sesion` y el `<KeyRelease>` solo la llaman y pintan.
- `<KeyRelease>` no ve un pegado con el ratón ni el menú contextual; un `trace_add("write", …)` sobre la variable del
  campo sí. El diseño dice `<KeyRelease>`; si se usa la traza, el comportamiento observable es el mismo (o mejor) y
  `refrescar` también la dispara.
- La acción de iniciar puede ignorar una segunda pulsación si `_login_abierto` ya es `True`: `DialogoLoginCopilot` hace
  `grab_set` a los 100 ms (`src/ui_copilot.py:58`, `DialogoLoginCopilot.__init__`) y un doble clic rápido abriría dos diálogos. No lo pide el diseño.
- `_cerrar_sesion_copilot` puede repintar el campo del modelo del panel con `mostrar_modelos_ia` (D2), que ya existe,
  en vez de tocar su menú directamente; `_panel_de_modelos` (`src/ui.py:60`) ya tolera los dobles sin panel.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es que «Cerrar sesión» toque lo que no es suyo (el archivo de opencode o la variable) o
   que, tras cerrar, la app siga usando la sesión cerrada (un asistente viejo con el token borrado, o una lista de «↻»
   de la sesión anterior que pisa el selector). Lo cubren el criterio 3, `test_cerrar_sesion_copilot_olvida_el_asistente_y_avanza_la_epoca`
   y los pasos 9–10 del guion.
2. **D2 en la copia de trabajo.** Se toma su código sin commit: `AppTranscriptor._login_abierto` (`src/ui.py:184`, lo
   pone `_iniciar_sesion_copilot` tras construir el diálogo y lo quita `al_terminar`, `:1049-1061`),
   `_panel_de_modelos` y `_marcar_cargar_modelos` (`:60` y `:65`), `PanelConfiguracion.mostrar_modelos_ia` y el «↻» de la
   vista (`src/ui_configuracion.py:174`, `_crear_fila_modelo`; `:224`), `motivo_para_no_guardar` con cuatro
   parámetros (`:58`) y «Modelo de IA» como primer campo del grupo IA. `_epoca_ia`, `_cerrar_consulta_de_modelos`
   (`src/ui.py:73`) y el olvido del asistente en `aplicar_guardado` (`:1187`) son de D1, ya en `d69fb45`. Si D2 se
   cierra con otros nombres, esta historia sigue a los que queden.
3. **Textos que el diseño no fija.** Título del rechazo de los dos botones durante un proceso: «Sesión de GitHub
   Copilot» (el mismo que el del `OSError` en el diseño); el diseño solo dice que se rechaza con
   `motivo_para_no_guardar(transcribiendo, generando)`. La frase del dominio sin guardar lleva punto final («Guarda
   primero el dominio.») y va después del texto de la sesión, separada por un espacio, como las frases de
   `describir_sesion`.
4. **Inicio de sesión abierto por «↻» desde la vista.** Si no hay sesión y se pulsa el «↻» de la vista,
   `_sin_sesion_para_modelos` abre el login con `al_conectar = _cargar_modelos_ia`: al terminar bien, la sección sigue
   diciendo «No has iniciado sesión…» hasta que se vuelve a mostrar la vista, y la época no avanza (no hace falta: el
   «↻» que relanza captura la vigente). El diseño solo describe el `al_conectar` del botón de la vista; se deja fuera
   de alcance. Si el orquestador lo quiere, lo mínimo es repintar la sección del panel (si existe) en la rama de éxito
   de `_iniciar_sesion_copilot`, coherente con la decisión técnica 8 («tras iniciar o cerrar sesión»), sin añadir
   archivos.
5. **Rechazos.** Iniciar y cerrar se rechazan solo durante una transcripción o una generación, como dice el diseño; no
   con «↻» en curso (alternativa I) ni con el login abierto (el diálogo es modal). Durante el proceso los botones
   siguen con el estado de la tabla; el rechazo es el diálogo, no deshabilitarlos.
6. **Lecturas del token.** Mostrar la vista lee la sesión una vez (`estado_sesion` → `leer_token`, `src/copilot.py:172`
   y `:129`), y también cada `refrescar`: tras Guardar o Restablecer (`PanelConfiguracion._guardar`, `:269`, llama a
   `refrescar`) y al volver a la vista. Es disco, en el hilo principal (decisión técnica 8); la «Verificación común»
   cuenta solo el primer `mostrar_vista`. Tras un Guardar que cambia el dominio, la sección se repinta con el dominio
   nuevo.
7. **Tests añadidos** a los dos del diseño: cubren el rechazo y la respuesta «No» (criterio 3), el `al_conectar` de la
   vista (criterio 2) y la sección y el dominio sin guardar (criterio 1), que el diseño deja a la ventana real.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa (495 tests). Code review: revisión del orquestador, listo para commit. Ampliaciones aprobadas por el orquestador e implementadas en el pair, cada una con su test: (1) tras cualquier inicio de sesión que termine bien (también el que abre «↻» sin sesión) la sección de la vista se repinta; (2) el aviso de dominio sin guardar usa `trace_add` sobre la variable del campo, así vale también al pegar; (3) con un diálogo de inicio de sesión ya abierto no se abre otro.

Delta de spec (`docs/specs/configuracion.md` y `docs/specs/documentos-ia.md`, con `Origen` en esta historia):

- «Vista Configuración», primer bullet: [MODIFICA], con `(antes: …)`. Abrir la ventana no lee el token; mostrar la vista lo lee una vez del disco, sin red. La frase de grupos ya no dice que la sesión llega con otras historias.
- «Sesión de GitHub Copilot en la vista Configuración», «Iniciar sesión desde la vista Configuración», «Cerrar sesión desde la vista Configuración» y «Sesión de GitHub Copilot durante un proceso»: [NUEVO], con los criterios 1 a 3 y las ampliaciones (1) y (3) como bullets de su sección y (2) en el bullet del dominio pegado.
- «Cambio del dominio de GitHub Enterprise en la vista», bullet de la lista descartada: [MODIFICA], con `(antes: …)`. Se quita «pendiente, E2 de la historia 24»; ya no es verdad que ninguna acción de la vista cambie la época mientras consulta, porque iniciar o cerrar sesión sí la cambia.
- «Fallo de una parte» (`docs/specs/documentos-ia.md`): [MODIFICA]. Las notas conservadas también se pierden al iniciar o cerrar sesión desde la vista.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: configuracion › Vista Configuración] | Abrir la ventana no lee el token ni hace red. Al mostrar la vista, la sección «Sesión de GitHub Copilot» va al principio del grupo IA con el texto y los botones de cada sesión (ninguna, solo opencode, variable y archivo propio); mostrarla lee el disco una vez, sin red. Con el dominio escrito sin guardar, los botones se deshabilitan y el texto termina en «Guarda primero el dominio.» | `tests/test_ui.py:1080` (`test_seccion_de_sesion_segun_el_estado_y_el_dominio_escrito`), `:1107` (`test_refrescar_sesion_lee_el_disco_sin_red`), `:1172` (`test_campo_de_dominio_avisa_tambien_al_pegar`); `src/ui_configuracion.py:80` (`SeccionSesion`), `:87` (`seccion_de_sesion`), `:166` (`_construir_seccion_sesion`), `:215` (`trace_add`), `:267` (`refrescar_sesion`), `:272` (`_pintar_sesion`) | cumple (tests y ventana real) |
| 2 | [NUEVO] | Con «No has iniciado sesión…» y un asistente creado, «Iniciar sesión» y autorizar deja la sección en «Sesión iniciada con la app…», Registro, época +1 y asistente olvidado; la lista de «↻» que llega después se descarta. Cancelar no cambia nada ni crea el archivo | `tests/test_ui.py:987` (`test_iniciar_sesion_desde_la_vista_avanza_la_epoca_y_olvida_el_asistente`), `:1021` (`test_inicio_de_sesion_bien_terminado_repinta_la_seccion_de_la_vista`), `:951` (`test_acciones_de_sesion_rechazadas_o_canceladas_no_cambian_nada`); `src/ui.py:1049` (`_iniciar_sesion_copilot`), `:1069` (`iniciar_sesion_desde_la_vista`) | cumple (tests y ventana real) |
| 3 | [NUEVO] | Con archivo propio y opencode, «Cerrar sesión» + «Sí» borra solo el archivo propio, deja la sección en la fila de opencode, olvida el asistente, repone el selector a `auto` y el configurado, descarta «↻» en vuelo y anota Registro. «No» no cambia nada. Un `OSError` muestra «No se pudo cerrar la sesión: <motivo>.» y no cambia nada. Con un proceso en curso, ambos botones muestran «Espera a que termine el proceso en curso.» sin preguntar | `tests/test_ui.py:869` (`test_cerrar_sesion_copilot_olvida_el_asistente_y_avanza_la_epoca`), `:912` (`test_cerrar_sesion_copilot_con_oserror_no_aplica_nada`), `:951` (parametrizado: proceso y «No»); `src/ui.py:1082` (`_cerrar_sesion_copilot`), `src/ui_configuracion.py:282` (`_cerrar_sesion`) | cumple (tests y ventana real) |
| A1 | [NUEVO, ampliación] | Un inicio de sesión que termina bien repinta la sección de la vista, también el que abre «↻» sin sesión | `tests/test_ui.py:1021` (parametrizado `vista` y `sin_sesion`); `src/ui.py:1061` (`panel.refrescar_sesion()` en `_iniciar_sesion_copilot`) | cumple (tests y ventana real) |
| A2 | [NUEVO, ampliación] | El aviso de dominio sin guardar también salta al pegar | `tests/test_ui.py:1172`; `src/ui_configuracion.py:215` (`trace_add`), `:221` (`_al_escribir_dominio`) | cumple (tests) |
| A3 | [NUEVO, ampliación] | Con un diálogo de inicio de sesión abierto, otra pulsación de «Iniciar sesión» no abre otro | `tests/test_ui.py:1056` (`test_iniciar_sesion_con_login_abierto_no_abre_otro_dialogo`); `src/ui.py:1052` (`if self._login_abierto: return`) | cumple (tests y ventana real) |

**Verificación (2026-11-22):** `./venv/bin/python -m pytest -q` pasa (495). Comprobado por el orquestador en la ventana real con el guion de la historia (pasos 1 a 14), con rutas del token en carpeta temporal, sin `COPILOT_GITHUB_TOKEN`, `httpx` interceptado, `copilot.leer_token` contado, `cargar_opciones_de_modelo` bloqueable, el asistente, los diálogos y `DialogoLoginCopilot` sustituidos por dobles:

- Al abrir la ventana: 0 lecturas del token y 0 llamadas de red. Con `Ctrl+3`: 1 lectura y 0 llamadas; sección «No has iniciado sesión en GitHub Copilot.», «Iniciar sesión» habilitado y «Cerrar sesión» deshabilitado.
- Dominio `empresa.ghe.com` escrito sin guardar: «No has iniciado sesión en GitHub Copilot. Guarda primero el dominio.» con los dos botones deshabilitados; al borrarlo, vuelve la sección.
- Doble pulsación de «Iniciar sesión»: un solo diálogo. Cancelar: nada cambia (época, asistente, sin archivo). Autorizar: «Sesión iniciada con la app. La sesión se comprueba al usarla.», época +1, asistente olvidado, selector sin cambios, «Iniciar sesión» deshabilitado y «Cerrar sesión» habilitado.
- Con sesión de opencode: «Cerrar sesión» + «No»: nada cambia. Con «↻» en vuelo, «Sí»: archivo propio borrado, el de opencode con el mismo sha256 y fecha, época +1, asistente olvidado, selector `auto` y `claude-haiku-5.5`, Registro «Sesión de GitHub Copilot cerrada», sección «Se usa la sesión de opencode…» con «Iniciar sesión con la app». La lista de «↻» que llega después se descarta («Se descarta una lista de modelos de una sesión o un dominio anteriores»).
- Carpeta del token sin permiso de escritura: diálogo de error, el archivo sigue y la sección no cambia.
- Con transcripción en curso: «Espera a que termine el proceso en curso.» (título «Sesión de GitHub Copilot»), sin pregunta ni diálogo de inicio de sesión.
- Con la variable de entorno y archivo propio: «Se usa el token de la variable de entorno COPILOT_GITHUB_TOKEN…», «Iniciar» deshabilitado y «Cerrar sesión» habilitado; el texto no contiene el token.
- 0 llamadas de red en todo el recorrido.

Arreglo del orquestador tras la revisión: el error al cerrar sesión es ahora «No se pudo cerrar la sesión: <motivo>.» (solo el motivo, sin «[Errno 13]» ni la ruta, como el resto del panel). Se ajustó `test_cerrar_sesion_copilot_con_oserror_no_aplica_nada` (`tests/test_ui.py:912`).

**Pendientes aceptados:**

- Cada refresco de la vista vuelve a leer la sesión del disco (al mostrarla, tras «Guardar» o «Restablecer», y tras un inicio de sesión que termina bien). Es lectura de disco en el hilo principal, sin red.
- Con ventanas estrechas, la sección queda fuera de la vista hasta desplazarse.
