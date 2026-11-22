# Stack

> Resumen; si algo choca con `docs/`, manda `docs/`. Versiones verificadas el 2026-11-22 (ver `inventario.md`).

| Pieza | Declarado | Instalado en este equipo |
|---|---|---|
| Python | «3.10 o superior (probado con 3.12)» (`README.md`) | 3.14.10 |
| faster-whisper | `>=1.0.0` | 1.2.1 (ctranslate2 4.9.0) |
| av (PyAV) | `<19` | 18.1.1 |
| CustomTkinter | `>=6.0.0` | 6.0.0 |
| tkinterdnd2-universal | `>=1.7.0` | 1.7.3 (opcional: sin él no hay arrastrar y soltar) |
| httpx | `>=0.27.0` | 0.28.1 |
| PyYAML | `>=6.0` | 6.0.4 |
| ffmpeg-python | `>=0.2.0` | 0.2.0 |
| ffmpeg / ffprobe (binarios) | en el `PATH` | n9.0.2 |
| Tkinter | requerido | Tk 8.6 |
| SQLite | biblioteca estándar | — |
| pytest | **sin declarar** | **no instalado** |

## Avisos

- `av` está limitado a `<19` porque PyAV 19 quitó `metadata_errors`, que faster-whisper 1.2.1 usa.
- No hay lockfile: todo son cotas mínimas salvo `av`. Fijar versiones está en el backlog (Salud del código #2).
- `pydantic` y `tqdm` están en `requirements.txt` y ningún módulo los importa (Salud del código #12).
- No hay `pyproject.toml`, CI, linter ni comprobación de tipos.
- La compatibilidad con Python 3.10 a 3.13 y con Windows está sin verificar.
- La API de Copilot que se usa no está documentada oficialmente; `API_VERSION` está fijo en `src/copilot.py`.
