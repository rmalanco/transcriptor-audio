# Inventario del repositorio

> Generado por /escanear (Tándem) el 2026-11-22. Resumen verificado; si algo choca con `docs/`, manda `docs/`.

## Estado
- Clasificación: **código sin Tándem** (hay código; no existen `AGENTS.md`, `BACKLOG.md`, `docs/disenos/` ni `docs/historias/`)
- Rama: `main` (única rama local; al día con `origin/main`) · Cambios sin commitear: no · Último commit: 2026-11-21 (`0332488`)
- Historial: 6 commits en `main`, del 2026-09-30 al 2026-11-21 (≈1 cada 1–2 semanas). Un solo contribuyente, con dos
  identidades de autor (`Rafael Malanco` en 5 commits, `rmalanco` en 1).
- Remoto: `origin` → GitHub (`rmalanco/transcriptor-audio`, por SSH).
- Refs ocultas: 7 refs `refs/agents/<id>/checkpoints/turn/0..6` con 13 commits del 2026-11-21 titulados
  «Agent host session … turn N» (puntos de control de una sesión de agente). No están en `main` ni en `origin`.
- Tamaño: 3 262 líneas en `src/` (11 archivos), 725 en `tests/` (6 archivos).

## Stack (verificado)
| Pieza | Declarado | Instalado aquí | Fuente |
|---|---|---|---|
| Python | «3.10 o superior (probado con 3.12)» | 3.14.10 (sistema y `venv/`) | `README.md`; `python --version`; `venv/pyvenv.cfg` |
| ffmpeg | en el `PATH`, sin versión | n9.0.2 (`/usr/bin/ffmpeg`) | `README.md`; `ffmpeg -version` |
| Tkinter | requerido, sin versión | Tk 8.6 | `README.md`; `import tkinter` |
| faster-whisper | `>=1.0.0` | 1.2.1 (ctranslate2 4.9.0) | `requirements.txt`; `pip list` |
| CustomTkinter | `>=6.0.0` | 6.0.0 | `requirements.txt`; `pip list` |
| httpx | `>=0.27.0` | 0.28.1 | `requirements.txt`; `pip list` |
| SQLite | — (biblioteca estándar `sqlite3`) | incluida en Python | `src/historial.py` |
| pytest | no declarado en ningún manifiesto (solo `pip install pytest` en el README) | **no instalado** | `README.md`; `pip list` |

No hay `pyproject.toml`, `setup.py`, `setup.cfg`, `pytest.ini` ni `tox.ini`: el único manifiesto es `requirements.txt`.
No hay restricción de versión de Python legible por máquina (`python_requires`, `.python-version`).

## Estructura y componentes
| Carpeta / archivo | Responsabilidad (según el código) | Punto de entrada |
|---|---|---|
| `run_ui.py` | Lanzador de la interfaz gráfica | `python run_ui.py` → `src.ui.main` |
| `src/main.py` (214 líneas) | CLI con `argparse`: transcribir, `--listar-modelos`, `--copilot-login/-logout/-modelos`, `--ui` | `python -m src.main` |
| `src/ui.py` (1 183) | Ventana principal `AppTranscriptor` (CustomTkinter + arrastrar y soltar) | `python -m src.ui` |
| `src/ui_copilot.py` (101) | `DialogoLoginCopilot`: diálogo modal del device flow | — |
| `src/ui_historial.py` (277) | `PanelHistorial`: vista del historial | — |
| `src/transcriber.py` (224) | `TranscriptorAudio` (faster-whisper), filtro de alucinaciones, `cargar_configuracion`, `guardar_modelo_ia` | — |
| `src/asistente_ia.py` (487) | `AsistenteIA`: división en bloques, peticiones en paralelo, post-proceso de la minuta | — |
| `src/copilot.py` (322) | Login por device flow, lectura/guardado del token, catálogo de modelos, sesión `auto` | — |
| `src/historial.py` (233) | `Historial` y `EntradaHistorial` sobre SQLite | — |
| `src/registro.py` (60) | `configurar_logging` y `latido` | — |
| `src/utils.py` (155) | Validación e info de archivos (ffmpeg), formatos de tiempo, `guardar_transcripcion` | — |
| `config/settings.yaml` | Configuración: `modelo`, `audio`, `transcripcion`, `salida`, `ia`, `historial` | — |
| `tests/` | 6 archivos, 60 funciones `test_*` | `python -m pytest -q` |
| `docs/` | `integracion-copilot.md` (95 líneas) | — |
| `data/` (ignorado) | `historial.db` (1,4 MB) y `ui.log` (59 KB), locales | — |
| `venv/` (ignorado) | Entorno virtual, recreado el 2026-11-21 | — |

Variables de entorno leídas por el código: `COPILOT_GITHUB_TOKEN` (token de Copilot; `src/copilot.py:34` y `:89`)
y `TRANSCRIPTOR_LOG` (nivel de log; `src/registro.py:13` y `:20`). No hay `.env` ni `.env.example`.

## Dependencias
| Dependencia | Versión declarada | Lockfile | Nota |
|---|---|---|---|
| faster-whisper | `>=1.0.0` | no | instalada 1.2.1 |
| av | `<19` | no | instalada 18.1.1; tope por `metadata_errors` (comentario en `requirements.txt`) |
| ffmpeg-python | `>=0.2.0` | no | instalada 0.2.0; usada en `src/utils.py` |
| pydantic | `>=2.0.0` | no | instalada 2.14.4; **ningún `import pydantic` en `src/`** |
| pyyaml | `>=6.0` | no | instalada 6.0.4 |
| tqdm | `>=4.66.0` | no | instalada 4.70.1; **ningún `import tqdm` en `src/`** |
| customtkinter | `>=6.0.0` | no | instalada 6.0.0 |
| tkinterdnd2-universal | `>=1.7.0` | no | instalada 1.7.3 |
| httpx | `>=0.27.0` | no | instalada 0.28.1 |
| pytest (desarrollo) | sin declarar | no | no instalada |

Sin lockfile: todas las versiones son cotas mínimas (salvo `av<19`), así que una instalación nueva puede traer
versiones distintas de las probadas. El venv tiene 36 paquetes en total.

## Verificación
- Comando de tests: `./venv/bin/python -m pytest -q` (documentado en `CLAUDE.md` y `README.md`) ·
  Resultado: **no ejecutado** — falla con `No module named pytest`; ejecutarlo exige instalar pytest, y este paso
  no instala nada. Tampoco está en el Python del sistema.
- Indicio de una ejecución anterior: `.pytest_cache` del 2026-11-01 con 62 tests recogidos y `lastfailed` vacío.
  El venv se recreó después (2026-11-21), y ahí se perdió pytest. No equivale a un resultado actual.
- Comprobación de humo: `./venv/bin/python -m src.main --listar-modelos` funciona (lista 8 modelos de Whisper).
- CI: **no hay** (no existe `.github/`, ni otro pipeline).
- Linters / formatters / typecheck: **ninguno configurado**; tampoco hay ruff, black, mypy ni flake8 instalados.
  `.vscode/settings.json` solo contiene palabras de cSpell.

## Documentación existente
| Documento | Vigente / histórico / obsoleto | Nota |
|---|---|---|
| `CLAUDE.md` | Vigente — **fuente de verdad para IA** | Comandos, arquitectura, reglas del proyecto y pendientes. No lista `src/utils.py` en la tabla de arquitectura |
| `README.md` | Vigente | Instalación, uso, modelos, privacidad, tests. La URL de clonado lleva el marcador `<tu-usuario>` |
| `docs/integracion-copilot.md` | Vigente (notas de septiembre de 2026) | Versionado |
| `LICENSE` | Vigente | MIT |

No existen `AGENTS.md`, `.github/copilot-instructions.md` ni `.cursor/rules/`.

## Riesgos visibles (sin auditar todavía)
- Secretos versionados: **ninguno**. No hay `.env`, `*.pem`, `*.key` ni `credentials` en `git ls-files`, ni cadenas
  con forma de token real de GitHub. `tests/test_copilot.py` usa tokens ficticios cortos. `src/copilot.py:27` y
  `docs/integracion-copilot.md:29` llevan el `client_id` de OAuth de opencode, que el README declara público.
- `data/ui.log`: sin cadenas con forma de token (búsqueda por patrón; no se leyó el contenido).
- TODO/FIXME/HACK: 0.
- Tests no ejecutables tal como está el entorno: falta pytest en el venv y no está declarado en ningún manifiesto.
- Sin CI, sin linter y sin typecheck: nada verifica los cambios de forma automática.
- Sin lockfile y con Python 3.14 instalado frente al 3.12 «probado».
- ~~`.gitignore` ignoraba `docs/`~~ — resuelto el 2026-11-22: se quitó la regla (cambio sin commitear).
- `.gitignore` ignora `*.json` y `*.txt` de forma global (con excepciones para `README.md`, `requirements.txt` y
  `config/settings.yaml`): cualquier JSON o TXT nuevo del proyecto queda fuera sin aviso.
- `.context/` no está en `.gitignore`: este inventario aparece como archivo sin seguimiento.
- `src/ui.py` concentra 1 183 líneas (36 % de `src/`) y solo tiene 4 tests en `tests/test_ui.py`.
- `pydantic` y `tqdm` declarados sin uso aparente en `src/`.
- Binarios o archivos grandes versionados: ninguno (el mayor es `src/ui.py`, 56 KB).
- El repositorio vive en un disco montado con `core.fileMode=false`: todos los archivos se ven ejecutables en disco;
  en el índice solo uno figura como `100755`.

## Sin verificar
- Que los tests pasen hoy (pytest no instalado; ver Verificación).
- Compatibilidad real con Python 3.10–3.13: solo hay 3.14.10 en este equipo.
- La interfaz gráfica: no se lanzó (`run_ui.py` abre una ventana y, al arrancar, abre una sesión `auto` contra Copilot).
- Todo lo que toca la red: login, catálogo de modelos, modo `auto`, generación de resumen y minuta (requiere
  credenciales y hace llamadas reales).
- La transcripción de extremo a extremo (necesita un audio y, la primera vez, descargar el modelo).
- Las afirmaciones de `docs/integracion-copilot.md` y de `CLAUDE.md` sobre el comportamiento de la API de Copilot.
- El contenido de `data/historial.db` y de `data/ui.log` (datos locales; no se abrieron).
- A qué herramienta pertenecen las refs `refs/agents/…` y si pueden borrarse.
- El estado del repositorio en GitHub (visibilidad, issues, protecciones de rama).
