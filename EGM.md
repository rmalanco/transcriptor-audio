# transcriptor-audio Blueprint

## System Overview

Aplicación de escritorio en Python que transcribe audio y video en el propio equipo con faster-whisper y, a
petición del usuario, genera un resumen y una minuta enviando el texto transcrito a GitHub Copilot. Guarda cada
transcripción en un historial SQLite local. Se usa desde una interfaz gráfica (CustomTkinter) o desde una CLI.

Todo el código vive en un solo paquete, `src/`. La instalación y el uso están en [README.md](./README.md); las
reglas para agentes, en [AGENTS.md](./AGENTS.md). Este archivo es el contrato de arquitectura y no los sustituye.

## Local Interface & Invariants

- `run_ui.py` — lanzador de la interfaz gráfica: importa `src.ui.main` y lo ejecuta.
- `config/settings.yaml` — configuración con las secciones `modelo`, `transcripcion`, `salida`, `ia` e `historial`.
  La lee `configuracion.py` contra la raíz del proyecto, así que la CLI y la ventana la usan desde cualquier carpeta.
  `python -m src.main` sigue necesitando la raíz para importar `src`.
- `requirements.txt` (ejecución) y `requirements-dev.txt` (desarrollo, incluye al anterior y fija `pytest`) — manifiestos de dependencias. No hay lockfile.

## Subdirectories & System Boundaries

- `src`: [./src/EGM.md](./src/EGM.md) — transcripción, IA, acceso a Copilot, historial, interfaz gráfica y CLI.
- `tests`: sin contrato (solo tests) — trece archivos `test_*.py` y `conftest.py`, con `pytest`.
- `docs`: sin contrato (solo documentación) — [docs/integracion-copilot.md](./docs/integracion-copilot.md),
  [docs/disenos/00-actual.md](./docs/disenos/00-actual.md), `docs/specs/` (comportamiento verificado) y `docs/historias/`.
- `config`: sin contrato — solo `settings.yaml`.

## Global Invariants

- El audio no sale del equipo: solo el texto transcrito se envía, y solo a la API de Copilot. Los destinos de red de la
  app son GitHub (login), la API de Copilot y, la primera vez de cada modelo, la descarga del modelo de Whisper
  (`src/copilot.py`, `src/asistente_ia.py`, `src/transcriber.py`).
- GitHub Copilot es el único proveedor de IA (`src/asistente_ia.py:NOMBRE_PROVEEDOR`).
- Para generar solo se usa el endpoint `/chat/completions`: el catálogo y el modo `auto` descartan los modelos que no lo
  admiten (`src/copilot.py:listar_modelos`, `src/copilot.py:abrir_sesion_auto`). Un modelo escrito a mano en `ia.modelo`
  o elegido en el selector no pasa por ese filtro: se envía tal cual. Además se usan `GET /models` y
  `POST /models/session` (`src/copilot.py`).
- Ningún texto de la transcripción se envía a un modelo de `FAMILIAS_EXCLUIDAS`, tampoco en modo `auto` ni con un
  modelo escrito a mano (`src/copilot.py:familia_excluida`, `src/asistente_ia.py:AsistenteIA._modelo_para_peticion`).
- El trabajo del usuario se guarda antes de exportarlo: primero el historial y después el archivo junto al audio; un
  fallo de guardado avisa y no descarta el resultado (`src/persistencia.py`).
- La fecha de la minuta la pone la aplicación, no el modelo (`src/asistente_ia.py:AsistenteIA.generar_minuta`).
- Los widgets solo se modifican desde el hilo principal (`src/ui.py:AppTranscriptor._en_ui`).

## Global Side Effects

- Red: `github.com` (device flow) y `api.githubcopilot.com`, o los dominios equivalentes de GitHub Enterprise.
  También la descarga del modelo de Whisper la primera vez.
- Token de Copilot en `~/.local/share/transcriptor-audio/copilot.json`; lectura de
  `~/.local/share/opencode/auth.json` y de la variable `COPILOT_GITHUB_TOKEN`.
- Caché de modelos en `~/.cache/faster-whisper`.
- Base SQLite `data/historial.db` (tabla `transcripciones`).
- Archivos junto al audio: `<archivo>.<ext>_transcripcion.<formato>`, `<archivo>.<ext>_resumen.md`, `<archivo>.<ext>_minuta.md`.
- Preferencias del usuario (el modelo de IA elegido en la interfaz) en `~/.local/share/transcriptor-audio/preferencias.json`;
  `config/settings.yaml` solo se lee, la app no lo reescribe.
- Procesos externos: `ffprobe` (opcional), `xdg-open` / `open` / `os.startfile` y el navegador (`webbrowser.open`).

## System Verification

- Run: `./venv/bin/python -m pytest -q`
