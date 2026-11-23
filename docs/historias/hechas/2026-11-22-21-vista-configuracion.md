# 21 · Vista «Configuración» con Transcripción y Salida

> Origen: `BACKLOG.md`, «Backlog» #5 (panel de configuración, carril L), sexta de sus historias — Diseño:
> docs/disenos/06-panel-de-configuracion.md §Historia C1 (con «Plan técnico», 5: `Campo`, `CAMPOS`,
> `motivo_para_no_guardar`, `PanelConfiguracion`, `mostrar_vista` para tres vistas, `guardar_configuracion` y
> `aplicar_guardado`; «Decisiones tomadas», de producto 1, 3, 4 y 6 y técnicas 2 y 7; CUJ 1; «Verificación común», y
> «Revisión (2026-11-22)», fila «C demasiado grande» y «Motivo de rechazar Guardar durante un proceso») — carril M.
> Reglas de oro 3, 5, 8 y 9 de `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver
> «Supuestos»). Parte del estado que dejan la 17 (A1, hecha), la 18 (A2a, hecha), la 19 (A2b, hecha: commit
> `470fc76`), C0 (hecha, commit `5612335`) y la 20 (A3, aprobada y en implementación en la copia de trabajo, sin
> commit). Es la primera historia del panel que el usuario ve.

## Historia

Como usuario de la ventana, quiero una vista «⚙ Configuración» (`Ctrl+3`) donde cambiar y guardar los valores por
defecto de la transcripción y de la salida (modelo de Whisper, idioma, dispositivo, precisión, formato, marcas de
tiempo y marcas por palabra), para no tener que editar `config/settings.yaml` y para que lo que ajusté a mano en el
panel lateral para esta transcripción no se pierda al guardar.

## Criterios de aceptación

- [ ] [NUEVO] Dado el YAML del proyecto (`salida.formato: "txt"`, `modelo.nombre: "large-v3-turbo"`), sin
  `preferencias.json` y con el modelo de Whisper del panel lateral cambiado a mano a `tiny`, cuando se abre «⚙
  Configuración» con `Ctrl+3` (o con el botón de la barra), se elige `srt` en «Formato de salida» y se pulsa
  «Guardar», entonces el pie de la vista dice «Configuración guardada», `preferencias.json` queda exactamente
  `{"configuracion": {"salida": {"formato": "srt"}}}`, `config/settings.yaml` no cambia (mismos bytes y misma fecha de
  modificación), y al volver con `Ctrl+1` el selector de formato del lateral muestra `srt` y el de modelo sigue en
  `tiny`. La vista muestra dos grupos, «Transcripción» (Modelo de Whisper, Idioma, Dispositivo, Precisión) y «Salida»
  (Formato de salida, Incluir marcas de tiempo, Marcas por palabra), cada campo con su clave del YAML debajo; mientras
  se ve, no se ven las pestañas de resultado. Abrirla no hace ninguna petición de red ni lee el token.
- [ ] [NUEVO] Dado «Idioma» con `nl` escrito a mano, cuando se pulsa «Guardar», entonces `preferencias.json` guarda
  `transcripcion.idioma` = `nl` y el selector de idioma del lateral muestra `nl` y lo ofrece al final de su lista; y
  si después se cambia «Formato de salida» a `vtt` sin guardar, se va a Transcribir (`Ctrl+1`) y se vuelve (`Ctrl+3`),
  el campo vuelve a mostrar el valor guardado (`srt`), el lateral no cambió y `preferencias.json` tampoco.
- [ ] [NUEVO] Dado una transcripción en curso (o una generación de resumen o minuta), cuando se pulsa «Guardar» en la
  vista, entonces aparece el diálogo «Configuración» con «Espera a que termine el proceso en curso.», el pie de la
  vista muestra ese mismo texto, `preferencias.json` no cambia (ni se crea) y los controles del lateral conservan sus
  valores. Al terminar el proceso, «Guardar» funciona como en el criterio 1.

Ningún criterio cubre un error de validación en el formulario: en C1 los seis campos de lista, botones o
interruptor no admiten valores inválidos, y el único libre («Idioma») solo falla vacío; los errores bajo cada campo se
pintan ya en esta historia (el plan los necesita), pero el recorrido con errores es el CUJ 2 y el criterio 1 de C2.
El guion de verificación manual comprueba aun así el caso del idioma vacío (paso 9).

### Cómo se verifican

**Sin ventana** (con `pytest`, sin red, sin `AppTranscriptor` instanciado; `RUTA_PREFERENCIAS` aislada por el fixture
autouse `preferencias_aisladas` de `tests/conftest.py`):

- `tests/test_ui.py::test_campos_de_transcripcion_y_salida` (criterio 1): `CAMPOS` contiene exactamente las siete
  claves de C1 (`modelo.nombre`, `transcripcion.idioma`, `modelo.dispositivo`, `modelo.compute_type`,
  `salida.formato`, `salida.incluir_timestamps`, `salida.palabra_por_palabra`), en ese orden, todas con
  `avanzado=False`, con los grupos «Transcripción» y «Salida» de la tabla del diseño, y las opciones de las listas y
  botones son `MODELOS_WHISPER`, `DISPOSITIVOS`, `TIPOS_COMPUTO` y `FORMATOS` de `src/configuracion.py`; todas las
  claves están en `configuracion._tabla()`.
- `tests/test_ui.py::test_motivo_para_no_guardar_durante_un_proceso` (criterio 3): `(False, False)` → `None`;
  `(True, False)`, `(False, True)` y `(True, True)` → «Espera a que termine el proceso en curso.».
- `tests/test_ui.py::test_guardar_configuracion_durante_un_proceso_no_escribe` (criterio 3; añadido por esta
  historia, ver «Supuestos», 6): `AppTranscriptor.guardar_configuracion` sin enlazar, con un `types.SimpleNamespace`
  como `self` cuyo `_transcribiendo` devuelve `True`, `messagebox.showwarning` de `src.ui` parcheado para anotar y
  `src.ui.guardar_formulario` parcheado para fallar si se llama: devuelve un resultado con `efectiva` `None` y
  `mensaje` «Espera a que termine el proceso en curso.», el aviso se anotó con el título «Configuración», no se llamó
  a `guardar_formulario` y `preferencias.json` no existe.
- `tests/test_ui.py::test_aplicar_guardado_solo_toca_las_claves_cambiadas` (criterios 1 y 2; añadido por esta
  historia, ver «Supuestos», 6): `AppTranscriptor.aplicar_guardado` sin enlazar, con un `SimpleNamespace` cuyos
  `var_modelo`, `var_idioma`, `var_formato`, `var_dispositivo`, `var_compute` y `var_timestamps` son dobles que anotan
  `set`, y `combo_idioma` un doble que anota `configure`; con un `ResultadoGuardado` cuya `efectiva` tiene `idioma`
  `nl` y `formato` `srt` y cuyas `cambiadas` son esas dos claves: `self.configuracion` es **el mismo objeto** que
  `resultado.efectiva` (sustitución), solo `var_idioma` («nl») y `var_formato` («srt») recibieron `set`,
  `combo_idioma` recibió `values` con «nl» al final, y `var_modelo` no se tocó.
- `tests/test_importaciones.py`: `src.ui_configuracion` añadido a `MODULOS`, antes de `src.ui` (no va en `SIN_TK`:
  pinta con CustomTkinter); `test_ningun_modulo_carga_faster_whisper_al_importarse` comprueba que importarlo no carga
  `faster_whisper`.
- Siguen pasando sin cambios los de C0 (`test_el_hilo_de_transcripcion_no_lee_la_configuracion`,
  `test_los_parametros_se_capturan_en_el_hilo_principal`), los de idioma de `tests/test_ui.py` y todos los de las
  historias 17 a 20.

Paso rojo: con el código de hoy fallan al importar `src.ui_configuracion` (no existe) y al buscar
`AppTranscriptor.guardar_configuracion` y `aplicar_guardado`.

**Solo en la ventana real:** la vista pintada, la barra con tres botones, los atajos, que el lateral cambie de verdad
y el diálogo de rechazo. Lo ejecuta el orquestador con el guion de abajo.

### Guion de verificación manual (ventana real)

Un script en la carpeta temporal (no en el repo), lanzado desde la raíz con `./venv/bin/python <script>`:

1. **Antes de importar `src.ui`:** apunta `src.configuracion.RUTA_PREFERENCIAS` a `<tmp>/preferencias.json` (sin
   crearlo); parchea `httpx.get`, `httpx.post` y `httpx.stream` (sobre el módulo `httpx`, que es el mismo
   `copilot.httpx`) y `src.copilot.leer_token` con funciones que anotan cada llamada en una lista `llamadas` y lanzan
   `AssertionError`. Guarda los bytes y `st_mtime_ns` de `config/settings.yaml`.
2. Construye la ventana como `ui.main()`: `proyecto = cargar_configuracion()`, `efectiva, avisos = combinar(proyecto,
   leer_ajustes())`, `app = AppTranscriptor(efectiva, proyecto=proyecto, avisos=avisos)`; procesa eventos un segundo
   (`app.update()` en bucle). **Comprueba:** `llamadas == []`.
3. En el lateral elige a mano «tiny» en «Modelo» (o `app.var_modelo.set("tiny")`).
4. Pulsa `Ctrl+3` (o el botón «⚙  Configuración» de la barra). **Comprueba:** la barra tiene tres botones y marca
   «⚙  Configuración»; se ven los grupos «Transcripción» (Modelo de Whisper `large-v3-turbo`, Idioma «Español»,
   Dispositivo `cpu`, Precisión `int8`) y «Salida» (Formato `txt`, Incluir marcas de tiempo encendido, Marcas por
   palabra apagado), cada uno con su clave del YAML en gris debajo; no se ven el panel lateral ni las pestañas
   Texto/Resumen/Minuta; `llamadas == []`.
5. Elige `srt` en «Formato de salida» y pulsa «Guardar». **Comprueba:** el pie dice «Configuración guardada»;
   `preferencias.json` es exactamente `{"configuracion": {"salida": {"formato": "srt"}}}`; `config/settings.yaml`
   tiene los mismos bytes y `st_mtime_ns`; Registro anota las claves cambiadas.
6. Pulsa `Ctrl+1`. **Comprueba:** el selector de formato del lateral marca `srt` y el de modelo sigue en `tiny`.
7. `Ctrl+3`, escribe `nl` en «Idioma» y pulsa «Guardar». `Ctrl+1`. **Comprueba:** el selector de idioma del lateral
   muestra `nl` y su lista termina en `nl`; `preferencias.json` tiene además `"transcripcion": {"idioma": "nl"}`.
8. `Ctrl+3`, cambia «Formato de salida» a `vtt` y enciende «Marcas por palabra», **sin** guardar; `Ctrl+1`; `Ctrl+3`.
   **Comprueba:** el formato vuelve a `srt` y «Marcas por palabra» a apagado; el lateral sigue en `srt`;
   `preferencias.json` no cambió. Prueba también `Ctrl+2` (Historial) → `Ctrl+3` → `Ctrl+1`: cada atajo muestra su
   vista y la barra la marca.
9. `Ctrl+3`, borra «Idioma» y pulsa «Guardar». **Comprueba:** bajo «Idioma» aparece «`transcripcion.idioma` debe ser
   un texto no vacío (vale «»).», el pie dice «No se guardó nada: corrige 1 valor.» y `preferencias.json` no cambió.
   Vuelve con `Ctrl+1` y `Ctrl+3`: el campo muestra `nl` y el error ya no está.
10. Rechazo durante una transcripción (sin Whisper real: `tiny` no está en la caché y no se descarga): asigna
    `app.transcripcion_thread = threading.Thread(target=time.sleep, args=(5,), daemon=True)` y arráncalo; en la vista,
    cambia el formato a `json` y pulsa «Guardar». **Comprueba:** diálogo «Configuración» con «Espera a que termine el
    proceso en curso.» (ciérralo, o parchea antes `src.ui.messagebox.showwarning` para anotarlo); el pie muestra el
    mismo texto; `preferencias.json` no cambió; en el lateral el formato sigue en `srt`. Repite con
    `app._generando_ia = lambda: True` (sin hilo vivo): mismo resultado. Quita el parche, espera a que acabe el hilo y
    pulsa «Guardar» otra vez: ahora guarda `json` y el lateral pasa a `json`.
11. Cierra la ventana (`app.destroy()`) y construye otra igual que en el paso 2, con el mismo `RUTA_PREFERENCIAS`.
    **Comprueba:** el lateral abre con formato `json` e idioma `nl`, y la vista Configuración los muestra;
    `llamadas == []` después de `mostrar_vista(VISTA_CONFIGURACION)` («Verificación común» del diseño).
12. Al terminar: `git status --short` no lista `config/settings.yaml` ni ningún archivo de preferencias, y
    `./venv/bin/python -m pytest -q` pasa.

(Opcional, si hay un audio corto y un modelo en la caché, por ejemplo `medium`: transcribirlo tras el paso 6 exporta
`<audio>_transcripcion.srt`, como en el CUJ 1.)

## Plan

- Un módulo de vista nuevo con la descripción de cada campo (clave, etiqueta, tipo de control, grupo y opciones) para
  los siete de Transcripción y Salida, la regla pura de cuándo no se puede guardar (transcripción o generación en
  curso) y el panel que pinta los campos en una lista desplazable, con la clave del YAML en gris y una línea de error
  bajo cada uno, y un pie con «Guardar» y una línea de estado; al mostrarse de nuevo, vuelve a poner los valores
  guardados y limpia errores y pie.
- La ventana pasa a tres vistas: tercer botón en la barra, atajo `Ctrl+3`, y el cambio de vista oculta las otras dos
  y construye el panel de configuración la primera vez que se muestra (como el Historial) o lo refresca las demás.
- Guardar desde la ventana: si hay un proceso en curso, avisa con el diálogo «Configuración» y no hace nada; si no,
  compone el guardado sin ventana (A3) con la configuración del proyecto, la actual y el modelo preferido; si la
  escritura falla, diálogo de error y nada se aplica; si va bien, aplica el resultado.
- Aplicar un guardado: sustituir la configuración de la ventana por la nueva (sin mutarla), quedarse con los avisos
  nuevos de las preferencias y poner en el panel lateral solo los valores de las claves que cambiaron (incluidas las
  opciones del selector de idioma), anotando en Registro qué cambió.
- Tests sin ventana de los campos, de la regla de rechazo, del rechazo en la ventana y de que aplicar un guardado solo
  toca lo cambiado; el nuevo módulo entra en la comprobación de importaciones.

Archivos del `/pair` (lista cerrada, la del diseño): `src/ui_configuracion.py` (crear: `Campo`, `CAMPOS` de C1,
`motivo_para_no_guardar(transcribiendo, generando)`, `PanelConfiguracion` con `__init__`, `refrescar` y `_guardar`),
`src/ui.py` (`VISTA_CONFIGURACION`, `self.panel_configuracion = None` en `__init__`, `self.nav` en
`_construir_encabezado`, `mostrar_vista`, `<Control-Key-3>` en `_configurar_atajos`, `guardar_configuracion`,
`aplicar_guardado` sin las partes de C2 y D1, e importar `guardar_formulario`, `valores_laterales` y
`ResultadoGuardado` de `src.configuracion`), `tests/test_ui.py`, `tests/test_importaciones.py`. Si hace falta otro, se
para y se vuelve al diseño. El delta de spec (`docs/specs/configuracion.md`) y el resto de la documentación
(`docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md`, tabla de `AGENTS.md`, `README.md` con la vista y `Ctrl+3`) los
escribe `/cerrar`.

## Fuera de alcance

- **C2:** los campos avanzados de Transcripción (las siete claves de decodificación, plegadas en «Avanzado»), el grupo
  Historial (`historial.ruta` con su nota «Se aplica al reiniciar la app.»), «Restablecer valores del proyecto»
  (`restablecer_configuracion`, `restablecer_formulario`), el recuadro de avisos de preferencias arriba de la vista, y
  en `aplicar_guardado` lo de `_modelo_preferido`, `var_modelo_ia`, las etiquetas de las pestañas de IA y olvidar el
  asistente.
- **D1 y D2:** el grupo IA (dominio de Enterprise, revisión de fidelidad, ajuste fino, «Modelo de IA» con su «↻»),
  `_epoca_ia`, `aviso_modelo`, `argumentos_asistente`, y los parámetros `consultando_modelos` y `login_abierto` de
  `motivo_para_no_guardar` (rechazar Guardar con «↻» en vuelo o el login abierto).
- **E2 (y B, E1):** la sección «Sesión de GitHub Copilot» de la vista; en C1 mostrar la vista no lee el token.
- Reabrir el historial al cambiar `historial.ruta`, recordar el tema o el tamaño de la ventana, y que la CLI lea las
  preferencias (decisión de producto 4; `docs/specs/cli.md` no cambia).
- Cambiar `Ctrl+S`: en la vista Configuración sigue guardando el resultado de la transcripción, si lo hay, no la
  configuración. Cambiar `Ctrl+H` (sigue abriendo el Historial).
- Cambiar `guardar_formulario`, `valores_laterales`, `validar_formulario`, `guardar_ajustes` o sus mensajes.

## Sugerencias (a tu criterio)

- `PanelConfiguracion` puede seguir el patrón de `PanelHistorial` (`src/ui_historial.py:38-57`): `__init__(master,
  app)`, guarda `self.app`, construye y llama a `refrescar()` al final; `mostrar_vista` ya llama a `refrescar()` cuando
  el panel existe (`src/ui.py:1112-1113`).
- Para «Idioma» (lista editable) un `CTkComboBox` con `values=opciones_de_idioma(codigo)` y, al leerlo,
  `codigo_de_idioma(texto)`, que devuelve tal cual lo que no es un nombre conocido; las listas, un `CTkOptionMenu`;
  «Formato», un `CTkSegmentedButton` como el del lateral; los interruptores, `CTkSwitch` con `BooleanVar` (así
  `valor_desde_formulario` recibe un `bool`).
- Un diccionario `(sección, clave) → variable Tk del panel` deja `refrescar` y la lectura de `valores_widget` en un
  bucle sobre `CAMPOS`.
- `self.nav` con tres textos largos puede quedar ancho junto al título; si en la ventana mínima (`900x640`) se corta,
  basta con reducir la fuente de la barra, sin tocar los textos de las vistas.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es que «Guardar» cambie un control del lateral que el usuario había ajustado a mano para
   esta transcripción, o que escriba en `config/settings.yaml`. Lo cubren el criterio 1 (`tiny` se conserva; el YAML
   no cambia) y `test_aplicar_guardado_solo_toca_las_claves_cambiadas`.
2. **Dependencia de A3 (sin implementar).** Se toma de la historia 20: `guardar_formulario(proyecto, anterior,
   valores_widget, modelo_ia=None, preferido_anterior=None) -> ResultadoGuardado` con los campos `(errores, efectiva,
   modelo_preferido, avisos, cambiadas, mensaje)`; `mensaje` «Configuración guardada» o `resumen_errores(n)` o «No se
   pudo guardar la configuración: <motivo>.»; `valores_laterales(cambiadas, configuracion) -> dict` con las claves
   `var_modelo`, `var_dispositivo`, `var_compute`, `var_idioma`, `opciones_idioma`, `var_formato` y `var_timestamps`;
   y los ayudantes de idioma en `src/idiomas.py`. Si A3 se cierra con otra firma, esta historia sigue a la que quede.
   En C1, `guardar_configuracion` llama con `modelo_ia=None` (no hay campo de IA) y `preferido_anterior =
   self._modelo_preferido`.
3. **Nombre del método.** El encargo lo llamaba `aplicar_configuracion`; el diseño («Plan técnico», 5, y la lista de
   archivos de C1) lo llama `aplicar_guardado`. Se sigue el diseño.
4. **Rechazo de Guardar en C1: solo transcripción y generación.** El diseño pone en C1 `motivo_para_no_guardar` «con
   los dos primeros parámetros» y deja `consultando_modelos` y `login_abierto` para D2; además hoy no existen ni
   `_consultando_modelos` ni `_login_abierto` en `src/ui.py`, y en C1 el formulario no tiene campos de IA, así que
   «↻» y el login no compiten con este guardado. La razón del rechazo es la del diseño (técnica 7): el estado de los
   controles, no los hilos (eso lo resolvió C0). Durante una transcripción `_bloquear_opciones` (`src/ui.py:647-651`)
   deshabilita los controles laterales que `aplicar_guardado` cambiaría, y durante una generación el selector de modelo
   de IA está deshabilitado (`src/ui.py:867`); cambiarlos por debajo dejaría la vista incoherente con lo que corre.
   Durante el rechazo, `guardar_configuracion` muestra `messagebox.showwarning("Configuración", motivo)` y devuelve
   `ResultadoGuardado({}, None, None, [], set(), motivo)`, que el panel pinta en el pie.
5. **Qué hace `refrescar`.** Pone en cada campo el valor de `app.configuracion` y limpia las líneas de error y el pie
   (descarta lo no guardado). Se llama al construir el panel, cada vez que se vuelve a mostrar y tras un guardado
   correcto. El recuadro de avisos que el diseño también pone en `refrescar` es de C2.
6. **Dos tests añadidos** a los dos del diseño: `test_guardar_configuracion_durante_un_proceso_no_escribe` y
   `test_aplicar_guardado_solo_toca_las_claves_cambiadas`. Siguen la técnica de «Dobles de test» del diseño (método
   sin enlazar con un `SimpleNamespace` como `self`) y cubren sin ventana el criterio 3 y el caso que más duele; no
   añaden archivos a la lista cerrada.
7. **Registro.** `guardar_configuracion` anota con `_log` las claves cambiadas tras un guardado correcto; el diseño
   no fija el texto, así que no entra en los criterios. Los `avisos` del resultado (descartes de claves que no sirven)
   se guardan en `self.avisos_preferencias`; mostrarlos en la vista es de C2.
8. **Marcas.** Los tres criterios son `[NUEVO]`: `docs/specs/configuracion.md` describe qué gana al abrir la ventana
   («Preferencias del usuario al abrir la ventana») y el modelo de IA elegido, pero no hay ninguna vista ni acción de
   guardar desde un formulario; las vistas de la barra y `Ctrl+1`/`Ctrl+2` no tienen spec y no cambian. El dominio de
   la spec es `configuracion`.
9. **`salida.palabra_por_palabra`** no tiene control lateral: tras guardarla, la siguiente transcripción la toma de
   `self.configuracion` sustituida (`OpcionesTranscripcion.desde_configuracion`, `src/flujo_transcripcion.py:44`).
10. **Líneas** (commit `470fc76`; manda el nombre de la función. A3, en curso en la copia de trabajo, ya saca los
    ayudantes de idioma de `src/ui.py` y sube unas 28 líneas todo lo que sigue: por ejemplo `mostrar_vista` pasa a
    `:1071`, `_configurar_atajos` a `:445` y el `__init__` a `:87`): `src/ui.py`: importación de `src.configuracion` `:28-29`,
    `VISTA_TRANSCRIBIR`/`VISTA_HISTORIAL` `:76-77`, `AppTranscriptor.__init__` `:115-176` (`self.configuracion` y
    `configuracion_proyecto` `:127-128`, `avisos_preferencias` `:129`, `self.panel_historial = None` `:150`, variables
    del lateral `:161-167`), `_construir_encabezado` `:196-227` (`self.nav` `:207-215`), `combo_idioma` `:275-279`,
    `btn_cargar_modelos_ia` `:297-298`, `_configurar_atajos` `:473-482` (`Ctrl+1`/`Ctrl+2` `:479-480`),
    `_transcribiendo` `:599-600`, `_bloquear_opciones` `:647-651`, `_generando_ia` `:777-778`, `mostrar_vista`
    `:1099-1120`, `main` `:1287-1305`; `src/ui_historial.py`: `PanelHistorial.__init__` `:39-57`, `refrescar` `:126`;
    `src/configuracion.py`: `FORMATOS`, `DISPOSITIVOS`, `TIPOS_COMPUTO`, `MODELOS_WHISPER` `:26-30`, `_tabla`
    `:91-122`, `validar_formulario` `:414-438`, `resumen_errores` `:441-443`; `tests/test_importaciones.py`: `MODULOS`
    `:15-19`, `SIN_TK` `:22`.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa (421 tests). Code review: revisión del orquestador, listo para commit. Delta de spec: `docs/specs/configuracion.md`, nueva sección «Vista Configuración», con `Origen` en esta historia.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Vista «⚙ Configuración» (`Ctrl+3` o botón de la barra) con los grupos Transcripción y Salida; guardar `srt` con «Guardar» deja `preferencias.json` exacto, el YAML sin cambios y el lateral con `srt` y `tiny` conservado | Campos: `tests/test_ui.py:78` (`test_campos_de_transcripcion_y_salida`). Lateral solo con las claves guardadas: `tests/test_ui.py:136`. Implementación: `src/ui.py:1106` (`guardar_configuracion`), `:1124` (`aplicar_guardado`), `src/ui_configuracion.py:27` (`CAMPOS`), `:144` (`_guardar`). Ventana real: verificación manual, pasos 2 a 6 | cumple (tests y verificación en la ventana) |
| 2 | [NUEVO] | Idioma `nl` escrito a mano: se guarda, el lateral lo muestra y lo ofrece al final de su lista; una edición sin guardar se descarta al volver a la vista | Lateral con `nl` al final: `tests/test_ui.py:136`. Descarte al volver: `src/ui_configuracion.py:121` (`refrescar`). Ventana real: verificación manual, pasos 7 y 8 | cumple (tests y verificación en la ventana) |
| 3 | [NUEVO] | Con transcripción o generación en curso, «Guardar» muestra «Espera a que termine el proceso en curso.» (diálogo y pie) y no escribe; al terminar, guarda | Regla: `tests/test_ui.py:99` (`test_motivo_para_no_guardar_durante_un_proceso`). No escribe: `tests/test_ui.py:110` (`test_guardar_configuracion_durante_un_proceso_no_escribe`). Implementación: `src/ui_configuracion.py:38` (`motivo_para_no_guardar`), `src/ui.py:1106`. Ventana real: verificación manual, paso 10 | cumple (tests y verificación en la ventana) |

**Verificación (2026-11-22):** `./venv/bin/python -m pytest -q` pasa (421). Comprobado por el orquestador en la ventana real, con un script que intercepta `httpx` y `copilot.leer_token`, `RUTA_PREFERENCIAS` temporal y los diálogos capturados:

- Al arrancar y al mostrar la vista, 0 llamadas de red y 0 lecturas del token; la vista se construye la primera vez que se muestra.
- `Ctrl+3` muestra la barra con tres botones; los siete campos tienen los valores del YAML (`large-v3-turbo`, Español, `cpu`, `int8`, `txt`, marcas de tiempo sí, por palabra no) y su clave del YAML debajo.
- `srt` + «Guardar»: pie «Configuración guardada»; `preferencias.json` exacto; el YAML con los mismos bytes y fecha. `Ctrl+1`: el lateral muestra `srt` y `tiny` se conserva.
- Idioma `nl` guardado: el lateral muestra «nl» y su lista termina en «Coreano», «nl».
- `vtt` y «Marcas por palabra» sin guardar: al volver con `Ctrl+1` y `Ctrl+3`, vuelven a `srt` y apagado. `Ctrl+2`, `Ctrl+3` y `Ctrl+1` cambian de vista.
- Idioma vacío: bajo el campo, «`transcripcion.idioma` debe ser un texto no vacío (vale «»).»; pie «No se guardó nada: corrige 1 valor.»; archivo sin cambios.
- Con transcripción en curso y con generación en curso: diálogo «Configuración» «Espera a que termine el proceso en curso.», mismo texto en el pie, archivo y lateral sin cambios. Libre de nuevo, guardar `json` funciona y el lateral pasa a `json`.
- Reabrir la ventana: formato `json` e idioma `nl` en el lateral y en la vista; 0 llamadas.

**Pendientes aceptados:**

- `Ctrl+S` en la vista Configuración sigue guardando la transcripción (si la hay), no la configuración.
- El rechazo de Guardar con «↻» en vuelo o con el login abierto llega con la historia D2 (backlog #22).
- El panel de `src/ui_configuracion.py` se escribió de una vez y se verificó en la ventana; `PanelConfiguracion` no tiene tests propios (sí la regla, `CAMPOS` y el guardado sin ventana).
