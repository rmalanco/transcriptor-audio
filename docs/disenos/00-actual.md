# Arquitectura actual

> Status: as-is (no aprobado como diseño objetivo)
>
> Generado por /analizar (Tándem) el 2026-11-22 a partir de [EGM.md](../../EGM.md), [src/EGM.md](../../src/EGM.md),
> [README.md](../../README.md) y `.context/inventario.md`. Describe lo que el código hace hoy, no lo que debería hacer.

## Resumen

Aplicación de escritorio en Python que transcribe audio y video en el propio equipo con faster-whisper y, cuando el
usuario lo pide, genera un resumen y una minuta enviando el texto transcrito a GitHub Copilot. Cada transcripción
terminada en la interfaz gráfica se guarda en un historial SQLite local, con su resumen y su minuta. Hay dos formas
de uso: una interfaz gráfica (CustomTkinter) y una CLI que solo transcribe y gestiona la sesión de Copilot. Todo el
código está en un paquete, `src/`, de once módulos y 3 262 líneas.

## Componentes

No hay subcarpetas con código: los componentes son módulos de `src/`. Todos se documentan en
[src/EGM.md](../../src/EGM.md).

| Componente | Módulos | Responsabilidad |
|---|---|---|
| Transcripción | `transcriber.py`, `utils.py` | Cargar el modelo de Whisper, transcribir con filtro de silencios y de alucinaciones, validar archivos, leer metadatos con `ffprobe`, exportar a `txt`, `srt`, `vtt` o `json`, leer y reescribir `settings.yaml` |
| Resumen y minuta | `asistente_ia.py` | Dividir el texto en bloques, sacar notas en paralelo, redactar el documento, reintentar secciones faltantes, revisar la fidelidad y normalizar la minuta |
| Acceso a Copilot | `copilot.py` | Login por device flow, lectura y guardado del token, catálogo de modelos, filtro de modelos económicos y sesión del modo `auto` |
| Historial | `historial.py` | Tabla `transcripciones` en SQLite: crear, guardar documentos, renombrar, eliminar, buscar |
| Interfaz gráfica | `ui.py`, `ui_copilot.py`, `ui_historial.py` | Ventana principal, diálogo de login y panel del historial |
| CLI | `main.py` | Transcribir a `stdout` o a un archivo; login, logout y lista de modelos de Copilot |
| Registro | `registro.py` | Configurar el logging y avisar cada cierto tiempo en operaciones largas (`latido`) |

Fuera de `src/`: `run_ui.py` (lanzador), `config/settings.yaml` (configuración) y `tests/` (seis archivos de tests).

## Flujo de datos

Sin diagrama: los caminos se describen como pasos, cada uno con el símbolo que lo ejecuta.

### Transcribir desde la interfaz

1. El usuario elige o arrastra un archivo. `utils.validar_archivo` comprueba la extensión y
   `utils.obtener_info_archivo` lee los metadatos con `ffprobe`.
2. `AppTranscriptor._iniciar_transcripcion` lee las opciones en el hilo principal y lanza un hilo de fondo.
3. En ese hilo, `TranscriptorAudio.transcribir` procesa el audio con faster-whisper y entrega cada segmento a la
   interfaz mediante `on_segmento`.
4. Todavía en el hilo de fondo, `persistencia.persistir_transcripcion` guarda primero en el historial
   (`Historial.crear` inserta la fila en `transcripciones`) y después escribe
   `<nombre>_transcripcion.<formato>` junto al audio con `utils.guardar_transcripcion`.
5. Un fallo del historial o de la exportación no descarta el resultado: vuelve como aviso y la ventana lo muestra
   en un diálogo de advertencia y en la pestaña Registro.

### Generar el resumen o la minuta

1. `AppTranscriptor._generar_documento_ia` crea un `AsistenteIA` con la sección `ia:` de la configuración. Si no hay
   token, se abre `DialogoLoginCopilot` y, tras el login, se repite la petición.
2. En un hilo de fondo, `AsistenteIA.generar_resumen` o `generar_minuta` envían el texto a
   `POST <url_api>/chat/completions` en streaming.
3. Si el texto supera `max_caracteres_bloque`, primero se piden notas por bloque en paralelo y el documento se
   redacta a partir de esas notas.
4. `persistencia.persistir_documento` guarda primero en el historial: `Historial.guardar_documento` guarda el
   documento y el modelo usado y, con la minuta, también actualiza el título si no se editó a mano.
5. Después el resultado se escribe en `<nombre>_resumen.md` o `<nombre>_minuta.md` junto al audio, si el audio
   existe. Un fallo de guardado no descarta el documento: se avisa en la línea de estado de la pestaña y en Registro.

### Iniciar sesión en Copilot

1. `copilot.iniciar_login` pide un código a `/login/device/code`.
2. El usuario introduce el código en GitHub.
3. `copilot.esperar_login` consulta `/login/oauth/access_token` hasta recibir el token y `copilot.guardar_token` lo
   escribe en `~/.local/share/transcriptor-audio/copilot.json`.

### Transcribir desde la CLI

`main.main` valida el archivo, transcribe con `TranscriptorAudio.transcribir` y escribe en `stdout` o en el archivo
de `-o`. No genera resumen ni minuta y no guarda en el historial.

## Dependencias externas

| Dependencia | Para qué | Dónde |
|---|---|---|
| faster-whisper (y `av < 19`) | Transcripción local | `transcriber.py` |
| ffmpeg y ffprobe (binarios), `ffmpeg-python` | Metadatos y corte en trozos | `utils.py`, `transcriber.py` |
| CustomTkinter, Tkinter, `tkinterdnd2-universal` | Interfaz gráfica y arrastrar y soltar | `ui*.py` |
| httpx | Llamadas a GitHub y a Copilot | `copilot.py`, `asistente_ia.py` |
| PyYAML | Leer la configuración | `transcriber.py` |
| SQLite (biblioteca estándar) | Historial | `historial.py` |
| GitHub (`github.com`) | Login por device flow, con el `client_id` de opencode | `copilot.py` |
| API de Copilot (`api.githubcopilot.com`) | `/models`, `/models/session`, `/chat/completions` | `copilot.py`, `asistente_ia.py` |
| Descarga de modelos (la hace faster-whisper; origen sin verificar en este repo) | Primera carga de cada modelo de Whisper | `transcriber.py` |

`requirements.txt` declara además `pydantic` y `tqdm`, que ningún módulo de `src/` importa. No hay lockfile.

## Cómo se prueba

- Comando: `./venv/bin/python -m pytest -q`.
- Estado al 2026-11-22: **no ejecutado**. `pytest` no está instalado en el venv ni declarado en `requirements.txt`;
  el README pide instalarlo aparte.
- Hay 60 funciones de test en seis archivos de `tests/`. Según el README, no hacen llamadas reales a la red.
- No hay CI, linter ni comprobación de tipos.

## Huecos conocidos

- **Tests sin ejecutar.** No se sabe si pasan hoy, y menos con Python 3.14 (el README dice «probado con 3.12»).
- **Comportamiento real de la API de Copilot.** Lo documentado sale del código, no de llamadas reales: no se probó
  el login, el catálogo de modelos, el modo `auto` ni la generación.
- **Interfaz gráfica sin ejecutar.** Los atajos, los estados de los botones y el diseño se leyeron en el código.
- **Contenido de los prompts.** `PROMPT_SISTEMA` y los demás se identificaron, pero sus reglas de fidelidad no se
  contrastaron con salidas reales.
- **Tests no documentados.** `tests/` queda fuera de los contratos por diseño del flujo.
- **Código sin llamadores.** `TranscriptorAudio.transcribir_archivo_largo` no se usa en ningún módulo, y las claves
  `audio.sample_rate` y `audio.chunk_duration` de `settings.yaml` no se leen. No se sabe si es código en desuso o
  una función pendiente.
- **Dos valores por defecto para el modelo de IA.** `settings.yaml` trae `claude-haiku-5.5` y el código usa
  `gpt-4.1` (`MODELO_POR_DEFECTO`) cuando falta la clave. Lo mismo ocurre con `temperatura` (0.2 en el YAML, 0.3 en
  el código) y `revision_fidelidad` (`false` en el YAML, `True` en el código).
- **`condition_on_previous_text`.** El YAML lo pone en `false`; el valor por defecto de `transcribir` es `True`.
  La interfaz y la CLI siempre pasan el del YAML.
