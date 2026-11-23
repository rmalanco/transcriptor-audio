# Inventario del repositorio

> Generado por /escanear (Tándem) el 2026-11-22 y sincronizado con el código el mismo día, tras cerrar veintisiete
> historias (incluido el panel de configuración) y varios puntos de «Salud del código». Resumen verificado; si algo
> choca con `docs/`, manda `docs/`.

## Estado
- Clasificación: **con Tándem** (`AGENTS.md`, `BACKLOG.md`, `docs/disenos/`, `docs/historias/` y `docs/specs/` existen y se versionan)
- Rama: `tandem/ronda-2` (17 commits por delante de `main`, que sigue en `ac08776` igual que `origin/main`) ·
  Cambios sin commitear: solo la documentación de esta sincronización (antes de ella, ninguno) · Último commit:
  2026-11-22 (`5e18f2f`)
- Historial: 48 commits en la rama, del 2026-09-30 al 2026-11-22. Un solo contribuyente, con dos identidades de autor
  (`Rafael Malanco` en 5 commits, `rmalanco` en 43).
- Remoto: `origin` → GitHub (`rmalanco/transcriptor-audio`, por SSH).
- Refs ocultas: 7 refs `refs/agents/<id>/checkpoints/turn/0..6` con 13 commits del 2026-11-21 titulados
  «Agent host session … turn N» (puntos de control de una sesión de agente). No están en `main` ni en `origin`.
- Tamaño: 5 446 líneas en `src/` (17 archivos `.py`), 7 018 en `tests/` (13 archivos `test_*.py` y `conftest.py`).

## Stack (verificado)
| Pieza | Declarado | Instalado aquí | Fuente |
|---|---|---|---|
| Python | «3.10 o superior (probado con 3.12)» | 3.14.10 (sistema y `venv/`) | `README.md`; `python --version`; `venv/pyvenv.cfg` |
| ffprobe (del paquete ffmpeg) | en el `PATH`, sin versión; opcional | n9.0.2 (`/usr/bin/ffprobe`) | `README.md`; `src/utils.py`; `ffprobe -version` |
| Tkinter | requerido, sin versión | Tk 8.6 | `README.md`; `import tkinter` |
| faster-whisper | `==1.2.1` | 1.2.1 (ctranslate2 4.9.0) | `requirements.txt`; `pip list` |
| CustomTkinter | `==6.0.0` | 6.0.0 | `requirements.txt`; `pip list` |
| httpx | `==0.28.1` | 0.28.1 | `requirements.txt`; `pip list` |
| SQLite | — (biblioteca estándar `sqlite3`) | incluida en Python | `src/historial.py` |
| pytest | `==9.2.0` en `requirements-dev.txt` | 9.2.0 | `requirements-dev.txt`; `pip list` |

No hay `pyproject.toml`, `setup.py`, `setup.cfg`, `pytest.ini` ni `tox.ini`: los manifiestos son `requirements.txt` y `requirements-dev.txt`.
No hay restricción de versión de Python legible por máquina (`python_requires`, `.python-version`).
El binario `ffmpeg` no se ejecuta: solo `ffprobe`, a través de `ffmpeg.probe` de `ffmpeg-python`, y sin él la app sigue.

## Estructura y componentes
| Carpeta / archivo | Responsabilidad (según el código) | Punto de entrada |
|---|---|---|
| `run_ui.py` | Lanzador de la interfaz gráfica | `python run_ui.py` → `src.ui.main` |
| `src/main.py` (223 líneas) | CLI con `argparse`: transcribir, `--listar-modelos`, `--copilot-login/-logout/-modelos`, `--ui` | `python -m src.main` |
| `src/ui.py` (1 458) | Ventana principal `AppTranscriptor` (CustomTkinter + arrastrar y soltar): barra de tres vistas (Transcribir, Historial y Configuración, con `Ctrl+1/2/3`), guardado y restablecimiento de la configuración, sesión de Copilot desde la vista | `python -m src.ui` |
| `src/ui_configuracion.py` (401) | `PanelConfiguracion`: vista «⚙ Configuración» (21 campos en los grupos Transcripción, Salida, IA e Historial, «Avanzado» plegable, sección de la sesión de Copilot, Guardar y Restablecer) | — |
| `src/ui_copilot.py` (101) | `DialogoLoginCopilot`: diálogo modal del device flow | — |
| `src/ui_historial.py` (277) | `PanelHistorial`: vista del historial | — |
| `src/idiomas.py` (35) | Nombres y códigos del selector de idioma, sin Tk | — |
| `src/transcriber.py` (173) | `TranscriptorAudio` (faster-whisper), filtro de alucinaciones | — |
| `src/configuracion.py` (535) | Carga y validación de `config/settings.yaml` (21 claves con valores por defecto), `ErrorConfiguracion`, `MODELOS_WHISPER`, y las preferencias del usuario en `preferencias.json` (modelo de IA y bloque `configuracion`): `leer_ajustes`, `combinar`, validación con los topes del panel, `guardar_formulario` y `restablecer_formulario` (escritura atómica) | — |
| `src/persistencia.py` (114) | Guardar sin interfaz: primero el historial y después el archivo junto al audio; devuelve avisos en vez de lanzar | — |
| `src/flujo_transcripcion.py` (113) | Flujo de transcribir y persistir, sin interfaz (sacado de `ui.py`) | — |
| `src/flujo_documentos.py` (194) | Gestor sin interfaz de los documentos: generación vigente, asistente y decisión de qué se guarda de cada generación | — |
| `src/asistente_ia.py` (846) | `AsistenteIA`: prompts, división en bloques, notas en paralelo, streaming SSE, reintentos, revisión de fidelidad, post-proceso de la minuta | — |
| `src/copilot.py` (491) | Login por device flow, lectura/guardado del token, origen de la sesión sin red (`estado_sesion`, `describir_sesion`), cierre de la sesión propia (`cerrar_sesion_propia`), catálogo de modelos, familias excluidas, sesión `auto` | — |
| `src/historial.py` (233) | `Historial` y `EntradaHistorial` sobre SQLite | — |
| `src/registro.py` (60) | `configurar_logging` y `latido` | — |
| `src/utils.py` (189) | Validación e info de archivos (`ffprobe`, opcional), formatos de tiempo, `serializar_transcripcion` y `guardar_transcripcion` | — |
| `config/settings.yaml` | Configuración: `modelo`, `transcripcion`, `salida`, `ia`, `historial`; la app solo la lee | — |
| `tests/` | 13 archivos `test_*.py` y `conftest.py`; 501 tests (376 funciones `test_*`, el resto casos parametrizados) | `python -m pytest -q` |
| `docs/` | `integracion-copilot.md` (111 líneas), `disenos/` (`00-actual.md`, `05-flujos-fuera-de-la-ventana.md`, `06-panel-de-configuracion.md`), `specs/` (4 specs), `historias/hechas/` (27 historias) | — |
| `data/` (ignorado) | `historial.db` (1,4 MB) y `ui.log` (59 KB, del 6 de noviembre: ningún código actual lo escribe), locales | — |
| `venv/` (ignorado) | Entorno virtual, recreado el 2026-11-21 | — |

Variables de entorno leídas por el código: `COPILOT_GITHUB_TOKEN` (token de Copilot; `src/copilot.py:34` y `:132`)
y `TRANSCRIPTOR_LOG` (nivel de log; `src/registro.py:13` y `:20`). No hay `.env` ni `.env.example`.

## Dependencias
| Dependencia | Versión declarada | Lockfile | Nota |
|---|---|---|---|
| faster-whisper | `==1.2.1` | no | instalada 1.2.1 |
| av | `==18.1.1` | no | instalada 18.1.1; tope por `metadata_errors` (comentario en `requirements.txt`) |
| ffmpeg-python | `==0.2.0` | no | instalada 0.2.0; `src/utils.py` solo usa `ffmpeg.probe` (ejecuta `ffprobe`) |
| pyyaml | `==6.0.4` | no | instalada 6.0.4 |
| customtkinter | `==6.0.0` | no | instalada 6.0.0 |
| tkinterdnd2-universal | `==1.7.3` | no | instalada 1.7.3 |
| httpx | `==0.28.1` | no | instalada 0.28.1 |
| pytest (desarrollo) | `==9.2.0` en `requirements-dev.txt` | no | instalada 9.2.0 |

Las directas están fijadas con `==`; no hay lockfile de las transitivas, así que una instalación nueva puede traer
transitivas distintas de las probadas. `pydantic` y `tqdm` ya no están declaradas (nadie las importa en `src/`); en el
venv siguen instaladas, `tqdm` porque la piden `faster-whisper` y `huggingface_hub` y `pydantic` como resto de la
instalación anterior. El venv tiene 40 paquetes en total.

## Verificación
- Comando de tests: `./venv/bin/python -m pytest -q` (documentado en `AGENTS.md` y `README.md`) ·
  Resultado: **501 tests en verde** (Python 3.14.10, Linux, sin red).
- Comprobación de humo: `./venv/bin/python -m src.main --listar-modelos` funciona (lista 8 modelos de Whisper).
- CI: **no hay** (no existe `.github/`, ni otro pipeline).
- Linters / formatters / typecheck: **ninguno configurado**; tampoco hay ruff, black, mypy ni flake8 instalados.
  `.vscode/settings.json` solo contiene palabras de cSpell.

## Documentación existente
| Documento | Vigente / histórico / obsoleto | Nota |
|---|---|---|
| `AGENTS.md` (y `CLAUDE.md`, que solo lo importa con `@AGENTS.md`) | Vigente — **fuente de verdad para IA** | Reglas de oro, comandos, arquitectura y pendientes |
| `README.md` | Vigente | Instalación, uso, la vista Configuración, modelos, privacidad, tests. La URL de clonado lleva el marcador `<tu-usuario>` |
| `docs/disenos/00-actual.md` | Vigente | Arquitectura actual, concurrencia, datos y secretos, riesgos |
| `docs/disenos/05-flujos-fuera-de-la-ventana.md`, `06-panel-de-configuracion.md` | Diseños; el 06 está implementado (historias 17 a 27); el 05, en las historias 08 a 14 | Detalle y alternativas de cada diseño; manda `00-actual.md` para el estado de hoy |
| `docs/specs/` | Vigente | Comportamiento verificado por área (CLI, configuración, documentos de IA, transcripción) |
| `EGM.md`, `src/EGM.md` | Vigente | Contratos de arquitectura |
| `BACKLOG.md` | Vigente | Salud del código e historias pendientes |
| `audit_report.md`, `goldfish_review_report.md`, `2026-11-22_DRIFT_REPORT.md` | Histórico (auditoría del 2026-11-22 y sus decisiones) | Los hallazgos viven en `BACKLOG.md` |
| `docs/integracion-copilot.md` | Vigente (notas de septiembre de 2026, ajustadas después) | Versionado |
| `LICENSE` | Vigente | MIT |

No existen `.github/copilot-instructions.md` ni `.cursor/rules/`.

## Riesgos visibles (sin auditar todavía)
- Secretos versionados: **ninguno**. No hay `.env`, `*.pem`, `*.key` ni `credentials` en `git ls-files`, ni cadenas
  con forma de token real de GitHub. `tests/test_copilot.py` usa tokens ficticios cortos. `src/copilot.py:27` y
  `docs/integracion-copilot.md:29` llevan el `client_id` de OAuth de opencode, que el README declara público.
- `data/ui.log`: sin cadenas con forma de token (búsqueda por patrón; no se leyó el contenido).
- TODO/FIXME/HACK: 0.
- Tests ejecutables con `requirements-dev.txt`, que fija `pytest` (9.2.0): 501 pasan el 2026-11-22.
- Sin CI, sin linter y sin typecheck: nada verifica los cambios de forma automática.
- Sin lockfile y con Python 3.14 instalado frente al 3.12 «probado».
- ~~`.gitignore` ignoraba `docs/`~~ — resuelto el 2026-11-22: se quitó la regla (`docs/` ya está versionado).
- `.gitignore` ignora `*.json` y `*.txt` de forma global (con excepciones para `README.md`, `requirements.txt`,
  `requirements-dev.txt` y `config/settings.yaml`): cualquier JSON o TXT nuevo del proyecto queda fuera sin aviso.
- `.context/` se versiona (no está en `.gitignore`).
- `src/ui.py` concentra 1 458 líneas (27 % de `src/`); `tests/test_ui.py` tiene 43 tests, que llaman a sus métodos y a los de
  `PanelConfiguracion` sobre dobles (ningún test abre una ventana). El guardado también se prueba sin interfaz a través
  de `persistencia.py` y `configuracion.py`; cómo se ve la ventana solo se verifica a mano.
- Binarios o archivos grandes versionados: ninguno (el mayor es `tests/test_asistente_ia.py`, 99 KB; el mayor de `src/`, `ui.py`, 74 KB).
- El repositorio vive en un disco montado con `core.fileMode=false`: todos los archivos se ven ejecutables en disco;
  en el índice solo uno figura como `100755`.

## Sin verificar
- Que los tests pasen en otros equipos o versiones de Python: solo se ejecutaron con Python 3.14.10 en Linux (ver Verificación).
- Compatibilidad real con Python 3.10–3.13: solo hay 3.14.10 en este equipo.
- La interfaz gráfica no tiene test automático con Tk: los tests usan dobles. Cada cambio visible de las rondas 1 y 2
  (incluida la vista Configuración con su sección de sesión) se verificó a mano en la ventana real con scripts que
  interceptan la red, aíslan el token y las preferencias y responden los diálogos; esos scripts no están en el repo.
- Todo lo que toca la red: login, catálogo de modelos, modo `auto`, generación de resumen y minuta (requiere
  credenciales y hace llamadas reales).
- La transcripción de extremo a extremo (necesita un audio y, la primera vez, descargar el modelo).
- Las afirmaciones de `docs/integracion-copilot.md` y de `AGENTS.md` sobre el comportamiento de la API de Copilot.
- El contenido de `data/historial.db` y de `data/ui.log` (datos locales; no se abrieron).
- A qué herramienta pertenecen las refs `refs/agents/…` y si pueden borrarse.
- El estado del repositorio en GitHub (visibilidad, issues, protecciones de rama).
