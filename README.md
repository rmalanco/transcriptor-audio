# Transcriptor de audio y video

App de escritorio en Python que **transcribe audio y video en local** con
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) y genera un **resumen** y una **minuta** de la
reunión con los modelos de **GitHub Copilot**.

- El audio nunca sale de tu equipo: la transcripción se hace en local. Solo el texto transcrito se envía a
  Copilot, y únicamente cuando pides un resumen o una minuta.
- Interfaz gráfica (CustomTkinter) con arrastrar y soltar, historial con búsqueda, una vista de configuración y
  línea de comandos.
- Salida en `txt`, `srt`, `vtt` o `json`.

## Requisitos

- Python 3.10 o superior (probado con 3.12)
- [ffmpeg](https://ffmpeg.org/) en el `PATH`
- Tkinter (en Ubuntu/Debian: `sudo apt install python3-tk`)
- Para resumen y minuta: una cuenta de GitHub con [Copilot](https://github.com/features/copilot) (sirve el plan Free)

## Instalación

```bash
git clone https://github.com/<tu-usuario>/transcriptor-audio.git
cd transcriptor-audio

python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# ffmpeg
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS:         brew install ffmpeg
# Windows:       winget install ffmpeg
```

Para desarrollo y tests, instala en su lugar `pip install -r requirements-dev.txt` (incluye las dependencias de
ejecución y `pytest`, fijado a la misma versión con la que pasan los tests).

La primera transcripción descarga el modelo de Whisper elegido (de 39 MB a 1.6 GB) en
`~/.cache/faster-whisper`; las siguientes ya no necesitan red.

## Uso

### Interfaz gráfica (recomendado)

```bash
# Lanzar UI de escritorio
python run_ui.py

# O desde el módulo
python -m src.ui
```

La interfaz permite:
- Arrastrar y soltar archivos de audio/video
- Seleccionar modelo, idioma y formato de salida
- Ver progreso en tiempo real
- Guardar transcripciones automáticamente
- Moverse entre las tres vistas de la barra del encabezado: **Transcribir** (`Ctrl+1`), **Historial** (`Ctrl+2`) y
  **⚙ Configuración** (`Ctrl+3`)
- Cambiar los valores por defecto sin editar ningún archivo (ver [Configuración](#configuración))

### Línea de comandos

```bash
# Transcribir un archivo
python -m src.main archivo.mp4 --modelo base --idioma es

# Transcribir con salida a archivo
python -m src.main video.mp4 -o transcripcion.txt --modelo small

# Ver modelos disponibles
python -m src.main --listar-modelos
```

## Resumen y minuta con IA

Tras transcribir, las pestañas **Resumen** y **Minuta** generan esos documentos con los modelos de
**GitHub Copilot** (sección `ia:` de `config/settings.yaml`, que puedes ajustar en la vista Configuración). Se guardan automáticamente junto al audio como
`<archivo>.<ext>_resumen.md` y `<archivo>.<ext>_minuta.md` (por ejemplo `reunion.m4a_minuta.md`).

La transcripción se envía a GitHub Copilot; el audio nunca sale de tu equipo. Al arrancar, la app no se conecta a
Copilot ni lee el token: solo lo hace al pulsar «↻» junto al selector de modelo (una consulta al catálogo), al
iniciar sesión y al generar un resumen o una minuta. Mostrar la vista Configuración lee la sesión guardada en el disco
(para decir de dónde sale), pero no hace ninguna petición de red.

La integración replica la de [opencode](https://opencode.ai): inicio de sesión con el *device flow* de OAuth
de GitHub y llamadas a la API de Copilot (`api.githubcopilot.com`, compatible con OpenAI). Detalles técnicos,
hallazgos y fuentes en [docs/integracion-copilot.md](docs/integracion-copilot.md).

- **Iniciar sesión:** al pulsar «Generar» por primera vez se abre un diálogo con un código; se introduce en
  github.com/login/device y la sesión se detecta sola. También con el botón «Iniciar sesión» de la vista
  Configuración, o desde la terminal: `python -m src.main --copilot-login`.
- **Modelos disponibles** para tu cuenta: `python -m src.main --copilot-modelos`. El modelo que eliges en el selector
  se recuerda en `~/.local/share/transcriptor-audio/preferencias.json`, no en `settings.yaml`; `ia.modelo` es solo el
  valor por defecto.
  Los modelos "premium" consumen peticiones premium de la licencia; `gpt-4.1` está incluido sin coste extra.
  Cada documento cuenta como una petición del usuario; los pasos internos (partes, reintentos, revisión) se
  marcan como automáticos (`x-initiator: agent`), igual que en opencode.
- **Modo `auto`**: como la opción "Auto" de VS Code, Copilot ofrece los modelos disponibles en ese momento y
  descuenta un 10 % de las peticiones premium. La app usa el primero que admite `/chat/completions` (los que
  solo funcionan por `/responses`, como los `*-codex`, se saltan). El modelo usado aparece en la pestaña y se
  guarda en el historial como `auto → <modelo>`. La sesión dura 1 h y se renueva sola.
- **Token:** se guarda en `~/.local/share/transcriptor-audio/copilot.json` (permisos 600). Orden de búsqueda: variable
  `COPILOT_GITHUB_TOKEN`, sesión propia de la app (`copilot.json`) y sesión de Copilot de opencode
  (`~/.local/share/opencode/auth.json`). Cerrar sesión: botón «Cerrar sesión» de la vista Configuración o
  `python -m src.main --copilot-logout`; las dos formas solo borran la sesión guardada por la app (`copilot.json`).
- **GitHub Enterprise** con dominio propio (`empresa.ghe.com`): indícalo en `ia.copilot_enterprise_url` o en el campo
  «Dominio de GitHub Enterprise» de la vista Configuración.

## Historial

Cada transcripción terminada se guarda automáticamente en una base de datos SQLite
(`data/historial.db`, configurable en la sección `historial:` de `config/settings.yaml` o en la vista
Configuración) con:
título, nombre y ruta del archivo, fecha, duración, idioma, modelo de Whisper, texto con marcas
de tiempo, y el resumen y la minuta con el modelo de IA que los generó.

- **Título:** por defecto es el nombre del archivo; al generar la minuta se toma el suyo.
  Se puede editar en la pestaña Texto o en el historial (un título editado a mano ya no se reemplaza).
- **Vista 📚 Historial** (barra de navegación del encabezado, que tiene tres vistas, o `Ctrl+2`; `Ctrl+1` vuelve a
  Transcribir):
  buscar (sin distinguir mayúsculas ni acentos) en títulos, archivos, textos, resúmenes y minutas;
  ver el detalle; abrir una entrada (doble clic) para seguir trabajando con ella; o eliminarla.
  Todo ocurre dentro de la misma ventana.
- Si el audio original ya no existe, la entrada se puede abrir y regenerar su resumen o minuta,
  que entonces solo se guardan en el historial.

## Log por consola

La app escribe en la terminal (stderr) qué está haciendo: carga o descarga del modelo, preparación del
audio (VAD e idioma), avance cada 10 % con la velocidad (×tiempo real), peticiones a la IA con su
duración y tokens, reintentos y errores. Mientras un paso largo sigue en curso aparece un aviso
periódico `… (lleva N s)`, así se ve en qué paso está esperando.

```bash
python run_ui.py                          # nivel INFO
TRANSCRIPTOR_LOG=DEBUG python run_ui.py   # además cada segmento transcrito y cada petición HTTP
python -m src.main audio.m4a --log DEBUG  # en la CLI: --log o -v
```

## Modelos disponibles

| Modelo | Tamaño | Velocidad | Precisión |
|--------|--------|-----------|-----------|
| tiny   | 39 MB  | ~32x      | Baja      |
| base   | 74 MB  | ~16x      | Media     |
| small  | 244 MB | ~6x       | Buena     |
| medium | 769 MB | ~2x       | Muy buena |
| large-v3-turbo | 1.6 GB | ~1x en CPU (medido: 1.1x con 4 núcleos) | Mejor · **por defecto** |

Medido sobre una reunión real de 27 min en español (CPU de 4 núcleos, int8): `base` transcribe
a ~6x tiempo real pero confunde nombres y términos; `large-v3-turbo`
va a ~1x y los acierta. Para ir más rápido con calidad aceptable, usa `small` (~3.4x).

También se aceptan `large-v1`, `large-v2` y `large-v3` (`-m large-v3` en la CLI). No existe un modelo `large` sin
versión. La lista completa la muestra `python -m src.main --listar-modelos`.

## Configuración

Los valores por defecto salen de dos sitios:

- **`config/settings.yaml`** (el del proyecto, versionado): modelo de Whisper, idioma, formato de salida, modelo de
  Copilot, etc. Cada opción está comentada en el propio archivo. La CLI y la ventana leen ese mismo archivo desde
  cualquier carpeta; en la CLI, las opciones de la línea de órdenes (`-l`, `-f`, `--no-timestamps`…) ganan a lo que
  diga el YAML. Si el YAML tiene un error, la CLI lo muestra en la terminal y no transcribe; la ventana lo muestra en
  un diálogo y no arranca.
- **Vista «⚙ Configuración»** (barra del encabezado o `Ctrl+3`): cambia esos valores sin editar el YAML. Lo que
  guardas va a `~/.local/share/transcriptor-audio/preferencias.json`, fuera del repositorio, y al abrir la ventana
  gana a lo que diga el YAML. `config/settings.yaml` no se modifica nunca.

La vista tiene cuatro grupos; debajo de cada campo se ve la clave del YAML que cambia:

| Grupo | Campos |
|---|---|
| Transcripción | Modelo de Whisper, idioma, dispositivo y precisión; un bloque plegado «▶ Avanzado» con los parámetros de decodificación (haz de búsqueda, candidatos, temperatura, umbrales…) |
| Salida | Formato de salida, marcas de tiempo y marcas por palabra |
| IA | Sesión de GitHub Copilot (ver abajo), modelo de IA, dominio de GitHub Enterprise y revisión de fidelidad; un «▶ Avanzado» con la temperatura de la IA, los caracteres por parte y las partes a la vez |
| Historial | Archivo del historial |

- **Guardar** valida los campos que has cambiado: si alguno no es válido, no se guarda nada, cada error aparece bajo
  su campo (con un «Avanzado» plegado, se despliega solo) y la vista va al primero. Si todo está bien, solo se guarda
  lo que difiere del YAML. Los valores del panel tienen topes que el YAML no tiene (por ejemplo, «Haz de búsqueda» va
  de 1 a 20); un valor del YAML fuera de esos topes no impide guardar otro campo.
- **Los cambios valen para la ventana, no para la CLI**, que sigue leyendo solo el YAML y las opciones de la línea de
  órdenes.
- **No se puede guardar ni restablecer** mientras hay una transcripción o una generación en curso, una consulta de
  «↻» o el diálogo de inicio de sesión abierto: el pie de la vista dice cuál es el motivo.
- **Restablecer valores del proyecto** vuelve a lo que dice `config/settings.yaml` tras pedir confirmación: borra lo
  guardado desde la vista y también el modelo de IA elegido. El resto de lo que pudiera haber en `preferencias.json`
  se conserva.
- **El archivo del historial se aplica al reiniciar la app**: hasta entonces la ventana sigue usando el historial
  anterior.
- **El panel lateral «Opciones» sigue siendo para esta transcripción**: lo que cambias ahí (modelo de Whisper,
  idioma, formato…) no se guarda ni modifica los valores por defecto; la excepción es el selector del modelo de IA, que
  se recuerda. Al guardar desde la vista Configuración, solo cambian en el panel lateral los controles de los ajustes
  que cambiaste.
- **Preferencias con errores:** si un valor de `preferencias.json` no es válido (editado a mano, por ejemplo), la
  ventana abre igual con el valor del YAML y muestra un recuadro de avisos arriba de la vista y en Registro.
- **Modelo de IA:** es el mismo que el selector «Modelo de IA» del panel lateral (con su «↻») y se guarda en la misma
  preferencia (`modelo_ia`). Un modelo de una familia no autorizada por la empresa se avisa en rojo y no se puede guardar.
- **Sesión de GitHub Copilot:** el primer elemento del grupo IA dice de dónde sale la sesión (ninguna, la de esta
  app, la de opencode o la variable `COPILOT_GITHUB_TOKEN`) sin conectarse a la red ni mostrar el token. «Iniciar
  sesión» abre el mismo diálogo que al generar; «Cerrar sesión» pide confirmación y **solo borra la sesión guardada
  por la app** (`copilot.json`): no toca la sesión de opencode ni la variable de entorno. Si cambias el dominio de
  GitHub Enterprise sin guardarlo, los dos botones se deshabilitan hasta que guardes.

## Privacidad y datos locales

Nada de lo siguiente se sube al repositorio. El historial y los archivos exportados junto al audio están en
`.gitignore`; el token, las preferencias y los modelos de Whisper se guardan fuera de la carpeta del proyecto:

| Dato | Dónde se guarda |
|---|---|
| Historial (transcripciones, resúmenes, minutas) | `data/historial.db` (en `.gitignore`) |
| Transcripciones exportadas | junto al archivo de audio (`.txt`, `.srt`, `.vtt`, `.json`; en `.gitignore`) |
| Resumen y minuta exportados | junto al archivo de audio (`<archivo>.<ext>_resumen.md`, `<archivo>.<ext>_minuta.md`; en `.gitignore`) |
| Token de GitHub Copilot | `~/.local/share/transcriptor-audio/copilot.json` (permisos 600, fuera del repo) |
| Preferencias (lo guardado en la vista Configuración y el modelo de IA elegido) | `~/.local/share/transcriptor-audio/preferencias.json` (fuera del repo) |
| Modelos de Whisper | `~/.cache/faster-whisper` (fuera del repo) |

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Ejecuta el comando desde la raíz del repositorio. Los tests no hacen llamadas reales a la red, no cargan ningún
modelo de Whisper ni abren ventanas: las peticiones a GitHub se simulan y la transcripción usa un doble del modelo.

## Aviso

Proyecto independiente, sin relación con GitHub ni con Microsoft. Usa la API de Copilot igual que lo hace
[opencode](https://opencode.ai) (incluido su `client_id` público de OAuth), que no es una API documentada
oficialmente y puede cambiar. Su uso está sujeto a los
[términos de GitHub Copilot](https://docs.github.com/es/site-policy/github-terms/github-terms-for-additional-products-and-features#github-copilot).

## Licencia

[MIT](LICENSE) © 2026 Rafael Malanco
