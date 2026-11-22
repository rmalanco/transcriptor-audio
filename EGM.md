# transcriptor-audio Blueprint

## System Overview

Aplicación de escritorio en Python que transcribe audio y video en el propio equipo con faster-whisper y, a
petición del usuario, genera un resumen y una minuta enviando el texto transcrito a GitHub Copilot. Guarda cada
transcripción en un historial SQLite local. Se usa desde una interfaz gráfica (CustomTkinter) o desde una CLI.

Todo el código vive en un solo paquete, `src/`. La instalación y el uso están en [README.md](./README.md); las
reglas para agentes, en [CLAUDE.md](./CLAUDE.md). Este archivo es el contrato de arquitectura y no los sustituye.

## Local Interface & Invariants

- `run_ui.py` — lanzador de la interfaz gráfica: importa `src.ui.main` y lo ejecuta.
- `config/settings.yaml` — configuración con las secciones `modelo`, `audio`, `transcripcion`, `salida`, `ia` e
  `historial`. La aplicación lo lee con una ruta relativa al directorio de trabajo, así que se ejecuta desde la raíz.
- `requirements.txt` (ejecución) y `requirements-dev.txt` (desarrollo, incluye al anterior y fija `pytest`) — manifiestos de dependencias. No hay lockfile.

## Subdirectories & System Boundaries

- `src`: [./src/EGM.md](./src/EGM.md) — transcripción, IA, acceso a Copilot, historial, interfaz gráfica y CLI.
- `tests`: sin contrato (solo tests) — nueve archivos `test_*.py` y `conftest.py`, con `pytest`.
- `docs`: sin contrato (solo documentación) — [docs/integracion-copilot.md](./docs/integracion-copilot.md) y
  [docs/disenos/00-actual.md](./docs/disenos/00-actual.md).
- `config`: sin contrato — solo `settings.yaml`.

## Global Invariants

- El audio no sale del equipo: los únicos destinos de red del código son GitHub (login) y la API de Copilot, y
  solo reciben texto (`src/copilot.py`, `src/asistente_ia.py`).
- GitHub Copilot es el único proveedor de IA (`src/asistente_ia.py:NOMBRE_PROVEEDOR`).
- Solo se usa el endpoint `/chat/completions`; los modelos que no lo admiten se descartan
  (`src/copilot.py:listar_modelos`, `src/copilot.py:abrir_sesion_auto`).
- La fecha de la minuta la pone la aplicación, no el modelo (`src/asistente_ia.py:AsistenteIA.generar_minuta`).
- Los widgets solo se modifican desde el hilo principal (`src/ui.py:AppTranscriptor._en_ui`).

## Global Side Effects

- Red: `github.com` (device flow) y `api.githubcopilot.com`, o los dominios equivalentes de GitHub Enterprise.
  También la descarga del modelo de Whisper la primera vez.
- Token de Copilot en `~/.local/share/transcriptor-audio/copilot.json`; lectura de
  `~/.local/share/opencode/auth.json` y de la variable `COPILOT_GITHUB_TOKEN`.
- Caché de modelos en `~/.cache/faster-whisper`.
- Base SQLite `data/historial.db` (tabla `transcripciones`).
- Archivos junto al audio: `<nombre>_transcripcion.<formato>`, `<nombre>_resumen.md`, `<nombre>_minuta.md`.
- Reescritura de `config/settings.yaml` al cambiar el modelo de IA en la interfaz.
- Procesos externos: `ffprobe`, `ffmpeg`, y `xdg-open` / `open` / `os.startfile`.

## System Verification

- Run: `./venv/bin/python -m pytest -q`
