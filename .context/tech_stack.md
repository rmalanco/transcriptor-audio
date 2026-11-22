# Stack

> Resumen; si algo choca con `docs/`, manda `docs/`. Versiones verificadas el 2026-11-22 (ver `inventario.md`) y
> sincronizadas con el código tras las historias del día.

| Pieza | Declarado | Instalado en este equipo |
|---|---|---|
| Python | «3.10 o superior (probado con 3.12)» (`README.md`) | 3.14.10 |
| faster-whisper | `==1.2.1` | 1.2.1 (ctranslate2 4.9.0) |
| av (PyAV) | `==18.1.1` | 18.1.1 |
| CustomTkinter | `==6.0.0` | 6.0.0 |
| tkinterdnd2-universal | `==1.7.3` | 1.7.3 (opcional: sin él no hay arrastrar y soltar) |
| httpx | `==0.28.1` | 0.28.1 |
| PyYAML | `==6.0.4` | 6.0.4 |
| ffmpeg-python | `==0.2.0` | 0.2.0 (solo `ffmpeg.probe`) |
| `ffprobe` (binario, opcional; el binario `ffmpeg` no se ejecuta) | en el `PATH` | n9.0.2 |
| Tkinter | requerido | Tk 8.6 |
| SQLite | biblioteca estándar | — |
| pytest | `==9.2.0` en `requirements-dev.txt` | 9.2.0 |

## Avisos

- `av` está limitado a `<19` porque PyAV 19 quitó `metadata_errors`, que faster-whisper 1.2.1 usa.
- Las dependencias directas están fijadas con `==` en `requirements.txt` y `requirements-dev.txt`. No hay lockfile de las transitivas, así que una instalación nueva puede traer transitivas no probadas.
- No hay `pyproject.toml`, CI, linter ni comprobación de tipos.
- `ffprobe` es opcional: sin él, la app carga el archivo sin duración ni códec (`src/utils.py`).
- La compatibilidad con Python 3.10 a 3.13 y con Windows está sin verificar.
- La API de Copilot que se usa no está documentada oficialmente; `API_VERSION` está fijo en `src/copilot.py`.
