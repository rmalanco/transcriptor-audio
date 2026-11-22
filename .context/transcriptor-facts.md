# Hechos del proyecto

> Resumen; si algo choca con `docs/`, manda `docs/`. Actualizado el 2026-11-22.
> Sirve para no volver a proponer lo que ya se decidió o se descartó.

## Decisiones tomadas

- **Solo GitHub Copilot como IA.** En la auditoría del 2026-11-22 un revisor propuso admitir otros proveedores o un
  modelo local para mitigar la dependencia de una API no documentada (A-14). Se rechazó: el riesgo se acepta y la
  regla se mantiene. No lo vuelvas a proponer.
- **La exclusión de las familias `kimi` y `mistral` es un requisito real de la empresa del usuario** (A-12), no una
  preferencia. No propongas quitarla ni moverla a una opción que el usuario pueda desactivar. Lo pendiente es
  aplicarla también en modo `auto` y con un modelo escrito a mano (`BACKLOG.md`, historia #2).
- **Los contratos se llaman `EGM.md`**, no `README.md`, para no tocar el README escrito a mano.
- **`docs/` se versiona.** La regla que lo ignoraba se quitó del `.gitignore` el 2026-11-22.

## Hechos verificados en el código

- La CLI no genera resumen ni minuta y no guarda en el historial; solo la interfaz lo hace.
- El token se busca en este orden: `COPILOT_GITHUB_TOKEN`, `~/.local/share/transcriptor-audio/copilot.json`,
  `~/.local/share/opencode/auth.json`.
- `config/settings.yaml` se lee con ruta relativa al directorio de trabajo; `historial.ruta` se resuelve contra la
  raíz del proyecto.
- Con más de un bloque, el documento se redacta a partir de notas y la revisión de fidelidad compara contra ellas.
- `transcribir_archivo_largo` no tiene llamadores; `audio.sample_rate`, `audio.chunk_duration` y
  `transcripcion.task` no se leen.
- `MODELO_POR_DEFECTO` en el código es `gpt-4.1`; `settings.yaml` trae `claude-haiku-5.5`.

## Según la documentación, sin verificar con llamadas reales

- Un modelo está disponible si `policy.state == "enabled"`; `model_picker_enabled` viene en `false`.
- Los modelos `*-codex` y `gpt-5.4-mini` solo admiten `/responses`.
- Copilot cuenta como premium solo las peticiones con `x-initiator: user`.
- El modo `auto` descuenta un 10 % de las peticiones premium.

Fuente: `docs/integracion-copilot.md`.

## Hallazgos descartados (no reabrir sin un motivo nuevo)

| Id | Hallazgo | Motivo |
|---|---|---|
| A-23 | `PRAGMA user_version` sin migraciones; columnas `resumen_en` y `minuta_en` sin leer | Sin efecto hasta el primer cambio de esquema |
| A-24 | Los permisos `600` del token no se reaplican si el archivo ya existía | Sin escenario confirmado |
| A-28 | `--ui` pierde `--log` y `--config` | Hay otras dos formas de lanzar la interfaz |
| A-31 | Un hilo de `latido` por operación larga | Aceptable hoy |
| A-32 | Supuestos de los tests sin documentar | Absorbido por A-22 |

## Pospuesto

- A-18: la búsqueda del historial corre en el hilo de la interfaz. Sin medición; se retoma si se nota lentitud.

## Sin verificar

- Que los tests pasen hoy (`pytest` no está instalado).
- El comportamiento real de la API de Copilot y de la interfaz gráfica: la auditoría fue por lectura.
- Que no haya secretos en commits anteriores.
