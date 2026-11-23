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
3. ✅ [🟡] Al cargar otro archivo, invalidar el resultado, las pestañas de IA y el vínculo al historial del anterior, y avisar si la entrada del historial se eliminó mientras se generaba un documento (review de la historia 01) — hallazgo A-02 — carril S
4. ✅ [🟡] Completar `.gitignore` (`*_resumen.md`, `*_minuta.md`, extensiones de audio y video que faltan), quitar los patrones sin efecto y corregir el modelo `large` del README — hallazgos A-03, A-30 — carril S
5. ✅ [🟡] Sacar de la clase Tk los flujos «transcribir y persistir» y «generar y persistir» a funciones sin interfaz, y dejar de cargar `faster_whisper` donde no se transcribe — hallazgo A-15 — diseño aprobado el 2026-11-22: docs/disenos/05-flujos-fuera-de-la-ventana.md, se implementa con las historias #7, #8, #9, #10, #11, #12 y #13 — carril L
6. ✅ [🟡] Un módulo de configuración que resuelva la ruta contra la raíz, valide el YAML y tenga los valores por defecto en un solo lugar; que la CLI los use y se quiten las claves que nadie lee — hallazgos A-08, A-09 — carril M
7. ✅ [🟡] Tratar el 401 del modo `auto` como falta de sesión, y decir en el error cuándo el token rechazado viene de `COPILOT_GITHUB_TOKEN` en vez de reabrir el login — hallazgos A-06, A-07 — carril S
8. ✅ [🟡] Hacer que la revisión de fidelidad compare contra la transcripción original, no contra las notas, o advertir de que el documento se redactó a partir de notas — hallazgo A-05 — carril M
9. ✅ [🟡] En la CLI, validar la combinación de formato y salida antes de transcribir y usar el mismo serializador que la exportación a archivo — hallazgo A-10 — carril S
10. ✅ [🟡] Consultar el catálogo de Copilot una sola vez y bajo demanda, sin abrir una sesión `auto` al arrancar, y documentar ese tráfico y el orden de búsqueda del token — hallazgo A-13 — carril S
11. ✅ [🟡] Guardar el modelo de IA elegido fuera del repo, junto al token, en vez de reescribir `config/settings.yaml` — hallazgo A-19 — carril S
12. ✅ [🟡] Eliminar `transcribir_archivo_largo`, `_on_drop`, `duracion_archivo`, `pydantic` y `tqdm`, y tratar los metadatos de `ffprobe` como opcionales — hallazgo A-20 — carril S
13. ✅ [🟡] Dejar una sola lista de modelos de Whisper y de extensiones, y un solo formateador de tiempo por uso — hallazgo A-21 — carril S
14. ✅ [🟡] Añadir a `docs/disenos/00-actual.md` los riesgos y límites, el modelo de concurrencia y los datos y secretos, y aplicar las correcciones de `2026-11-22_DRIFT_REPORT.md` a los tres contratos — hallazgo A-22 — carril S
15. ✅ [🟡] Convertir en `ErrorCopilot` las respuestas de GitHub con formato inesperado, para que el diálogo de login no se quede colgado — hallazgo A-17 (posible) — carril S
16. ✅ [🟢] No habilitar «Transcribir» tras generar un documento de una entrada cuyo audio ya no existe — hallazgo A-26 — carril S
17. ✅ [🟢] Mostrar en pantalla o en la pestaña Registro los errores de «Guardar como…» — hallazgo A-27 — carril S
18. ✅ [🟡] No sobrescribir sin aviso la transcripción, el resumen o la minuta de otra grabación con el mismo nombre en la misma carpeta (`reunion.m4a` y `reunion.mp4`); decidir antes entre incluir la extensión de origen en el nombre o preguntar antes de sobrescribir — hallazgo A-25, separado del punto 1 — carril S o M según la decisión
19. ✅ [🟡] Cubrir con tests los rechazos de la CLI (archivo inexistente o extensión no admitida, fallo al transcribir) y sus órdenes de sesión (`--copilot-logout`, `--copilot-modelos` sin sesión), con las rutas de token aisladas y sin red, sin fijar lo que cambiará el punto 9 — hallazgo A-16, separado del punto 2 — carril S
20. ✅ [🟡] Que `--copilot-modelos` y el selector de modelo de la ventana no ofrezcan modelos de familias no autorizadas ni sugieran ponerlos en `ia.modelo` — hallazgo A-12, complemento de la historia 03 — carril S
21. ✅ [🟡] Decidir si la exclusión de Mistral AI cubre también los modelos cuyo nombre no contiene «mistral» (Codestral, Devstral, Ministral, Pixtral, Magistral) y, si es así, ampliar la lista de familias — decisión del usuario pendiente, historia 03 — carril S
22. ✅ [🟡] Que la ventana no cambie en silencio por «Auto-detectar» un idioma de `transcripcion.idioma` que Whisper admite pero que no está en su selector (por ejemplo `nl`): hoy el mismo YAML da resultados distintos en la ventana y en la CLI — hallazgo nuevo de la historia 05 — carril S
23. [🟡] Que la revisión de fidelidad contraste el documento con la transcripción original y no con las notas, para que un dato que se coló al extraer las notas no pase como revisado: revisar por partes no detecta datos inventados y una sola petición supera `max_caracteres_bloque`, así que necesita diseño — hallazgo A-05 (salida «revisar contra el original»), historia 06 — carril L
24. ✅ [🟡] Aceptar la revisión de fidelidad solo si conserva las tareas y los acuerdos del documento, no solo sus secciones, para que una revisión que borra tareas no sustituya a la minuta — hallazgo A-05 (segunda mitad del escenario) — carril S
25. ✅ [🟡] Avisar en el documento cuando Copilot cortó una respuesta (por longitud, por el filtro de contenido o porque el stream terminó sin cierre), también en las notas de una parte, para no dar por completo un documento truncado — hallazgo A-11 (escenario B, posible), historia 07 — carril S
26. ✅ [🟡] Avisar antes de redactar si las notas de todas las partes superan el límite de entrada del modelo (`max_prompt_tokens`, que sale del catálogo del punto 10), para no pagar las notas y fallar en la redacción — hallazgo A-11 (escenario C, posible), historia 07 — carril M
27. ✅ [🟡] Respetar `Retry-After` en los 429 de Copilot en vez de la espera fija de 2, 4 y 8 s — hallazgo A-11 (dirección del arreglo), historia 07 — carril S
28. ✅ [🟡] Entregar el documento ya redactado con una nota de la aplicación, en vez de un error, si falla la pasada de completar secciones o la revisión de fidelidad, para no pagar otra vez la redacción — hallazgo A-11 (relacionado: `_generar` no protege esas dos pasadas), historia 07 — carril S

## Backlog

1. ✅ Como usuario, quiero cancelar la generación de un resumen o una minuta, para no tener que cerrar la app cuando el modelo tarda. — hallazgo A-04 — carril M
2. ✅ Como usuario con una cuenta de empresa, quiero que mi transcripción nunca se envíe a un modelo de una familia no autorizada, tampoco en modo `auto` ni con un modelo escrito a mano, para cumplir la política de mi empresa. — hallazgo A-12 — carril M
3. ✅ Como usuario, quiero que la app me avise cuando un documento quedó incompleto y que conserve las partes ya procesadas si una falla, para no pagar de nuevo toda la generación. — hallazgo A-11 (en parte posible) — carril M
4. ✅ Como usuario, quiero un botón para cerrar el programa, para salir sin depender del control de la ventana. — carril S
5. Como usuario, quiero un panel de configuración con todo lo que se puede configurar, para ajustar la app sin editar `config/settings.yaml` a mano. — diseño aprobado el 2026-11-22: docs/disenos/06-panel-de-configuracion.md, se implementa con las historias #14, #15, #16, #17, #18, #19, #20, #21 y #22 — carril L
6. Como usuario, quiero iniciar y cerrar la sesión de GitHub Copilot desde el panel de configuración, para activar la IA sin esperar a generar un documento ni usar la terminal. Requires: #5 — diseño aprobado el 2026-11-22: docs/disenos/06-panel-de-configuracion.md, se implementa con las historias #23, #24 y #25 — carril M
7. ✅ Como quien mantiene el código, quiero que `faster_whisper` se cargue solo al construir un modelo de Whisper, para que abrir la ventana o la CLI sin transcribir no pague la carga de la librería de transcripción. — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia A — carril M
8. ✅ Como quien mantiene el código, quiero sacar de la ventana las opciones, el transcriptor y la ruta de la transcripción, para poder probarlos y usarlos sin interfaz gráfica. — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia B1 — Requires: #7 — carril M
9. ✅ Como quien mantiene el código, quiero que «transcribir y persistir» viva fuera de la ventana, para que la ventana solo lo llame y pinte el resultado. — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia B2 — Requires: #8 — carril M
10. ✅ Como quien mantiene el código, quiero sacar de la ventana el texto, la ruta y la fecha de los documentos, para probarlos sin interfaz gráfica. — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia C1 — Requires: #7 — carril M
11. ✅ Como quien mantiene el código, quiero que la generación de fondo viva fuera de la ventana, para que la cancelación y la vista no dependan de Tk. — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia C2 — Requires: #10 — carril M
12. ✅ Como quien mantiene el código, quiero que un gestor de documentos lleve la generación vigente y el asistente, para tener un solo sitio que sabe qué generación está activa. — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia D1 — Requires: #11 — carril M
13. ✅ Como quien mantiene el código, quiero que el gestor decida y guarde lo que llega de cada generación, para que el único punto de decisión sea un objeto sin interfaz. — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia D2 — Requires: #12 — carril M
14. ✅ Como quien mantiene el código, quiero que al abrir la ventana las preferencias guardadas ganen al YAML y que los valores inválidos den aviso y se ignoren, para leer la configuración efectiva sin tocar `config/settings.yaml`. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia A1 — carril M
15. ✅ Como quien mantiene el código, quiero convertir y validar los valores del formulario con los topes y los mensajes del panel, para que un valor inválido no llegue a las preferencias. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia A2a — Requires: #14 — carril S
16. ✅ Como quien mantiene el código, quiero guardar y restablecer las preferencias en una sola escritura atómica, para que un fallo a medio escribir no deje el archivo a medias ni pierda lo que ya estaba. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia A2b — Requires: #15 — carril S
17. ✅ Como quien mantiene el código, quiero que `guardar_formulario` y los valores laterales se calculen sin ventana, para probar el guardado y el aviso de reinicio sin interfaz gráfica. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia A3 — Requires: #16 — carril S
18. ✅ Como quien mantiene el código, quiero que el hilo de la transcripción reciba sus parámetros desde el hilo principal y no lea la configuración, para que cambiar los ajustes en el panel no provoque una carrera con una transcripción en curso. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia C0 — carril S
19. ✅ Como usuario, quiero una vista «⚙ Configuración» (`Ctrl+3`) con los ajustes de Transcripción y Salida, para cambiar el formato de salida y el idioma sin editar `config/settings.yaml`. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia C1 — Requires: #17, #18 — carril M
20. ✅ Como usuario, quiero que la vista Configuración tenga las opciones avanzadas de Transcripción y de Historial y el botón «Restablecer valores del proyecto», para ajustar los parámetros finos y volver a los valores del proyecto. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia C2 — Requires: #19 — carril M
21. ✅ Como usuario, quiero ajustar en el panel el dominio de Copilot Enterprise, la revisión de fidelidad y la temperatura de la IA, para que los documentos usen mis valores sin editar el YAML. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia D1 — Requires: #20 — carril M
22. ✅ Como usuario, quiero elegir el modelo de IA desde el panel de configuración y ver un aviso si el modelo es de una familia no autorizada, para cambiarlo sin usar el selector lateral ni el YAML. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia D2 — Requires: #21 — carril M
23. ✅ Como quien mantiene el código, quiero que la app sepa de dónde sale la sesión de Copilot (ninguna, opencode, archivo propio o variable de entorno) sin hacer red, para que la vista lo muestre sin leer ni mostrar el token. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia B — Requires: Salud #26 — carril S
24. ✅ Como quien mantiene el código, quiero cerrar solo la sesión propia de la app y dejar intacta la de opencode, para que cerrar la sesión desde el panel no borre credenciales ajenas. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia E1 — Requires: #23 — carril S
25. Como usuario, quiero ver en la vista Configuración la sección Sesión de GitHub Copilot, con botones para iniciarla o cerrarla, para activar o desactivar la IA sin esperar a generar un documento ni usar la terminal. — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia E2 — Requires: #24, #22 — carril M

## Pospuesto

- A-18 — La búsqueda del historial corre en el hilo de la interfaz y podría congelar la ventana con cientos de reuniones. Motivo: sin medición; se retoma cuando el historial crezca o se note lentitud.
- Pendientes de `AGENTS.md` (modelo por defecto, reutilizar la sesión `auto`, soporte de `/responses`): fuera del backlog por decisión del 2026-11-22; se añaden con `/backlog`.
