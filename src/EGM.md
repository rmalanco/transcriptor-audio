# src

## Overview

Paquete único de la aplicación. Contiene la transcripción local con faster-whisper, la generación de resumen y
minuta con GitHub Copilot, el historial en SQLite, la interfaz gráfica (CustomTkinter) y la CLI. No tiene
subpaquetes: los once módulos se importan entre sí como `src.<módulo>`.

Dependencias entre módulos (quién importa a quién):

| Módulo | Usa |
|---|---|
| `main.py` | `transcriber`, `utils`, `registro`, `copilot`; `ui` solo con `--ui` |
| `ui.py` | `transcriber`, `utils`, `asistente_ia`, `copilot`, `historial`, `registro`, `ui_copilot`, `ui_historial` |
| `ui_copilot.py` | `copilot` |
| `ui_historial.py` | `historial`, y métodos de `AppTranscriptor` (incluidos privados) |
| `asistente_ia.py` | `copilot`, `registro` |
| `historial.py` | `transcriber` (solo las dataclasses de resultado) |
| `transcriber.py` | `registro` |
| `copilot.py`, `registro.py`, `utils.py` | ningún módulo hermano |

## Interface

### Puntos de entrada

- `main.py:main` — CLI (`python -m src.main`). Argumentos: `archivo` (posicional), `-o/--salida`, `-m/--modelo`,
  `-d/--dispositivo`, `-c/--compute-type`, `-l/--idioma`, `-t/--task`, `-f/--formato`, `--no-timestamps`,
  `--word-timestamps`, `--config`, `--listar-modelos`, `--copilot-login`, `--copilot-logout`, `--copilot-modelos`,
  `--ui`, `-v/--verbose`, `--log`.
- `ui.py:main` — interfaz gráfica (`python -m src.ui`, o `run_ui.py` en la raíz).
- `__init__.py` — reexporta `TranscriptorAudio`, `validar_archivo` y `obtener_info_archivo`; `__version__ = "0.1.0"`.

### Transcripción — `transcriber.py`, `utils.py`

- `transcriber.py:TranscriptorAudio(modelo_nombre="base", dispositivo="cpu", compute_type="int8", cache_dir=None)`
  - `.modelo` — propiedad que carga el `WhisperModel` la primera vez que se usa.
  - `.transcribir(archivo, idioma, task, beam_size, best_of, temperature, condition_on_previous_text, …,
    word_timestamps, on_segmento, cancelar) -> ResultadoTranscripcion`
- `transcriber.py:SegmentoTranscripcion(inicio, fin, texto, palabras)` y
  `transcriber.py:ResultadoTranscripcion(texto_completo, segmentos, idioma_detectado, probabilidad_idioma, duracion_total)`.
- `transcriber.py:es_alucinacion_conocida(texto)` y el conjunto `ALUCINACIONES_CONOCIDAS`.
- `configuracion.py:RUTA_POR_DEFECTO` (`<raíz del proyecto>/config/settings.yaml`), `configuracion.py:ErrorConfiguracion`.
- `configuracion.py:cargar_configuracion(ruta=None) -> dict`: sin `ruta`, usa `RUTA_POR_DEFECTO`;
  una ruta relativa se interpreta desde la carpeta de trabajo. Devuelve todas las secciones y las 21 claves que usa la
  app, con sus valores por defecto. valida `modelo.nombre` contra `configuracion.MODELOS_WHISPER`, la única lista de modelos de Whisper (la usan la CLI y la ventana).
- `configuracion.py:guardar_modelo_ia(modelo, ruta=None) -> bool`
- `utils.py:validar_archivo(ruta)`, `utils.py:obtener_info_archivo(ruta) -> InfoArchivo` (sin `ffprobe` o si falla, devuelve el tamaño sin duración ni códec),
  `utils.py:guardar_transcripcion(resultado, ruta_salida, formato="txt", incluir_timestamps=True)`.
- `utils.py:formatear_tiempo`, `formatear_tiempo_srt`, `formatear_tiempo_vtt`; `EXTENSIONES_AUDIO`, `EXTENSIONES_VIDEO`.

### Resumen y minuta — `asistente_ia.py`

- `asistente_ia.py:AsistenteIA(api_key=None, modelo=MODELO_POR_DEFECTO, temperatura=0.3, max_caracteres_bloque=60000,
  timeout=180.0, revision_fidelidad=True, peticiones_paralelas=3, enterprise_url=None)`
  - `.generar_resumen(texto, on_progreso=None, cancelar=None) -> str`
  - `.generar_minuta(texto, on_progreso=None, cancelar=None, fecha=None) -> str`
  - `.modelo_usado` — `"auto → <modelo>"` en modo auto con sesión abierta; si no, el modelo configurado.
- `asistente_ia.py:ErrorAsistenteIA` y su subclase `ErrorSinSesionCopilot`.
- Funciones de apoyo: `dividir_texto`, `limpiar_respuesta`, `normalizar_tabla_tareas`, `secciones_faltantes`.
- Constantes: `NOMBRE_PROVEEDOR = "GitHub Copilot"`, `MODELO_POR_DEFECTO = "gpt-4.1"`, `PROMPT_SISTEMA`,
  `PROMPT_RESUMEN`, `PROMPT_MINUTA`, `PROMPT_REVISION`, `PROMPT_NOTAS_BLOQUE`, `SECCIONES_RESUMEN`, `SECCIONES_MINUTA`.

### Acceso a GitHub Copilot — `copilot.py`

- Sesión y token: `leer_token(enterprise_url=None) -> Optional[Sesion]`, `guardar_token`, `cerrar_sesion`,
  `invalidar_token`.
- Login: `iniciar_login(enterprise_url=None) -> CodigoDispositivo`, `esperar_login(codigo, …) -> str`.
- Modelos: `listar_modelos(sesion)`, `precio_entrada(modelo)`, `modelos_economicos(sesion)`,
  `abrir_sesion_auto(sesion) -> SesionAuto`.
- HTTP: `url_api(enterprise_url=None)`, `cabeceras(token, iniciador="user")`, `normalizar_dominio(url)`.
- Tipos: `Sesion(token, enterprise_url, origen)`, `CodigoDispositivo`, `SesionAuto` (con `.vigente()`), `ErrorCopilot`.
- Constantes: `RUTA_TOKEN` (`~/.local/share/transcriptor-audio/copilot.json`), `RUTA_AUTH_OPENCODE`
  (`~/.local/share/opencode/auth.json`), `VARIABLE_ENTORNO = "COPILOT_GITHUB_TOKEN"`, `CLIENT_ID`, `API_VERSION`,
  `USER_AGENT`, `ESPERA_EXTRA`, `PRECIO_MAX_ECONOMICO = 50`, `FAMILIAS_EXCLUIDAS = ("kimi", "mistral")`,
  `MODELO_AUTO = "auto"`, `MARGEN_RENOVACION_AUTO` (300 s).

### Historial — `historial.py`

- `historial.py:Historial(ruta=None)` con `crear(archivo_ruta, resultado, modelo_whisper=None, titulo=None) -> int`,
  `guardar_documento(id_, tipo, contenido, modelo=None)`, `renombrar(id_, titulo)`, `eliminar(id_)`,
  `listar(busqueda="", limite=500)`, `obtener(id_)`.
- `historial.py:EntradaHistorial` — dataclass con la propiedad `archivo_existe` y el método `a_resultado()`.
- `historial.py:normalizar(texto)`, `historial.py:titulo_desde_minuta(minuta)`.
- Constantes: `RUTA_POR_DEFECTO` (`<raíz del proyecto>/data/historial.db`), `VERSION_ESQUEMA = 1`, `ESQUEMA`,
  `DOCUMENTOS = ("resumen", "minuta")`.

### Interfaz gráfica — `ui.py`, `ui_copilot.py`, `ui_historial.py`

- `ui.py:AppTranscriptor` — ventana principal. Métodos que usa `PanelHistorial`: `mostrar_vista(vista)`,
  `cargar_desde_historial(id_historial) -> bool`, `historial_eliminado(id_historial)`.
- `ui_copilot.py:DialogoLoginCopilot(master, enterprise_url, al_terminar)` — diálogo modal de login.
- `ui_historial.py:PanelHistorial(master, app, historial)` con `refrescar()`; `LIMITE_LISTA = 200`.
- `ui.py:DOCUMENTOS_IA` — define los sufijos `_resumen.md` y `_minuta.md`.

### Registro — `registro.py`

- `registro.py:configurar_logging(nivel=None)` y `registro.py:latido(descripcion, cada=15.0, logger=log)` (context manager).
- `VARIABLE_NIVEL = "TRANSCRIPTOR_LOG"`.

## Invariants

### Hilos e interfaz gráfica

- Los widgets solo se tocan desde el hilo principal. Los hilos de fondo pasan por `ui.py:AppTranscriptor._en_ui`,
  que usa `self.after(0, …)` y no hace nada si la ventana se está cerrando.
- Solo hay una transcripción a la vez (`ui.py:AppTranscriptor._transcribiendo`), y no se genera un documento de IA
  mientras se transcribe ni al revés (`ui.py:AppTranscriptor._generar_documento_ia`).
- La cancelación es cooperativa: un `threading.Event` (`cancelar_flag`) que `transcriber.py:TranscriptorAudio.transcribir`
  revisa tras cada segmento; al activarse, devuelve lo transcrito hasta ahí.
- `ui.py:AppTranscriptor._procesar_documento_ia` recibe el `id_historial` vigente al pulsar el botón, así que el
  documento se guarda en esa entrada aunque después se abra otra.
- Si `Historial` no se puede abrir, `self.historial` queda en `None` y la app sigue sin historial
  (`ui.py:AppTranscriptor.__init__`).

### Transcripción

- `utils.py:validar_archivo` lanza `FileNotFoundError` si la ruta no existe y `ValueError` si no es un archivo o su
  extensión no está en `EXTENSIONES_AUDIO` ni en `EXTENSIONES_VIDEO`.
- `transcriber.py:TranscriptorAudio.transcribir` usa siempre `vad_filter=True` con `min_silence_duration_ms=500`, y
  convierte `idioma == "auto"` en `language=None`.
- `transcriber.py:es_alucinacion_conocida` descarta un segmento solo si, en minúsculas y sin puntuación en los
  extremos, coincide entero con una frase de `ALUCINACIONES_CONOCIDAS`.
- `configuracion.py:guardar_modelo_ia` cambia solo la primera línea `modelo:` dentro del bloque `ia:` y conserva los
  comentarios; devuelve `False` si no la encuentra.
- `utils.py:guardar_transcripcion` lanza `ValueError` con un formato distinto de `txt`, `srt`, `vtt` o `json`.

### Configuración

- La CLI y la interfaz toman todos los valores de `configuracion.py:cargar_configuracion`, que devuelve el dict
  completo (las 21 claves con sus valores por defecto y validadas). No hay valores por defecto propios en `main.py` ni
  en `ui.py`. Un YAML con errores da `configuracion.py:ErrorConfiguracion`: la CLI sale con código 1 y
  `Error: <mensaje>` en `stderr` antes de cargar Whisper; la ventana muestra el mensaje en un diálogo y no arranca.
- Claves con valor `null` (por ejemplo `beam_size:` sin valor) se tratan como ausentes y toman su valor por defecto.
  Las claves desconocidas (incluidas `audio.*` y `transcripcion.task` de configuraciones antiguas) se ignoran sin error.
- En la CLI, `-l`, `-f`, `--no-timestamps` y `--word-timestamps` no tienen valor fijo: si no se pasan, valen
  `transcripcion.idioma`, `salida.formato`, `salida.incluir_timestamps` y `salida.palabra_por_palabra`. `-t` sigue con
  `transcribe` por defecto y no lee configuración. La interfaz lee esas claves y fija `task` en `"transcribe"`.
- La CLI no usa `AsistenteIA` ni `Historial`: no genera resumen ni minuta y no guarda en el historial.

### GitHub Copilot

- Orden de búsqueda del token en `copilot.py:leer_token`: variable `COPILOT_GITHUB_TOKEN`, luego `RUTA_TOKEN`, luego
  `RUTA_AUTH_OPENCODE` (clave `github-copilot`). Los archivos solo valen si su dominio coincide con el pedido; la
  variable de entorno no se compara con el dominio.
- `asistente_ia.py:AsistenteIA.__init__` lanza `ErrorSinSesionCopilot` si no hay token.
- `x-initiator`: la primera petición de cada documento va con `user` y las siguientes con `agent`
  (`asistente_ia.py:AsistenteIA._cabeceras`, `asistente_ia.py:AsistenteIA._generar`).
- `copilot.py:listar_modelos` acepta un modelo si `policy.state == "enabled"` o `model_picker_enabled`, si es de tipo
  `chat` y, cuando declara `supported_endpoints`, si incluyen `/chat/completions`.
- `copilot.py:modelos_economicos` descarta los modelos sin precio, con precio de entrada mayor que
  `PRECIO_MAX_ECONOMICO` o de `FAMILIAS_EXCLUIDAS`.
- `copilot.py:abrir_sesion_auto` elige el primer modelo ofrecido que admite `/chat/completions` y no es de una familia
  de `FAMILIAS_EXCLUIDAS`, y lanza `ErrorCopilot` si no queda ninguno. `copilot.py:SesionAuto.vigente` da la sesión por caducada 300 s antes de `expires_at`.
- `asistente_ia.py:AsistenteIA._completar` hace hasta 4 intentos con espera exponencial ante errores de red, 429 y
  5xx. Un 401 fuera del modo auto invalida el token guardado y lanza `ErrorSinSesionCopilot`.
- `copilot.py:invalidar_token` borra `RUTA_TOKEN` solo si el token guardado es el rechazado; nunca toca el archivo de
  opencode.

### Documentos generados

- Una transcripción vacía lanza `ErrorAsistenteIA` (`asistente_ia.py:AsistenteIA._generar`).
- Con más de un bloque, el documento se redacta a partir de notas por bloque, y la revisión de fidelidad compara
  contra esas notas, no contra la transcripción (`asistente_ia.py:AsistenteIA._generar`). Con dos o más partes, la app añade al final del documento una nota que lo advierte, y el progreso de la revisión nombra la fuente real (`asistente_ia.py:AsistenteIA._con_nota`).
- Si faltan secciones de `SECCIONES_RESUMEN` o `SECCIONES_MINUTA`, se hace un solo reintento, que se acepta solo si
  faltan menos que antes.
- La fecha de la minuta la pone la aplicación: `asistente_ia.py:AsistenteIA.generar_minuta` reescribe la línea
  `**Fecha:**` con la fecha recibida o con `No especificada`.

### Historial

- `historial.py:Historial.guardar_documento` solo admite `tipo` en `DOCUMENTOS`; si no, `ValueError`. Esa lista
  protege el nombre de columna, que se interpola en el SQL.
- Un título editado a mano no se reemplaza: el título tomado de la minuta se aplica solo donde `titulo_editado = 0`,
  y `historial.py:Historial.renombrar` pone `titulo_editado = 1`.
- `historial.py:Historial.renombrar` lanza `ValueError` si el título queda vacío.
- Una ruta relativa se resuelve contra `RAIZ_PROYECTO`, no contra el directorio de trabajo
  (`historial.py:Historial.__init__`).
- La búsqueda ignora mayúsculas y acentos (`historial.py:normalizar`) y cubre `titulo`, `archivo_nombre`, `texto`,
  `resumen` y `minuta` (`historial.py:Historial.listar`).
- No hay migraciones: `PRAGMA user_version` se fija en cada apertura sin comparar el valor anterior.

## Side Effects

### Red

- `POST https://<dominio o github.com>/login/device/code` — `copilot.py:iniciar_login`.
- `POST https://<dominio o github.com>/login/oauth/access_token`, en bucle — `copilot.py:esperar_login`.
- `GET <url_api>/models` — `copilot.py:listar_modelos` y `copilot.py:abrir_sesion_auto`.
- `POST <url_api>/models/session` — `copilot.py:abrir_sesion_auto`.
- `POST <url_api>/chat/completions` en streaming — `asistente_ia.py:AsistenteIA._completar`.
- `url_api` es `https://api.githubcopilot.com`, o `https://copilot-api.<dominio>` con GitHub Enterprise
  (`copilot.py:url_api`).
- Al arrancar la interfaz, `ui.py:AppTranscriptor._cargar_modelos_ia` consulta los modelos y abre una sesión auto.
- Descarga del modelo de Whisper la primera vez que se usa — `transcriber.py:TranscriptorAudio.modelo`.

### Disco

- `~/.local/share/transcriptor-audio/copilot.json`: se crea con modo `0o600` (`copilot.py:guardar_token`) y se borra
  en `copilot.py:cerrar_sesion` y `copilot.py:invalidar_token`.
- `~/.local/share/opencode/auth.json`: solo lectura (`copilot.py:leer_token`).
- `~/.cache/faster-whisper`: caché de modelos (`transcriber.py:TranscriptorAudio.__init__`).
- `config/settings.yaml`: lectura con `yaml.safe_load` (`configuracion.py:cargar_configuracion`) y reescritura de la
  línea `ia.modelo` al cambiar el modelo de IA (`configuracion.py:guardar_modelo_ia`). La ruta se resuelve contra
  `RAIZ_PROYECTO`, no contra el directorio de trabajo.
- Junto al audio: `<nombre>_transcripcion.<formato>` (`ui.py:AppTranscriptor._generar_ruta_salida`), y
  `<nombre>_resumen.md` y `<nombre>_minuta.md` (`ui.py:AppTranscriptor._procesar_documento_ia`).
- La CLI escribe en `stdout`, o en el archivo de `-o` mediante `utils.py:guardar_transcripcion`.

### Base de datos

- `historial.py:Historial.__init__` crea la carpeta de la base y ejecuta `CREATE TABLE IF NOT EXISTS transcripciones`
  y `CREATE INDEX IF NOT EXISTS idx_transcripciones_creado`.
- Columnas de `transcripciones`: `id`, `titulo`, `titulo_editado`, `archivo_nombre`, `archivo_ruta`, `creado_en`,
  `actualizado_en`, `duracion_segundos`, `idioma`, `probabilidad_idioma`, `modelo_whisper`, `texto`, `segmentos_json`,
  `resumen`, `resumen_modelo`, `resumen_en`, `minuta`, `minuta_modelo`, `minuta_en`.
- `INSERT` en `crear`, `UPDATE` en `guardar_documento` y `renombrar`, `DELETE` en `eliminar`. Cada operación abre su
  propia conexión.

### Procesos, hilos y sistema

- `ffprobe` mediante `ffmpeg.probe` (`utils.py:obtener_info_archivo`); es opcional: sin él, la carga sigue sin duración.
- `xdg-open`, `open` u `os.startfile` para abrir la carpeta de salida (`ui.py:AppTranscriptor._abrir_carpeta`).
- `webbrowser.open` y copia del código al portapapeles (`ui_copilot.py:DialogoLoginCopilot._abrir_github`).
- Hilos `daemon`: transcripción, generación de IA y consulta de modelos (`ui.py`), `login-copilot`
  (`ui_copilot.py`), `latido` (`registro.py:latido`) y un `ThreadPoolExecutor` `ia-parte`
  (`asistente_ia.py:AsistenteIA._notas_por_bloque`).
- `registro.py:configurar_logging` reemplaza los manejadores del logger raíz por uno a `stderr` y asigna
  `threading.excepthook`.

## Verification

- Run: `./venv/bin/python -m pytest -q` (los tests están en `../tests/`; `pytest` figura en `requirements-dev.txt`).
