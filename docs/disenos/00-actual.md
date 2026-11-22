# Arquitectura actual

> Status: as-is (no aprobado como diseño objetivo)
>
> Generado por /analizar (Tándem) el 2026-11-22 a partir de [EGM.md](../../EGM.md), [src/EGM.md](../../src/EGM.md),
> [README.md](../../README.md) y `.context/inventario.md`. Describe lo que el código hace hoy, no lo que debería hacer.
> Sincronizado con el código el 2026-11-22, tras cerrar las historias 01 a 07 y varios puntos de «Salud del código», y
> ampliado con los riesgos, la concurrencia y los datos y secretos (A-22).

## Resumen

Aplicación de escritorio en Python que transcribe audio y video en el propio equipo con faster-whisper y, cuando el
usuario lo pide, genera un resumen y una minuta enviando el texto transcrito a GitHub Copilot. Cada transcripción
terminada en la interfaz gráfica se guarda en un historial SQLite local, con su resumen y su minuta. Hay dos formas
de uso: una interfaz gráfica (CustomTkinter) y una CLI que transcribe, lista los modelos de Whisper y gestiona la
sesión de Copilot (iniciar y cerrar sesión, ver los modelos disponibles); con `--ui` también lanza la interfaz. Todo el
código está en un paquete, `src/`, de trece archivos y 4 009 líneas.

## Componentes

No hay subcarpetas con código: los componentes son módulos de `src/`. Todos se documentan en
[src/EGM.md](../../src/EGM.md).

| Componente | Módulos | Responsabilidad |
|---|---|---|
| Transcripción | `transcriber.py`, `utils.py` | Cargar el modelo de Whisper, transcribir con filtro de silencios y de alucinaciones, validar archivos, leer metadatos con `ffprobe` (opcionales), exportar a `txt`, `srt`, `vtt` o `json` con un solo serializador |
| Configuración | `configuracion.py` | Leer y validar `settings.yaml` contra la raíz del proyecto, con los valores por defecto en un solo lugar; la lista de modelos de Whisper; las preferencias del usuario (`preferencias.json`). La app no reescribe el YAML |
| Resumen y minuta | `asistente_ia.py` | Dividir el texto en bloques, sacar notas en paralelo, redactar el documento, reintentar secciones faltantes, revisar la fidelidad, normalizar la minuta y añadir las notas de la aplicación |
| Acceso a Copilot | `copilot.py` | Login por device flow, lectura y guardado del token, catálogo de modelos, filtro de modelos económicos y de familias no autorizadas, y sesión del modo `auto` |
| Persistencia | `persistencia.py` | Guardar sin interfaz una transcripción o un documento: primero el historial y después el archivo junto al audio; devuelve avisos en vez de lanzar |
| Historial | `historial.py` | Tabla `transcripciones` en SQLite: crear, guardar documentos, renombrar, eliminar, buscar |
| Interfaz gráfica | `ui.py`, `ui_copilot.py`, `ui_historial.py` | Ventana principal, diálogo de login y panel del historial |
| CLI | `main.py` | Transcribir a `stdout` o a un archivo; listar los modelos de Whisper; login, logout y lista de modelos de Copilot; lanzar la interfaz con `--ui` |
| Registro | `registro.py` | Configurar el logging y avisar cada cierto tiempo en operaciones largas (`latido`) |

Fuera de `src/`: `run_ui.py` (lanzador), `config/settings.yaml` (configuración) y `tests/` (once archivos `test_*.py` y `conftest.py`).

## Flujo de datos

Sin diagrama: los caminos se describen como pasos, cada uno con el símbolo que lo ejecuta.

### Transcribir desde la interfaz

1. El usuario elige o arrastra un archivo. `utils.validar_archivo` comprueba la extensión y
   `utils.obtener_info_archivo` lee los metadatos con `ffprobe`; sin `ffprobe`, o si falla, el archivo se carga igual,
   sin duración ni códec.
2. `AppTranscriptor._iniciar_transcripcion` lee las opciones en el hilo principal y lanza un hilo de fondo.
3. En ese hilo, `TranscriptorAudio.transcribir` procesa el audio con faster-whisper y entrega cada segmento a la
   interfaz mediante `on_segmento`.
4. Todavía en el hilo de fondo, `flujo_transcripcion.transcribir_y_persistir` (sin ventana) llama a
   `persistencia.persistir_transcripcion`, que guarda primero en el historial
   (`Historial.crear` inserta la fila en `transcripciones`) y después escribe
   `<archivo>.<ext>_transcripcion.<formato>` junto al audio con `utils.guardar_transcripcion`.
5. Un fallo del historial o de la exportación no descarta el resultado: vuelve como aviso y la ventana lo muestra
   en un diálogo de advertencia y en la pestaña Registro.

### Generar el resumen o la minuta

1. `AppTranscriptor._generar_documento_ia` crea un `AsistenteIA` con la sección `ia:` de la configuración y el modelo
   elegido (la preferencia guardada en `preferencias.json` o, si no hay, `ia.modelo`), y reutiliza esa instancia hasta
   que cambia el modelo, se cancela una generación o hace falta iniciar sesión de nuevo. Si no hay token, se abre
   `DialogoLoginCopilot` y, tras el login, se repite la petición.
2. En un hilo de fondo, `flujo_documentos.py:procesar_generacion` llama a `AsistenteIA.generar_resumen` o
   `generar_minuta` (vía `generar_documento`), que envían el texto a `POST <url_api>/chat/completions` en streaming.
3. Si el texto supera `max_caracteres_bloque`, primero se piden notas por bloque en paralelo y el documento se
   redacta a partir de esas notas. Antes de entregarlo, `AsistenteIA` pide de nuevo las secciones que falten, revisa la
   fidelidad si `ia.revision_fidelidad` está activa y añade al final las notas de la aplicación que apliquen
   (documento redactado a partir de notas, secciones que faltan, pasadas que no se pudieron completar).
4. Mientras dura la generación, el botón de la pestaña es «■ Cancelar»: `AppTranscriptor._cancelar_documento_ia`
   devuelve la ventana al instante y deja abandonado el hilo de fondo, cuyo resultado se descartará.
5. Al terminar, `procesar_generacion` entrega el resultado una sola vez al hilo principal (`AppTranscriptor._recibir_documento_ia`,
   vía `_en_ui`), que pasa el resultado a `GestorDocumentos.recibir`: único punto que decide si sigue vigente y guarda. Si lo está, `flujo_documentos.py:GestorDocumentos.recibir` (con
   `persistencia.persistir_documento`) guarda primero en el historial: `Historial.guardar_documento` guarda el documento y el modelo usado y, con la minuta, también
   actualiza el título si no se editó a mano. Solo se guarda si el historial se abrió y la entrada de la transcripción
   sigue existiendo; si no, el documento no se descarta y el aviso dice por qué.
6. Después el resultado se escribe en `<archivo>.<ext>_resumen.md` o `<archivo>.<ext>_minuta.md` junto al audio, si el audio
   existe. Un fallo de guardado no descarta el documento: se avisa en la línea de estado de la pestaña y en Registro.

### Iniciar sesión en Copilot

1. `copilot.iniciar_login` pide un código a `/login/device/code`.
2. El usuario introduce el código en GitHub.
3. `copilot.esperar_login` consulta `/login/oauth/access_token` hasta recibir el token y `copilot.guardar_token` lo
   escribe en `~/.local/share/transcriptor-audio/copilot.json`.

### Transcribir desde la CLI

`main.main` valida el archivo, carga la configuración con `configuracion.cargar_configuracion` y comprueba que `srt` y
`vtt` tengan un archivo de salida (`-o`), todo antes de cargar Whisper. Después transcribe con
`TranscriptorAudio.transcribir` y escribe en `stdout` (solo `txt` y `json`) o en el archivo de `-o`, con el mismo
serializador (`utils.serializar_transcripcion`). No genera resumen ni minuta y no guarda en el historial.

## Dependencias externas

| Dependencia | Para qué | Dónde |
|---|---|---|
| faster-whisper (y `av`, fijado a 18.1.1: PyAV 19 quitó `metadata_errors`) | Transcripción local | `transcriber.py` |
| `ffprobe` (binario, opcional) y `ffmpeg-python` | Metadatos del archivo (duración, códec); el binario `ffmpeg` no se ejecuta | `utils.py` |
| CustomTkinter, Tkinter, `tkinterdnd2-universal` | Interfaz gráfica y arrastrar y soltar | `ui*.py` |
| httpx | Llamadas a GitHub y a Copilot | `copilot.py`, `asistente_ia.py` |
| PyYAML | Leer la configuración | `configuracion.py` |
| SQLite (biblioteca estándar) | Historial | `historial.py` |
| GitHub (`github.com`) | Login por device flow, con el `client_id` de opencode | `copilot.py` |
| API de Copilot (`api.githubcopilot.com`) | `/models`, `/models/session`, `/chat/completions` | `copilot.py`, `asistente_ia.py` |
| Descarga de modelos (la hace faster-whisper con `huggingface_hub`; el repositorio exacto no se verificó aquí) | Primera carga de cada modelo de Whisper | `transcriber.py` |

Las dependencias están fijadas con `==` en `requirements.txt` (y `pytest`, en `requirements-dev.txt`). No hay lockfile de las transitivas.

## Modelo de concurrencia

Tk no es seguro entre hilos, así que todo el trabajo largo corre fuera del hilo principal y solo entrega resultados
a él. Los hilos de trabajo que crea la app son `daemon`: no impiden cerrar el proceso. La excepción son los del
`ThreadPoolExecutor` de las notas de las partes, que no lo son pero se esperan dentro de la misma llamada.

- **Hilo principal (Tk).** Es el único que toca widgets, el historial en pantalla y los archivos de resultado de una
  generación. Regla de oro 9: un hilo de fondo no llama a un widget, sino a `AppTranscriptor._en_ui(funcion, *args)`,
  que usa `self.after(0, …)` y no hace nada si la ventana se está cerrando (`_cerrando`). `_log` y `_actualizar_estado`
  ya pasan por ahí. El diálogo de login tiene su propio `_en_ui`.
- **Hilo de la transcripción.** Uno solo a la vez (`_transcribiendo` mira si sigue vivo). Las opciones se leen en el
  hilo principal antes de lanzarlo. Llama a `flujo_transcripcion.py:transcribir_y_persistir`, que elige el transcriptor (`transcriptor_para`), carga el
  modelo, transcribe (`transcribir`) y, todavía en ese hilo, llama a `persistir_transcripcion`; después entrega el
  resultado con `_en_ui`. Se cancela con un `threading.Event`
  (`cancelar_flag`) que `TranscriptorAudio.transcribir` revisa tras cada segmento aceptado.
- **Hilo de fondo por generación de IA.** Cada resumen o minuta crea un `flujo_documentos.py:Generacion` con su propia
  señal de cancelación (`cancelar`) y un hilo que ejecuta `flujo_documentos.py:procesar_generacion`: solo llama a
  `AsistenteIA`, no toca widgets, historial ni archivos, y entrega lo que obtiene (o el error) una sola vez con
  `_en_ui(_recibir_documento_ia, …)`. El punto de decisión es único y está en el hilo
  principal: `GestorDocumentos.recibir` comprueba si la generación recibida sigue siendo la vigente (por identidad); si no
  (se canceló), la descarta, no guarda nada y no toca el asistente; si lo es, guarda o devuelve el error. `_recibir_documento_ia`
  solo pinta según el estado. Solo hay una generación a la vez, y no se genera mientras se
  transcribe ni al revés. Al cancelar, la señal de esa generación se activa y la siguiente usa otra, así que el hilo
  abandonado no afecta a la nueva.
- **Notas de las partes en paralelo.** `AsistenteIA._notas_por_bloque` lanza un `ThreadPoolExecutor`
  (`ia-parte`, hasta `ia.peticiones_paralelas` hilos) que se cierra dentro de la misma llamada. Un cerrojo
  (`_cerrojo_cache`) protege la caché de notas, el diccionario de notas de la generación y el progreso; otros dos
  protegen la marca de `x-initiator` (`_cerrojo_iniciador`) y la sesión `auto` compartida (`_cerrojo_auto`). Si una
  parte falla, un `Event` (`abortar`) y la cancelación de los futuros evitan enviar las que aún no empezaron.
- **Otros hilos.** La consulta del catálogo de modelos («↻»), el inicio de sesión (`login-copilot`, con su propio
  `Event` de cancelación) y un hilo `latido` por cada operación larga, que solo registra en el log.
- **SQLite.** `Historial` abre una conexión por operación (`sqlite3.connect(..., timeout=10)`) y la cierra al
  terminar, así que lo pueden usar el hilo principal y el de la transcripción sin compartir conexiones. No hay otro
  control de concurrencia: dos escrituras a la vez se serializan por el bloqueo de SQLite, que espera hasta 10 s.
- **Cierre de la ventana.** Con una transcripción o una generación en curso se pregunta; si se acepta, se activan sus
  señales de cancelación y se cierra. Los hilos `daemon` mueren con el proceso.

## Datos y secretos

### Qué se guarda y dónde

| Dato | Dónde | Permisos y notas |
|---|---|---|
| Token de GitHub Copilot | `~/.local/share/transcriptor-audio/copilot.json` (`token` y `enterprise_url`) | Se crea con modo `0o600` (`copilot.guardar_token`); en claro; el modo solo se fija al crear el archivo. Lo borran `--copilot-logout` y un 401 del token propio |
| Preferencias del usuario | `~/.local/share/transcriptor-audio/preferencias.json` (`modelo_ia`) | Permisos por defecto; solo guarda un nombre de modelo |
| Historial | `data/historial.db` (SQLite; `historial.ruta`, relativa a la raíz del proyecto) | Permisos por defecto, sin cifrar. Guarda el texto completo, los segmentos con marcas de tiempo, el resumen, la minuta, los títulos, la ruta absoluta del audio y los modelos usados |
| Resultados junto al audio | `<archivo>.<ext>_transcripcion.<formato>`, `<archivo>.<ext>_resumen.md`, `<archivo>.<ext>_minuta.md` en la carpeta del audio | Permisos por defecto. Regenerar la misma grabación las sobrescribe sin preguntar |
| Caché de modelos de Whisper | `~/.cache/faster-whisper` | Solo modelos, ningún dato del usuario |
| Log | Solo la consola (`stderr`); la app no escribe ningún archivo de log | Con `TRANSCRIPTOR_LOG=DEBUG` la consola muestra cada segmento transcrito |

El token se busca en este orden (`copilot.leer_token`): la variable de entorno `COPILOT_GITHUB_TOKEN`, el archivo
propio y la sesión de opencode (`~/.local/share/opencode/auth.json`, clave `github-copilot`, solo lectura). Los dos
archivos solo valen si su dominio (github.com o el de GitHub Enterprise) coincide con el pedido; la variable de entorno
no se compara. La app nunca modifica el archivo de opencode. `config/settings.yaml` no contiene secretos y la app solo
lo lee.

### Qué sale del equipo

- **Nunca el audio.** La transcripción se hace en local con faster-whisper.
- **Solo texto, y solo a GitHub Copilot.** Al generar un resumen o una minuta se envían a
  `POST <url_api>/chat/completions` el texto de la transcripción (los segmentos unidos con saltos de línea), las notas de
  cada parte, el documento redactado cuando se pide una corrección o una revisión, y la fecha de la minuta. El token va
  en la cabecera `Authorization`. El texto solo va a modelos autorizados: los de `FAMILIAS_EXCLUIDAS` no reciben nada,
  tampoco en modo `auto` ni con un modelo escrito a mano.
- **Cuándo hay tráfico de red.** Al abrir la ventana, ninguno: no se lee el token ni se consulta Copilot. Después, solo
  por una acción del usuario: «↻» (una consulta `GET /models`), iniciar sesión (`POST /login/device/code` y consultas
  a `/login/oauth/access_token`), generar un documento (`/chat/completions`; en modo `auto`, también
  `POST /models/session` y `GET /models`) y la primera carga de cada modelo de Whisper (descarga por
  faster-whisper). En la CLI, `--copilot-login`, `--copilot-modelos` (que también abre una sesión `auto`) y la primera
  carga de cada modelo; `--copilot-logout` y `--listar-modelos` no usan la red.
- **Sin telemetría propia.** El único `client_id` del código es el de opencode, que es público (el device flow no usa
  secreto).

### Qué nunca se versiona (regla de oro 8)

Grabaciones, transcripciones, resúmenes, minutas, el historial y el token. Lo cubre `.gitignore`: las extensiones
de audio y video que admite `utils.py`, `*_resumen.md`, `*_minuta.md`, `*.txt`, `*.srt`, `*.vtt`, `*.json`, `data/`,
`*.db`, `*.sqlite*`, `*.log` y `.env`. El token y las preferencias viven fuera de la carpeta del proyecto. Los
`*.json` y `*.txt` se ignoran de forma global (con excepciones para `README.md`, `requirements*.txt` y
`config/settings.yaml`): un JSON o un TXT nuevo del proyecto queda fuera del repositorio sin aviso. No se ha
comprobado que los commits anteriores estén libres de secretos.

## Cómo se prueba

- Comando: `./venv/bin/python -m pytest -q`, **desde la raíz del repositorio**: el paquete `src` debe poder
  importarse.
- Estado al 2026-11-22: **268 tests en verde** con Python 3.14.10 en Linux (`pytest` 9.2.0, fijado en
  `requirements-dev.txt`; instalar con `pip install -r requirements-dev.txt`).
- Hay 234 funciones de test (el resto son casos parametrizados) en once archivos `test_*.py` de `tests/`, más
  `conftest.py`. No hacen llamadas reales a la red (`httpx` se simula), no cargan ningún modelo de Whisper (el doble
  `modelo_whisper_falso` sustituye al modelo) ni abren ventanas. Las rutas del token y las preferencias se aíslan en
  carpetas temporales (`rutas_aisladas` en `tests/test_copilot.py`, `preferencias_aisladas` en `tests/conftest.py`).
- `tests/test_ui.py` importa `src.ui`, así que necesita que Tkinter y CustomTkinter se puedan importar, aunque no
  abra una ventana.
- No hay CI, linter ni comprobación de tipos.

## Riesgos y límites actuales

Lo que sigue es cierto hoy y se conoce; cada riesgo indica, si lo hay, el punto de `BACKLOG.md` que lo trata.

- **API no documentada de Copilot.** La integración replica la de opencode: usa su `client_id`, el token de GitHub
  directamente como `Bearer` y endpoints que GitHub no documenta oficialmente (`/chat/completions`, `/models` y
  `/models/session`); `API_VERSION` está fijo en `copilot.py`. GitHub puede cambiarlos sin aviso. Riesgo aceptado (A-14);
  no se admiten otros proveedores.
- **Cancelar una transcripción descarta lo transcrito.** `transcribir` devuelve lo hecho hasta ahí, pero la ventana
  lo descarta: no se guarda en el historial ni en un archivo. Además, la señal solo se revisa tras cada segmento
  aceptado, no durante la carga del modelo ni la preparación del audio (VAD e idioma), que pueden tardar. Sin punto en el
  backlog.
- **Una generación cancelada deja su petición abierta.** La ventana se libera al instante, pero la petición a Copilot no
  se aborta: el hilo abandonado se detiene al recibir la siguiente línea de la respuesta o al agotarse la espera de
  lectura (`AsistenteIA.timeout`, 180 s sin datos), y su resultado se descarta sin guardarlo. La petición ya enviada
  no se retira. Sin punto en el backlog.
- **Las notas conservadas viven en memoria.** Si una parte falla, las notas de las que terminaron se reutilizan al
  volver a generar, pero solo mientras viva la misma instancia de `AsistenteIA` con el mismo modelo (hasta 64 partes): se
  pierden al cancelar, al cambiar de modelo, al volver a iniciar sesión y al cerrar la app. Sin punto en el backlog.
- **La revisión de fidelidad con varias partes se hace contra las notas, no contra la transcripción.** Un dato que se
  coló al extraer las notas no se detecta, y el documento lo avisa con una nota de la aplicación.
  `ia.revision_fidelidad` viene desactivada en el YAML. Backlog, Salud del código #23.
- **Un documento truncado puede parecer completo.** Si Copilot corta la respuesta por longitud, solo queda un aviso en el
  log; el documento no lo dice. Tampoco se avisa antes de redactar si las notas de todas las partes superan el límite de
  entrada del modelo. Backlog, Salud del código #25 y #26.
- **La exclusión de familias es por nombre.** `FAMILIAS_EXCLUIDAS` (`kimi`, `mistral`, `codestral`, `devstral`, `ministral`,
  `pixtral`, `magistral`) se reconoce porque el id del modelo contiene el nombre; un modelo nuevo de Mistral AI cuyo
  nombre no contenga ninguno de esos textos no se excluye, y la lista se amplía a mano en `copilot.py`.
- **Solo el pintado de la ventana no tiene tests automáticos.** Ningún test instancia `AppTranscriptor`: `_recibir_documento_ia`,
  la cancelación y el cierre de la ventana solo se verifican a mano. Los flujos de transcripción y de documentos
  (`flujo_transcripcion.py`, `flujo_documentos.py`, con `GestorDocumentos.recibir`) y `AsistenteIA` se prueban sin ventana, y
  también `persistencia.py`.
- **La orquestación ya no vive en la clase Tk.** Transcribir y generar están en `flujo_transcripcion.py` y
  `flujo_documentos.py`, con su estado en `GestorDocumentos`; `AppTranscriptor` solo lanza, pinta y entrega. `historial.py` importa `transcriber.py` (solo las dataclasses; `faster_whisper`
  se carga al construir el modelo, historia 08). Backlog, Salud del código #5.
- **El historial no tiene migraciones.** `PRAGMA user_version` se fija en cada apertura sin comparar el valor anterior:
  el primer cambio de esquema tendrá que resolverlo (hallazgo A-23, descartado por ahora). La búsqueda del historial corre
  en el hilo de la interfaz y podría notarse con cientos de reuniones (A-18, pospuesto).
- **Entorno verificado: solo Python 3.14 en Linux.** El README declara «3.10 o superior (probado con 3.12)», pero los
  tests solo se han ejecutado con 3.14.10. Windows y macOS no se han probado. No hay lockfile de las transitivas, CI,
  linter ni comprobación de tipos.

## Huecos conocidos

- **Tests solo verificados en Python 3.14.** Pasan con 3.14.10 en Linux; el README dice «probado con 3.12» y no se ha comprobado con otras versiones.
- **Comportamiento real de la API de Copilot.** Lo documentado sale del código, no de llamadas reales: no se probó
  el login, el catálogo de modelos, el modo `auto` ni la generación.
- **Interfaz gráfica sin ejecutar.** Los atajos, los estados de los botones y el diseño se leyeron en el código.
- **Contenido de los prompts.** `PROMPT_SISTEMA` y los demás se identificaron, pero sus reglas de fidelidad no se
  contrastaron con salidas reales.
- **Tests no documentados.** `tests/` queda fuera de los contratos por diseño del flujo.
- **El YAML y el código usan valores por defecto distintos para la IA.** `settings.yaml` trae `claude-haiku-5.5`,
  `temperatura: 0.2` y `revision_fidelidad: false`; sin esas claves, `configuracion.py` usa `gpt-4.1`, `0.2` y `False`
  (los mismos valores que el YAML), y los parámetros de `AsistenteIA` siguen en `0.3` y `True`. Los valores por defecto de
  las claves viven solo en `configuracion.py`.
- **`condition_on_previous_text`.** El YAML y `configuracion.py` lo ponen en `false`; el valor por defecto del parámetro
  de `transcribir` es `True`, que ni la interfaz ni la CLI usan porque siempre pasan el de la configuración.
