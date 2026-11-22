# 08 · Cargar `faster_whisper` solo al cargar un modelo

> Origen: `BACKLOG.md`, «Salud del código» #5 — hallazgo A-15 — carril M (primera de las siete historias del diseño).
> — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia A — Cargar `faster_whisper` solo al cargar un modelo
> (y §Plan técnico, punto 1; §Decisiones abiertas 2 y 5; §Revisión (2026-11-22)).
> Reglas de oro 3 y 5 de `AGENTS.md`. No depende de ninguna otra historia; B1 y C1 dependen de esta.
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Criterios, tests y lista de archivos
> tomados del diseño y comprobados contra el código de `fd3b870` (sin cambios en `src/` ni `tests/` desde `c59d0ac`).

## Historia

Como quien mantiene el código (y como usuario que abre la ventana o cierra la sesión de Copilot sin transcribir),
quiero que `faster_whisper` se cargue solo cuando se carga un modelo de Whisper, para que importar cualquier módulo del
paquete, abrir la ventana, las órdenes de sesión de la CLI y cada sesión de tests no paguen su carga (unos 0,3 s).

Es un cambio interno. **Lo observable es para quien importa el paquete o mantiene el código**: qué módulos quedan en
`sys.modules`, cuándo se importa `faster_whisper` y qué pasa si ese import falla. **Para el usuario la app no cambia**:
mismos textos, misma fase «Cargando modelo …», mismos mensajes del log, mismas firmas; solo arranca algo antes. La única
diferencia visible es con `faster_whisper` ausente o roto (criterio 3).

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dado el entorno virtual del proyecto, cuando en un proceso nuevo se importan, en este orden,
  `src`, `src.registro`, `src.configuracion`, `src.utils`, `src.transcriber`, `src.historial`, `src.persistencia`,
  `src.copilot`, `src.asistente_ia`, `src.main`, `src.ui_copilot`, `src.ui_historial` y `src.ui`, entonces
  `faster_whisper` no está en `sys.modules` después de ninguno de ellos, y `import src` ya no expone
  `TranscriptorAudio`, `validar_archivo` ni `obtener_info_archivo` (solo `__version__ = "0.1.0"`). (antes:
  `src/__init__.py:3` importa `src.transcriber`, que importa `faster_whisper` en su cabecera (`src/transcriber.py:9`),
  así que el primer import de cualquier `src.<módulo>` lo cargaba; sin el `__init__`, seguirían cargándolo
  `src.historial`, `src.main`, `src.transcriber`, `src.ui` y `src.ui_historial`)
- [ ] [MODIFICA: sin spec] Dado un `TranscriptorAudio("small", "cpu", "int8", cache_dir=<carpeta temporal>)`, cuando se
  lee `.modelo` dos veces, entonces `faster_whisper` se importa en ese momento (no antes) y se construye un solo
  `WhisperModel`, con `"small"`, `device="cpu"`, `compute_type="int8"` y `download_root=<carpeta temporal>`; la segunda
  lectura devuelve el mismo objeto. (antes: `.modelo` construía el `WhisperModel` con los mismos argumentos y una sola
  vez, pero con `faster_whisper` ya cargado desde el import del paquete)
- [ ] [MODIFICA: sin spec] Dado que importar `faster_whisper` falla la primera vez (por ejemplo con `ImportError`, como
  cuando no está instalado o falla una biblioteca nativa de `av` o `ctranslate2`), cuando se lee `.modelo`, entonces
  sale ese mismo `ImportError` sin envolver, el transcriptor sigue sin modelo, y al leer `.modelo` otra vez, con el
  módulo ya disponible, se construye el modelo. En consecuencia la ventana abre y la CLI atiende `--copilot-login`,
  `--copilot-modelos`, `--copilot-logout` y `--listar-modelos`; el fallo aparece al transcribir, en la ventana como el
  diálogo «Error» genérico con el texto de la excepción y en la CLI como «Error durante la transcripción» con código 1.
  (antes: con `faster_whisper` ausente o roto no arrancaban ni la ventana ni ninguna orden de la CLI, porque fallaba el
  import del paquete)

### Cómo se verifican

- **Con tests sin red ni modelo real** (regla 3), en `tests/test_importaciones.py` (archivo nuevo):
  - `test_ningun_modulo_carga_faster_whisper_al_importarse` (criterio 1): **un solo** subproceso,
    `subprocess.run([sys.executable, "-c", GUION], cwd=RAIZ, capture_output=True, text=True)`, con
    `RAIZ = Path(__file__).resolve().parent.parent` y sin `shell` (la ruta del repo tiene espacios). `GUION` recorre la
    lista `MODULOS` en el orden del criterio con `importlib.import_module`, y tras cada import anota el módulo si
    `"faster_whisper" in sys.modules`; también anota, para los módulos de la lista `SIN_TK` (vacía en esta historia; la
    llenan B1 y C1), si están `tkinter` o `customtkinter`. Imprime lo anotado y sale con código 1 si hay algo. El test
    exige `returncode == 0` y muestra `stdout` y `stderr` si falla. En rojo falla ya en `src`.
  - `test_modelo_importa_faster_whisper_al_cargarse` (criterio 2), en el mismo proceso:
    `monkeypatch.setattr("src.transcriber.WhisperModel", prohibido, raising=False)` (`prohibido` lanza
    `AssertionError`, para que ni el paso rojo construya ni descargue el modelo real) y
    `monkeypatch.setitem(sys.modules, "faster_whisper", <types.ModuleType con un WhisperModel falso que anota sus
    argumentos>)`. Lee `.modelo` dos veces: una sola construcción, con los cuatro argumentos, y el mismo objeto. En rojo
    falla porque la cabecera ya enlazó el `WhisperModel` real y el parche lo cambia por `prohibido`.
  - `test_si_falla_el_import_se_reintenta_al_volver_a_pedir_el_modelo` (criterio 3): el mismo parche de `prohibido`;
    `monkeypatch.setitem(sys.modules, "faster_whisper", None)` (así el `import` lanza `ImportError`),
    `pytest.raises(ImportError)` al leer `.modelo`; después se pone el módulo falso y `.modelo` devuelve el modelo
    falso.
  - Ningún test existente cambia y todos siguen pasando (`./venv/bin/python -m pytest -q`, hoy 284). En particular
    `modelo_whisper_falso` (`tests/conftest.py:41`) sustituye la propiedad `modelo` entera, así que el import perezoso
    no se ejecuta en esos tests; `tests/test_basico.py:53` sigue importando `faster_whisper` a propósito; y
    `tests/test_cli.py:281` sigue parcheando `src.main.TranscriptorAudio`.
- **Verificación manual (la que pide el diseño):**
  - Una transcripción real con el modelo `tiny` por CLI (`./venv/bin/python -m src.main <audio corto> -m tiny`) y otra
    por la ventana: el import perezoso funciona en el hilo de fondo y se ve la fase «Cargando modelo tiny…».
  - `./venv/bin/python -X importtime -c "import src.main" 2>&1 | grep -c faster_whisper` da `0` (hoy da `8`), y
    `python -m src.main --help` baja de 319-517 ms a unos 200 ms en este equipo.
  - `grep -n "from .transcriber\|from .utils" src/__init__.py` y `grep -n "^from faster_whisper" src/transcriber.py`
    no devuelven nada.

## Plan

- Quitar el import de `faster_whisper` de la cabecera del módulo de transcripción y hacerlo dentro de la carga del
  modelo, bajo el aviso periódico que ya la envuelve y justo antes de construirlo; si el import o la construcción
  fallan, la excepción sale tal cual y el modelo queda sin cargar para que el siguiente acceso lo reintente.
- Mantener los tipos del modelo solo para el análisis estático (anotaciones diferidas e import bajo comprobación de
  tipos), sin cambiar firmas ni mensajes del log.
- Dejar el `__init__` del paquete con su docstring y la versión, sin ningún import ni reexportación.
- Tests en el orden rojo → verde: primero el del subproceso y los dos de la carga, luego el cambio, y la suite completa
  en verde.

## Fuera de alcance

- Historias B1 y B2 (opciones, transcriptor y «transcribir y persistir» fuera de la ventana), C1 y C2 (texto, ruta,
  fecha y generación de fondo de los documentos), D1 y D2 (`GestorDocumentos`, punto de decisión y borrado de
  `persistir_documento_si_vigente`): son las historias siguientes del diseño. En esta, `SIN_TK` queda vacía.
- La antigua historia E (que la CLI use `flujo_transcripcion.transcribir`): fuera del flujo TDD, sin historia; posible
  punto de «Salud del código» carril S tras B1.
- Un mensaje propio en español cuando falta `faster_whisper` (decisión abierta 5: sería un requisito nuevo).
- Reexportación perezosa con `__getattr__` de módulo en `src/__init__.py` (decisión abierta 2: se descarta) y la
  alternativa E del diseño (dejar el `__init__` como está).
- Precargar `faster_whisper` en un hilo al abrir la ventana (alternativa F, rechazada).
- Cargar `ffmpeg` de forma perezosa (`src/utils.py:5`): «Mejoras futuras» del diseño.
- Mover `ResultadoTranscripcion` y `SegmentoTranscripcion` a otro módulo (alternativa D, rechazada).
- Cambios en `src/main.py`, `src/ui.py`, `src/historial.py` o cualquier test existente.
- La documentación (`docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md:13`, `AGENTS.md`, `.context/*`, incluida
  `.context/conventions.md:17` sobre los imports relativos de `src/__init__.py`): la actualiza `/cerrar`, no el `/pair`.

**Archivos que puede tocar el `/pair` (lista cerrada):** `src/transcriber.py`, `src/__init__.py`,
`tests/test_importaciones.py` (crear). Si hace falta tocar otro, se para y se vuelve al diseño.

## Sugerencias

- Que el `GUION` del subproceso imprima la traza del import que falle, no solo el nombre del módulo (riesgo 5 del
  diseño: si `src.ui` deja de importarse sin pantalla, el test fallaría por otro motivo y hay que verlo).
- Comprobar en el test del criterio 2 que el módulo falso se instala **después** de crear el `TranscriptorAudio`
  importando la clase normalmente: así el test también demuestra que crear el transcriptor no importa nada.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **Las tres marcas son `[MODIFICA: sin spec]`.** Ninguna spec de `docs/specs/` describe cuándo se carga
   `faster_whisper` ni qué exporta el paquete (las de `cli.md` sobre «no carga Whisper» se refieren a crear el
   transcriptor, y siguen igual). Las tres notas `(antes: …)` salen del código leído, no de memoria. El criterio 2
   podría verse como `[NUEVO]` porque la construcción única ya existía; se marca `MODIFICA` porque lo que cambia es el
   momento del import.
2. **El criterio que cubre el caso que duele es el 3**: un import fallido que deje el transcriptor en mal estado y
   obligue a reiniciar la app. El criterio de error lo es también del camino infeliz.
3. **Quitar `TranscriptorAudio`, `validar_archivo`, `obtener_info_archivo` y `__all__` de `src/__init__.py` no rompe
   nada**: comprobado el 2026-11-22, ningún archivo del repo usa `from src import TranscriptorAudio` (ni
   `validar_archivo`, ni `obtener_info_archivo`). Los `from src import copilot|configuracion|utils|asistente_ia` que sí
   existen importan submódulos y siguen funcionando con el `__init__` vacío.
4. **El fallo de la ventana tras un import fallido ya se reintenta solo**: `_obtener_transcriptor` (`src/ui.py:641`)
   guarda el transcriptor en `self._transcriptor` solo después de `_ = t.modelo`, así que el siguiente «Transcribir»
   crea otro. El criterio 3 se prueba sobre `TranscriptorAudio` y no sobre la ventana.
5. **`from __future__ import annotations` se añade aunque el venv sea Python 3.14** (donde las anotaciones ya son
   diferidas): el README declara Python 3.10 o superior, y sin él `Optional[WhisperModel]` daría `NameError` en 3.10
   a 3.13. Solo se ha verificado con 3.14.10.
6. **El orden de `MODULOS` es el del criterio 1 del diseño**; los módulos que se añadan a `SIN_TK` en B1 y C1 deben ir
   antes de cualquier `src.ui*`.

### Discrepancias entre el diseño y el código actual

Ninguna que cambie la historia. Comprobado contra el código: `src/__init__.py:3` y `src/transcriber.py:9`,
`src/historial.py:13`, `src/main.py:10`, `src/ui.py:30` (import) y `:140` (anotación de `self._transcriptor`),
`tests/conftest.py:41`, `tests/test_basico.py:53`, `tests/test_cli.py:281`; la carga del modelo está en
`TranscriptorAudio.modelo` dentro de `with latido(…)`; la suite da 284 tests en verde. Matices menores:

- El diseño cita las líneas del commit `c59d0ac`; HEAD es ya `fd3b870`, pero solo añadió documentación: `src/` y
  `tests/` no cambiaron y las líneas coinciden.
- El diseño (§El problema, punto 3) solo nombra `src.historial`, `src.main` y `src.transcriber` como los que seguirían
  cargando `faster_whisper` sin el `__init__`; `src.ui` y `src.ui_historial` también (por `historial` y `transcriber`),
  como ya dice su tabla de mediciones. No cambia nada: el criterio 1 los cubre a todos.
- `src/EGM.md:13` y `.context/conventions.md:17` dicen que `src/__init__.py` importa `transcriber` y `utils` con
  imports relativos; quedarán desfasados tras el `/pair` hasta que `/cerrar` los actualice (como prevé el diseño).

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 287 tests (284 de antes más los 3 de `tests/test_importaciones.py`). Code review: revisión del orquestador, cambio pequeño (import perezoso en `src/transcriber.py` y `src/__init__.py` vacío): listo para commit. Delta de spec: `docs/specs/cli.md`, un comportamiento nuevo («Órdenes que no transcriben») con `Origen` en esta historia. Nada más en las specs.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Importar los 13 módulos en orden sin cargar `faster_whisper`; `import src` deja de exponer `TranscriptorAudio`, `validar_archivo` y `obtener_info_archivo` | test `test_ningun_modulo_carga_faster_whisper_al_importarse` (`tests/test_importaciones.py:54`). Implementación: `src/__init__.py:3` (solo `__version__`) y `src/transcriber.py:15-17` (import solo para tipos) | cumple (test) |
| 2 | [MODIFICA: sin spec] | `.modelo` importa `faster_whisper` al cargarse y construye un solo `WhisperModel` con los cuatro argumentos | test `test_modelo_importa_faster_whisper_al_cargarse` (`tests/test_importaciones.py:78`). Implementación: `src/transcriber.py:74` | cumple (test) |
| 3 | [MODIFICA: sin spec] | Si el import falla, sale el `ImportError` sin envolver, el modelo queda sin cargar y el siguiente acceso lo reintenta; las órdenes que no transcriben siguen funcionando | test `test_si_falla_el_import_se_reintenta_al_volver_a_pedir_el_modelo` (`tests/test_importaciones.py:91`). Implementación: `src/transcriber.py:74` (el import va antes de construir el modelo). Que la CLI muestre «Error durante la transcripción» con código 1: `src/main.py:218-220` (`except Exception`), sin test propio | cumple (tests). Pendiente aceptado: el mensaje de la CLI no tiene test propio |

**Verificación (2026-11-22)**, hecha por el orquestador fuera de los tests:

- `./venv/bin/python -X importtime -c "import src.main"` ya no carga `faster_whisper` (0 líneas; antes, 8).
- Una transcripción real por la CLI con el modelo `large-v3-turbo` (en caché, sin red) de un audio de 3 s termina con código 0 y el log «Modelo 'large-v3-turbo' listo».
- `python -m src.main --help` pasa de 389–533 ms a 195–262 ms en este equipo.

**Pendientes aceptados:**

- No se verificó una transcripción por la ventana. La ruta es la misma propiedad `TranscriptorAudio.modelo`, que se ejecuta en el hilo de fondo, pero no se ha visto la fase «Cargando modelo …» en la interfaz.
- Solo Python 3.14 verificado. Se añadió `from __future__ import annotations` para que las anotaciones no den `NameError` en 3.10 a 3.13 (el README declara 3.10 o superior).
- Mensaje propio en español cuando falta `faster_whisper`: descartado (decisión 5 del diseño, `docs/disenos/05-flujos-fuera-de-la-ventana.md`). Sigue saliendo el `ImportError` original.
