# 09 · Opciones, transcriptor y ruta de la transcripción fuera de la ventana

> Origen: `BACKLOG.md`, «Backlog» #8 (y «Salud del código» #5) — hallazgo A-15 — carril M (segunda de las siete
> historias del diseño).
> — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia B1 — Opciones, transcriptor y ruta de la
> transcripción fuera de la ventana (y §Plan técnico, punto 2, «Contrato» y «Cómo queda la ventana», viñeta B1;
> §Decisiones abiertas 1 y 4; §Revisión (2026-11-22)).
> Reglas de oro 3, 5 y 9 de `AGENTS.md`. Depende de la historia A (08, `faster_whisper` perezoso); B2 depende de esta.
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Criterios, tests y lista de archivos
> tomados del diseño y comprobados contra el código de `fd3b870` con los cambios de la historia A en el árbol de trabajo
> (suite: 287 tests en verde).

## Historia

Como quien mantiene el código, quiero sacar de la ventana las opciones de la transcripción, la elección del
transcriptor y la ruta del archivo de la transcripción, para poder probarlos y usarlos sin interfaz gráfica.

Es un cambio interno. **Lo observable es para quien mantiene el código**: existe un módulo sin Tk,
`src/flujo_transcripcion.py`, con `OpcionesTranscripcion`, `transcriptor_para`, `transcribir` y `ruta_transcripcion`,
que se puede importar y probar sin ventana; qué parámetros llegan a Whisper, cuándo se reutiliza un transcriptor y qué
ruta se propone para la transcripción se comprueban con tests sin ventana ni red. **Para el usuario la app no cambia**:
mismas opciones, mismos textos («Cargando modelo …», «Transcribiendo…»), misma reutilización del modelo cargado, mismo
nombre `reunion.m4a_transcripcion.<formato>` al exportar y en «Guardar como…». Ninguna spec de `docs/specs/` cambia.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dado un `config` de `cargar_configuracion` con `transcripcion.idioma: auto`,
  `transcripcion.beam_size: 3`, `transcripcion.logprob_threshold: -0.8` y `salida.palabra_por_palabra: true`, cuando se
  transcribe con `OpcionesTranscripcion.desde_configuracion(config, "reunion.m4a", modelo="small")` y
  `transcribir(transcriptor, opciones, config["transcripcion"])`, entonces Whisper recibe el audio `reunion.m4a`,
  `language=None`, `task="transcribe"`, `beam_size=3`, `log_prob_threshold=-0.8`, `word_timestamps=True` y el resto de
  parámetros de `config["transcripcion"]` (`best_of`, `temperature`, `condition_on_previous_text`,
  `compression_ratio_threshold`, `no_speech_threshold`) con sus valores; y
  `OpcionesTranscripcion.desde_configuracion(config, "reunion.m4a", timestamps=False)` lanza `TypeError` (un nombre de
  campo que no existe no se ignora). (antes: no existe ninguna función sin ventana que lo haga; las opciones son un
  `dict` que arma `AppTranscriptor._iniciar_transcripcion` con las claves `compute` y `timestamps`, y
  `_procesar_transcripcion` copia a mano los siete parámetros de `configuracion["transcripcion"]` y
  `salida.palabra_por_palabra` en la llamada a `TranscriptorAudio.transcribir`, igual que `src/main.py`; solo se puede
  comprobar con la ventana)
- [ ] [MODIFICA: sin spec] Dado un transcriptor creado para `small`, `cpu`, `int8`, cuando se pide
  `transcriptor_para(actual, "small", "cpu", "int8")`, entonces se devuelve la misma instancia; y con cualquiera de los
  tres valores distinto (o con `actual=None`), una instancia nueva con los valores pedidos, en los dos casos sin cargar el
  modelo de Whisper. (antes: `AppTranscriptor._obtener_transcriptor` reutiliza `self._transcriptor` si coinciden los tres
  valores; si no, crea uno nuevo, **lo carga** (`_ = t.modelo`) y solo entonces lo guarda en `self._transcriptor`; vive
  en la ventana y no se puede probar sin ella)
- [ ] [MODIFICA: sin spec] Dado el audio `/carpeta/reunion.m4a`, cuando se pide
  `ruta_transcripcion("/carpeta/reunion.m4a", "srt")`, entonces es `/carpeta/reunion.m4a_transcripcion.srt` (conserva la
  extensión del audio, como fijó el punto #18). (antes: `AppTranscriptor._generar_ruta_salida` devuelve la misma ruta con
  `utils.ruta_junto_al_audio`, pero toma el archivo y el formato de la ventana si no se le pasan; la usan el guardado tras
  transcribir y el nombre que propone «Guardar como…»)

### Cómo se verifican

- **Con tests sin red, sin ventana y sin modelo real** (regla 3), en `tests/test_flujo_transcripcion.py` (archivo
  nuevo), que usa `modelo_whisper_falso` de `tests/conftest.py` y no importa ningún doble privado de otros archivos de
  test:
  - `test_opciones_y_parametros_llegan_a_whisper` (criterio 1): escribe un `settings.yaml` en `tmp_path` con las cuatro
    claves del criterio, lo carga con `cargar_configuracion(ruta)`, coloca `doble = modelo_whisper_falso([(0.0, 2.0,
    "Hola.")])`, construye las opciones con `desde_configuracion(config, "reunion.m4a", modelo="small")` y un
    `TranscriptorAudio` (o el de `transcriptor_para(None, …)`) con los valores de las opciones, y llama a
    `transcribir(transcriptor, opciones, config["transcripcion"])`. Comprueba `doble.llamadas[0][0] == "reunion.m4a"` y,
    en `kw = doble.llamadas[0][1]`: `kw["language"] is None`, `kw["task"] == "transcribe"`, `kw["beam_size"] == 3`,
    `kw["log_prob_threshold"] == -0.8` (la clave real de Whisper, no `logprob_threshold`), `kw["word_timestamps"] is
    True`, y `best_of`, `temperature`, `condition_on_previous_text`, `compression_ratio_threshold` y
    `no_speech_threshold` iguales a los de `config["transcripcion"]`. Comprueba también que `opciones.modelo == "small"`
    y que los demás campos salen de `config` (`dispositivo`, `compute_type`, `formato`, `incluir_timestamps`).
  - `test_desde_configuracion_rechaza_un_campo_desconocido` (criterio 1): con `cargar_configuracion` de un YAML vacío
    en `tmp_path` (valores por defecto), `pytest.raises(TypeError)` en
    `desde_configuracion(config, "reunion.m4a", timestamps=False)`.
  - `test_transcriptor_para_reutiliza_o_recrea` (criterio 2): `monkeypatch.setattr(TranscriptorAudio, "modelo",
    property(<función que lanza AssertionError>))`, para que el test falle si algo lee el modelo. `actual =
    transcriptor_para(None, "small", "cpu", "int8")` es un `TranscriptorAudio` con esos tres valores;
    `transcriptor_para(actual, "small", "cpu", "int8") is actual`; y para cada variante
    (`"base", "cpu", "int8"`), (`"small", "cuda", "int8"`), (`"small", "cpu", "float32"`) devuelve otro objeto con los
    valores pedidos.
  - `test_ruta_transcripcion_conserva_la_extension` (criterio 3): `ruta_transcripcion(str(Path("/carpeta") /
    "reunion.m4a"), "srt") == str(Path("/carpeta") / "reunion.m4a_transcripcion.srt")`.
  - En `tests/test_importaciones.py`, se añade `"src.flujo_transcripcion"` a `MODULOS` y a `SIN_TK`. En `MODULOS` va
    **antes de `src.ui_copilot`** (por ejemplo, justo después de `src.persistencia`): el guion mira `sys.modules`
    acumulado y `src.ui_copilot` es el primero de la lista que carga `tkinter` y `customtkinter` (comprobado). Así el
    test existente `test_ningun_modulo_carga_faster_whisper_al_importarse` demuestra además que importar el módulo nuevo
    no carga `faster_whisper`, `tkinter` ni `customtkinter`.
  - En rojo, los cuatro tests nuevos fallan con `ImportError` (el módulo no existe) y el de importaciones falla al no
    poder importar `src.flujo_transcripcion`. Ningún test existente cambia, salvo las dos listas de
    `tests/test_importaciones.py`, y todos siguen pasando (`./venv/bin/python -m pytest -q`, hoy 287).
- **Verificación manual en la ventana real (la que pide el diseño):**
  - Transcribir un audio corto con `tiny`: se ve «Cargando modelo tiny…», el porcentaje avanza y el archivo
    `reunion.m4a_transcripcion.<formato>` aparece junto al audio.
  - Transcribir otro audio con el mismo modelo: no vuelve a mostrar una fase «Cargando modelo» larga (se reutiliza el
    transcriptor); cambiar a `base` sí lo carga.
  - «Guardar como…» propone `reunion.m4a_transcripcion.<formato>` con el formato elegido en el selector.
  - `grep -n "_obtener_transcriptor\|_generar_ruta_salida" src/ui.py` no devuelve nada.

## Plan

- Crear el módulo sin interfaz del flujo de transcripción, con un docstring que diga que sus funciones se llaman desde un
  hilo de fondo y no tocan widgets: las opciones congeladas con solo lo que eligen la ventana o la CLI (los parámetros
  de decodificación siguen en la configuración y se pasan aparte, decisión abierta 4), su construcción desde la
  configuración con cambios por nombre de campo, la ruta de la transcripción, la elección del transcriptor sin cargarlo
  y la llamada a Whisper.
- Que la ventana construya las opciones a partir de la configuración y de sus selectores en el hilo principal, como hoy,
  y que el hilo de la transcripción elija el transcriptor con la función nueva, fuerce él mismo la carga del modelo bajo
  «Cargando modelo …», guarde el transcriptor elegido y transcriba con la función nueva.
- El guardado tras transcribir sigue en la ventana con la misma función de persistencia y la ruta nueva; «Guardar
  como…» propone el nombre de la ruta nueva; se borran los dos métodos de la ventana que quedan sin uso.
- Tests en el orden rojo → verde: los cuatro nuevos y las dos listas de `tests/test_importaciones.py`, luego el módulo,
  luego la ventana, y la suite completa en verde.

## Fuera de alcance

- Historia B2: las fases (`FASE_CARGANDO_MODELO`, `FASE_TRANSCRIBIENDO`), `TranscripcionPersistida`,
  `transcribir_y_persistir`, los cambios de `_finalizar_ok` y el borrado de `tests/test_flujo.py`. En esta historia la
  ventana sigue revisando `cancelar_flag` y llamando a `persistir_transcripcion` dentro de `_procesar_transcripcion`.
- Historias C1 y C2 (texto, ruta, fecha y generación de fondo de los documentos), D1 y D2 (`GestorDocumentos`, punto de
  decisión y borrado de `persistir_documento_si_vigente`), y el módulo `src/flujo_documentos.py`.
- La antigua historia E: que la CLI (`src/main.py:186-198`) use `OpcionesTranscripcion` y `transcribir`. Sin historia;
  posible punto de «Salud del código» carril S con `/backlog` cuando esta historia esté cerrada.
- Copiar a `OpcionesTranscripcion` los siete parámetros de decodificación (decisión abierta 4: se descarta).
- Cambiar lo que pasa al cancelar una transcripción, el nombre de los archivos junto al audio (punto #18) o
  `utils.ruta_junto_al_audio`.
- Cambios en `src/transcriber.py`, `src/configuracion.py`, `src/utils.py`, `src/persistencia.py`, `src/main.py`,
  `tests/conftest.py`, `tests/test_flujo.py` o cualquier otro test existente.
- La documentación (`docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md`, `AGENTS.md` y su tabla de `src/`,
  `.context/*`): la actualiza `/cerrar`, no el `/pair`.

**Archivos que puede tocar el `/pair` (lista cerrada):** `src/flujo_transcripcion.py` (crear:
`OpcionesTranscripcion`, `ruta_transcripcion`, `transcriptor_para`, `transcribir`), `src/ui.py`
(`_iniciar_transcripcion`, `_procesar_transcripcion`, `_guardar_resultado`; borrar `_obtener_transcriptor` y
`_generar_ruta_salida`), `tests/test_flujo_transcripcion.py` (crear), `tests/test_importaciones.py` (añadir
`src.flujo_transcripcion` a `MODULOS` y a `SIN_TK`). Si hace falta tocar otro, se para y se vuelve al diseño.

## Sugerencias

- En `transcribir`, pasar los siete parámetros por nombre desde `parametros` (como en el pseudocódigo del diseño) y no
  con `**parametros`: `config["transcripcion"]` también trae `idioma`, que chocaría con el `idioma` de las opciones (el
  elegido en la ventana debe ganar al del YAML).
- En la ventana, guardar en `self._transcriptor` el transcriptor devuelto **después** de forzar `.modelo`, como hace hoy
  `_obtener_transcriptor`. Si se guarda antes y la carga falla, tampoco se rompe nada (desde la historia A el siguiente
  acceso a `.modelo` reintenta), pero así el comportamiento es idéntico al de hoy.
- Que el nombre del test del criterio 2 deje claro que no carga el modelo, o que el mensaje del `AssertionError` lo diga
  («transcriptor_para no debe cargar el modelo»), para que un fallo se entienda sin leer el test.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **Las tres marcas son `[MODIFICA: sin spec]`.** Los tres comportamientos existen hoy dentro de la ventana
   (`_iniciar_transcripcion` + `_procesar_transcripcion`, `_obtener_transcriptor`, `_generar_ruta_salida`) y ninguna
   spec los describe como API sin interfaz. Las specs de usuario que tocan lo mismo (`transcripcion.md`, «Guardado de la
   transcripción antes de exportarla», «Grabaciones con el mismo nombre», «Idioma configurado fuera del selector»)
   **no cambian**: `/cerrar` no debe reemplazarlas, solo puede actualizar su línea «Origen» si lo cree oportuno. Las
   notas `(antes: …)` salen del código leído.
2. **El caso que duele** es que un parámetro de la configuración deje de llegar a Whisper o llegue con otro nombre (el
   salto `logprob_threshold` → `log_prob_threshold`, o `auto` → `None`) sin que nada lo note, porque solo se vería en la
   calidad de la transcripción. Lo cubre el criterio 1. El camino no feliz es el `TypeError` del mismo criterio (un
   nombre de la ventana viejo, `compute` o `timestamps`, no se traga en silencio) y, en el criterio 2, que crear un
   transcriptor no cargue el modelo.
3. **`transcriptor_para` no carga el modelo** (diseño, «Contrato»): la carga sigue forzándose en
   `_procesar_transcripcion` para poder mostrar «Cargando modelo …» antes de transcribir. Es la única diferencia de
   reparto respecto a `_obtener_transcriptor`; el resultado para el usuario es el mismo.
4. **`palabra_por_palabra` sigue saliendo de la configuración**: la ventana no tiene un selector para él, así que
   `_iniciar_transcripcion` no lo pasa en los cambios y `desde_configuracion` toma `salida.palabra_por_palabra`, que es
   lo que hace hoy `_procesar_transcripcion`. `task` queda en su valor por defecto `"transcribe"` (la ventana no lo
   cambia).
5. **El YAML del test se escribe en `tmp_path`** y se carga con `cargar_configuracion(ruta)`: así el test usa la
   validación real (los cuatro valores del criterio son válidos: `auto` es un texto no vacío) sin depender de
   `config/settings.yaml`.

### Discrepancias entre el diseño y el código actual

Ninguna que cambie la historia. Comprobado contra el código: `_iniciar_transcripcion` (`src/ui.py:603`, opciones con
las claves `compute` y `timestamps`), `_obtener_transcriptor` (`:641`), `_procesar_transcripcion` (`:650`, revisa
`cancelar_flag` en `:657` y `:682`, parámetros en `:666-680`), `_generar_ruta_salida` (`:1238`), `_guardar_resultado`
(`:1249`, `initialfile` en `:1263`); `TranscriptorAudio.transcribir` recibe `logprob_threshold` y lo pasa a Whisper
como `log_prob_threshold` (`src/transcriber.py:119`) y convierte `idioma="auto"` en `language=None` (`:112`);
`utils.ruta_junto_al_audio` (`src/utils.py:174`); `configuracion._tabla` define las ocho claves de `transcripcion` y las
tres de `salida`; `modelo_whisper_falso` (`tests/conftest.py:41`) anota en `llamadas` tuplas `(audio, kwargs)` de
`WhisperModel.transcribe`; ningún test usa `_obtener_transcriptor`, `_generar_ruta_salida`, `_iniciar_transcripcion` ni
`_procesar_transcripcion`. Matices:

- **Orden en `MODULOS`.** El diseño solo dice que los módulos de `SIN_TK` van «antes de cualquier `src.ui*`». Como el
  guion comprueba `sys.modules` acumulado, lo exacto es «antes del primer módulo que carga Tk», que es `src.ui_copilot`
  (comprobado: hasta `src.main` ninguno carga `tkinter`). Ponerlo antes de `src.ui_copilot` cumple las dos cosas.
- **`config["transcripcion"]` incluye `idioma`.** El pseudocódigo del diseño enumera los siete parámetros, así que no
  hay conflicto; un `**parametros` sí lo tendría (ver «Sugerencias»).
- **Líneas del diseño.** El diseño cita las de `c59d0ac`; `src/ui.py` no cambió desde entonces y coinciden. La historia
  A (en el árbol de trabajo, sin commit al refinar esta) solo toca `src/transcriber.py`, `src/__init__.py` y
  `tests/test_importaciones.py`; las líneas de `src/transcriber.py` citadas arriba son ya las de después de A.
- **`_generar_ruta_salida` tiene valores por defecto** tomados de la ventana (`self.archivo_actual`,
  `self.var_formato`); `ruta_transcripcion` los exige. Por eso `_guardar_resultado` debe pasarle
  `self.archivo_actual` y `self.var_formato.get()` explícitamente, como dice el diseño.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 291 tests. Code review: revisión del orquestador (cambio interno acotado; la ventana conserva su comportamiento): listo para commit. Delta de spec: ninguno. Es un cambio interno; la app no cambia para el usuario y ninguna spec de `docs/specs/` cambia.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Con `transcripcion.idioma: auto`, `beam_size: 3`, `logprob_threshold: -0.8` y `palabra_por_palabra: true`, Whisper recibe `reunion.m4a`, `language=None`, `task="transcribe"`, `beam_size=3`, `log_prob_threshold=-0.8`, `word_timestamps=True` y el resto de parámetros de `config["transcripcion"]`; `desde_configuracion(..., timestamps=False)` lanza `TypeError` | tests `test_opciones_y_parametros_llegan_a_whisper` (`tests/test_flujo_transcripcion.py:37`) y `test_desde_configuracion_rechaza_un_campo_desconocido` (`tests/test_flujo_transcripcion.py:69`). Implementación: `src/flujo_transcripcion.py:28` (`desde_configuracion`) y `:58` (`transcribir`); la ventana las usa en `src/ui.py:610` y `src/ui.py:660` | cumple (tests y verificación manual) |
| 2 | [MODIFICA: sin spec] | `transcriptor_para` devuelve la misma instancia si los tres valores coinciden y una nueva si no, sin cargar el modelo | test `test_transcriptor_para_reutiliza_o_recrea` (`tests/test_flujo_transcripcion.py:23`, con `monkeypatch` que falla si se lee `.modelo`). Implementación: `src/flujo_transcripcion.py:49`; la ventana la usa en `src/ui.py:646`, que sigue forzando la carga con `_ = transcriptor.modelo` | cumple (test y verificación manual) |
| 3 | [MODIFICA: sin spec] | `ruta_transcripcion("/carpeta/reunion.m4a", "srt")` es `/carpeta/reunion.m4a_transcripcion.srt` | test `test_ruta_transcripcion_conserva_la_extension` (`tests/test_flujo_transcripcion.py:13`). Implementación: `src/flujo_transcripcion.py:44`; la ventana la usa en `src/ui.py:669` (guardado) y `src/ui.py:1239` (`initialfile` de «Guardar como…») | cumple (test y verificación manual) |

Apoyo a los tres criterios: el módulo nuevo no carga Tk ni `faster_whisper` (`tests/test_importaciones.py:21` en `SIN_TK` y `:17` en `MODULOS`, comprobado por `test_ningun_modulo_carga_faster_whisper_al_importarse`, `tests/test_importaciones.py:54`). Los métodos `_obtener_transcriptor` y `_generar_ruta_salida` se borraron de `src/ui.py` (`grep` no devuelve nada).

**Verificación (2026-11-22)**, hecha por el orquestador en la ventana real con Whisper simulado y sin red:

- Dos transcripciones seguidas del mismo audio usan el mismo transcriptor y cargan el modelo una sola vez.
- Whisper recibe `language="es"`, `beam_size=5`, `log_prob_threshold=-1.0` y `no_speech_threshold=0.6`.
- Se ven «Cargando modelo large-v3-turbo…» y «Transcribiendo…».
- El archivo es `reunion.m4a_transcripcion.txt` y el estado es «Completado · guardado como reunion.m4a_transcripcion.txt».
- Cancelar a mitad muestra «Cancelando… (termina el segmento actual)» y después «Transcripción cancelada», sin resultado y con «▶ Transcribir» de nuevo.

**Pendientes aceptados:**

- La CLI (`src/main.py:186-198`) todavía no usa `flujo_transcripcion`: es la antigua historia E, sin historia. Posible punto de «Salud del código» con `/backlog` cuando se decida.
- `persistir_transcripcion` sigue dentro de `_procesar_transcripcion` en la ventana; lo mueve la historia B2.
