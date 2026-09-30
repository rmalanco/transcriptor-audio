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

La carpeta **no es un repositorio git**.

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

- **Solo GitHub Copilot como IA.** Por política de la empresa no se pueden usar IAs externas (Kimi/Moonshot,
  Mistral, etc.); Informática aprobó Copilot. Se eliminó todo rastro de Kimi y Mistral el 2026-09-30.
  No reintroducir otros proveedores.
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

- **Modelo por defecto:** `settings.yaml` tiene `modelo: "auto"`, pero en la prueba con una reunión real Auto
  eligió `claude-haiku-4.5` y la minuta salió pobre (59 temas, nombres mal transcritos, responsables inventados).
  Recomendado probar y fijar `claude-sonnet-5.5` o `gpt-5.4`.
- **Historial:** las 2 entradas de `data/historial.db` aún tienen resumen/minuta generados con Kimi
  (`kimi-k3`); falta decidir si se borran para regenerarlos con Copilot.
- **`kimi-k3` dentro de Copilot:** aparece en el catálogo; falta que Informática confirme si está permitido.
- Posible mejora: soporte de `/responses` para usar los modelos que hoy se saltan en `auto`.
- Posible mejora: abrir la sesión `auto` en segundo plano al arrancar (tardó ~21 s en una prueba).
