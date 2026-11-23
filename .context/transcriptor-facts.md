# Hechos del proyecto

> Resumen; si algo choca con `docs/`, manda `docs/`. Actualizado el 2026-11-22.
> Sirve para no volver a proponer lo que ya se decidió o se descartó.

## Decisiones tomadas

- **Solo GitHub Copilot como IA.** En la auditoría del 2026-11-22 un revisor propuso admitir otros proveedores o un
  modelo local para mitigar la dependencia de una API no documentada (A-14). Se rechazó: el riesgo se acepta y la
  regla se mantiene. No lo vuelvas a proponer.
- **La exclusión de las familias de `FAMILIAS_EXCLUIDAS` es un requisito real de la empresa del usuario** (A-12), no una
  preferencia: `kimi` y todas las de Mistral AI (`mistral`, `codestral`, `devstral`, `ministral`, `pixtral`, `magistral`).
  No propongas quitarla ni moverla a una opción que el usuario pueda desactivar. Ya se aplica también en modo `auto` y
  con un modelo escrito a mano (`copilot.familia_excluida`, historia 03). La lista la decidió el usuario el 2026-11-22
  (`BACKLOG.md`, Salud del código #21).
- **Los contratos se llaman `EGM.md`**, no `README.md`, para no tocar el README escrito a mano.
- **`docs/` se versiona.** La regla que lo ignoraba se quitó del `.gitignore` el 2026-11-22.
- **La app nunca escribe `config/settings.yaml` ni el archivo de opencode** (diseño 06, alternativas A y G, rechazadas
  por el autor): lo que el usuario guarda desde la vista Configuración va a `preferencias.json` y «Cerrar sesión» solo
  borra `copilot.json`. Tampoco se reabre el historial en caliente al cambiar `historial.ruta` (alternativa E): se
  aplica al reiniciar. No lo vuelvas a proponer sin un motivo nuevo.

## Hechos verificados en el código

- La CLI no genera resumen ni minuta y no guarda en el historial; solo la interfaz lo hace.
- El token se busca en este orden: `COPILOT_GITHUB_TOKEN`, `~/.local/share/transcriptor-audio/copilot.json`,
  `~/.local/share/opencode/auth.json`.
- `config/settings.yaml` se lee siempre contra la raíz del proyecto (`configuracion.py`), salvo que `--config` indique
  otra ruta, que se interpreta desde la carpeta de trabajo; `historial.ruta` también se resuelve contra la raíz. La app
  ya no reescribe el YAML: el modelo de IA elegido y los ajustes guardados en la vista Configuración van a
  `~/.local/share/transcriptor-audio/preferencias.json` (`modelo_ia` y el bloque `configuracion`) y ganan al YAML al
  abrir la ventana (`combinar`); la CLI no lee ese archivo.
- Al abrir la ventana no hay tráfico con Copilot ni se lee el token; mostrar la vista Configuración lee la sesión del
  disco, sin red; «↻» consulta el catálogo una vez, sin sesión `auto`.
- Con más de un bloque, el documento se redacta a partir de notas y la revisión de fidelidad compara contra ellas.
- Cancelar una transcripción descarta lo transcrito. Cancelar una generación de IA devuelve la ventana al instante;
  el hilo abandonado termina solo y su resultado se descarta.
- `transcribir_archivo_largo` y las claves `audio.*` y `transcripcion.task` ya no existen; si un YAML antiguo las
  trae, se ignoran.
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
| A-32 | Supuestos de los tests sin documentar | Absorbido por A-22: están en «Cómo se prueba» de `docs/disenos/00-actual.md` |

## Pospuesto

- A-18: la búsqueda del historial corre en el hilo de la interfaz. Sin medición; se retoma si se nota lentitud.

## Sin verificar

- Que los tests pasen en otros equipos o versiones de Python: solo se ejecutaron con Python 3.14.10 en Linux (2026-11-22).
- El comportamiento real de la API de Copilot y de la interfaz gráfica: la auditoría y la sincronización de la documentación fueron por lectura del código.
- Que no haya secretos en commits anteriores.

- **Copilot, comprobado con peticiones reales el 2026-11-22:** una respuesta cortada por longitud termina con
  `finish_reason: "length"` y `[DONE]`; una normal, con `"stop"` y `[DONE]`. El catálogo (`GET /models`) trae
  `capabilities.limits.max_prompt_tokens` y `max_output_tokens` por modelo. Detalle en
  `docs/integracion-copilot.md` §«Comprobado con peticiones reales».
