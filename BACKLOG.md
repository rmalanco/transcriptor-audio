# Backlog

> Flujo Tándem: /story #N → docs/historias/NN-slug.md → /clear → /pair → code-review → /cerrar → commit.
> /cerrar actualiza docs/specs/, mueve la historia a docs/historias/hechas/ y pone el ✅.
> Carriles: S (beast-mode o /pair), M (/story), L (/idea o /diseno). Lo terminado lleva ✅ después del número: `1. ✅ Como…`.

## Context

App de escritorio para una persona que transcribe reuniones en su propio equipo y genera resumen y minuta con
GitHub Copilot · Stack: Python 3.14, faster-whisper, CustomTkinter, httpx, SQLite, pytest · Decisiones caras: ninguna
Arquitectura actual: docs/disenos/00-actual.md · Auditoría: audit_report.md (2026-11-22)

## Salud del código

1. ✅ [🔴] Guardar la transcripción y los documentos de IA en el historial antes de exportarlos; si la exportación falla, avisar sin descartar el resultado, y no sobrescribir archivos sin aviso — hallazgos A-01, A-25 — carril M
2. ✅ [🟡] Declarar `pytest` y las dependencias de desarrollo con versiones fijadas, y cubrir con tests el flujo transcribir → guardar → historial y la CLI — hallazgos A-16, A-29 — carril M
3. [🟡] Al cargar otro archivo, invalidar el resultado, las pestañas de IA y el vínculo al historial del anterior, y avisar si la entrada del historial se eliminó mientras se generaba un documento (review de la historia 01) — hallazgo A-02 — carril S
4. [🟡] Completar `.gitignore` (`*_resumen.md`, `*_minuta.md`, extensiones de audio y video que faltan), quitar los patrones sin efecto y corregir el modelo `large` del README — hallazgos A-03, A-30 — carril S
5. [🟡] Sacar de la clase Tk los flujos «transcribir y persistir» y «generar y persistir» a funciones sin interfaz, y dejar de cargar `faster_whisper` donde no se transcribe — hallazgo A-15 — carril L
6. [🟡] Un módulo de configuración que resuelva la ruta contra la raíz, valide el YAML y tenga los valores por defecto en un solo lugar; que la CLI los use y se quiten las claves que nadie lee — hallazgos A-08, A-09 — carril M
7. [🟡] Tratar el 401 del modo `auto` como falta de sesión, y decir en el error cuándo el token rechazado viene de `COPILOT_GITHUB_TOKEN` en vez de reabrir el login — hallazgos A-06, A-07 — carril S
8. [🟡] Hacer que la revisión de fidelidad compare contra la transcripción original, no contra las notas, o advertir de que el documento se redactó a partir de notas — hallazgo A-05 — carril M
9. [🟡] En la CLI, validar la combinación de formato y salida antes de transcribir y usar el mismo serializador que la exportación a archivo — hallazgo A-10 — carril S
10. [🟡] Consultar el catálogo de Copilot una sola vez y bajo demanda, sin abrir una sesión `auto` al arrancar, y documentar ese tráfico y el orden de búsqueda del token — hallazgo A-13 — carril S
11. [🟡] Guardar el modelo de IA elegido fuera del repo, junto al token, en vez de reescribir `config/settings.yaml` — hallazgo A-19 — carril S
12. [🟡] Eliminar `transcribir_archivo_largo`, `_on_drop`, `duracion_archivo`, `pydantic` y `tqdm`, y tratar los metadatos de `ffprobe` como opcionales — hallazgo A-20 — carril S
13. [🟡] Dejar una sola lista de modelos de Whisper y de extensiones, y un solo formateador de tiempo por uso — hallazgo A-21 — carril S
14. [🟡] Añadir a `docs/disenos/00-actual.md` los riesgos y límites, el modelo de concurrencia y los datos y secretos, y aplicar las correcciones de `2026-11-22_DRIFT_REPORT.md` a los tres contratos — hallazgo A-22 — carril S
15. [🟡] Convertir en `ErrorCopilot` las respuestas de GitHub con formato inesperado, para que el diálogo de login no se quede colgado — hallazgo A-17 (posible) — carril S
16. [🟢] No habilitar «Transcribir» tras generar un documento de una entrada cuyo audio ya no existe — hallazgo A-26 — carril S
17. [🟢] Mostrar en pantalla o en la pestaña Registro los errores de «Guardar como…» — hallazgo A-27 — carril S
18. [🟡] No sobrescribir sin aviso la transcripción, el resumen o la minuta de otra grabación con el mismo nombre en la misma carpeta (`reunion.m4a` y `reunion.mp4`); decidir antes entre incluir la extensión de origen en el nombre o preguntar antes de sobrescribir — hallazgo A-25, separado del punto 1 — carril S o M según la decisión
19. [🟡] Cubrir con tests los rechazos de la CLI (archivo inexistente o extensión no admitida, fallo al transcribir) y sus órdenes de sesión (`--copilot-logout`, `--copilot-modelos` sin sesión), con las rutas de token aisladas y sin red, sin fijar lo que cambiará el punto 9 — hallazgo A-16, separado del punto 2 — carril S

## Backlog

1. Como usuario, quiero cancelar la generación de un resumen o una minuta, para no tener que cerrar la app cuando el modelo tarda. — hallazgo A-04 — carril M
2. Como usuario con una cuenta de empresa, quiero que mi transcripción nunca se envíe a un modelo de una familia no autorizada, tampoco en modo `auto` ni con un modelo escrito a mano, para cumplir la política de mi empresa. — hallazgo A-12 — carril M
3. Como usuario, quiero que la app me avise cuando un documento quedó incompleto y que conserve las partes ya procesadas si una falla, para no pagar de nuevo toda la generación. — hallazgo A-11 (en parte posible) — carril M
4. Como usuario, quiero un botón para cerrar el programa, para salir sin depender del control de la ventana. — carril S
5. Como usuario, quiero un panel de configuración con todo lo que se puede configurar, para ajustar la app sin editar `config/settings.yaml` a mano. — carril L
6. Como usuario, quiero iniciar y cerrar la sesión de GitHub Copilot desde el panel de configuración, para activar la IA sin esperar a generar un documento ni usar la terminal. Requires: #5 — carril M

## Pospuesto

- A-18 — La búsqueda del historial corre en el hilo de la interfaz y podría congelar la ventana con cientos de reuniones. Motivo: sin medición; se retoma cuando el historial crezca o se note lentitud.
- Pendientes de `AGENTS.md` (modelo por defecto, reutilizar la sesión `auto`, soporte de `/responses`): fuera del backlog por decisión del 2026-11-22; se añaden con `/backlog`.
