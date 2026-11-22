# 02 · Dependencias fijadas y tests del flujo y la CLI

> Origen: `BACKLOG.md`, «Salud del código» #2 — hallazgos A-16 y A-29 — carril M. Regla de oro 5 de `AGENTS.md`.
> Refinada con `/story` el 2026-11-22. Esta historia declara y fija las dependencias, cubre el flujo transcribir →
> guardar → historial y la transcripción a archivo por la CLI. Los rechazos de la CLI y sus órdenes de sesión se
> proponen como historia aparte (ver «Historias derivadas»).

## Historia

Como quien mantiene el repositorio (una persona o un agente), quiero instalar con un solo comando documentado las
mismas versiones con las que pasan los tests, `pytest` incluido, y que un cambio que rompa el guardado de una
transcripción en el historial o la transcripción por la CLI haga fallar un test, para poder verificar cada arreglo
del backlog sin depender de lo que haya instalado en mi equipo ni de probar a mano.

## Criterios de aceptación

- [ ] [NUEVO] Dado un clon recién hecho del repositorio y un entorno virtual vacío con Python 3.14, cuando se
  instala con el comando de desarrollo que documentan el README y `AGENTS.md`, entonces cada dependencia declarada
  (las de ejecución y `pytest`) queda instalada exactamente en la versión fijada, y `python -m pytest -q`, ejecutado
  desde la raíz sin red, termina con todos los tests en verde sin descargar ningún modelo de Whisper.
- [ ] [NUEVO] Dado un audio `reunion.m4a` cuyo reconocimiento se simula con tres segmentos —«Hola equipo.»
  (0–2 s), «¡Suscríbete!» (2–3 s) y «Cerramos el punto.» (3–5 s), idioma `es`, 5 s de duración—, cuando se ejecuta
  `python -m pytest -q`, entonces un test lo transcribe y lo guarda con las mismas piezas y en el mismo orden que la
  interfaz (modelo `small`, formato `txt` con marcas de tiempo) y comprueba que la entrada `reunion` del historial
  tiene el texto «Hola equipo. Cerramos el punto.», solo esos dos segmentos con sus tiempos, idioma `es`, 5 s y
  modelo `small`, y que `reunion_transcripcion.txt` junto al audio tiene las mismas dos líneas. El test falla si se
  rompe cualquiera de esas cosas, también si la alucinación «¡Suscríbete!» llega al historial.
- [ ] [NUEVO] Dado un audio `reunion.m4a` cuyo reconocimiento se simula con «Hola equipo.» (0–2 s) y «Cerramos el
  punto.» (3–5 s), y una configuración propia del test, cuando se ejecuta la CLI con
  `reunion.m4a -o salida.srt -f srt --config <esa configuración>`, entonces termina con código 0, escribe en
  `stdout` «Transcripción guardada en: <ruta de salida.srt>» y `salida.srt` contiene los dos segmentos numerados en
  SRT (`1`, `00:00:00,000 --> 00:00:02,000`, `Hola equipo.`; `2`, `00:00:03,000 --> 00:00:05,000`,
  `Cerramos el punto.`). Un test lo comprueba sin depender de `config/settings.yaml` y falla si se rompe.

Sobre los casos de error: la historia no cambia el comportamiento del producto. Los fallos de guardado ya los
cubren los tests de la historia 01 (`tests/test_persistencia.py`); aquí, el primer criterio cubre el límite del
clon limpio (un manifiesto que git no versiona) y el segundo, un segmento que debe descartarse. Los errores de la
CLI pasan a la historia derivada.

Cómo se simula la transcripción: ningún test carga un modelo de Whisper ni lee audio. Un doble del modelo devuelve
segmentos fijos (con `start`, `end`, `text`, `words`) y un objeto con `duration`, `language` y
`language_probability`, igual que el `ModeloFalso` que ya usa `tests/test_basico.py:86-95`. El audio es un archivo
vacío con extensión `.m4a` en una carpeta temporal: la CLI solo comprueba que exista y su extensión, y el doble no
lo lee. El historial es una base temporal y no hay red ni ventanas.

Cómo se verifican:

- **Primer criterio, a mano:** antes del commit, `git check-ignore` no debe devolver nada para el manifiesto nuevo
  y `git status` debe mostrarlo como archivo nuevo. Después del commit, clonar el repositorio en una carpeta
  temporal, crear un venv vacío, instalar con el comando documentado y comparar `pip freeze` con las versiones
  declaradas. Ejecutar `python -m pytest -q` sin red (en Linux, `unshare -rn`) y con una caché de modelos vacía.
- **Segundo y tercer criterio, con tests:** `./venv/bin/python -m pytest -q`. Para comprobar que los tests muerden,
  romper a propósito y uno a uno (y deshacer después): no guardar los segmentos en el historial, quitar el filtro de
  alucinaciones, saltarse el guardado en el historial, cambiar el separador de milisegundos del SRT. Con cada
  rotura debe fallar al menos un test.

## Plan

- Fijar las dependencias de ejecución que ya se declaran a las versiones instaladas y probadas hoy, sin añadir ni
  quitar ninguna, y declarar `pytest` fijado en un manifiesto de desarrollo que incluya al de ejecución. Comprobar
  que git no ignora ese manifiesto.
- Cambiar la guía de instalación, la sección de tests, las instrucciones para agentes y los contratos que hoy dicen
  que `pytest` no está declarado, para que todos den el mismo comando.
- Un doble del modelo de Whisper reutilizable por los tests, colocado en el punto público por el que el
  transcriptor obtiene su modelo, que devuelva segmentos fijos con idioma y duración.
- Test del flujo: transcribir con el doble, guardar con la función de persistencia que ya usa la interfaz contra un
  historial temporal, y leer después la entrada y el archivo exportado.
- Test de la CLI: invocar su punto de entrada dentro del proceso con argumentos de prueba y una configuración
  temporal, y comprobar código de salida, salida estándar y archivo.

## Fuera de alcance

- Un lockfile de las dependencias transitivas. A-29 cita que no hay lockfile, pero el backlog pide «versiones
  fijadas». Aquí se fijan solo las directas; `numpy`, `ctranslate2`, `onnxruntime`, `huggingface_hub` y las demás
  siguen libres. Un lock completo exige elegir herramienta (`pip-tools`, `uv`…), que es decisión del usuario.
- Fijar la versión de Python o probar en Windows: las versiones se verificaron solo con Python 3.14.10 en Linux.
- CI, linter y comprobación de tipos.
- Quitar `pydantic` y `tqdm` (A-20, «Salud del código» #12): se fijan tal como están.
- El callback de la ventana que orquesta la transcripción (cancelar, error al transcribir, avisos): vive en la
  clase Tk y se cubre cuando se extraiga (A-15, #5). El segundo criterio prueba las piezas que usa ese callback,
  en su orden, no el callback.
- En la CLI no se fija con tests: la salida por `stdout` en `txt` y `json` ni el rechazo de `srt`/`vtt` sin `-o`
  después de transcribir (defectos de A-10, #9); que `-l`, `-f` y los demás valores por defecto ignoren el YAML
  (A-09, #6); `--verbose`, que exige `ffprobe` (A-20, #12); la lista de modelos de Whisper (A-21, #13); `--ui`
  (A-28, descartado); que la CLI no escriba en el historial (es un hecho de hoy, no una decisión).
- El resto de huecos que cita A-16: reintentos de `_completar` (429, 5xx, 403, `model_not_supported`),
  `ui_historial.py`, `ui_copilot.py`, `validar_archivo` y `obtener_info_archivo`.
- `test_cargar_configuracion`, que depende del directorio de trabajo y del `config/settings.yaml` real (A-16): se
  resuelve con los puntos #6 y #11. `tests/test_registro.py`, que depende de tiempos reales (A-30).
- Limpiar los patrones globales `*.txt` y `*.json` de `.gitignore` (A-30, #4): aquí solo se añade la excepción
  para el manifiesto nuevo.

## Sugerencias

- Doble del modelo compartido: `tests/test_basico.py:86-95` ya define un `ModeloFalso` dentro de un test, y los
  criterios 2 y 3 necesitan otro con segmentos. Esa repetición es la señal para un fixture común en
  `tests/conftest.py`.
- Interceptar en `TranscriptorAudio.modelo`, que es interfaz pública en `src/EGM.md`, y no en
  `src.transcriber.WhisperModel` ni en `src.main.TranscriptorAudio`. Así los tests no se rompen cuando el punto #5
  deje de cargar `faster_whisper` al importar el paquete, ni cuando el #6 cambie cómo la CLI lee la configuración.
  Comprobar solo salidas observables (entrada del historial, archivo, código de salida, `stdout`), no llamadas
  internas.
- En la CLI, pasar `--config` con un YAML temporal que solo tenga las claves que lee hoy (`modelo.*` y
  `transcripcion.*`), en vez de leer `config/settings.yaml`, que la interfaz reescribe (A-19).
- Cuando el punto #5 extraiga «transcribir y persistir», apuntar el test del segundo criterio a esa función: los
  datos y las comprobaciones sirven tal cual.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **Dónde se declaran las dependencias de desarrollo:** en un `requirements-dev.txt` en la raíz que empieza con
   `-r requirements.txt` y añade `pytest`. No hay `pyproject.toml` ni otro manifiesto (`.context/inventario.md`), y
   crear uno sería más cambio del que piden A-16 y A-29. El comando documentado de desarrollo es
   `./venv/bin/python -m pip install -r requirements-dev.txt`; `pip install -r requirements.txt` sigue siendo la
   instalación de uso.
2. **El manifiesto nuevo necesita una excepción en `.gitignore`:** `*.txt` (`.gitignore:36`) lo ignora hoy,
   comprobado con `git check-ignore`. Solo `requirements.txt` tiene excepción (`.gitignore:42`). Sin ella, el
   archivo se queda en el árbol local, el commit no lo incluye y un clon no puede instalar. Es **el caso que más
   duele** y por eso el primer criterio se verifica en un clon nuevo y no en el árbol de trabajo.
3. **«Versiones fijadas» incluye las de ejecución.** El escenario de A-29 es «una instalación nueva puede traer
   versiones no probadas», y eso pasa con las dependencias de ejecución, no con `pytest`. La opción más conservadora
   es `==` en las dependencias directas que ya se declaran, a las versiones del venv donde hoy pasan los 85 tests
   (`pip freeze`, 2026-11-22): `faster-whisper==1.2.1`, `av==18.1.1` (respeta el tope `<19` y se conserva su
   comentario), `ffmpeg-python==0.2.0`, `pydantic==2.14.4`, `pyyaml==6.0.4`, `tqdm==4.70.1`,
   `customtkinter==6.0.0`, `tkinterdnd2-universal==1.7.3`, `httpx==0.28.1`; y en desarrollo, `pytest==9.2.0`. Las
   dependencias de `pytest` (`pluggy`, `iniconfig`, `packaging`, `Pygments`) y las transitivas de ejecución no se
   fijan (ver «Fuera de alcance»).
4. **La historia se divide.** Cubrir toda la CLI no cabe en tres criterios. Aquí queda la transcripción a archivo,
   que es lo que más arriesgan los puntos #6 y #9. Los rechazos y las órdenes de sesión pasan a la historia
   derivada.
5. **Las marcas son `[NUEVO]`** porque lo que observa quien mantiene el repo (una instalación declarada, tests que
   fallan si se rompe algo) no existe hoy. El comportamiento del producto no cambia, así que
   `docs/specs/transcripcion.md` y `docs/specs/documentos-ia.md` no se tocan. `/cerrar` decide si hace falta una
   spec nueva, por ejemplo de la CLI.
6. **«Con las mismas piezas y en el mismo orden que la interfaz»** quiere decir `TranscriptorAudio.transcribir`
   seguido de `persistir_transcripcion` (historial primero, después el archivo), como en
   `src/ui.py:614-640`. Ese test no detecta que alguien cambie el propio callback de la ventana: eso queda para el
   punto #5.
7. **Los datos de los criterios** (nombre `reunion`, frases, tiempos, modelo `small`, formato `srt` en la CLI) son
   ejemplos elegidos para que el resultado sea concreto. «¡Suscríbete!» está en `ALUCINACIONES_CONOCIDAS`, y el
   formato SRT es el de `guardar_transcripcion`, que el punto #9 va a usar también para `stdout`.

## Historias derivadas (para el backlog)

- Como quien mantiene el repositorio, quiero que los rechazos de la CLI y sus órdenes de sesión estén cubiertos por
  tests, para que un cambio en la CLI no rompa en silencio esas respuestas. Casos: archivo inexistente o con
  extensión no admitida (código 1, «Error: …» en `stderr`, sin cargar el modelo de Whisper); fallo durante la
  transcripción (código 1, sin archivo de salida); `--copilot-logout` con y sin token propio (mensaje y código 0,
  sin tocar la sesión de opencode); `--copilot-modelos` sin sesión (aviso en `stderr` y código 1). Rutas de token
  aisladas como en `tests/test_copilot.py` y sin red. No fijar los comportamientos que cambiará el punto #9 (A-10).
  — hallazgo A-16 — carril S.

## Cierre

Cerrada con `/cerrar` el 2026-11-22. Tests: `./venv/bin/python -m pytest -q`, 87 pasan. Code review: listo para commit
(cambio sin código de producto: solo tests, manifiestos y documentación). Cuatro mutaciones (no guardar segmentos en el
historial, quitar el filtro de alucinaciones, saltarse el historial, cambiar el separador de milisegundos del SRT)
hicieron fallar los tests nuevos y se deshicieron.

| # | Marca | Criterio | Evidencia con test y `ruta:línea` | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Clon limpio y venv vacío con Python 3.14: instalar con el comando de desarrollo deja cada dependencia en la versión fijada, y `python -m pytest -q` sin red pasa sin descargar modelos | Manifiestos: `requirements.txt:1-9` (`==`), `requirements-dev.txt:1-2` (`-r requirements.txt` y `pytest==9.2.0`); excepción en `.gitignore:43` (`!requirements-dev.txt`; `git check-ignore` no lo ignora). Instalación en venv vacío y tests sin red: verificación del orquestador sobre el árbol de trabajo | cumple (verificado el 2026-11-22: instalación en un entorno virtual vacío y tests sobre un clon de la rama, sin red, 87 en verde) |
| 2 | [NUEVO] | Transcribir con un doble de Whisper (tres segmentos, uno de ellos alucinación), guardar en el historial temporal y exportar: la entrada `reunion` tiene solo «Hola equipo. Cerramos el punto.» con sus tiempos, idioma, duración y modelo, y `reunion_transcripcion.txt` tiene las dos líneas | Test: `tests/test_flujo.py:10` (`test_flujo_transcribir_guardar_historial_descarta_alucinacion_y_exporta`). Piezas usadas: `src/persistencia.py:30` (`persistir_transcripcion`), `src/transcriber.py:80` (`TranscriptorAudio.transcribir`) | cumple |
| 3 | [NUEVO] | CLI con `reunion.m4a -o salida.srt -f srt --config <propia>`: código 0, «Transcripción guardada en: <ruta>» en `stdout` y `salida.srt` con los dos segmentos en SRT | Test: `tests/test_cli.py:24` (`test_cli_transcribe_a_srt_con_configuracion_propia`). Comportamiento fijado en `docs/specs/cli.md` | cumple |

**Pendientes aceptados:**

- Versiones verificadas solo con Python 3.14 en Linux; no probadas en Windows ni en otras versiones de Python.
- Sin lockfile de dependencias transitivas (`numpy`, `ctranslate2`, `onnxruntime`, `huggingface_hub`…): decisión del
  usuario sobre la herramienta (`pip-tools`, `uv`…).
