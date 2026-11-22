# Flujos fuera de la ventana

*   **Autor:** rmalanco
*   **Estado:** Propuesto, revisado (arquitectura: «aprobar con cambios»; implementation readiness: «listo con
    ajustes»); cambios de la revisión aplicados el 2026-11-22, ver «Revisión (2026-11-22)»
*   **Fecha:** 2026-11-22
*   **Origen:** `BACKLOG.md`, «Salud del código» #5 (carril L), hallazgo A-15 de `audit_report.md`, aceptado en
    `goldfish_review_report.md` (fila 5: «Desbloquea los tests de A-01 y A-02»).

Las líneas citadas son las del commit `c59d0ac`, que ya incluye el punto #18 (`utils.ruta_junto_al_audio` conserva
la extensión del audio: `reunion.m4a_transcripcion.txt`, `reunion.m4a_resumen.md`, `reunion.m4a_minuta.md`). Si las
líneas se mueven, manda el nombre de la función.

--------------------------------------------------------------------------------

## Resumen

Hoy los dos caminos principales de la app, «transcribir y guardar» y «generar un resumen o una minuta y guardarlos»,
solo existen repartidos entre métodos de la clase de la ventana (`AppTranscriptor` en `src/ui.py`). Lo único que ya
salió de ella es el guardado (`src/persistencia.py`, historia 01). Por eso las reglas que más importan (guardar antes
de exportar, no guardar una generación cancelada, abrir el login tras un 401, reutilizar el asistente) solo se
comprueban con un guion visual que conduce la ventana real.

Este diseño saca esos dos caminos a dos módulos sin interfaz, `src/flujo_transcripcion.py` y
`src/flujo_documentos.py`, que la ventana llama y cuyo resultado solo pinta. El punto de decisión único de la
generación (historia 04) se mueve con su lógica a un objeto sin Tk, `GestorDocumentos`, que comprueba que se le llama
desde el hilo principal. Además, `faster_whisper` deja de cargarse al importar cualquier módulo del paquete: se
importa la primera vez que se carga un modelo de Whisper.

El trabajo se parte en siete historias pequeñas (A, B1, B2, C1, C2, D1, D2), cada una con tres criterios, sus tests y
una lista cerrada de archivos.

## El problema

1.  **La lógica que importa no tiene tests automáticos.** `00-actual.md` («Riesgos y límites actuales») lo dice: ningún
    test instancia `AppTranscriptor`; el punto de decisión `_recibir_documento_ia`, la cancelación y el cierre se
    verificaron a mano (historia 04, «Verificación visual»). Las piezas extraídas sí tienen tests
    (`tests/test_persistencia.py`, `tests/test_flujo.py`), pero la composición que hace la ventana no.
2.  **La composición vive en callbacks de Tk.** En concreto:
    *   `AppTranscriptor._procesar_transcripcion` (`src/ui.py:650`) carga el modelo (`_obtener_transcriptor`,
        `:641`), traduce la configuración a los argumentos de `TranscriptorAudio.transcribir` (`:666-680`), revisa la
        cancelación dos veces (`:657`, `:682`) y llama a `persistir_transcripcion`. La CLI (`src/main.py:179-198`)
        repite la misma traducción de la configuración.
    *   `AppTranscriptor._generar_documento_ia` (`:844`) decide si hay que crear un `AsistenteIA` (`:849`), arma el
        texto que se envía (los segmentos unidos con `\n`) y la ruta del documento junto al audio (`:868-870`), y
        guarda el estado de los botones en `_GeneracionIA` (`:86`).
    *   `AppTranscriptor._procesar_documento_ia` (`:893`) elige entre `generar_resumen` y `generar_minuta`, y calcula
        la fecha de la minuta llamando a `_fecha_archivo` (`:1075`) **desde el hilo de fondo** (`:900`): lee
        `self.archivo_actual` y `self._fecha_historial` fuera del hilo principal.
    *   `AppTranscriptor._recibir_documento_ia` (`:914`) es el único punto de decisión: compara la generación con
        `self._generacion` (`:918`), guarda con `persistir_documento_si_vigente(False, …)` (`:926`), descarta el
        asistente tras `ErrorSinSesionCopilot` (`:933`) y abre el login. `_cancelar_documento_ia` (`:939`, `:948`) y
        `_al_cambiar_modelo_ia` (`:1047`, `:1052`) también descartan el asistente. Esas reglas de reutilización del
        asistente (y con él, de la caché de notas de la historia 07) no tienen ningún test.
    *   `_finalizar_documento_ia` (`:964`) muestra el modelo leyendo `self._asistente.modelo_usado` (`:984`) en vez
        del modelo que ya recibe la generación.
3.  **`faster_whisper` se carga aunque no se transcriba.** `src/__init__.py:3` importa `src.transcriber`, que importa
    `faster_whisper` en su cabecera (`src/transcriber.py:9`). Python ejecuta `src/__init__.py` antes que cualquier
    `src.<módulo>`, así que **todo** import del paquete paga la carga. Lo pagan `--copilot-logout`, `--copilot-login`,
    `--copilot-modelos`, `--listar-modelos`, la apertura de la ventana (aunque no se transcriba) y cada sesión de
    tests. Sin `src/__init__.py`, siguen cargándolo `src.historial` (importa las dataclasses de `src/transcriber.py`,
    `src/historial.py:13`), `src.main` (`src/main.py:10`) y `src.transcriber`.

### Mediciones

Hechas el 2026-11-22 con `./venv/bin/python -X importtime` y con un guion de la carpeta temporal que sustituye
`src/__init__.py` por un paquete vacío, sin tocar el repositorio. Caché de disco caliente; varían ±30 %.

| Qué se importa | ¿Carga `faster_whisper` hoy? | ¿Y sin `src/__init__.py`? | Tiempo |
|---|---|---|---|
| `src` (el paquete) | Sí | — | 388 ms acumulados; `faster_whisper` 287 ms (`av` 110 ms, `ctranslate2` 45 ms) |
| `src.configuracion`, `src.utils`, `src.registro`, `src.persistencia` | Sí | No | `src.persistencia` sin el paquete: 102-118 ms (de ellos, `ffmpeg` 48-85 ms) |
| `src.copilot`, `src.asistente_ia` | Sí | No | `src.copilot`: 454-517 ms hoy, 190-261 ms sin el paquete |
| `src.historial` | Sí | **Sí** (por `src/transcriber.py:9`) | 400 ms sin el paquete |
| `src.main` | Sí | **Sí** (importa `TranscriptorAudio`, `src/main.py:10`) | 435 ms sin el paquete |
| `src.ui`, `src.ui_historial` | Sí | Sí (por `historial` y `transcriber`) | `customtkinter` añade unos 40 ms |
| `python -m src.main --help` (proceso entero) | Sí | — | 319-517 ms; `python -c pass`: 18-33 ms |

## Objetivos

1.  **Dos flujos sin interfaz, con tests.** «Transcribir y persistir» y «generar y persistir» viven en módulos que no
    importan `tkinter` ni `customtkinter`, y tienen tests que ejercen el flujo completo con un historial temporal, un
    Whisper simulado (`modelo_whisper_falso`) y un asistente simulado, sin ventana ni red.
2.  **El punto de decisión de la generación se prueba sin ventana.** Una generación cancelada que termina después, con
    documento, con error o con un 401, no guarda nada, no pide login y no descarta el asistente de la generación
    siguiente; y eso lo demuestra un test, no solo el guion visual.
3.  **La ventana solo pinta.** Tras el cambio, los métodos de `AppTranscriptor` que hoy orquestan solo leen widgets,
    llaman al flujo y pintan lo que devuelve. No deciden si se guarda, ni cuándo se recrea el asistente.
4.  **`faster_whisper` solo se carga al cargar un modelo.** Importar cualquier módulo de `src` (incluidos `src.ui` y
    `src.main`) no carga `faster_whisper`; lo carga la propiedad `TranscriptorAudio.modelo` la primera vez. Lo
    comprueba un test en un proceso aparte.
5.  **Ningún comportamiento de `docs/specs/` cambia.** Los textos, los avisos, el orden historial → archivo, la
    cancelación en menos de 1 s y las notas de la aplicación quedan igual.

## Fuera de alcance

*   Que la CLI guarde en el historial o genere documentos: `docs/specs/cli.md` y `src/EGM.md` («La CLI no usa
    `AsistenteIA` ni `Historial`») lo excluyen y nadie lo ha pedido.
*   Que la CLI use `flujo_transcripcion.transcribir` (antes «historia E»): **opcional y sin historia**. No tiene paso
    rojo (no cambia ningún comportamiento observable), así que no encaja en el flujo TDD de `/story` y `/pair`. Si se
    quiere quitar la traducción duplicada de la configuración en `src/main.py:186-198`, se añade como punto de «Salud
    del código» con `/backlog` (carril S) cuando la historia B1 esté cerrada.
*   Cambiar lo que pasa al cancelar una transcripción (se sigue descartando lo transcrito) o abortar la petición HTTP
    abierta de una generación cancelada. Son riesgos conocidos de `00-actual.md`, sin punto en el backlog.
*   `PanelHistorial` llamando a métodos privados de la ventana (`src/ui_historial.py:103`, `:236`, `:254`). A-15 lo
    cita en su escenario, pero el punto #5 del backlog no lo incluye.
*   Cambiar el nombre de los archivos junto al audio: el punto #18 ya lo fijó en `utils.ruta_junto_al_audio`; este
    diseño solo lo llama.
*   La revisión de fidelidad contra el original (#23), el panel de configuración (Backlog #5) y el soporte de
    `/responses`.
*   Cargar `ffmpeg` de forma perezosa (`src/utils.py:5`, 48-85 ms). Ver «Mejoras futuras».
*   Mover las dataclasses de resultado fuera de `src/transcriber.py` (ver «Alternativas»).

## Decisiones abiertas (para el orquestador)

Cada una lleva la opción que este diseño toma. Si el orquestador elige otra, cambian las historias que se indican.

1.  **¿Dos módulos o uno?** Se toman dos (`flujo_transcripcion.py` y `flujo_documentos.py`). Con uno, quien solo
    transcribe importaría `httpx` y `asistente_ia`. Afecta a B1, B2, C1, C2, D1 y D2.
2.  **¿`src/__init__.py` sin reexportaciones o con reexportación perezosa?** Se quitan `TranscriptorAudio`,
    `validar_archivo` y `obtener_info_archivo` y queda solo `__version__`: ningún archivo del repositorio usa
    `from src import TranscriptorAudio` (búsqueda del 2026-11-22) y la app no se publica como biblioteca. La otra opción
    es un `__getattr__` de módulo (PEP 562) que las importe al pedirlas. Afecta a A.
3.  **¿Se borra `persistencia.persistir_documento_si_vigente`?** Se borra en D2: tras el cambio nadie la llama (hoy la
    ventana solo la llama con `False`, `src/ui.py:926`), y la decisión de no guardar una generación cancelada pasa a
    probarse en `GestorDocumentos.recibir`. Sus dos tests (`tests/test_persistencia.py:111` y `:121`) se reescriben
    contra el gestor, no se pierden.
4.  **`OpcionesTranscripcion` pequeña.** Se acepta la sugerencia del revisor: la dataclass solo lleva lo que eligen la
    ventana o la CLI, y los parámetros de decodificación (`beam_size`, `best_of`, `temperature`,
    `condition_on_previous_text`, `compression_ratio_threshold`, `logprob_threshold`, `no_speech_threshold`) se pasan
    a `transcribir` como el dict `configuracion["transcripcion"]`. Motivo: ni la ventana ni la CLI cambian nunca esos
    siete valores; copiarlos a la dataclass duplica nombres y valores por defecto que ya viven en un solo sitio
    (`configuracion.py`), con riesgo de que diverjan. Afecta a B1.
5.  **El fallo por falta de `faster_whisper` se mueve.** Hoy, sin `faster_whisper` instalado, o si su import falla con
    un `ImportError` nativo de `av` o `ctranslate2` (biblioteca compartida que falta o no casa), ni la ventana ni la
    CLI arrancan. Después, la ventana abre, la CLI atiende las órdenes de sesión, y el error aparece al cargar el
    modelo: en la ventana como el diálogo de error genérico de `_procesar_transcripcion` (el texto de la excepción,
    por ejemplo «No module named 'faster_whisper'»), y en la CLI como «Error durante la transcripción» con código 1.
    Como el import va dentro de la carga del modelo y `_modelo` queda en `None` si falla, el siguiente intento vuelve a
    probar. Este diseño lo acepta sin mensaje propio; un mensaje en español sería un requisito nuevo. Afecta a A.

## Recorridos críticos (CUJ)

### CUJ 1: transcribir desde la ventana, con la carpeta del audio sin permiso de escritura

*   **Dado** `reunion.m4a` en una carpeta donde no se puede escribir, formato `txt` y un historial disponible.
*   **Cuando** la persona pulsa «Transcribir» y termina la transcripción.
*   **Entonces** se ve lo mismo que hoy (`docs/specs/transcripcion.md`, «Guardado de la transcripción antes de
    exportarla»): la entrada está en el historial y el diálogo de advertencia nombra `reunion.m4a_transcripcion.txt` y
    el motivo. Lo que cambia es dónde se decide: `flujo_transcripcion.transcribir_y_persistir` devuelve el resultado y
    la `Persistencia`, y `_finalizar_ok` solo pinta. Un test lo cubre sin ventana (B2).

### CUJ 2: cancelar una regeneración y que la petición abandonada termine con un 401

*   **Dado** una entrada del historial de `reunion.m4a` con minuta, y una regeneración en curso.
*   **Cuando** la persona pulsa «■ Cancelar», vuelve a generar y, segundos después, Copilot responde 401 a la petición
    abandonada.
*   **Entonces** la ventana volvió al instante a la minuta anterior, el historial y `reunion.m4a_minuta.md` no cambian
    por la abandonada, no se abre el login y la generación nueva conserva su asistente (`docs/specs/documentos-ia.md`,
    «Cancelar la generación»). `GestorDocumentos.recibir` devuelve «descartada» para la abandonada; un test lo cubre
    con un asistente simulado y un historial temporal (D2).

### CUJ 3: abrir la ventana o cerrar la sesión de Copilot sin cargar Whisper

*   **Dado** el entorno virtual del proyecto.
*   **Cuando** se ejecuta `python -m src.main --copilot-logout`, o se abre la ventana y se genera una minuta de una
    entrada del historial sin transcribir nada.
*   **Entonces** `faster_whisper` no aparece en `sys.modules`; solo se carga al pulsar «Transcribir» (o al transcribir
    desde la CLI), dentro del hilo de la transcripción (A).

## Plan técnico

### Estructura

```text
                 hilo principal (Tk)                              hilo de fondo
 ┌──────────────────────────────────────────┐
 │ AppTranscriptor (src/ui.py)              │
 │  lee widgets → OpcionesTranscripcion ────┼──► flujo_transcripcion.transcribir_y_persistir
 │  pinta con _en_ui ◄──────────────────────┼─── on_fase / on_segmento (los marshala la ventana)
 │  _finalizar_ok(TranscripcionPersistida) ◄┼─── vía _en_ui
 │                                          │
 │  GestorDocumentos (src/flujo_documentos) │
 │   .iniciar() → Generacion ───────────────┼──► flujo_documentos.procesar_generacion
 │   .cancelar()                            │       └─ AsistenteIA.generar_resumen / generar_minuta
 │   .recibir()  ◄── único punto de decisión┼─── entregar(...) vía _en_ui (una sola vez)
 │      └─ persistencia.persistir_documento │       on_progreso: desde el hilo de la generación
 │  _vista_previa_ia (estado de botones)    │       y desde los hilos «ia-parte»
 └──────────────────────────────────────────┘
 flujo_transcripcion → transcriber (faster_whisper solo en .modelo), persistencia, utils, historial (tipo)
 flujo_documentos    → asistente_ia (ErrorSinSesionCopilot, tipo AsistenteIA), persistencia, utils, historial (tipo)
 Ninguno importa tkinter ni customtkinter.
```

### 1. Carga perezosa de `faster_whisper` (historia A)

*   `src/transcriber.py`:
    *   Se añade `from __future__ import annotations` en la cabecera, para que `Optional[WhisperModel]` y
        `-> WhisperModel` no se evalúen (el README declara Python 3.10 o superior, aunque solo se ha verificado 3.14).
        `WhisperModel` se importa para los tipos dentro de `if TYPE_CHECKING:`.
    *   El `from faster_whisper import WhisperModel` sale de la cabecera (`:9`) y va **dentro** del
        `with latido(f"cargando/descargando el modelo …")` que ya existe en `TranscriptorAudio.modelo`, justo antes de
        construir el `WhisperModel`. Si el import o la construcción fallan, la excepción sale tal cual, `self._modelo`
        sigue en `None` y el siguiente acceso a `.modelo` vuelve a intentarlo.
    *   Nada más cambia: ni firmas ni mensajes del log.
*   `src/__init__.py`: queda con el docstring y `__version__ = "0.1.0"`. Ningún import (decisión abierta 2).
*   `src/historial.py` no cambia: sigue importando `ResultadoTranscripcion` y `SegmentoTranscripcion` de
    `src.transcriber`, que deja de ser pesado.
*   `src/main.py` no cambia: su `from src.transcriber import TranscriptorAudio` ya no arrastra Whisper, y
    `TranscriptorAudio` sigue en su espacio de nombres (lo parchea `tests/test_cli.py:281`).
*   `src/ui.py` no cambia en A: sigue importando `TranscriptorAudio`, que necesita para la anotación de
    `self._transcriptor` (`:140`), y el import ya es barato.
*   Los dobles de los tests siguen valiendo: `modelo_whisper_falso` (`tests/conftest.py:41`) sustituye la propiedad
    `modelo` entera, así que el import perezoso nunca se ejecuta en esos tests. `tests/test_basico.py:53` sigue
    importando `faster_whisper` a propósito, para comparar la firma de `WhisperModel.transcribe`.

### 2. «Transcribir y persistir»: `src/flujo_transcripcion.py` (historias B1 y B2)

Contrato (pseudocódigo de firmas, no código final):

```text
FASE_CARGANDO_MODELO = "cargando_modelo"
FASE_TRANSCRIBIENDO  = "transcribiendo"

@dataclass(frozen=True)
OpcionesTranscripcion:                       # solo lo que eligen la ventana o la CLI (decisión abierta 4)
    archivo: str
    modelo: str
    dispositivo: str
    compute_type: str
    idioma: str                              # código; "auto" = detectar
    formato: str
    incluir_timestamps: bool
    palabra_por_palabra: bool
    task: str = "transcribe"                 # el único campo con valor por defecto, al final

    @classmethod
    desde_configuracion(configuracion: dict, archivo: str, **cambios) -> OpcionesTranscripcion
        # base = OpcionesTranscripcion(
        #     archivo=archivo,
        #     modelo=configuracion["modelo"]["nombre"],
        #     dispositivo=configuracion["modelo"]["dispositivo"],
        #     compute_type=configuracion["modelo"]["compute_type"],
        #     idioma=configuracion["transcripcion"]["idioma"],
        #     formato=configuracion["salida"]["formato"],
        #     incluir_timestamps=configuracion["salida"]["incluir_timestamps"],
        #     palabra_por_palabra=configuracion["salida"]["palabra_por_palabra"])
        # return dataclasses.replace(base, **cambios)
        # Las claves de `cambios` son los nombres de los campos (compute_type, incluir_timestamps…);
        # una clave desconocida (p. ej. compute o timestamps, los nombres que usa hoy la ventana) lanza TypeError.

@dataclass
TranscripcionPersistida:
    resultado: ResultadoTranscripcion
    persistencia: Persistencia

ruta_transcripcion(archivo: str, formato: str) -> str
    # = utils.ruta_junto_al_audio(archivo, f"_transcripcion.{formato}")
    # (hoy AppTranscriptor._generar_ruta_salida, src/ui.py:1238-1240); "reunion.m4a", "txt" → "…/reunion.m4a_transcripcion.txt"

transcriptor_para(actual: Optional[TranscriptorAudio], modelo, dispositivo, compute_type) -> TranscriptorAudio
    # hoy _obtener_transcriptor (src/ui.py:641) sin el `self` y sin forzar la carga: devuelve `actual` si
    # coinciden (modelo_nombre, dispositivo, compute_type); si no, crea uno nuevo.

transcribir(transcriptor, opciones, parametros: dict, on_segmento=None, cancelar=None) -> ResultadoTranscripcion
    # parametros = configuracion["transcripcion"]; llama a transcriptor.transcribir(
    #     opciones.archivo, idioma=opciones.idioma, task=opciones.task,
    #     beam_size=…, best_of=…, temperature=…, condition_on_previous_text=…,
    #     compression_ratio_threshold=…, logprob_threshold=…, no_speech_threshold=…   (de `parametros`),
    #     word_timestamps=opciones.palabra_por_palabra, on_segmento=on_segmento, cancelar=cancelar)
    # (lo que hoy repiten src/ui.py:666-680 y src/main.py:186-198)

transcribir_y_persistir(transcriptor, opciones, parametros, historial: Optional[Historial], *,
                        on_fase=None, on_segmento=None, cancelar=None) -> TranscripcionPersistida
    1. on_fase(FASE_CARGANDO_MODELO); fuerza transcriptor.modelo (aquí se importa faster_whisper la 1.ª vez)
    2. si cancelar está activa → InterruptedError
    3. on_fase(FASE_TRANSCRIBIENDO); resultado = transcribir(...)
    4. si cancelar está activa → InterruptedError         (se descarta lo transcrito, como hoy)
    5. persistencia = persistir_transcripcion(historial, opciones.archivo, resultado, opciones.modelo,
                                              ruta_transcripcion(opciones.archivo, opciones.formato),
                                              opciones.formato, opciones.incluir_timestamps)
    6. devuelve TranscripcionPersistida(resultado, persistencia)
    # Cualquier otra excepción (Whisper, audio ilegible, falta faster_whisper) sale tal cual y no se guarda nada.
    # Los fallos de guardado no lanzan: van en `persistencia` (regla 6, A-01).
```

Reglas del contrato:

*   **Hilos.** `transcribir` y `transcribir_y_persistir` se llaman desde un hilo de fondo; `on_fase` y `on_segmento`
    se ejecutan en ese mismo hilo. El módulo no conoce Tk: es la ventana quien pasa callbacks que ya llaman a `_en_ui`
    (regla 9). Lo dice el docstring del módulo, y `tests/test_importaciones.py` comprueba que importarlo no carga
    `tkinter`.
*   **Cancelación.** El mismo `threading.Event` de hoy (`AppTranscriptor.cancelar_flag`), revisado en los mismos dos
    puntos que `_procesar_transcripcion` (`src/ui.py:657` y `:682`) más los que ya revisa
    `TranscriptorAudio.transcribir`. Se señala con `InterruptedError`, igual que `AsistenteIA`.
*   **Historial.** Se recibe como parámetro (puede ser `None`); el orden historial → archivo lo sigue garantizando
    `persistir_transcripcion`, sin cambios.
*   **El transcriptor cacheado** sigue siendo de la ventana (`self._transcriptor`): la ventana llama a
    `transcriptor_para` en el hilo de fondo, como hoy, y guarda el devuelto.

Cómo queda la ventana:

*   **B1.** `_iniciar_transcripcion` construye `OpcionesTranscripcion.desde_configuracion(self.configuracion,
    self.archivo_actual, modelo=…, idioma=self._codigo_idioma(), dispositivo=…, compute_type=…, formato=…,
    incluir_timestamps=…)` con los valores de los widgets, en el hilo principal como hoy, y lo pasa al hilo.
    `_procesar_transcripcion` usa `transcriptor_para` (y fuerza `.modelo` él mismo, como hoy), `transcribir` con
    `self.configuracion["transcripcion"]`, y sigue llamando él a `persistir_transcripcion` con
    `ruta_transcripcion(...)`. Se borran `_obtener_transcriptor` y `_generar_ruta_salida`; `_guardar_resultado`
    («Guardar como…», `:1249`) propone `Path(ruta_transcripcion(self.archivo_actual, self.var_formato.get())).name`.
*   **B2.** `_procesar_transcripcion` se reduce a: `transcriptor_para`, `transcribir_y_persistir` con `on_fase` que
    traduce cada fase al texto de hoy («Cargando modelo <m>…», «Transcribiendo…», con el progreso 0 en la segunda)
    mediante `_actualizar_estado`, y `on_segmento` que llama a `_en_ui(self._agregar_segmento, …)`; después
    `_en_ui(self._finalizar_ok, …)`. Los `except InterruptedError` y `except Exception` y sus textos quedan iguales.
    `_finalizar_ok` recibe la `TranscripcionPersistida`.
*   `_agregar_segmento`, `_finalizar`, `_cancelar_transcripcion` y `_tick_tiempo` no cambian.

### 3. «Generar y persistir»: `src/flujo_documentos.py` (historias C1, C2, D1 y D2)

Hoy el guardado de un documento ocurre en el hilo principal **a propósito**: así «cancelar» y «guardar» nunca se pisan
(historia 04, «Plan»; `00-actual.md`, «Modelo de concurrencia»). Por eso este flujo no puede ser una sola función de
fondo que genere y guarde: se parte en una función de fondo que solo genera y un gestor sin Tk que decide y guarda en
el hilo principal.

```text
SUFIJOS_DOCUMENTO = {"resumen": "_resumen.md", "minuta": "_minuta.md"}   # hoy en ui.DOCUMENTOS_IA[…]["sufijo"]

# ---- C1: funciones puras, se llaman en el hilo principal
texto_para_ia(resultado: ResultadoTranscripcion) -> str
    # "\n".join(seg.texto for seg in resultado.segmentos)  (hoy src/ui.py:866; no usa texto_completo)
ruta_documento(archivo: str, clave: str) -> Optional[str]
    # utils.ruta_junto_al_audio(archivo, SUFIJOS_DOCUMENTO[clave]) si Path(archivo).exists(); si no, None
    # (hoy src/ui.py:868-870); "reunion.m4a", "minuta" → "…/reunion.m4a_minuta.md"
fecha_de_la_reunion(archivo: str, fecha_historial: Optional[str]) -> str
    # hoy AppTranscriptor._fecha_archivo (src/ui.py:1075): "<d> de <mes> de <año> (fecha del archivo)" con el mtime
    # del audio si existe; si no, "… (fecha de transcripción)" con fecha_historial[:10]; si no, "No especificada".
    # Captura (OSError, ValueError) — audio que desaparece entre exists y getmtime, creado_en mal formado —
    # y devuelve "No especificada".

# ---- C2: la generación de fondo
@dataclass(eq=False)        # se compara por identidad
Generacion:
    clave: str                         # "resumen" | "minuta"
    asistente: AsistenteIA
    texto: str
    fecha: Optional[str]               # solo minuta; calculada en el hilo principal
    ruta_salida: Optional[str]         # None si el audio ya no existe → solo historial
    id_historial: Optional[int]        # el vigente al pulsar el botón
    cancelar: threading.Event = field(default_factory=threading.Event)   # propia de cada generación
    # Sin campo para la vista: el estado de los botones lo guarda la ventana (self._vista_previa_ia).

@dataclass
DocumentoGenerado:
    contenido: str
    modelo_usado: str                  # generacion.asistente.modelo_usado, leído DESPUÉS de generar
    segundos: float                    # time.monotonic() medido dentro de generar_documento

generar_documento(generacion, on_progreso=None) -> DocumentoGenerado
    # resumen → asistente.generar_resumen(texto, on_progreso=…, cancelar=generacion.cancelar)
    # minuta  → asistente.generar_minuta(texto, on_progreso=…, cancelar=generacion.cancelar, fecha=generacion.fecha)
    # No toca historial, archivos ni widgets; las excepciones salen tal cual (incluida InterruptedError).

procesar_generacion(generacion, on_progreso, entregar) -> None        # destino del hilo de fondo
    # try:    documento, error = generar_documento(generacion, on_progreso), None
    # except Exception as e: documento, error = None, e
    # entregar(generacion, documento, error)      # UNA sola llamada, fuera del try
    # Docstring: `on_progreso` se llama desde el hilo que ejecuta procesar_generacion y también desde los hilos
    # «ia-parte» de AsistenteIA._notas_por_bloque (notas en paralelo); `entregar` se llama una vez, desde el hilo
    # que ejecuta procesar_generacion. Ninguno de los dos puede tocar widgets: la ventana los envuelve en _en_ui.
    # Si `entregar` lanza, la excepción sale de procesar_generacion (la registra threading.excepthook) y no se reintenta.

# ---- D1 y D2: el gestor (solo hilo principal)
@dataclass
Recepcion:                                                           # D2
    estado: str                        # "descartada" | "lista" | "error" | "sin_sesion"
    generacion: Generacion
    documento: Optional[DocumentoGenerado] = None
    persistencia: Optional[Persistencia] = None
    mensaje: Optional[str] = None      # str(error) or type(error).__name__, como hoy (src/ui.py:931)

GestorDocumentos(historial: Optional[Historial], crear_asistente: Callable[[], AsistenteIA])
    # __init__ guarda self._hilo = threading.get_ident(). Cada método público empieza con
    # _comprobar_hilo(): si threading.get_ident() != self._hilo → RuntimeError("GestorDocumentos solo se usa
    # desde el hilo principal"). Se crea en AppTranscriptor.__init__ DESPUÉS de self.historial (src/ui.py:153).
    vigente: Optional[Generacion]                         # D1; sustituye a AppTranscriptor._generacion
    asistente() -> AsistenteIA                            # D1; reutiliza o crea con crear_asistente();
                                                          #     deja pasar ErrorSinSesionCopilot / ErrorAsistenteIA
    olvidar_asistente()                                   # D1; al cambiar de modelo (hoy _al_cambiar_modelo_ia)
    iniciar(clave, resultado, archivo, id_historial, fecha_historial) -> Generacion          # D1
        # si vigente no es None → ValueError (la ventana ya lo impide antes)
        # calcula TODO antes de tocar estado: asistente(), texto_para_ia, ruta_documento y, si es minuta,
        # fecha_de_la_reunion; solo entonces fija vigente. Si asistente() lanza, vigente sigue en None.
    cancelar() -> Optional[Generacion]                                                       # D1
        # activa generacion.cancelar, vigente = None, olvida el asistente; devuelve la cancelada (o None)
    terminar(generacion) -> bool                                                             # D1
        # si generacion is vigente: vigente = None y True; si no: False (no toca nada)
    recibir(generacion, documento, error) -> Recepcion    # D2; ÚNICO PUNTO DE DECISIÓN
        si not terminar(generacion) → Recepcion("descartada"): no guarda, no toca el asistente, no pide login
        si error is None → persistencia = persistir_documento(historial, generacion.id_historial, generacion.clave,
                                                              documento.contenido, documento.modelo_usado,
                                                              generacion.ruta_salida)
                           → Recepcion("lista", documento=…, persistencia=…)
        si isinstance(error, ErrorSinSesionCopilot) → olvidar_asistente() → Recepcion("sin_sesion", mensaje=…)
        si otro error (incluida InterruptedError de una vigente) → Recepcion("error", mensaje=…)
```

Por qué así:

*   **El punto de decisión sigue siendo único y sigue en el hilo principal, y ahora se comprueba.** `recibir` es la
    misma lógica que `_recibir_documento_ia` hoy (`src/ui.py:918-937`), sin widgets. La ventana sigue llamándola a
    través de `_en_ui`, y el gestor lanza `RuntimeError` si alguien lo llama desde otro hilo. Así `cancelar` y
    `recibir` no pueden intercalarse, y la garantía de la historia 04 («o se guarda y se muestra terminado, o se
    descarta y se muestra cancelado») no cambia.
*   **Las reglas del asistente se vuelven comprobables.** Hoy se reparten en cuatro sitios de la ventana (`:849`,
    `:933`, `:948`, `:1052`). En el gestor son tres, con test: `cancelar`, `recibir` con `sin_sesion` y
    `olvidar_asistente`. Con eso queda cubierta también la duración de las notas conservadas (historia 07: «se
    pierden al cancelar, al cambiar de modelo, tras tener que iniciar sesión de nuevo»).
*   **`crear_asistente` se inyecta.** La ventana pasa un método propio, `_crear_asistente`, que crea el `AsistenteIA`
    con `config["ia"]` y `_modelo_ia_configurado()` (lo de `src/ui.py:850-857`); los tests pasan una función que
    devuelve un asistente simulado y no necesitan token ni `httpx`.
*   **`iniciar` no deja estado a medias.** Todo lo que puede fallar (crear el asistente) ocurre antes de fijar
    `vigente`, y `fecha_de_la_reunion` no lanza.
*   **`terminar` existe para partir D en dos.** En D1 la ventana ya usa el gestor para el estado (`vigente`, asistente)
    pero sigue guardando ella en `_recibir_documento_ia`; en D2 `recibir` absorbe ese guardado y la ventana deja de
    llamar a `terminar` directamente. `terminar` sigue siendo público (lo usa `recibir` y tiene su test).
*   **La fecha se calcula en el hilo principal** desde C1: `_generar_documento_ia` llama a `fecha_de_la_reunion` y
    pasa el resultado al hilo, en vez de que el hilo de fondo lea atributos de la ventana (`src/ui.py:900`). Se calcula
    milisegundos antes que hoy, con el mismo resultado.
*   **El modelo que se muestra sale del documento** desde C2: `_finalizar_documento_ia` usa
    `documento.modelo_usado`, el mismo valor que se guarda en el historial, en vez de `self._asistente.modelo_usado`
    (`src/ui.py:984`).

Cómo queda la ventana:

*   **C1.** `_generar_documento_ia` usa `texto_para_ia`, `ruta_documento` y, para la minuta,
    `fecha_de_la_reunion(self.archivo_actual, self._fecha_historial)`, todo en el hilo principal; la fecha se pasa al
    hilo de fondo como argumento. Se borra `_fecha_archivo`. `DOCUMENTOS_IA[…]["sufijo"]` toma su valor de
    `SUFIJOS_DOCUMENTO`, así que «Guardar como…» (`_guardar_documento_ia`, `:1103`) y el guardado automático proponen
    el mismo nombre que hoy.
*   **C2.** Desaparece `_GeneracionIA`: la ventana crea directamente una `flujo_documentos.Generacion` y la guarda en
    `self._generacion`. El estado previo de la vista va a `self._vista_previa_ia` (un dataclass privado de `ui.py`,
    `_VistaPreviaIA(contenido, texto_boton, estado_transcribir)`, o un dict con esas tres claves), que se fija al
    generar y se pone a `None` al recibir y al cancelar. Un solo método, `_restaurar_controles_ia(clave)`, devuelve el
    texto del botón de esa pestaña, habilita «Generar» de las dos pestañas y el selector de modelo, devuelve
    «Transcribir» a su estado anterior y limpia `_vista_previa_ia`; lo usan `_recibir_documento_ia` y
    `_cancelar_documento_ia`. El hilo de fondo pasa a ser `procesar_generacion` con
    `on_progreso=lambda m: self._en_ui(self._progreso_documento_ia, generacion, m)` y
    `entregar=lambda *a: self._en_ui(self._recibir_documento_ia, *a)`. `_recibir_documento_ia` pasa a tener tres
    argumentos (generación, documento, error). `_finalizar_documento_ia` recibe el `DocumentoGenerado` y deja de leer
    `self._asistente.modelo_usado`. Se borra `_procesar_documento_ia`.
*   **D1.** `__init__` crea `self._documentos = GestorDocumentos(self.historial, self._crear_asistente)` después de
    `self.historial`; desaparecen `self._asistente` y `self._generacion`. `_generando_ia()` pasa a
    `self._documentos.vigente is not None`. `_alternar_documento_ia`, `_generar_documento_ia` (con `iniciar` dentro
    del mismo `try` de hoy: `ErrorSinSesionCopilot` → login; `ErrorAsistenteIA` → diálogo), `_progreso_documento_ia`,
    `_cancelar_documento_ia` (con `cancelar()`), `_al_cambiar_modelo_ia` (con `olvidar_asistente()`) y `_al_cerrar`
    pasan por el gestor. `_recibir_documento_ia` usa `terminar` para la identidad y `olvidar_asistente()` ante
    `ErrorSinSesionCopilot`, y sigue llamando a `persistir_documento_si_vigente(False, …)`.
*   **D2.** `_recibir_documento_ia` llama a `self._documentos.recibir(...)` y pinta según `estado`: «descartada» solo
    anota en Registro («Resultado de <clave> descartado: la generación se canceló»); «lista» llama a
    `_finalizar_documento_ia`; «error» y «sin_sesion» muestran el error, y «sin_sesion» además abre el login. Los
    textos no cambian. Se quita el import de `persistir_documento_si_vigente`.

### 4. Qué no cambia

*   `historial.py`, `asistente_ia.py`, `copilot.py`, `configuracion.py`, `utils.py`, `ui_copilot.py`, `ui_historial.py`
    y `main.py`; de `persistencia.py`, todo salvo borrar `persistir_documento_si_vigente` en D2.
*   El modelo de concurrencia de `00-actual.md`: un hilo de transcripción que guarda en su propio hilo; un hilo por
    generación que no guarda; la decisión y el guardado del documento en el hilo principal; `_en_ui` como única
    entrada a los widgets.

## Historias

Cada historia cabe en tres criterios de `/story` y en un `/pair`. Cada una deja `./venv/bin/python -m pytest -q` en
verde, sin red (regla 3), y tiene su lista **cerrada** de archivos: si necesita tocar otro, se para y se vuelve a este
diseño. La documentación (`docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md`, `AGENTS.md`, `.context/*`, incluido
`.context/conventions.md:17` sobre los imports relativos de `src/__init__.py`, y las líneas «Origen» de
`docs/specs/`) la actualiza `/cerrar`, no el `/pair`, y por eso no figura en las listas.

| Orden | Historia | Carril | Depende de |
|---|---|---|---|
| A | Cargar `faster_whisper` solo al cargar un modelo | M | — |
| B1 | Opciones, transcriptor y ruta de la transcripción fuera de la ventana | M | A |
| B2 | «Transcribir y persistir» fuera de la ventana | M | B1 |
| C1 | Texto, ruta y fecha de los documentos fuera de la ventana | M | A |
| C2 | La generación de fondo fuera de la ventana | M | C1 |
| D1 | El gestor de documentos lleva la generación vigente y el asistente | M | C2 |
| D2 | El gestor decide y guarda lo que llega de cada generación | M | D1 |

B y C son independientes entre sí; el orden propuesto es A, B1, B2, C1, C2, D1, D2. D2 es la de más riesgo (cambia
el único punto de decisión) y va la última.

### Dobles de test que usan los archivos nuevos

*   `rutas_aisladas` es un fixture local de `tests/test_copilot.py`, `tests/test_asistente_ia.py` (y su variante en
    `tests/test_cli.py`), y `_Stream` y `_Respuesta` son privados de `tests/test_asistente_ia.py`: los archivos nuevos
    **no** los importan.
*   `tests/test_flujo_transcripcion.py` usa `modelo_whisper_falso` de `tests/conftest.py` y un fixture propio
    `historial` (`Historial(str(tmp_path / "historial.db"))`).
*   `tests/test_flujo_documentos.py` define sus propios dobles: `AsistenteFalso` (con `generar_resumen`,
    `generar_minuta`, `modelo_usado`, que anota lo que recibe y devuelve o lanza lo que se le diga) y su propio fixture
    `historial`. Para el caso con `AsistenteIA` real (D2, criterio 3) define en el mismo archivo un fixture autouse
    que aísla el token (`copilot.RUTA_TOKEN`, `copilot.RUTA_AUTH_OPENCODE`, sin `COPILOT_GITHUB_TOKEN`), un
    `_StreamFalso` propio y parchea `asistente_ia.httpx.stream`, `asistente_ia.httpx.get` y `asistente_ia.httpx.post`
    (estos dos, prohibidos).
*   `tests/test_importaciones.py` no usa fixtures salvo `monkeypatch` y `tmp_path`.

### Historia A — Cargar `faster_whisper` solo al cargar un modelo

**Criterios:**

1.  *Dado* el entorno del proyecto, *cuando* se importan en un proceso nuevo `src`, `src.registro`,
    `src.configuracion`, `src.utils`, `src.transcriber`, `src.historial`, `src.persistencia`, `src.copilot`,
    `src.asistente_ia`, `src.main`, `src.ui_copilot`, `src.ui_historial` y `src.ui`, *entonces* `faster_whisper` no
    está en `sys.modules` después de ninguno de ellos.
2.  *Dado* un `TranscriptorAudio("small", "cpu", "int8", cache_dir=<tmp>)`, *cuando* se lee `.modelo` dos veces,
    *entonces* `faster_whisper` se importa en ese momento y se construye un solo `WhisperModel` con `"small"`,
    `device="cpu"`, `compute_type="int8"` y `download_root=<tmp>`.
3.  *Dado* que importar `faster_whisper` falla la primera vez (por ejemplo con `ImportError`), *cuando* se lee
    `.modelo`, *entonces* sale ese `ImportError`, y al leerlo otra vez, con el módulo ya disponible, se construye el
    modelo.

**Tests:**

*   `tests/test_importaciones.py::test_ningun_modulo_carga_faster_whisper_al_importarse` (criterio 1): **un solo**
    subproceso, `subprocess.run([sys.executable, "-c", GUION], cwd=RAIZ, capture_output=True, text=True)`, con
    `RAIZ = Path(__file__).resolve().parent.parent` y sin `shell` (la ruta del repo tiene espacios). `GUION` recorre
    una lista `MODULOS` en orden, hace `importlib.import_module` de cada uno y, tras cada import, anota el módulo si
    `"faster_whisper" in sys.modules`; también anota, para los módulos de una lista `SIN_TK`, si `"tkinter"` o
    `"customtkinter"` están en `sys.modules`. Imprime lo anotado y sale con código 1 si hay algo. El test exige
    `returncode == 0` y muestra `stdout` y `stderr` si falla. Los módulos de `SIN_TK` van en `MODULOS` antes de
    cualquier `src.ui*`. En A, `SIN_TK` está vacía.
*   `tests/test_importaciones.py::test_modelo_importa_faster_whisper_al_cargarse` (criterio 2), en el mismo proceso:
    `monkeypatch.setattr("src.transcriber.WhisperModel", prohibido, raising=False)` (donde `prohibido` lanza
    `AssertionError`), para que ni en el paso rojo se construya ni se descargue el modelo real;
    `monkeypatch.setitem(sys.modules, "faster_whisper", <types.ModuleType con un WhisperModel falso que anota sus
    argumentos>)`. En rojo falla porque la cabecera ya enlazó el `WhisperModel` de verdad y el parche lo sustituye por
    `prohibido`; en verde usa el módulo falso.
*   `tests/test_importaciones.py::test_si_falla_el_import_se_reintenta_al_volver_a_pedir_el_modelo` (criterio 3): el
    mismo parche de `prohibido`; primero `monkeypatch.setitem(sys.modules, "faster_whisper", None)` (así `import`
    lanza `ImportError`), `pytest.raises(ImportError)` al leer `.modelo`; después se pone el módulo falso y `.modelo`
    funciona.

**Archivos (lista cerrada):** `src/transcriber.py`, `src/__init__.py`, `tests/test_importaciones.py` (crear). Ningún
test existente cambia.

**Verificación en la ventana real:** una transcripción real con el modelo `tiny` por CLI
(`./venv/bin/python -m src.main <audio corto> -m tiny`) y otra por la ventana, para comprobar que el import perezoso
funciona en un hilo de fondo y que la fase «Cargando modelo tiny…» se ve; y el recuento
`./venv/bin/python -X importtime -c "import src.main" 2>&1 | grep -c faster_whisper`, que debe dar `0` (y
`python -m src.main --help` debe bajar de 319-517 ms a unos 200 ms en este equipo). `grep -n "from .transcriber\|from
.utils" src/__init__.py` y `grep -n "^from faster_whisper" src/transcriber.py` no devuelven nada.

### Historia B1 — Opciones, transcriptor y ruta de la transcripción fuera de la ventana

**Criterios:**

1.  *Dado* un `config` de `cargar_configuracion` con `transcripcion.idioma: auto`, `beam_size: 3`,
    `logprob_threshold: -0.8` y `salida.palabra_por_palabra: true`, *cuando* se transcribe con
    `OpcionesTranscripcion.desde_configuracion(config, "reunion.m4a", modelo="small")` y `transcribir(…,
    config["transcripcion"])`, *entonces* Whisper recibe `language=None`, `task="transcribe"`, `beam_size=3`,
    `log_prob_threshold=-0.8`, `word_timestamps=True` y el resto de parámetros de `config["transcripcion"]`; y
    `desde_configuracion(config, "reunion.m4a", timestamps=False)` lanza `TypeError`.
2.  *Dado* un transcriptor creado para `small`, `cpu`, `int8`, *cuando* se pide `transcriptor_para` con los mismos
    tres valores, *entonces* se devuelve la misma instancia; con cualquiera distinto, una nueva con los valores
    pedidos, sin cargar el modelo.
3.  *Dado* el audio `/carpeta/reunion.m4a`, *cuando* se pide `ruta_transcripcion(…, "srt")`, *entonces* es
    `/carpeta/reunion.m4a_transcripcion.srt`.

**Tests:** `tests/test_flujo_transcripcion.py` — `test_opciones_y_parametros_llegan_a_whisper` (criterio 1, con
`modelo_whisper_falso` y `doble.llamadas[0][1]`; comprueba la clave real `log_prob_threshold`, no `logprob_threshold`,
y `language is None`), `test_desde_configuracion_rechaza_un_campo_desconocido` (criterio 1),
`test_transcriptor_para_reutiliza_o_recrea` (criterio 2, con `TranscriptorAudio.modelo` parcheado para fallar si se
lee), `test_ruta_transcripcion_conserva_la_extension` (criterio 3).

**Archivos (lista cerrada):** `src/flujo_transcripcion.py` (crear: `OpcionesTranscripcion`, `ruta_transcripcion`,
`transcriptor_para`, `transcribir`), `src/ui.py` (`_iniciar_transcripcion`, `_procesar_transcripcion`,
`_guardar_resultado`; borrar `_obtener_transcriptor` y `_generar_ruta_salida`), `tests/test_flujo_transcripcion.py`
(crear), `tests/test_importaciones.py` (añadir `src.flujo_transcripcion` a `MODULOS` y a `SIN_TK`). Ningún test
existente cambia.

**Verificación en la ventana real:** transcribir un audio corto con `tiny`; el porcentaje avanza; transcribir otro
con el mismo modelo no vuelve a mostrar «Cargando modelo» largo (se reutiliza); cambiar a `base` sí lo carga;
«Guardar como…» propone `reunion.m4a_transcripcion.<formato>`. `grep -n "_obtener_transcriptor\|_generar_ruta_salida"
src/ui.py` no devuelve nada.

### Historia B2 — «Transcribir y persistir» fuera de la ventana

**Criterios:**

1.  *Dado* `reunion.m4a` con los segmentos «Hola equipo.», «¡Suscríbete!» y «Cerramos el punto.», formato `txt` y un
    historial temporal, *cuando* se llama a `transcribir_y_persistir`, *entonces* `on_fase` recibe
    `cargando_modelo` y después `transcribiendo`, `on_segmento` recibe los dos segmentos aceptados en orden, la entrada
    del historial tiene el texto sin la alucinación y `reunion.m4a_transcripcion.txt` contiene las dos líneas con sus
    marcas.
2.  *Dado* una carpeta del audio donde no se puede escribir (o un historial `None`, o los dos), *cuando* se llama a
    `transcribir_y_persistir`, *entonces* no lanza, devuelve el resultado, y `persistencia` dice lo que no se guardó:
    `motivo_exportacion` empieza por `reunion.m4a_transcripcion.txt:`, `motivo_historial` es «Historial no
    disponible», y con los dos fallos `texto_sin_guardado` devuelve «El resultado no quedó guardado en ningún sitio.
    Usa «Guardar como…» para conservarlo.».
3.  *Dado* una cancelación activada antes de transcribir, o desde `on_segmento`, o un modelo que falla al transcribir,
    *cuando* se llama a `transcribir_y_persistir`, *entonces* sale `InterruptedError` (o la excepción del modelo), el
    historial queda vacío y no hay archivo.

**Tests:** `tests/test_flujo_transcripcion.py` — `test_flujo_completo_guarda_en_historial_y_exporta` (criterio 1; es
el test de `tests/test_flujo.py` movido aquí y ampliado con fases y segmentos), `test_exportacion_fallida_no_lanza_y_
deja_la_entrada`, `test_sin_historial_exporta_y_avisa`, `test_sin_historial_ni_exportacion_no_queda_en_ningun_sitio`
(criterio 2; la carpeta no escribible se simula con una ruta de audio dentro de un archivo regular, para no depender
de permisos ni de `root`), `test_cancelar_antes_de_transcribir_no_guarda`, `test_cancelar_durante_la_transcripcion_
no_guarda`, `test_error_de_whisper_no_guarda` (criterio 3).

**Archivos (lista cerrada):** `src/flujo_transcripcion.py` (añadir `FASE_*`, `TranscripcionPersistida`,
`transcribir_y_persistir`), `src/ui.py` (`_procesar_transcripcion`, `_finalizar_ok`),
`tests/test_flujo_transcripcion.py`. Test existente que cambia: **`tests/test_flujo.py` se borra** (su único test pasa
a `test_flujo_completo_guarda_en_historial_y_exporta`, con las mismas aserciones).

**Verificación en la ventana real:** cancelar durante «Cargando modelo…» (modelo no cacheado) y durante
«Transcribiendo…»: en los dos casos «Transcripción cancelada» y nada nuevo en el historial ni junto al audio; el
porcentaje avanza; un audio corrupto da el diálogo de error; una segunda transcripción reutiliza el modelo; y el guion
de la historia 01 (carpeta no escribible: diálogo con `reunion.m4a_transcripcion.txt` y el motivo; «Abrir carpeta»
deshabilitado; historial que falla). `grep -n "persistir_transcripcion\|cancelar_flag.is_set" src/ui.py` no devuelve
ninguna línea dentro de `_procesar_transcripcion`.

### Historia C1 — Texto, ruta y fecha de los documentos fuera de la ventana

**Criterios:**

1.  *Dado* un resultado con los segmentos «Hola equipo.» y «Cerramos el punto.» y un `texto_completo` distinto,
    *cuando* se pide `texto_para_ia`, *entonces* es «Hola equipo.\nCerramos el punto.».
2.  *Dado* `reunion.m4a` existente, *cuando* se pide `ruta_documento(…, "minuta")` y `ruta_documento(…, "resumen")`,
    *entonces* son `<carpeta>/reunion.m4a_minuta.md` y `<carpeta>/reunion.m4a_resumen.md`; si el audio no existe, las
    dos son `None`.
3.  *Dado* un audio con fecha de modificación 5 de marzo de 2026 (fijada con `os.utime`), *cuando* se pide
    `fecha_de_la_reunion`, *entonces* es «5 de marzo de 2026 (fecha del archivo)»; sin audio y con `creado_en`
    «2026-04-07T10:00:00», «7 de abril de 2026 (fecha de transcripción)»; sin audio y sin fecha, o con `creado_en`
    mal formado («ayer»), «No especificada».

**Tests:** `tests/test_flujo_documentos.py` — `test_texto_para_ia_une_segmentos_con_salto_de_linea`,
`test_ruta_documento_conserva_la_extension_y_es_none_sin_audio`, `test_fecha_de_la_reunion_desde_archivo_historial_o_
ninguna` (parametrizado con los cuatro casos).

**Archivos (lista cerrada):** `src/flujo_documentos.py` (crear: `SUFIJOS_DOCUMENTO`, `texto_para_ia`,
`ruta_documento`, `fecha_de_la_reunion`), `src/ui.py` (`_generar_documento_ia` calcula texto, ruta y fecha en el hilo
principal y pasa la fecha al hilo; `_procesar_documento_ia` recibe la fecha; `DOCUMENTOS_IA` toma el sufijo de
`SUFIJOS_DOCUMENTO`; borrar `_fecha_archivo`), `tests/test_flujo_documentos.py` (crear), `tests/test_importaciones.py`
(añadir `src.flujo_documentos` a `MODULOS` y a `SIN_TK`). Ningún test existente cambia.

**Verificación en la ventana real:** generar una minuta (con un asistente simulado) de un audio existente y de una
entrada del historial cuyo audio ya no existe: la línea `**Fecha:**` dice «(fecha del archivo)» y «(fecha de
transcripción)», y el archivo se llama `reunion.m4a_minuta.md` (solo en el primer caso). `grep -n "_fecha_archivo"
src/ui.py` no devuelve nada.

### Historia C2 — La generación de fondo fuera de la ventana

**Criterios:**

1.  *Dado* una `Generacion` de minuta con fecha «5 de marzo de 2026 (fecha del archivo)» y un asistente simulado que
    devuelve «# Minuta» y cuyo `modelo_usado` pasa a «auto → gpt-5.4» al generar, *cuando* se llama a
    `generar_documento`, *entonces* el asistente recibe el texto, esa fecha, `on_progreso` y la señal de esa
    generación, y el `DocumentoGenerado` lleva «# Minuta», «auto → gpt-5.4» y `segundos >= 0`; con un resumen, el
    asistente no recibe fecha.
2.  *Dado* un asistente que devuelve un documento, o que lanza `ErrorAsistenteIA`, `InterruptedError` o `ValueError`,
    *cuando* se llama a `procesar_generacion`, *entonces* `entregar` se llama exactamente una vez, con `(generacion,
    documento, None)` o `(generacion, None, error)`; y si `entregar` lanza, la excepción sale de
    `procesar_generacion` y `entregar` se ha llamado una sola vez.
3.  *Dado* dos generaciones creadas una tras otra, *cuando* se activa la señal de cancelación de la primera,
    *entonces* la de la segunda sigue sin activar.

**Tests:** `tests/test_flujo_documentos.py` — `test_generar_documento_minuta_pasa_fecha_senal_y_progreso`,
`test_generar_documento_resumen_sin_fecha` (criterio 1), `test_procesar_generacion_entrega_una_vez` (parametrizado con
documento y los tres errores), `test_procesar_generacion_entregar_que_lanza_no_reentrega` (criterio 2),
`test_cada_generacion_tiene_su_propia_senal` (criterio 3).

**Archivos (lista cerrada):** `src/flujo_documentos.py` (añadir `Generacion`, `DocumentoGenerado`,
`generar_documento`, `procesar_generacion`), `src/ui.py` (borrar `_GeneracionIA` y `_procesar_documento_ia`; añadir
`_vista_previa_ia` y `_restaurar_controles_ia`; cambiar `_generar_documento_ia`, `_progreso_documento_ia`,
`_recibir_documento_ia` (tres argumentos), `_cancelar_documento_ia` y `_finalizar_documento_ia` (recibe el
`DocumentoGenerado`)), `tests/test_flujo_documentos.py`. Ningún test existente cambia.

**Verificación en la ventana real:** con un asistente simulado, generar resumen y minuta: la línea de estado dice
«Listo en N s con <modelo> · …» con el modelo del documento; la fecha de la minuta es la del archivo; cancelar una vez
deja «Generación cancelada» y los botones como estaban; regenerar y cancelar conserva el documento anterior.
`grep -n "_GeneracionIA\|_procesar_documento_ia\|_asistente.modelo_usado" src/ui.py` no devuelve nada.

### Historia D1 — El gestor de documentos lleva la generación vigente y el asistente

**Criterios:**

1.  *Dado* un gestor con un `crear_asistente` que cuenta sus llamadas, *cuando* se inicia una generación, se termina
    (`terminar`) y se inicia otra, *entonces* las dos usan el mismo asistente (una llamada); y tras `cancelar` o tras `olvidar_asistente`,
    la siguiente generación usa uno nuevo (la recreación tras «sin sesión» se prueba en D2).
2.  *Dado* un gestor, *cuando* `crear_asistente` lanza `ErrorSinSesionCopilot` o `ErrorModeloIA` al iniciar, o se
    inicia con otra generación vigente, *entonces* el error (o `ValueError`) sale y `vigente` no cambia (`None` en el
    primer caso, la anterior en el segundo).
3.  *Dado* una generación vigente, *cuando* se llama a `cancelar`, *entonces* devuelve esa generación con su señal
    activada y `vigente` queda en `None`; y *cuando* se llama a cualquier método público del gestor desde otro hilo,
    *entonces* lanza `RuntimeError`.

**Tests:** `tests/test_flujo_documentos.py` — `test_gestor_reutiliza_el_asistente_entre_generaciones`,
`test_gestor_recrea_el_asistente_tras_cancelar_u_olvidar` (criterio 1), `test_iniciar_sin_asistente_no_deja_vigente`
(parametrizado con los dos errores), `test_iniciar_con_otra_vigente_lanza_value_error` (criterio 2),
`test_cancelar_devuelve_la_cancelada_y_libera`, `test_gestor_desde_otro_hilo_lanza_runtime_error` (lanza un
`threading.Thread` que llama a `cancelar`, `iniciar`, `terminar`, `asistente` y `olvidar_asistente` y recoge las
excepciones) (criterio 3).

**Archivos (lista cerrada):** `src/flujo_documentos.py` (añadir `GestorDocumentos` con `vigente`, `asistente`,
`olvidar_asistente`, `iniciar`, `cancelar`, `terminar` y la comprobación de hilo), `src/ui.py` (`__init__`,
`_crear_asistente`, `_generando_ia`, `_al_cerrar`, `_alternar_documento_ia`, `_generar_documento_ia`,
`_progreso_documento_ia`, `_recibir_documento_ia`, `_cancelar_documento_ia`, `_al_cambiar_modelo_ia`),
`tests/test_flujo_documentos.py`. Ningún test existente cambia.

**Verificación en la ventana real:** el guion de la historia 04, criterios 1 y 3 (cancelar en menos de 1 s, generar,
cargar otro archivo y abrir el historial al momento; cerrar la ventana con una generación en curso con «No» y con
«Sí»), y cambiar de modelo entre dos generaciones. `grep -n "self\._asistente\b\|self\._generacion\b" src/ui.py` no
devuelve nada.

### Historia D2 — El gestor decide y guarda lo que llega de cada generación

**Criterios:**

1.  *Dado* `reunion.m4a` en el historial (sin título editado) y una generación de minuta vigente, *cuando* llega su
    documento a `recibir`, *entonces* devuelve «lista», la minuta queda en la entrada con el modelo usado y el título
    de la minuta, se escribe `reunion.m4a_minuta.md` y `vigente` queda en `None`; si la entrada se eliminó mientras
    tanto, `motivo_historial` es «La entrada ya no está en el historial» y el archivo se escribe igual; si el audio ya
    no existe, solo se guarda en el historial.
2.  *Dado* la secuencia `iniciar(G1)`, `cancelar()`, `iniciar(G2)` (que crea el asistente B), *cuando* llega a
    `recibir` el resultado de G1 con un documento, con `ErrorAsistenteIA` o con `ErrorSinSesionCopilot`, *entonces*
    devuelve «descartada», el historial y `reunion.m4a_minuta.md` no cambian (contenido y `mtime`), `vigente` sigue
    siendo G2, `asistente()` sigue siendo B y `crear_asistente` se llamó 2 veces.
3.  *Dado* una transcripción que se procesa en varias partes con un `AsistenteIA` real (`httpx` simulado) cuya parte 2
    falla, *cuando* llega ese error a `recibir`, *entonces* devuelve «error» con el mensaje de la parte, y al generar
    después el otro documento solo se piden las notas de las partes que no terminaron y la redacción; tras `cancelar`
    una generación, la siguiente vuelve a pedir todas las partes; y con `ErrorSinSesionCopilot` de la vigente
    devuelve «sin_sesion» y la siguiente generación crea otro asistente.

**Tests:** `tests/test_flujo_documentos.py` — `test_recibir_vigente_guarda_y_devuelve_lista`,
`test_recibir_entrada_eliminada_exporta_y_avisa`, `test_recibir_sin_audio_solo_historial` (criterio 1);
`test_recibir_cancelada_descarta_sin_guardar_ni_olvidar` (parametrizado con documento, `ErrorAsistenteIA` y
`ErrorSinSesionCopilot`, con la secuencia exacta del criterio 2; sustituye a los dos tests de
`persistir_documento_si_vigente`) (criterio 2); `test_fallo_de_una_parte_reutiliza_notas_y_cancelar_las_pierde` (con
`AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=300, revision_fidelidad=False,
peticiones_paralelas=1)` creado por `crear_asistente`, `_StreamFalso` que responde 403 a la petición cuyo cuerpo
contiene el texto de la parte 2 mientras un interruptor esté activo y, si no, un documento con todas las secciones de
`SECCIONES_RESUMEN` y `SECCIONES_MINUTA`; cuenta las peticiones de notas por el texto de cada parte) y
`test_recibir_sin_sesion_vigente_olvida_el_asistente` (criterio 3).

**Archivos (lista cerrada):** `src/flujo_documentos.py` (añadir `Recepcion` y `GestorDocumentos.recibir`),
`src/ui.py` (`_recibir_documento_ia` pinta según `Recepcion`; quitar el import de `persistir_documento_si_vigente`),
`src/persistencia.py` (borrar `persistir_documento_si_vigente`, `:92-104`), `tests/test_flujo_documentos.py`. Test
existente que cambia: **`tests/test_persistencia.py`**: borrar
`test_documento_de_generacion_cancelada_no_se_guarda_ni_se_exporta` (`:111`) y
`test_documento_de_generacion_vigente_se_guarda_y_se_exporta` (`:121`) y quitar `persistir_documento_si_vigente` del
import (`:8`).

**Verificación en la ventana real:** los guiones completos de la historia 04 (los cinco pasos, incluido el 401
abandonado que no abre el login) y de la historia 07 (fallo de una parte con el texto «falló la parte N de M…» y nueva
generación que solo pide las que faltan). `grep -n "persistir_documento_si_vigente" src/ tests/` no devuelve nada.

### Tests y archivos que no cambian en ninguna historia

`tests/test_cli.py`, `tests/test_ui.py`, `tests/test_basico.py`, `tests/conftest.py`, `tests/test_historial.py`,
`tests/test_asistente_ia.py`, `tests/test_copilot.py`, `tests/test_configuracion.py`, `tests/test_utils.py`,
`tests/test_registro.py`; `src/main.py` (conserva `TranscriptorAudio` en su espacio de nombres), `src/historial.py`,
`src/asistente_ia.py`, `src/copilot.py`, `src/configuracion.py`, `src/utils.py`, `src/registro.py`,
`src/ui_copilot.py`, `src/ui_historial.py`, `config/settings.yaml`, `requirements*.txt`. Sin dependencias nuevas.

## Alternativas consideradas

### A. Una sola función de fondo «generar y persistir» que mira la cancelación antes de guardar

*   **A favor:** la firma más simple; la ventana solo recibiría el resultado final.
*   **En contra:** entre «mirar la señal» y «guardar» la persona puede pulsar «■ Cancelar»; el documento quedaría
    guardado en el historial y junto al audio con la pestaña diciendo «Generación cancelada». Es exactamente lo que la
    historia 04 cerró moviendo la decisión al hilo principal.
*   **Motivo del rechazo:** rechazada por el autor: reabre la carrera entre cancelar y guardar que la historia 04
    eliminó.

### B. La función de fondo guarda, protegida con un cerrojo compartido con «cancelar»

*   **A favor:** guardar no bloquearía el hilo principal (SQLite y un archivo `.md`, milisegundos).
*   **En contra:** cambia el modelo de concurrencia documentado; el cerrojo se tomaría desde el hilo de Tk y desde el
    de fondo, y «cancelar» tendría que esperar a un guardado en curso, lo que rompe «la ventana vuelve al instante».
*   **Motivo del rechazo:** rechazada por el autor: más complejidad y riesgo de bloqueo a cambio de una mejora no
    medible.

### C. Un único objeto `Orquestador` para los dos flujos, en un solo módulo

*   **A favor:** un solo sitio y un solo objeto que guarda el historial, el transcriptor y el asistente.
*   **En contra:** la transcripción no tiene estado que coordinar más allá del modelo cacheado; meterla en un objeto
    con estado complica sus tests. Un módulo único haría que importar el flujo de transcripción cargue `httpx` y
    `asistente_ia`.
*   **Motivo del rechazo:** rechazada por el autor: une dos cosas con ciclos de vida distintos. Ver decisión abierta 1.

### D. Mover `ResultadoTranscripcion` y `SegmentoTranscripcion` a un módulo propio (`src/resultado.py`)

*   **A favor:** `historial.py` y `persistencia.py` dejarían de depender del módulo de Whisper; es lo que sugiere la
    dirección de A-15.
*   **En contra:** con el import perezoso, `src/transcriber.py` ya no es pesado (solo `registro` y `utils`); el cambio
    tocaría `historial.py`, `persistencia.py`, `utils.py` y varios tests sin efecto medible.
*   **Motivo del rechazo:** rechazada por el autor: el import perezoso consigue lo mismo con un solo archivo. Se puede
    retomar si `transcriber.py` vuelve a importar algo pesado en su cabecera; `tests/test_importaciones.py` lo
    detectaría.

### E. Dejar `src/__init__.py` como está y solo hacer perezoso el import de `transcriber.py`

*   **A favor:** un archivo menos tocado.
*   **En contra:** el paquete seguiría importando `transcriber` y `utils` (y `ffmpeg`, 48-85 ms) en cada
    `import src.<módulo>`, y cualquier import pesado que alguien añada a esos módulos volvería a cargarse en todas
    partes.
*   **Motivo del rechazo:** rechazada por el autor: el `__init__.py` del paquete es la puerta de todos los imports y
    debe quedar vacío. Ver decisión abierta 2 para la variante perezosa.

### F. Importar `faster_whisper` al arrancar la ventana en un hilo de fondo («precarga»)

*   **A favor:** la primera transcripción no pagaría los ~0,3 s del import.
*   **En contra:** es un requisito nuevo; la carga del modelo (segundos o minutos) ya domina sobre ese import.
*   **Motivo del rechazo:** rechazada por el autor: no lo pide ninguna spec y el ahorro es despreciable frente a cargar
    el modelo.

### G. Guardar el estado previo de la vista dentro de la `Generacion` (campo opaco)

*   **A favor:** una sola referencia por generación; nada que limpiar aparte.
*   **En contra:** mete datos de Tk en un tipo del módulo sin interfaz, y en C2 dejaba dos objetos con identidad
    (`_GeneracionIA` y `Generacion`) durante un paso intermedio.
*   **Motivo del rechazo:** rechazada en la revisión: la ventana guarda su propio `_vista_previa_ia`, que se limpia en
    `_restaurar_controles_ia`.

--------------------------------------------------------------------------------

## Requisitos no funcionales

*   **Rendimiento.** Abrir la ventana y las órdenes de sesión de la CLI dejan de pagar `faster_whisper` (285-308 ms
    acumulados en este equipo). La primera transcripción de cada proceso lo paga dentro de su hilo de fondo, bajo la
    fase «Cargando modelo…».
*   **Privacidad.** Sin cambios: ningún flujo nuevo usa la red; el texto sigue saliendo solo por `AsistenteIA` y solo
    hacia modelos autorizados (reglas 1, 2 y 7).
*   **Hilos (regla 9).** Los módulos nuevos no importan `tkinter` (lo comprueba `tests/test_importaciones.py`). Los
    callbacks de los flujos se ejecutan en hilos de fondo y la ventana los envuelve en `_en_ui`. `GestorDocumentos`
    lanza `RuntimeError` si se le llama fuera del hilo en que se creó.
*   **Despliegue y vuelta atrás.** Cada historia es un commit independiente con la suite en verde; volver atrás es
    revertir ese commit. No hay migraciones ni cambios de configuración.

--------------------------------------------------------------------------------

### Recursos

*   `audit_report.md` (A-15), `goldfish_review_report.md` (fila 5).
*   `docs/disenos/00-actual.md` («Modelo de concurrencia», «Riesgos y límites actuales»), `EGM.md`, `src/EGM.md`.
*   `docs/specs/transcripcion.md`, `docs/specs/documentos-ia.md`, `docs/specs/cli.md`.
*   `docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md`, `…-02-dependencias-y-tests-del-flujo.md`,
    `…-04-cancelar-generacion.md`, `…-07-documento-incompleto.md`.

### Mejoras futuras

*   **`ffmpeg` perezoso.** `src/utils.py:5` importa `ffmpeg-python` (48-85 ms) aunque solo lo usa
    `obtener_info_archivo`. Mismo patrón que `faster_whisper`.
*   **La CLI con `OpcionesTranscripcion` y `transcribir`** (antes «historia E»): punto de backlog carril S, sin
    historia, tras B1.
*   **`PanelHistorial` sin métodos privados de la ventana** (resto de A-15).
*   **Reutilizar la sesión `auto` en el gestor** (pendiente de `AGENTS.md`): `GestorDocumentos` es el sitio natural,
    pero no se adelanta.

### Riesgos

1.  **Regresión visual que los tests no ven.** La ventana sigue pintando: un estado de botón mal restaurado no lo
    detecta ningún test. Mitigación: `_restaurar_controles_ia` concentra la restauración en un solo método, y cada
    historia tiene su verificación en la ventana real.
2.  **Cambio del momento en que falla la falta de `faster_whisper`** (decisión abierta 5).
3.  **Una referencia olvidada a `self._asistente` o `self._generacion`** tras D1 daría un `AttributeError` solo en la
    ventana. Mitigación: el `grep` de la verificación de D1.
4.  **Callbacks del flujo de transcripción llamados desde el hilo de fondo.** Si alguien pasa un callback que toca un
    widget directamente, rompe la regla 9. Mitigación: el docstring del módulo y los nombres (`on_fase`,
    `on_segmento`); la ventana es el único llamador.
5.  **El test de importaciones depende de que `src.ui` se pueda importar sin pantalla.** Hoy `tests/test_ui.py` ya lo
    hace; si deja de poder, el test fallaría por otro motivo. Mitigación: el guion imprime la traza del import que
    falla.

--------------------------------------------------------------------------------

## Revisión (2026-11-22)

Revisores: arquitectura («aprobar con cambios») e implementation readiness («listo con ajustes»).

| Hallazgo | Cómo quedó |
|---|---|
| Historias B, C y D demasiado grandes para tres criterios y un `/pair` | Partidas en B1/B2, C1/C2 y D1/D2, cada una con tres criterios, tests y lista cerrada de archivos («Historias») |
| La historia E no tiene paso rojo | Sacada del flujo TDD: opcional, sin historia, posible punto de backlog carril S («Fuera de alcance», «Mejoras futuras») |
| C dejaba un estado intermedio con dos identidades (`_GeneracionIA` y `Generacion`) y un campo opaco `datos_vista` | C2 usa `Generacion` directamente; sin `datos_vista`; la ventana guarda `_vista_previa_ia` (alternativa G) |
| La firma de `_recibir_documento_ia` y el uso de `self._asistente.modelo_usado` cambiaban tarde | Cambian en C2; `DocumentoGenerado` lleva `segundos` (medido dentro) y `modelo_usado` (leído después de generar) |
| «Solo desde el hilo principal» no se comprobaba | `GestorDocumentos` guarda `threading.get_ident()` y lanza `RuntimeError`; test en D1; docstring de `procesar_generacion` sobre los hilos de `on_progreso` |
| `procesar_generacion` podía entregar dos veces si `entregar` lanzaba | Una sola llamada fuera del `try`; test con `entregar` que lanza (C2) |
| `fecha_de_la_reunion` podía lanzar y dejar `iniciar` a medias | Captura `(OSError, ValueError)`; `iniciar` calcula todo antes de fijar `vigente`; tests en C1 y D1 |
| Faltaban `_alternar_documento_ia`, `_generar_documento_ia` y el orden de creación del gestor | Incluidos en D1; el gestor se crea después de `self.historial` |
| Restauración de botones repartida | Un solo método, `_restaurar_controles_ia`, desde C2 |
| Anotaciones evaluadas en Python 3.10 sin `WhisperModel` | `from __future__ import annotations` en `transcriber.py` (A) |
| Import fallido dejaba el modelo en mal estado; `ImportError` nativos | Import dentro del `latido`; `_modelo` queda en `None` y se reintenta; test (A); decisión abierta 5 ampliada a `av`/`ctranslate2` |
| El paso rojo de A podía descargar el modelo real | `monkeypatch.setattr("src.transcriber.WhisperModel", prohibido, raising=False)` |
| Un subproceso por módulo; ruta con espacios | Un solo subproceso, sin `shell`, `cwd` desde `__file__`, comprueba `faster_whisper` y, en los flujos, `tkinter`/`customtkinter`; archivo de A, B1 y C1 |
| `ui.py` necesita `TranscriptorAudio` para su anotación | Dicho en «Plan técnico», punto 1: se conserva el import |
| Nombres de archivo anteriores al punto #18 | Literales nuevos (`reunion.m4a_transcripcion.txt`, `reunion.m4a_minuta.md`, `reunion.m4a_resumen.md`) en CUJ, criterios y tests |
| `OpcionesTranscripcion` no compilaba (`task` con valor por defecto en medio) y la ventana usa otros nombres | `task` al final; `desde_configuracion` con `dataclasses.replace` (clave desconocida → `TypeError`); se acepta dejar en la dataclass solo lo elegible (decisión abierta 4) |
| Los tests debían usar `log_prob_threshold` y `language=None` | En el criterio 1 de B1 |
| Secuencia exacta del 401 abandonado | Criterio 2 de D2 |
| C6 duplicaba tests existentes; faltaba demostrar la caché de notas con el gestor | C6 quitado; criterio 3 de D2 con `AsistenteIA` real y `httpx` simulado |
| Dobles de test no disponibles fuera de sus archivos | «Dobles de test que usan los archivos nuevos» |
| Límite de archivos no cerrado por historia | Lista cerrada en cada historia y «Tests y archivos que no cambian»; documentación a `/cerrar` |
| Faltaba qué verificar en la ventana tras cada historia | «Verificación en la ventana real» y un `grep` en cada historia |

Una desviación respecto a lo pedido: la firma es `desde_configuracion(configuracion, archivo, **cambios)` y no
`desde_configuracion(configuracion, **cambios)`, porque `archivo` no tiene valor en la configuración y es obligatorio.

--------------------------------------------------------------------------------

*Redactado con EGM (Tándem `/diseno`); revisado el 2026-11-22.*
