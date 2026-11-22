# 11 · «Transcribir y persistir» fuera de la ventana

> Origen: `BACKLOG.md`, «Backlog» #9 (y «Salud del código» #5) — hallazgo A-15 — carril M (tercera de las siete
> historias del diseño).
> — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia B2 — «Transcribir y persistir» fuera de la ventana
> (y §Plan técnico, punto 2, «Contrato» (`FASE_*`, `TranscripcionPersistida`, `transcribir_y_persistir`), «Reglas del
> contrato» y «Cómo queda la ventana», viñeta B2; §CUJ 1; §Revisión (2026-11-22)).
> Reglas de oro 3, 5, 6 y 9 de `AGENTS.md`. Depende de la historia B1 (09, cerrada en `d3037e0`): construye sobre
> `src/flujo_transcripcion.py`. Ninguna historia depende de esta.
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Criterios, tests y lista de archivos
> tomados del diseño y comprobados contra el código de `d3037e0` (suite en ese commit: 291 tests en verde; en el árbol
> de trabajo hay cambios a medias de la historia C1, ver «Convivencia con C1»).

## Historia

Como quien mantiene el código, quiero que «transcribir y persistir» viva fuera de la ventana, para que la ventana solo
lo llame y pinte el resultado.

Es un cambio interno. **Lo observable es para quien mantiene el código**: `src/flujo_transcripcion.py` gana
`FASE_CARGANDO_MODELO`, `FASE_TRANSCRIBIENDO`, `TranscripcionPersistida` y `transcribir_y_persistir`, que carga el
modelo, transcribe, respeta la cancelación y guarda (historial primero, archivo después) sin ventana; el recorrido
completo, los fallos de guardado y la cancelación se prueban sin Tk ni red. `AppTranscriptor._procesar_transcripcion`
deja de revisar `cancelar_flag` y de llamar a `persistir_transcripcion`. **Para el usuario la app no cambia**: mismos
textos («Cargando modelo <m>…», «Transcribiendo…», «Transcripción cancelada», «Error en la transcripción»), mismo
porcentaje, mismos avisos y diálogo de advertencia, mismo `reunion.m4a_transcripcion.<formato>`, y lo transcrito se
sigue descartando al cancelar. Ninguna spec de `docs/specs/` cambia.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dado `reunion.m4a` con los segmentos «Hola equipo.», «¡Suscríbete!» y «Cerramos el punto.»
  (5 s, idioma `es`), formato `txt` con marcas de tiempo y un historial temporal, cuando se llama a
  `transcribir_y_persistir`, entonces `on_fase` recibe `cargando_modelo` y después `transcribiendo`; `on_segmento`
  recibe los dos segmentos aceptados en orden («Hola equipo.», «Cerramos el punto.»); la entrada del historial
  (`reunion`, modelo `small`, idioma `es`, 5 s) tiene el texto «Hola equipo. Cerramos el punto.» sin la alucinación; y
  `reunion.m4a_transcripcion.txt`, junto al audio, contiene las dos líneas con sus marcas
  (`[00:00:00,000 --> 00:00:02,000] Hola equipo.` y `[00:00:03,000 --> 00:00:05,000] Cerramos el punto.`); el valor
  devuelto lleva el resultado y la `Persistencia` con esa ruta y sin motivos. (antes: el recorrido solo existe repartido
  en `AppTranscriptor._procesar_transcripcion` (`src/ui.py:642`): fija los textos de estado con `_actualizar_estado`,
  fuerza `transcriptor.modelo`, llama a `transcribir` y a `persistir_transcripcion` con `ruta_transcripcion(...)`; el
  único test sin ventana, `tests/test_flujo.py`, lo reconstruye a mano llamando a `TranscriptorAudio.transcribir` y a
  `persistir_transcripcion` con una ruta escrita en el test, `reunion_transcripcion.txt`)
- [ ] [MODIFICA: sin spec] Dado el audio `reunion.m4a` en una carpeta donde no se puede escribir (o un historial
  `None`, o las dos cosas), cuando se llama a `transcribir_y_persistir`, entonces no lanza y devuelve el resultado
  transcrito, y su `persistencia` dice lo que no se guardó: con la carpeta no escribible, `ruta_exportada` es `None`,
  `motivo_exportacion` empieza por `reunion.m4a_transcripcion.txt:` y la entrada **sí** está en el historial; sin
  historial, `motivo_historial` es «Historial no disponible» y el archivo sí se exporta; con los dos fallos,
  `texto_sin_guardado(persistencia)` devuelve «El resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para
  conservarlo.». (antes: lo mismo, pero solo comprobable llamando a `persistir_transcripcion` directamente
  (`tests/test_persistencia.py`) o con el guion visual de la historia 01: la ventana es la única que une la
  transcripción, la ruta `reunion.m4a_transcripcion.<formato>` y el guardado)
- [ ] [MODIFICA: sin spec] Dado una cancelación activada antes de transcribir, o activada desde `on_segmento` tras el
  primer segmento, o un modelo de Whisper que lanza al transcribir, cuando se llama a `transcribir_y_persistir`,
  entonces sale `InterruptedError` (en los dos primeros casos) o la misma excepción del modelo (en el tercero), el
  historial temporal queda vacío y no existe `reunion.m4a_transcripcion.txt`; con la cancelación previa, además, Whisper
  no llega a llamarse. (antes: `_procesar_transcripcion` revisa `self.cancelar_flag.is_set()` después de cargar el
  modelo (`src/ui.py:651`) y después de transcribir (`:663`) y lanza `InterruptedError`, que su `except` convierte en
  «Transcripción cancelada»; cualquier otra excepción da «Error en la transcripción» y el diálogo con su texto; en
  ninguno de los dos casos se llama a `persistir_transcripcion`. Solo se puede comprobar con la ventana)

### Cómo se verifican

- **Con tests sin red, sin ventana y sin modelo real** (regla 3), en `tests/test_flujo_transcripcion.py` (ya existe
  desde B1; se añaden tests). Usan `modelo_whisper_falso` de `tests/conftest.py` y un fixture propio `historial`
  (`Historial(str(tmp_path / "historial.db"))`); las opciones se construyen con
  `OpcionesTranscripcion.desde_configuracion(config, str(audio), modelo="small", idioma="es", formato="txt",
  incluir_timestamps=True)` sobre `cargar_configuracion` de un YAML vacío en `tmp_path`, y `parametros` es
  `config["transcripcion"]`. El transcriptor, `TranscriptorAudio(modelo_nombre="small")` (o
  `transcriptor_para(None, …)`). No importan dobles privados de otros archivos de test.
  - `test_flujo_completo_guarda_en_historial_y_exporta` (criterio 1): es `tests/test_flujo.py` movido aquí, con las
    mismas aserciones sobre la entrada (`titulo`, `texto`, sin «Suscríbete», `segmentos` con sus tiempos, `idioma`,
    `duracion_segundos`, `modelo_whisper`) y sobre el contenido del archivo; la ruta ya no se escribe en el test: es
    `tmp_path / "reunion.m4a_transcripcion.txt"` y se comprueba que `persistencia.ruta_exportada` es esa. Se amplía con
    `on_fase` y `on_segmento` que anotan en listas: fases `== [FASE_CARGANDO_MODELO, FASE_TRANSCRIBIENDO]` (y
    `FASE_CARGANDO_MODELO == "cargando_modelo"`, `FASE_TRANSCRIBIENDO == "transcribiendo"`), y los textos de los
    segmentos recibidos `== ["Hola equipo.", "Cerramos el punto."]` (primer argumento de cada llamada, que es un
    `SegmentoTranscripcion`).
  - `test_exportacion_fallida_no_lanza_y_deja_la_entrada` (criterio 2): la carpeta no escribible se simula con un
    archivo regular `tmp_path / "bloqueo"` y el audio en `tmp_path / "bloqueo" / "reunion.m4a"` (no hace falta que
    exista: el doble no lee el audio), para no depender de permisos ni de `root`. Comprueba que devuelve sin lanzar,
    `resultado.texto_completo == "Hola equipo. Cerramos el punto."`, `ruta_exportada is None`,
    `motivo_exportacion.startswith("reunion.m4a_transcripcion.txt:")` y que la entrada `id_historial` existe en el
    historial.
  - `test_sin_historial_exporta_y_avisa` (criterio 2): `historial=None`; `motivo_historial == "Historial no
    disponible"`, `id_historial is None` y el archivo `reunion.m4a_transcripcion.txt` existe junto al audio.
  - `test_sin_historial_ni_exportacion_no_queda_en_ningun_sitio` (criterio 2): `historial=None` y el audio dentro de
    `bloqueo`; `texto_sin_guardado(persistencia)` devuelve exactamente la frase del criterio y el resultado sigue en el
    valor devuelto.
  - `test_cancelar_antes_de_transcribir_no_guarda` (criterio 3): un `threading.Event` ya activado como `cancelar`;
    `pytest.raises(InterruptedError)`, `doble.llamadas == []`, fases `== [FASE_CARGANDO_MODELO]`,
    `historial.listar() == []` y el archivo no existe.
  - `test_cancelar_durante_la_transcripcion_no_guarda` (criterio 3): `on_segmento` activa el `Event` en el primer
    segmento (`TranscriptorAudio.transcribir` corta tras él y devuelve lo transcrito); `pytest.raises(InterruptedError)`,
    `historial.listar() == []` y el archivo no existe.
  - `test_error_de_whisper_no_guarda` (criterio 3): el `transcribe` del doble se sustituye por uno que lanza, por
    ejemplo, `RuntimeError("audio ilegible")`; `pytest.raises(RuntimeError, match="audio ilegible")`,
    `historial.listar() == []` y el archivo no existe.
  - `tests/test_flujo.py` **se borra** en el mismo cambio (su único test pasa a
    `test_flujo_completo_guarda_en_historial_y_exporta`).
  - En rojo, los siete tests fallan con `ImportError` (no existen `FASE_*` ni `transcribir_y_persistir`). Los demás
    tests no cambian y siguen pasando (`./venv/bin/python -m pytest -q`: 291 − 1 + 7 = 297 en `d3037e0` más B2, más los
    que añada C1).
- **Verificación manual en la ventana real (la que pide el diseño):**
  - Cancelar durante «Cargando modelo <m>…» (con un modelo no cacheado) y durante «Transcribiendo…»: en los dos casos
    «Cancelando… (termina el segmento actual)», después «Transcripción cancelada», «▶ Transcribir» de nuevo, y nada
    nuevo en el historial ni junto al audio.
  - Una transcripción normal: el porcentaje avanza («Transcribiendo… N %»), el estado final es «Completado · guardado
    como reunion.m4a_transcripcion.<formato>» y la entrada aparece en el historial.
  - Un audio corrupto da «Error en la transcripción» y el diálogo de error con el texto de la excepción.
  - Una segunda transcripción con el mismo modelo lo reutiliza (no hay fase «Cargando modelo» larga).
  - El guion de la historia 01 (`docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md`): audio en una carpeta
    de solo lectura → la entrada está en el historial y el diálogo de advertencia nombra
    `reunion.m4a_transcripcion.txt` y el motivo, con la misma línea en Registro; «Abrir carpeta» deshabilitado;
    historial que falla al guardar (o no disponible) → el archivo se exporta y el diálogo da el motivo del historial;
    los dos fallos → el aviso «El resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para conservarlo.».
  - `grep -n "persistir_transcripcion\|cancelar_flag.is_set" src/ui.py` no devuelve ninguna línea dentro de
    `_procesar_transcripcion`.

## Plan

- Añadir al módulo del flujo las dos fases, el resultado con lo transcrito y lo guardado, y la función que, en el hilo
  de fondo, avisa de la fase de carga, fuerza la carga del modelo, mira la cancelación, avisa de la fase de
  transcripción, transcribe con la función de B1, vuelve a mirar la cancelación y guarda con la persistencia de hoy y
  la ruta de B1. Las excepciones del modelo salen tal cual; los fallos de guardado van en el valor devuelto.
- Reducir el hilo de la transcripción de la ventana a: elegir el transcriptor, guardarlo como el de la ventana, llamar
  a la función nueva con callbacks que traducen cada fase al texto de hoy («Cargando modelo <m>…»; «Transcribiendo…»
  con progreso 0) y llevan cada segmento a la vista por el hilo principal, y pasar el resultado a la pintura final.
  Los dos `except` y sus textos quedan iguales.
- La pintura final de la transcripción recibe el resultado combinado en vez de dos argumentos, y pinta lo mismo.
- Tests en el orden rojo → verde: los siete nuevos y el borrado de `tests/test_flujo.py`, luego el módulo, luego la
  ventana, y la suite completa en verde.

## Fuera de alcance

- Historias C1 (`src/flujo_documentos.py`: texto, ruta y fecha de los documentos), C2 (generación de fondo,
  `_restaurar_controles_ia`), D1 (`GestorDocumentos`, generación vigente y asistente) y D2 (`GestorDocumentos.recibir`,
  borrado de `persistir_documento_si_vigente`).
- La antigua historia E: que la CLI (`src/main.py`) use `flujo_transcripcion`. Sin historia; posible punto de «Salud
  del código» carril S con `/backlog`. En concreto, la CLI **no** pasa a usar `transcribir_y_persistir`: la CLI no guarda
  en el historial (`docs/specs/cli.md`, `src/EGM.md`).
- Cambiar lo que pasa al cancelar una transcripción (se sigue descartando lo transcrito), el nombre de los archivos
  junto al audio (punto #18), los textos de estado o de aviso, o `persistir_transcripcion` / `texto_sin_guardado`.
- `_iniciar_transcripcion`, `_agregar_segmento`, `_finalizar`, `_cancelar_transcripcion`, `_alternar_transcripcion`,
  `_tick_tiempo`, `_al_cerrar` y `_actualizar_estado`: no cambian (el diseño lo fija para los cuatro primeros y
  `_tick_tiempo`; los otros solo se llaman).
- Cambios en `src/transcriber.py`, `src/persistencia.py`, `src/utils.py`, `src/historial.py`, `src/main.py`,
  `tests/conftest.py`, `tests/test_persistencia.py`, `tests/test_importaciones.py` o cualquier otro test existente salvo
  el borrado de `tests/test_flujo.py`.
- La documentación (`docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md`, `AGENTS.md`, `.context/*`, incluidas las
  menciones a `tests/test_flujo.py` y las líneas «Origen» de `docs/specs/`): la actualiza `/cerrar`, no el `/pair`.

**Archivos que puede tocar el `/pair` (lista cerrada):** `src/flujo_transcripcion.py` (añadir `FASE_CARGANDO_MODELO`,
`FASE_TRANSCRIBIENDO`, `TranscripcionPersistida`, `transcribir_y_persistir`), `src/ui.py` (`_procesar_transcripcion`,
`_finalizar_ok` y, por consecuencia, la línea de imports de `src.flujo_transcripcion` y la de `src.persistencia`, de
la que sale `persistir_transcripcion` si queda sin uso), `tests/test_flujo_transcripcion.py` (añadir los siete tests y
el fixture `historial`), `tests/test_flujo.py` (borrar). Si hace falta tocar otro, se para y se vuelve al diseño.

### Convivencia con C1

La historia C1 (10) se está implementando ahora y también toca `src/ui.py` (métodos de generación de documentos, no
los de transcripción) y `tests/test_importaciones.py`. Los métodos de B2 no se solapan con los de C1, pero las dos
pueden tocar la cabecera de imports de `src/ui.py` (C1 añade el de `src.flujo_documentos`; B2 retoca el de
`src.flujo_transcripcion` y el de `src.persistencia`). Por eso **el `/pair` de B2 empieza después de que C1 tenga
commit**, sobre ese commit, y recalcula las líneas citadas aquí por el nombre de la función.

## Sugerencias

- Guardar `self._transcriptor = transcriptor` **justo después de `transcriptor_para`** y antes de llamar a
  `transcribir_y_persistir`. Hoy se guarda tras forzar la carga y antes de la primera comprobación de cancelación
  (`src/ui.py:649`), así que un transcriptor cargado se reutiliza aunque se cancele después. Si se guardara tras volver
  de `transcribir_y_persistir`, una cancelación o un error tras cargar el modelo lo perderían y la siguiente
  transcripción lo volvería a cargar. Guardarlo antes de cargar no rompe nada: desde la historia A, si la carga falla,
  `_modelo` queda en `None` y el siguiente acceso lo reintenta.
- En `on_fase`, un `if` sobre las dos constantes basta (no hace falta un dict de textos): `FASE_CARGANDO_MODELO` →
  `_actualizar_estado(f"Cargando modelo {opciones.modelo}…")`; `FASE_TRANSCRIBIENDO` →
  `_actualizar_estado("Transcribiendo…", 0)`. `_actualizar_estado` ya pasa por `_en_ui` (regla 9). Conservar el
  `self._log(f"Iniciando transcripción con modelo: …")` de hoy.
- Los tests del criterio 2 no deben repetir lo que ya prueba `tests/test_persistencia.py`
  (`test_transcripcion_exportacion_fallida_deja_entrada_en_historial`,
  `test_transcripcion_sin_historial_exporta_con_aviso_de_historial`,
  `test_transcripcion_sin_historial_ni_exportacion_no_guarda_en_ningun_sitio`,
  `test_aviso_sin_guardado_remite_a_guardar_como`): su valor es que el flujo no lanza, devuelve el resultado y deriva
  la ruta `reunion.m4a_transcripcion.txt` del audio. Basta con las aserciones de la lista de arriba, sin volver a mirar
  segmentos ni el texto del historial.
- En el test de cancelación previa, comprobar `doble.llamadas == []` deja claro que la cancelación se mira antes de
  llamar a Whisper, no solo antes de guardar.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **Las tres marcas son `[MODIFICA: sin spec]`.** Los tres comportamientos existen hoy dentro de
   `_procesar_transcripcion` y ninguna spec los describe como API sin interfaz. Las specs de usuario que tocan lo mismo
   (`transcripcion.md`: «Guardado de la transcripción antes de exportarla», «Abrir carpeta», «Aviso cuando el resultado
   no queda guardado en ningún sitio») **no cambian**: `/cerrar` no debe reemplazarlas, como mucho actualizar su
   «Origen». La cancelación de la transcripción no tiene spec. Las notas `(antes: …)` salen del código de `d3037e0`.
2. **El caso que duele** es que una transcripción cancelada (o fallida) deje una entrada en el historial o un archivo
   junto al audio, o que un fallo de guardado tire la transcripción (regla 6, A-01). Lo cubren los criterios 3 y 2.
   El camino no feliz está en los dos.
3. **`on_segmento` conserva la firma de hoy** `(segmento, duracion_total)`: `transcribir_y_persistir` lo pasa tal cual a
   `transcribir` y de ahí a `TranscriptorAudio.transcribir`, que lo llama así; la ventana sigue calculando el
   porcentaje con los dos argumentos. «Recibe los dos segmentos» del diseño se comprueba con el primer argumento.
4. **El modelo que falla** se simula sustituyendo `transcribe` en el doble que devuelve `modelo_whisper_falso`, sin
   tocar `tests/conftest.py` (el diseño lo deja fuera de todas las historias).
5. **«El historial queda vacío»** se comprueba con `Historial.listar() == []`.
6. **`cancelar=None`** (como pasarán otros llamadores) significa «sin cancelación»: no se comprueba nada.

### Discrepancias entre el diseño y el código actual

Ninguna que cambie la historia. Comprobado contra `d3037e0`: `src/flujo_transcripcion.py` (B1: `OpcionesTranscripcion`
`:15`, `ruta_transcripcion` `:44`, `transcriptor_para` `:49`, `transcribir` `:58`, que ya recibe `on_segmento` y
`cancelar`); en `src/ui.py`, `cancelar_flag` (`threading.Event`, `:140`), `_alternar_transcripcion` (`:593`),
`_iniciar_transcripcion` (`:604`, `cancelar_flag.clear()` en `:620`), `_procesar_transcripcion` (`:642`),
`_agregar_segmento` (`:682`), `_finalizar_ok` (`:693`, recibe `resultado, persistencia`), `_finalizar` (`:737`),
`_cancelar_transcripcion` (`:749`), `_actualizar_estado` (`:1307`, ya usa `_en_ui`), `_al_cerrar` (`:506`, activa
`cancelar_flag`); `persistir_transcripcion` (`src/persistencia.py:35`, con `historial=None` da «Historial no
disponible»; el motivo de exportación es `<nombre>: <causa>`) y `texto_sin_guardado` (`:107`);
`guardar_transcripcion` hace `mkdir(parents=True)`, por eso un archivo regular como «carpeta» falla con
`NotADirectoryError`; `TranscriptorAudio.transcribir` (`src/transcriber.py`) descarta «¡Suscríbete!», llama a
`on_segmento(segmento, info.duration)` y corta tras el segmento en que ve la cancelación. Ningún test usa
`_procesar_transcripcion` ni `_finalizar_ok`. Matices:

- **Líneas del diseño.** El diseño cita `src/ui.py:657` y `:682` para las comprobaciones de `cancelar_flag` (líneas de
  `c59d0ac`); tras B1 son `:651` y `:663`.
- **«Con las mismas aserciones».** El test de `tests/test_flujo.py` escribe la ruta a mano
  (`reunion_transcripcion.txt`, anterior al punto #18); en el test movido la ruta la decide el flujo
  (`reunion.m4a_transcripcion.txt`). Las aserciones sobre la entrada y el contenido son las mismas; la de la ruta
  cambia de literal.
- **Orden de «Cargando modelo».** Hoy el estado «Cargando modelo <m>…» se fija antes de `transcriptor_para`; con B2
  llega por `on_fase`, después de `transcriptor_para` (que no carga nada y es instantáneo). No se nota.
- **Dónde se guarda el transcriptor cacheado.** El diseño dice «la ventana llama a `transcriptor_para` … y guarda el
  devuelto» sin decir cuándo; ver la primera sugerencia.
- **Árbol de trabajo.** Al refinar esta historia la suite completa no se recoge entera (`tests/test_flujo_documentos.py`
  en rojo, C1 a medias); `tests/test_flujo.py`, `tests/test_flujo_transcripcion.py` y `tests/test_persistencia.py`
  pasan (40 tests).

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 304 tests. Code review: revisión del orquestador, listo para commit. Cuatro de los siete tests nuevos nacieron verdes (delegan en `persistir_transcripcion`, que ya no lanzaba); el orquestador comprobó con tres mutaciones que los tests las detectan (pasar el historial como `None`: 2 fallos; una ruta de exportación equivocada: 3; tragar el error de Whisper: 1) y restauró el código. Delta de spec: ninguno. Es un cambio interno; la app no cambia para el usuario, y `docs/specs/` no se toca. Las marcas `[MODIFICA: sin spec]` quedan como registro del comportamiento anterior.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | `transcribir_y_persistir` avisa de las fases, transcribe con los segmentos aceptados y guarda en el historial y junto al audio | test `test_flujo_completo_guarda_en_historial_y_exporta` (`tests/test_flujo_transcripcion.py:97`). Implementación: `src/flujo_transcripcion.py:91`, persistencia en `src/flujo_transcripcion.py:109-112`; la ventana la llama en `src/ui.py:662` | cumple (test y verificación manual) |
| 2 | [MODIFICA: sin spec] | Un fallo de guardado no lanza: el resultado sigue en el valor devuelto y `persistencia` dice qué no se guardó | tests `test_exportacion_fallida_no_lanza_y_deja_la_entrada` (`tests/test_flujo_transcripcion.py:146`), `test_sin_historial_exporta_y_avisa` (`:167`) y `test_sin_historial_ni_exportacion_no_queda_en_ningun_sitio` (`:183`). Implementación: `src/flujo_transcripcion.py:109-113` (los motivos los da `src/persistencia.py`) | cumple (tests y verificación manual) |
| 3 | [MODIFICA: sin spec] | La cancelación se respeta antes de transcribir y después de transcribir, sin guardar nada; un error de Whisper sale tal cual sin guardar | tests `test_cancelar_antes_de_transcribir_no_guarda` (`tests/test_flujo_transcripcion.py:198`), `test_cancelar_durante_la_transcripcion_no_guarda` (`:219`) y `test_error_de_whisper_no_guarda` (`:239`). Implementación: comprobaciones en `src/flujo_transcripcion.py:102-103` y `:107-108` | cumple (tests y verificación manual) |

Apoyo: `_procesar_transcripcion` ya no revisa `cancelar_flag` ni llama a `persistir_transcripcion` (`src/ui.py:645-674`); `_finalizar_ok` recibe un `TranscripcionPersistida` (`src/ui.py:688`); `tests/test_flujo.py` se borra y su único test pasa a `test_flujo_completo_guarda_en_historial_y_exporta`.

**Verificación (2026-11-22)**, hecha por el orquestador en la ventana real con Whisper simulado y sin red:

- Cancelar durante «Cargando modelo…» y durante «Transcribiendo…»: en los dos casos «Transcripción cancelada», sin resultado ni entrada en el historial, y «▶ Transcribir» de nuevo.
- El modelo se cargó una sola vez en toda la sesión, también después de cancelar.
- Una transcripción completa da «Completado · guardado como reunion.m4a_transcripcion.txt» y entra en el historial.
- Un audio corrupto da «Error en la transcripción» y el diálogo con el error.
- Con la carpeta de solo lectura, la transcripción entra en el historial y avisa «No se pudo exportar reunion.m4a_transcripcion.txt: Permission denied».
- Sin historial y con la carpeta de solo lectura, la transcripción sigue en pantalla con «Copiar» habilitado y el aviso de los dos fallos.

**Pendientes aceptados:** la CLI (`src/main.py`) todavía no usa `transcribir_y_persistir`: es la antigua historia E, sin historia abierta, y la CLI no guarda en el historial (`docs/specs/cli.md`, `src/EGM.md`).
