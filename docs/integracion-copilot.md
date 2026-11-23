# Integración con GitHub Copilot

Notas técnicas del análisis e implementación (septiembre de 2026). Código en `src/copilot.py` y
`src/asistente_ia.py`; tests en `tests/test_copilot.py`.

## Contexto

La app usa GitHub Copilot como único proveedor de IA para el resumen y la minuta. La integración replica cómo
lo hace opencode.

## Análisis de opencode

Hay dos implementaciones distintas:

| | opencode Go (`~/Documentos/Visual Studio Code/opencode`) | opencode actual (v1.18, instalado vía npm) |
|---|---|---|
| Estado | Archivado en 2025; continúa como **Crush** (Charm) | Mantenido; integración oficial con GitHub |
| Token | Lee `~/.config/github-copilot/hosts.json` (dejado por plugins de VS Code/Vim) | Login propio con device flow |
| Llamadas | Intercambia el token en `api.github.com/copilot_internal/v2/token` y se identifica como VS Code (`Copilot-Integration-Id: vscode-chat`) | Token de GitHub directo como `Bearer` |
| Veredicto | Obsoleto, no se usó | **Es el que se replicó** |

El código del opencode actual se extrajo del binario instalado
(`~/.local/share/fnm/.../node_modules/opencode-ai/node_modules/opencode-linux-x64/bin/opencode`).

## Protocolo

### Inicio de sesión (device flow de OAuth)

1. `POST https://github.com/login/device/code` con `{"client_id": "Ov23li8tweQw6odWQebz", "scope": "read:user"}`
   → `device_code`, `user_code`, `verification_uri`, `interval`, `expires_in`.
2. El usuario abre `verification_uri` e introduce `user_code`.
3. Consultar `POST https://github.com/login/oauth/access_token` con
   `{"client_id", "device_code", "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}` cada
   `interval + 3` s. Respuestas: `authorization_pending` (seguir), `slow_down` (usar el nuevo `interval`),
   `expired_token`, `access_denied`, o `access_token` (listo).

`Ov23li8tweQw6odWQebz` es la app OAuth de opencode (pública; el device flow no usa secreto). Al autorizar,
GitHub muestra "opencode". Registrar una app OAuth propia no garantiza que la API de Copilot acepte su token.

GitHub Enterprise con dominio propio: mismas rutas sobre `https://<dominio>/login/...` y API en
`https://copilot-api.<dominio>`.

### Peticiones

`POST https://api.githubcopilot.com/chat/completions` (compatible con OpenAI, streaming SSE) con cabeceras:

```
Authorization: Bearer <token de GitHub>
User-Agent: transcriptor-audio/1.0
X-GitHub-Api-Version: 2026-06-01
Openai-Intent: conversation-edits
x-initiator: user | agent
```

`x-initiator: agent` marca pasos automáticos que no cuentan como una nueva petición premium (opencode y VS Code
lo usan igual). La app manda `user` solo en la primera petición de cada documento.

### Catálogo de modelos

`GET /models`. Hallazgos con la cuenta real:

- `model_picker_enabled` vino en `false` para **todos** los modelos; lo que indica que el plan lo permite es
  `policy.state == "enabled"`.
- `supported_endpoints`: si no incluye `/chat/completions` (p. ej. solo `/responses`), el modelo no sirve para
  esta app. Sin ese campo = modelo antiguo que sí funciona por `/chat/completions`.
- La API no informa el multiplicador de peticiones premium de cada modelo.
- Un modelo con `policy.state == "enabled"` puede aun así responder `400 model_not_supported` si el plan no lo
  incluye (pasó con Copilot Free).

### Modo `auto`

opencode no lo implementa; se tomó de la extensión de VS Code y del PR #3902 de Crush.

1. `POST /models/session` con `{"auto_mode": {"model_hints": ["auto"]}}` → `available_models`,
   `selected_model`, `session_token`, `expires_at` (1 h), `discounted_costs` (0.1 = 10 % de descuento).
2. Las peticiones llevan `Copilot-Session-Token: <session_token>` y `model` = el modelo elegido.
3. La sesión se renueva 5 min antes de caducar. Un 401 al abrir la sesión o en una petición se trata como falta de sesión:
   se invalida el token guardado si es el rechazado (el de opencode no se toca) y se pide iniciar sesión; si el token
   viene de `COPILOT_GITHUB_TOKEN`, no se abre el login y el error lo dice.

`selected_model` suele ser un modelo solo-`/responses` (`gpt-5.3-codex`), así que se usa el primero de la lista
que admita `/chat/completions` y no sea de una familia de `FAMILIAS_EXCLUIDAS`. El orden del servidor cambia entre sesiones: en una prueba tocó `gpt-5.4`, en
otra `claude-haiku-4.5`.

## Observaciones sobre `auto`

- En pruebas, `auto` llegó a elegir modelos ligeros (p. ej. `claude-haiku-4.5`) que producen minutas menos
  fieles en reuniones largas. Para minutas conviene fijar un modelo potente (`claude-sonnet-5.5` o `gpt-5.4`).
- Los modelos disponibles dependen del plan de Copilot de cada cuenta (`--copilot-modelos`).

## Comprobado con peticiones reales (2026-11-22)

Cinco peticiones con texto sintético (nunca una transcripción), con la sesión propia de la app:

- **Límites en el catálogo.** `GET /models` devuelve en `capabilities.limits` de cada modelo: `max_prompt_tokens`,
  `max_output_tokens`, `max_context_window_tokens` y `max_non_streaming_output_tokens`. Ejemplos de ese día:
  `claude-haiku-5.5` y `claude-sonnet-5.5`, 936 000 tokens de entrada y 128 000 de salida; `gpt-4.1`, 64 000 de
  entrada y 16 384 de salida; `claude-haiku-4.5`, 128 000 y 32 000.
- **Respuesta cortada.** En `/chat/completions` con `stream: true`, una respuesta que llega al límite de salida
  (forzado con `max_tokens: 20`, en `claude-haiku-5.5` y en `gpt-4.1`) termina con `finish_reason: "length"` y
  después `data: [DONE]`. Una respuesta normal termina con `finish_reason: "stop"` y `[DONE]`.
- **Petición grande y caracteres por token.** Una petición a `claude-haiku-5.5` con 164 993 caracteres (transcripción
  sintética en español de 1 300 líneas con nombres y cifras, más `PROMPT_SISTEMA`) se aceptó (200, `fin=stop`, 3,9 s)
  y el modelo localizó tres claves plantadas al principio, en medio y al final. Copilot contó **70 318 tokens de
  entrada: ≈2,35 caracteres por token**, menos que los 4 que estima hoy `_comprobar_limite_de_entrada`. Es un texto
  con muchas cifras y nombres; el español corrido puede dar algo más, pero no 4.
- **No comprobado:** `finish_reason: "content_filter"` (no se forzó a propósito) ni un stream que se corte sin
  `[DONE]`.

## Fuentes

- [Auto model selection en VS Code (GitHub Changelog)](https://github.blog/changelog/2025-09-15-auto-model-selection-for-copilot-in-vs-code-in-public-preview/)
- [Auto en JetBrains, disponibilidad general y descuento del 10 %](https://github.blog/changelog/2026-03-12-copilot-auto-model-selection-is-generally-available-in-jetbrains-ides)
- [Auto en Copilot CLI con enrutamiento por tarea](https://github.blog/changelog/2026-07-01-copilot-cli-auto-model-selection-routes-based-on-task)
- [Crush PR #3902: soporte del modo Auto de Copilot](https://github.com/charmbracelet/crush/pull/3902)
- [vscode-copilot-chat PR #3780](https://github.com/microsoft/vscode-copilot-chat/pull/3780)
