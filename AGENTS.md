# Transcriptor de audio/video

App de escritorio (Python, CustomTkinter) que transcribe audio/video **en local** con faster-whisper y genera
**resumen y minuta** con los modelos de **GitHub Copilot**. Cada transcripción hecha en la interfaz se guarda en un
historial SQLite local. Hay una interfaz gráfica y una CLI que solo transcribe y gestiona la sesión de Copilot. Todo
el código, la UI, los logs y los mensajes están en español; mantén ese idioma y el estilo de nombres
(`generar_minuta`, `ErrorAsistenteIA`, etc.).

## Antes de nada

Lee, en este orden:

1. Este archivo.
2. [.context/inventario.md](.context/inventario.md) — stack y estado verificados.
3. [docs/disenos/00-actual.md](docs/disenos/00-actual.md) — arquitectura de hoy. Contratos: [EGM.md](EGM.md) y
   [src/EGM.md](src/EGM.md).
4. `docs/specs/` del área que vas a tocar, si existe (lo crea `/cerrar`).
5. [BACKLOG.md](BACKLOG.md) — qué sigue.

Hechos verificados y propuestas ya descartadas: [.context/transcriptor-facts.md](.context/transcriptor-facts.md).

## Reglas de oro

1. **Solo GitHub Copilot como IA.** No introducir otros proveedores. La dependencia de su API no documentada es un
   riesgo aceptado (auditoría, A-14).
2. El audio nunca sale del equipo; solo el texto transcrito va a Copilot.
3. Los tests no deben hacer llamadas reales: se simula `httpx` con `monkeypatch` y las rutas de token se aíslan
   (fixture `rutas_aisladas` en `tests/test_copilot.py`).
4. La minuta debe ser fiel: no inventar datos, conservar condiciones con las palabras del hablante (ver
   `PROMPT_SISTEMA`). La fecha la pone la app, no el modelo.
5. `./venv/bin/python -m pytest -q` debe pasar antes de dar un cambio por terminado.
6. El trabajo del usuario se guarda antes de exportarlo: primero el historial, después el archivo junto al audio. Un
   fallo de exportación avisa, no descarta el resultado (A-01).
7. Las familias de modelos de `FAMILIAS_EXCLUIDAS` no están autorizadas por la empresa: la exclusión debe valer
   también en modo `auto` y con un modelo escrito a mano (A-12).
8. Nunca se versionan grabaciones, transcripciones, resúmenes, minutas, el historial ni el token.
9. Los widgets solo se tocan desde el hilo principal; los hilos de fondo pasan por `_en_ui`.
10. Solo se usa `/chat/completions`; no dar por compatible un modelo que solo admite `/responses`.

Las reglas 6 y 7 se cumplen desde el 2026-11-22: la 6 en `src/persistencia.py` y la 7 en `src/copilot.py` (`familia_excluida`), que se comprueba al elegir el modelo de `auto` y justo antes de cada envío.

## Mantener el estado al día

- Historia terminada → `/cerrar` antes del commit: actualiza `docs/specs/`, mueve la historia a
  `docs/historias/hechas/` y marca ✅ en `BACKLOG.md`.
- Cambio de una decisión de arquitectura → actualizar `docs/disenos/`.

## Comandos

```bash
./venv/bin/python -m pytest -q                    # tests (sin llamadas reales a red)
./venv/bin/python run_ui.py                        # interfaz gráfica (TRANSCRIPTOR_LOG=DEBUG para más detalle)
./venv/bin/python -m src.main audio.m4a            # transcribir por CLI
./venv/bin/python -m src.main --copilot-login      # iniciar sesión en GitHub Copilot (device flow)
./venv/bin/python -m src.main --copilot-modelos    # modelos disponibles para la cuenta (incluye "auto")
./venv/bin/python -m src.main --copilot-logout
```

Las dependencias de desarrollo, incluido `pytest`, se instalan con `./venv/bin/python -m pip install -r requirements-dev.txt`
(ese archivo incluye `requirements.txt`). Los comandos se ejecutan desde la raíz del repo, porque
`config/settings.yaml` se lee con ruta relativa.

## Arquitectura (`src/`)

| Archivo | Responsabilidad |
|---|---|
| `transcriber.py` | `TranscriptorAudio` (faster-whisper), filtro de alucinaciones, `cargar_configuracion` |
| `copilot.py` | Integración con GitHub Copilot: login (device flow), token, catálogo de modelos, modo `auto` |
| `asistente_ia.py` | `AsistenteIA`: prompts, división en bloques, notas en paralelo, streaming SSE, reintentos, post-proceso de la minuta |
| `ui.py` | Ventana principal: transcribir, pestañas Texto/Resumen/Minuta, atajos |
| `ui_copilot.py` | Diálogo modal de inicio de sesión en Copilot |
| `ui_historial.py` / `historial.py` | Vista y base SQLite (`data/historial.db`) del historial |
| `persistencia.py` | Guardar sin interfaz: primero el historial y después el archivo; devuelve avisos en vez de lanzar |
| `registro.py` | Logging por consola y `latido` (aviso periódico en pasos largos) |
| `utils.py` | Validación de archivos, metadatos con `ffprobe`, exportación a `txt`/`srt`/`vtt`/`json` |
| `main.py` | CLI |

Configuración en `config/settings.yaml` (sección `ia:`: `modelo`, `copilot_enterprise_url`, `temperatura`,
`max_caracteres_bloque`, `peticiones_paralelas`, `revision_fidelidad`).

## Mapa del repo

| Ruta | Qué es |
|---|---|
| `src/` | Todo el código (un solo paquete) |
| `tests/` | Tests con `pytest` |
| `config/settings.yaml` | Configuración |
| `docs/disenos/` | Arquitectura actual y diseños aprobados |
| `docs/historias/` | Historias refinadas por `/story`; las cerradas, en `hechas/` |
| `docs/integracion-copilot.md` | Notas técnicas de la integración con Copilot |
| `.context/` | Resúmenes para agentes: inventario, stack, convenciones y hechos |
| `BACKLOG.md` | Salud del código e historias pendientes |
| `audit_report.md`, `goldfish_review_report.md` | Auditoría del 2026-11-22 y sus decisiones |
| `data/`, `venv/` | Historial local y entorno virtual (ignorados por git) |

## Integración con GitHub Copilot (resumen)

Detalle completo, fuentes y hallazgos en [docs/integracion-copilot.md](docs/integracion-copilot.md).

- Replica el flujo **actual** de opencode (v1.x, no el repo Go archivado): device flow con el `client_id` de
  opencode y el token de GitHub usado directamente como `Bearer` contra `api.githubcopilot.com/chat/completions`.
- Token en `~/.local/share/transcriptor-audio/copilot.json` (600). Orden de búsqueda: `COPILOT_GITHUB_TOKEN`,
  archivo propio, sesión de opencode (`~/.local/share/opencode/auth.json`, clave `github-copilot`).
- Un modelo está disponible si `policy.state == "enabled"` (no `model_picker_enabled`, que viene en `false`).
- Solo se usa `/chat/completions`; los modelos que solo admiten `/responses` (`*-codex`, `gpt-5.4-mini`…) no sirven.
- `x-initiator`: `user` en la primera petición de cada documento, `agent` en las demás.
- Modo `auto`: `POST /models/session` → `Copilot-Session-Token`; se elige el primer modelo autorizado (fuera de
  `FAMILIAS_EXCLUIDAS`) y compatible con `/chat/completions`; sesión de 1 h renovada 5 min antes.

## Pendientes / decisiones abiertas

- **Modelo por defecto:** `settings.yaml` tiene `modelo: "claude-haiku-5.5"` (el modo `auto` llegó a ofrecer solo
  modelos `/responses`). La UI tiene un selector que, al arrancar, carga `auto` (si funciona) y los modelos de
  `copilot.modelos_economicos` (precio de entrada ≤ `PRECIO_MAX_ECONOMICO`); al cambiarlo se reescribe solo la
  línea `ia.modelo` del YAML (`guardar_modelo_ia`). Para minutas de calidad, fijar `claude-sonnet-5.5` a mano.
- Al arrancar se abre una sesión `auto` solo para comprobar si funciona; aún no se reutiliza en el `AsistenteIA`.
- Posible mejora: soporte de `/responses` para usar los modelos que hoy se saltan en `auto`.

Estos tres pendientes no están en `BACKLOG.md` (decisión del 2026-11-22); se añaden con `/backlog` cuando toque.
