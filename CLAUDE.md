# Transcriptor de audio/video

App de escritorio (Python, CustomTkinter) que transcribe audio/video **en local** con faster-whisper y genera
**resumen y minuta** con los modelos de **GitHub Copilot**. Todo el código, la UI, los logs y los mensajes están
en español; mantén ese idioma y el estilo de nombres (`generar_minuta`, `ErrorAsistenteIA`, etc.).

## Comandos

```bash
./venv/bin/python -m pytest -q                    # tests (sin llamadas reales a red)
./venv/bin/python run_ui.py                        # interfaz gráfica (TRANSCRIPTOR_LOG=DEBUG para más detalle)
./venv/bin/python -m src.main audio.m4a            # transcribir por CLI
./venv/bin/python -m src.main --copilot-login      # iniciar sesión en GitHub Copilot (device flow)
./venv/bin/python -m src.main --copilot-modelos    # modelos disponibles para la cuenta (incluye "auto")
./venv/bin/python -m src.main --copilot-logout
```

## Arquitectura (`src/`)

| Archivo | Responsabilidad |
|---|---|
| `transcriber.py` | `TranscriptorAudio` (faster-whisper), filtro de alucinaciones, `cargar_configuracion` |
| `copilot.py` | Integración con GitHub Copilot: login (device flow), token, catálogo de modelos, modo `auto` |
| `asistente_ia.py` | `AsistenteIA`: prompts, división en bloques, notas en paralelo, streaming SSE, reintentos, post-proceso de la minuta |
| `ui.py` | Ventana principal: transcribir, pestañas Texto/Resumen/Minuta, atajos |
| `ui_copilot.py` | Diálogo modal de inicio de sesión en Copilot |
| `ui_historial.py` / `historial.py` | Vista y base SQLite (`data/historial.db`) del historial |
| `registro.py` | Logging por consola y `latido` (aviso periódico en pasos largos) |
| `main.py` | CLI |

Configuración en `config/settings.yaml` (sección `ia:`: `modelo`, `copilot_enterprise_url`, `temperatura`,
`max_caracteres_bloque`, `peticiones_paralelas`, `revision_fidelidad`).

## Reglas del proyecto

- **Solo GitHub Copilot como IA.** No introducir otros proveedores.
- El audio nunca sale del equipo; solo el texto transcrito va a Copilot.
- Los tests no deben hacer llamadas reales: se simula `httpx` con `monkeypatch` y las rutas de token se aíslan
  (fixture `rutas_aisladas` en `tests/test_copilot.py`).
- La minuta debe ser fiel: no inventar datos, conservar condiciones con las palabras del hablante (ver
  `PROMPT_SISTEMA`). La fecha la pone la app, no el modelo.

## Integración con GitHub Copilot (resumen)

Detalle completo, fuentes y hallazgos en [docs/integracion-copilot.md](docs/integracion-copilot.md).

- Replica el flujo **actual** de opencode (v1.x, no el repo Go archivado): device flow con el `client_id` de
  opencode y el token de GitHub usado directamente como `Bearer` contra `api.githubcopilot.com/chat/completions`.
- Token en `~/.local/share/transcriptor-audio/copilot.json` (600). Orden de búsqueda: `COPILOT_GITHUB_TOKEN`,
  archivo propio, sesión de opencode (`~/.local/share/opencode/auth.json`, clave `github-copilot`).
- Un modelo está disponible si `policy.state == "enabled"` (no `model_picker_enabled`, que viene en `false`).
- Solo se usa `/chat/completions`; los modelos que solo admiten `/responses` (`*-codex`, `gpt-5.4-mini`…) no sirven.
- `x-initiator`: `user` en la primera petición de cada documento, `agent` en las demás.
- Modo `auto`: `POST /models/session` → `Copilot-Session-Token`; se elige el primer modelo compatible con
  `/chat/completions`; sesión de 1 h renovada 5 min antes.

## Pendientes / decisiones abiertas

- **Modelo por defecto:** `settings.yaml` tiene `modelo: "claude-haiku-5.5"` (el modo `auto` llegó a ofrecer solo
  modelos `/responses`). La UI tiene un selector que, al arrancar, carga `auto` (si funciona) y los modelos de
  `copilot.modelos_economicos` (precio de entrada ≤ `PRECIO_MAX_ECONOMICO`); al cambiarlo se reescribe solo la
  línea `ia.modelo` del YAML (`guardar_modelo_ia`). Para minutas de calidad, fijar `claude-sonnet-5.5` a mano.
- Al arrancar se abre una sesión `auto` solo para comprobar si funciona; aún no se reutiliza en el `AsistenteIA`.
- Posible mejora: soporte de `/responses` para usar los modelos que hoy se saltan en `auto`.