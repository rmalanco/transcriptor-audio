# Informe de auditoría

Status: resolved (2026-11-22) — decisiones en `goldfish_review_report.md`

> /auditar (Tándem) · 2026-11-22 · Preset: completa (4 revisores) · Alcance: todo el repositorio
>
> Los revisores trabajaron por lectura del código, sin ejecutar la aplicación ni los tests. Los 67 hallazgos
> originales se deduplicaron en 32. Los ids entre paréntesis remiten al hallazgo de cada revisor. Las decisiones
> sobre cada hallazgo están en `goldfish_review_report.md`.

## Resumen

| Severidad | Cantidad |
|---|---|
| 🔴 Blocker | 1 |
| 🟡 Major | 21 |
| 🟢 Nit | 10 |

## Revisores

| Revisor | Objetivo | Estado | Hallazgos |
|---|---|---|---|
| tandem-code-auditor | Código de todo el repo | completado | 22 (0 🔴, 11 🟡, 11 🟢) |
| tandem-codebase-details | `docs/disenos/00-actual.md` contra el código | completado | 11 (0 🔴, 7 🟡, 4 🟢) |
| tandem-zoom-out | Simplicidad y alcance | completado | 15 (0 🔴, 9 🟡, 6 🟢) |
| tandem-design | Arquitectura | completado | 19 (1 🔴, 13 🟡, 5 🟢) |

## Hallazgos (de más grave a menos)

### [A-01] 🔴 Blocker · Corrección (pérdida de datos) · `src/ui.py:628-645`, `:658-667`, `:812-815`
(design-1, code-auditor-1, zoom-out-1, codebase-details-1, codebase-details-2)
- **Escenario:** el audio está en una carpeta sin permiso de escritura, en un medio de solo lectura o en un disco
  lleno. Al terminar la transcripción, `guardar_transcripcion` lanza `OSError` antes de `_finalizar_ok`: no se fija
  `resultado_actual`, no se llama a `Historial.crear` y Copiar y Guardar quedan deshabilitados. El trabajo se pierde.
  Con el resumen y la minuta pasa lo mismo: `write_text` va antes de `guardar_documento`, y la petición ya se gastó.
- **Dirección del arreglo:** guardar primero en el historial y mostrar el resultado; tratar el fallo de exportación
  como un aviso aparte.
- **Verificado por el Elefante:** sí, el orden de las llamadas es el descrito.

### [A-02] 🟡 Major · Corrección · `src/ui.py:494-520`, `:783-786`, `:925-937`, `:953`
(code-auditor-2, design-2)
- **Escenario:** se transcribe A, se carga B sin transcribirlo y se pulsa «Generar minuta». `_cargar_archivo` solo
  cambia `archivo_actual`. La minuta de A se escribe como `B_minuta.md`, sobrescribe sin aviso la que hubiera y lleva
  la fecha de B, que además queda en la entrada de A del historial. También puede ocurrir durante una generación,
  porque solo se comprueba `_transcribiendo()`.
- **Dirección del arreglo:** al cargar otro archivo, reiniciar resultado, pestañas de IA y vínculo al historial, o
  derivar ruta y fecha del archivo que originó el resultado.
- **Verificado por el Elefante:** sí, `_cargar_archivo` no toca `resultado_actual` ni `id_historial`.

### [A-03] 🟡 Major · Seguridad / Documentación · `.gitignore:35-42`, `:55-63`; `README.md:147-154`
(code-auditor-3)
- **Escenario:** con un audio dentro del repositorio, la app escribe `<audio>_resumen.md` y `<audio>_minuta.md`.
  Ningún patrón ignora esos `.md`, así que `git add -A` publica el contenido de la reunión. La lista de grabaciones
  ignoradas omite extensiones que la app acepta: `.aac`, `.opus`, `.wma`, `.avi`, `.mov`, `.flv`, `.wmv`, `.m4v`,
  `.ts`, `.mts`.
- **Dirección del arreglo:** ignorar `*_resumen.md` y `*_minuta.md` y completar las extensiones, o corregir el README.

### [A-04] 🟡 Major · Operación · `src/ui.py:811`, `:469-475`; `src/asistente_ia.py:283-309`
(design-3, codebase-details-10)
- **Escenario:** `AsistenteIA` acepta `cancelar`, pero la interfaz no se lo pasa. El timeout de 180 s es de
  inactividad y cada petición admite 4 intentos, así que un modelo lento bloquea «Transcribir» y «Generar» sin
  límite. La única salida es cerrar la app, que mata el hilo sin preguntar.
- **Dirección del arreglo:** pasar un `Event` de cancelación, añadir un botón de cancelar y confirmar al cerrar.

### [A-05] 🟡 Major · Corrección (fidelidad) · `src/asistente_ia.py:446`, `:472-475`
(design-4, zoom-out-9)
- **Escenario:** con más de un bloque, `texto` pasa a ser las notas, y la «revisión de fidelidad» compara contra
  esas notas, no contra la transcripción. Un error al extraer las notas (un nombre, una fecha, una condición) nunca
  se contrasta con la fuente. La revisión se acepta solo contando secciones, así que una que borre tareas pasa.
- **Dirección del arreglo:** revisar por bloque contra el texto original, o advertir al usuario de que el documento
  se redactó a partir de notas.

### [A-06] 🟡 Major · Corrección · `src/asistente_ia.py:248-255`; `src/copilot.py:299-300`; `src/ui.py:822-824`
(code-auditor-5)
- **Escenario:** con `ia.modelo: auto` y el token revocado, el 401 de `abrir_sesion_auto` llega como
  `ErrorAsistenteIA` genérico. No se invalida el token ni se abre el diálogo de login, y `self._asistente` queda con
  el token viejo. Cada intento repite «Vuelve a iniciar sesión» sin ofrecer cómo.
- **Dirección del arreglo:** propagar ese 401 como falta de sesión, igual que el de `/chat/completions`.

### [A-07] 🟡 Major · Corrección · `src/copilot.py:89-91`, `:129-135`; `src/ui.py:817-821`
(code-auditor-6, design-12)
- **Escenario:** `COPILOT_GITHUB_TOKEN` contiene un token caducado. Tras el 401 se abre el login, que guarda un token
  válido en el archivo, pero `leer_token` sigue devolviendo primero el de la variable. La generación se reintenta,
  vuelve el 401 y el diálogo se abre otra vez, sin fin.
- **Dirección del arreglo:** si el token rechazado viene de la variable de entorno, decirlo en el error en vez de
  abrir el login.

### [A-08] 🟡 Major · Operación · `src/ui.py:99`, `:131-137`; `src/transcriber.py:205-210`; `src/main.py:115`, `:135-137`; `src/asistente_ia.py:150`
(code-auditor-7, design-11, codebase-details-5, zoom-out-3, zoom-out-13)
- **Escenario A:** lanzar `run_ui.py` desde otra carpeta da `FileNotFoundError` antes de mostrar la ventana, porque
  `config/settings.yaml` se resuelve contra el directorio de trabajo. El historial, en cambio, se resuelve contra la
  raíz del proyecto.
- **Escenario B:** un YAML sin alguna clave de `modelo`, `transcripcion` o `salida` da `KeyError`; con `ia:` vacío,
  `main.py:115` da `AttributeError`; con `max_caracteres_bloque: 0`, `dividir_texto` da `ZeroDivisionError`.
- **Escenario C (posible):** `cargar_configuracion` abre sin `encoding`; en Windows con cp1252 podría fallar.
- **Dirección del arreglo:** un módulo de configuración que resuelva la ruta contra la raíz, valide y tenga los
  valores por defecto en un solo lugar.

### [A-09] 🟡 Major · Corrección / Documentación · `src/main.py:88-92`; `src/ui.py:615`; `README.md:142-143`
(code-auditor-8, codebase-details-6, zoom-out-3, design-13)
- **Escenario:** poner `transcripcion.idioma: "en"` o `salida.formato: "srt"` no cambia la CLI, que usa sus valores
  de argparse (`es`, `txt`). `transcripcion.task`, `audio.sample_rate` y `audio.chunk_duration` no las lee nadie.
- **Dirección del arreglo:** que los valores por defecto de la CLI salgan del YAML y quitar las claves muertas.

### [A-10] 🟡 Major · Corrección · `src/main.py:75`, `:180-207`; `src/utils.py:104-156`
(code-auditor-4, design-13, zoom-out-5, codebase-details-7)
- **Escenario:** `python -m src.main audio.wav --formato srt` (ejemplo de la propia ayuda) transcribe todo el audio y
  solo entonces responde «use --salida» y sale con código 1. Además, el `txt` y el `json` de `stdout` tienen otro
  formato que los de archivo: `--word-timestamps` sin `-o` pierde las palabras.
- **Dirección del arreglo:** validar la combinación antes de transcribir y usar un único serializador por formato.

### [A-11] 🟡 Major · Corrección / Coste · `src/asistente_ia.py:313-319`, `:354-356`, `:367-386`, `:414-425`
(design-5, code-auditor-11, zoom-out-9)
- **Escenario A:** en una transcripción de 10 bloques, uno recibe 429 cuatro veces. Falla todo el documento y se
  descartan las notas ya obtenidas; reintentar reenvía todo. No se lee `Retry-After`.
- **Escenario B (posible):** si el modelo corta por longitud, solo hay un `warning` en el log; el documento truncado
  se guarda y la interfaz muestra «Listo».
- **Escenario C (posible):** las notas de N bloques se concatenan sin consultar `max_prompt_tokens`; una grabación
  muy larga puede fallar en la redacción final, después de pagar todas las notas.
- **Dirección del arreglo:** cachear las notas por bloque, respetar `Retry-After` y mostrar el truncado al usuario.

### [A-12] 🟡 Major · Cumplimiento · `src/copilot.py:237-238`, `:258`, `:316-321`; `src/ui.py:888-893`
(design-6, zoom-out-8)
- **Escenario:** `FAMILIAS_EXCLUIDAS` («no autorizadas por la empresa») y `PRECIO_MAX_ECONOMICO` solo filtran el
  desplegable. El modo `auto` toma el primer modelo compatible sin filtrar, y un modelo excluido escrito a mano en el
  YAML se respeta. Posible: que Copilot ofrezca un modelo de esas familias en `auto`.
- **Dirección del arreglo:** aplicar la política en el punto de envío, o eliminarla si no es un requisito real.

### [A-13] 🟡 Major · Privacidad / Simplicidad · `src/ui.py:143`, `:865-886`; `src/copilot.py:86-107`, `:287-322`
(design-7, codebase-details-3, codebase-details-4, zoom-out-8, code-auditor-nit-8)
- **Escenario:** con un token disponible, cada arranque de la interfaz hace `GET /models`, `POST /models/session` y
  otro `GET /models` sin acción del usuario; la sesión abierta se descarta. El token puede ser el de opencode, leído
  sin consentimiento. El README da a entender que solo hay red al pedir un resumen o una minuta.
- **Dirección del arreglo:** consultar el catálogo una vez y bajo demanda; documentar el tráfico y el orden de
  búsqueda del token.

### [A-14] 🟡 Major · Riesgo externo · `src/copilot.py:27-28`, `:71-81`; `src/asistente_ia.py:257-261`
(design-8, zoom-out-8)
- **Escenario:** toda la función de IA depende de una API no documentada, del `client_id` de otra aplicación y de un
  `API_VERSION` fijo. Si GitHub bloquea ese `client_id` o cambia `/models/session`, resumen y minuta dejan de
  funcionar sin alternativa. Posible: marcar las peticiones internas como `x-initiator: agent` puede tratarse como
  evasión de facturación.
- **Dirección del arreglo:** registrarlo como riesgo explícito y concentrar lo específico de Copilot en `copilot.py`.
  El revisor propone además admitir otros proveedores; eso choca con la regla del proyecto «Solo GitHub Copilot».

### [A-15] 🟡 Major · Arquitectura · `src/ui.py` completo; `src/ui_historial.py:103`, `:236`, `:254`; `src/historial.py:13`; `src/__init__.py:3-4`
(design-9, zoom-out-7, codebase-details-9)
- **Escenario:** los flujos transcribir → exportar → historial y generar → escribir → historial solo existen dentro
  de callbacks de Tk. Por eso la CLI no tiene IA ni historial y A-01 y A-02 no se pueden cubrir con tests sin
  ventana. `PanelHistorial` llama a métodos privados de la app. `historial.py` y `__init__.py` cargan
  `faster_whisper` incluso para `--copilot-logout`.
- **Dirección del arreglo:** extraer dos funciones sin Tk (transcribir y persistir; generar y persistir) y mover
  dataclasses y configuración a módulos sin dependencias pesadas.

### [A-16] 🟡 Major · Tests · `requirements.txt`; `tests/test_ui.py:13-33`; `tests/test_basico.py:40-45`
(code-auditor-10, codebase-details-11)
- **Escenario:** `pytest` no está en ningún manifiesto ni instalado, y no hay CI. Los 4 tests de `ui.py` (1 183
  líneas) solo comprueban constantes. Sin ningún test: `main.py`, `ui_historial.py`, `ui_copilot.py`,
  `validar_archivo`, `obtener_info_archivo` y `guardar_transcripcion`. Sin test en `_completar`: reintentos por
  429/5xx, 403 y `model_not_supported`. `test_cargar_configuracion` depende del directorio de trabajo y del
  `settings.yaml` real, que la interfaz reescribe.
- **Dirección del arreglo:** declarar las dependencias de desarrollo y cubrir primero el flujo transcribir, guardar,
  historial y la CLI.

### [A-17] 🟡 Major (posible) · Corrección · `src/copilot.py:153-159`, `:188`, `:222`, `:310`; `src/ui_copilot.py:67-78`
(code-auditor-9)
- **Escenario:** una respuesta 200 que no es JSON (portal cautivo, proxy) lanza `ValueError` o `KeyError`, que
  `_iniciar` no captura: el hilo muere y el diálogo modal se queda en «Solicitando código…». En
  `abrir_sesion_auto` no se comprueba el estado del catálogo. Falta una respuesta real que lo confirme.
- **Dirección del arreglo:** convertir los errores de formato en `ErrorCopilot`.

### [A-18] 🟡 Major (posible) · Escala · `src/historial.py:190-197`; `src/ui_historial.py:120-143`; `src/ui.py:1042-1043`
(design-10)
- **Escenario:** cada búsqueda recorre toda la tabla aplicando `normalizar` a cinco columnas, incluido el texto
  completo, en el hilo de la interfaz. `refrescar` recrea hasta 200 marcos en cada cambio. Con cientos de reuniones
  la ventana se congelaría al teclear. Sin medir. Más allá de 200 entradas solo se llega buscando.
- **Dirección del arreglo:** medir primero; después, columna normalizada precalculada o FTS5 y consultas en un hilo.

### [A-19] 🟡 Major · Colocación · `src/transcriber.py:210-225`; `src/ui.py:897-911`
(zoom-out-2, code-auditor-nit-10)
- **Escenario:** elegir un modelo en el desplegable reescribe `config/settings.yaml`, que está versionado. Una
  preferencia personal ensucia el árbol de trabajo y altera el archivo que lee `test_cargar_configuracion`.
- **Dirección del arreglo:** guardar las preferencias de usuario fuera del repo, junto al token.

### [A-20] 🟡 Major · YAGNI · `src/transcriber.py:171-197`; `requirements.txt:3-6`; `src/utils.py:42-61`; `src/ui.py:464-467`
(zoom-out-4, design-18, code-auditor-nit-2, codebase-details-8)
- **Escenario:** `transcribir_archivo_largo` no tiene llamadores, escribe en `/tmp` con nombre predecible y no limpia
  si falla. `_on_drop` y `duracion_archivo` tampoco se usan, ni `pydantic` ni `tqdm`. `ffprobe` solo aporta una
  etiqueta informativa, pero si falta en el `PATH` la interfaz rechaza el archivo.
- **Dirección del arreglo:** eliminar el código y las dependencias muertas, y tratar los metadatos como opcionales.

### [A-21] 🟡 Major · Reutilización · `src/main.py:13` y `src/ui.py:32`; `src/utils.py:22-23` y `src/ui.py:485-487`; `src/utils.py:75`
(zoom-out-6, design-19, code-auditor-nit-3)
- **Escenario:** `MODELOS_DISPONIBLES` está definido dos veces. `.ts` y `.mts` pasan `validar_archivo` pero no
  aparecen en el diálogo de selección. Hay cuatro formateadores de tiempo; `formatear_tiempo(1.001)` devuelve
  `00:00:01,000` porque trunca.
- **Dirección del arreglo:** una constante por lista y un formateador por uso.

### [A-22] 🟡 Major · Documentación · `docs/disenos/00-actual.md`
(design-14, zoom-out-14, zoom-out-15, codebase-details-1 a 11)
- **Escenario:** el documento describe los componentes pero omite riesgos y límites. Un lector nuevo no se entera de
  que cancelar descarta el resultado parcial, de las llamadas de red al arrancar, de las tres fuentes del token, de
  que la configuración depende del directorio de trabajo, ni del modelo de concurrencia. Varias de estas omisiones ya
  figuran en `2026-11-22_DRIFT_REPORT.md`.
- **Dirección del arreglo:** añadir «Riesgos y límites actuales», «Modelo de concurrencia» y «Datos y secretos», y
  aplicar las correcciones del informe de deriva.

### [A-23] 🟢 Nit · Esquema · `src/historial.py:18`, `:37`, `:40`, `:110-112`, `:201-233`
(design-15, zoom-out-10, zoom-out-11, code-auditor-nit-11)
- **Escenario:** `PRAGMA user_version` se escribe y nunca se lee, así que el primer cambio de esquema no tiene dónde
  decidir la migración. `resumen_en` y `minuta_en` se escriben y no se leen.
- **Dirección del arreglo:** leer la versión y aplicar migraciones ordenadas cuando haga falta la primera.

### [A-24] 🟢 Nit (posible) · Seguridad · `src/copilot.py:111-116`; `src/historial.py:115`
(design-16, code-auditor-nit-7)
- **Escenario:** el modo `0o600` solo se aplica al crear `copilot.json`; si ya existía con permisos más amplios, se
  conservan. `historial.db` se crea con la umask por defecto.
- **Dirección del arreglo:** `chmod` explícito tras abrir.

### [A-25] 🟢 Nit · Corrección · `src/ui.py:1083-1086`, `:786`
(design-17, code-auditor-nit-5)
- **Escenario:** `reunion.m4a` y `reunion.mp4` en la misma carpeta comparten `reunion_transcripcion.txt` y los `.md`;
  el segundo pisa al primero sin aviso.
- **Dirección del arreglo:** incluir la extensión de origen en el nombre o avisar antes de sobrescribir.

### [A-26] 🟢 Nit · Corrección · `src/ui.py:831`
(code-auditor-nit-4)
- **Escenario:** tras generar un documento de una entrada del historial cuyo audio ya no existe, «Transcribir» se
  habilita; pulsarlo limpia la vista y falla.
- **Dirección del arreglo:** restaurar el estado previo del botón.

### [A-27] 🟢 Nit · Operación · `src/ui.py:1149-1151`
(code-auditor-nit-6)
- **Escenario:** si «Guardar como…» falla, el error solo va a `stderr`; no aparece en pantalla ni en la pestaña
  Registro.
- **Dirección del arreglo:** llevar esos errores a la pestaña Registro o a un diálogo.

### [A-28] 🟢 Nit · Operación · `src/main.py:104-108`; `src/ui.py:1175`
(code-auditor-nit-9)
- **Escenario:** `python -m src.main --ui --log DEBUG` vuelve a INFO, porque `ui.main()` llama otra vez a
  `configurar_logging()` sin nivel. `--ui --config otro.yaml` ignora `--config`.
- **Dirección del arreglo:** pasar el nivel y la ruta de configuración a `ui.main`.

### [A-29] 🟢 Nit · Dependencias · `requirements.txt:1-9`
(code-auditor-nit-1)
- **Escenario:** no hay lockfile y todo son cotas mínimas salvo `av<19`, que depende de una versión concreta de
  `faster-whisper` declarada como `>=1.0.0`. Una instalación nueva puede traer versiones no probadas.
- **Dirección del arreglo:** fijar versiones y añadir un archivo de dependencias de desarrollo.

### [A-30] 🟢 Nit · Incoherencias menores · `README.md:134`; `.gitignore`; `tests/test_registro.py:17-26`
(code-auditor-nit-11)
- **Escenario:** el README lista el modelo `large`, que la CLI rechaza. En `.gitignore`, `~/.cache/faster-whisper/` y
  `/tmp/chunk_*.wav` no hacen nada, y `*.json` y `*.txt` globales ocultarán archivos futuros. `test_registro.py`
  depende de tiempos reales (posible inestabilidad).
- **Dirección del arreglo:** corregir el README y limpiar los patrones.

### [A-31] 🟢 Nit · Simplicidad · `src/registro.py:40-60`
(zoom-out-12)
- **Escenario:** con tres peticiones paralelas hay tres hilos extra solo para registrar. Aceptable hoy.
- **Dirección del arreglo:** no ampliarlo.

### [A-32] 🟢 Nit · Documentación · `docs/disenos/00-actual.md`, «Cómo se prueba»
(codebase-details-11)
- **Escenario:** el documento no dice que los tests deben ejecutarse desde la raíz, que `test_ui.py` necesita Tkinter
  ni qué versión de Python se requiere.
- **Dirección del arreglo:** añadir esos supuestos junto con A-22.

## Cobertura

- **Revisado a fondo:** los 11 módulos de `src/`, `run_ui.py`, `config/settings.yaml`, `requirements.txt`,
  `.gitignore` y `docs/disenos/00-actual.md`. El auditor de código leyó también los 6 archivos de `tests/` completos.
- **Superficial:** `tests/` para los otros tres revisores (búsquedas por patrón).
- **No evaluado:**
  - El resultado real de los tests y el comportamiento en ejecución de la interfaz, la red y faster-whisper (nada se
    ejecutó; `pytest` no está instalado).
  - El comportamiento real de la API de Copilot: afecta a A-11, A-12, A-14 y A-17.
  - El historial de git: la ausencia de secretos en commits anteriores queda sin verificar.
  - Vulnerabilidades conocidas de las dependencias (sin lockfile ni base de avisos).
  - La compatibilidad con Python 3.10 a 3.13 y con Windows.
  - `CLAUDE.md`, `EGM.md`, `src/EGM.md` y `docs/integracion-copilot.md`: no formaban parte del contexto entregado.
- **Hallazgos «posibles»:** A-17, A-18 y A-24 enteros, y partes de A-08, A-11, A-12 y A-14. Se deducen del código,
  pero les falta una ejecución, una medición o una respuesta real que los confirme.
