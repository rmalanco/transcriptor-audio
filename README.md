# Transcriptor de Audio/Video a Texto

Sistema base para transcribir archivos de audio y video usando faster-whisper.

## Instalación

```bash
# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar ffmpeg (requerido)
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg
```

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
**GitHub Copilot** (sección `ia:` de `config/settings.yaml`). Se guardan automáticamente junto al audio como
`<archivo>_resumen.md` y `<archivo>_minuta.md`.

La transcripción se envía a GitHub Copilot; el audio nunca sale de tu equipo.

La integración replica la de [opencode](https://opencode.ai): inicio de sesión con el *device flow* de OAuth
de GitHub y llamadas a la API de Copilot (`api.githubcopilot.com`, compatible con OpenAI). Detalles técnicos,
hallazgos y fuentes en [docs/integracion-copilot.md](docs/integracion-copilot.md).

- **Iniciar sesión:** al pulsar «Generar» por primera vez se abre un diálogo con un código; se introduce en
  github.com/login/device y la sesión se detecta sola. Desde la terminal: `python -m src.main --copilot-login`.
- **Modelos disponibles** para tu cuenta: `python -m src.main --copilot-modelos`. El elegido va en `ia.modelo`.
  Los modelos "premium" consumen peticiones premium de la licencia; `gpt-4.1` está incluido sin coste extra.
  Cada documento cuenta como una petición del usuario; los pasos internos (partes, reintentos, revisión) se
  marcan como automáticos (`x-initiator: agent`), igual que en opencode.
- **Modo `auto`**: como la opción "Auto" de VS Code, Copilot ofrece los modelos disponibles en ese momento y
  descuenta un 10 % de las peticiones premium. La app usa el primero que admite `/chat/completions` (los que
  solo funcionan por `/responses`, como los `*-codex`, se saltan). El modelo usado aparece en la pestaña y se
  guarda en el historial como `auto → <modelo>`. La sesión dura 1 h y se renueva sola.
- **Token:** se guarda en `~/.local/share/transcriptor-audio/copilot.json` (permisos 600). También se usa la
  variable `COPILOT_GITHUB_TOKEN` o la sesión de Copilot de opencode si ya existe. Cerrar sesión:
  `python -m src.main --copilot-logout`.
- **GitHub Enterprise** con dominio propio (`empresa.ghe.com`): indícalo en `ia.copilot_enterprise_url`.

## Historial

Cada transcripción terminada se guarda automáticamente en una base de datos SQLite
(`data/historial.db`, configurable en la sección `historial:` de `config/settings.yaml`) con:
título, nombre y ruta del archivo, fecha, duración, idioma, modelo de Whisper, texto con marcas
de tiempo, y el resumen y la minuta con el modelo de IA que los generó.

- **Título:** por defecto es el nombre del archivo; al generar la minuta se toma el suyo.
  Se puede editar en la pestaña Texto o en el historial (un título editado a mano ya no se reemplaza).
- **Vista 📚 Historial** (barra de navegación del encabezado, o `Ctrl+2`; `Ctrl+1` vuelve a Transcribir):
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
| large  | 1550 MB| ~0.3x     | Mejor     |

Medido sobre una reunión real de 27 min en español (CPU de 4 núcleos, int8): `base` transcribe
a ~6x tiempo real pero confunde nombres y términos ("Procebo", "capéis"); `large-v3-turbo`
va a ~1x y los acierta ("ProSegur", "KPIs"). Para ir más rápido con calidad aceptable, usa `small` (~3.4x).

## Configuración

Edita `config/settings.yaml` para ajustar parámetros por defecto.