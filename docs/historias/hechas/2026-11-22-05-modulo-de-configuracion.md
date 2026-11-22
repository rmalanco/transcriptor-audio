# 05 · Módulo de configuración

> Origen: `BACKLOG.md`, «Salud del código» #6 — hallazgos A-08 y A-09 (aceptados en `goldfish_review_report.md`,
> órdenes 6 y 13) — carril M. Refinada con `/story` el 2026-11-22, sin usuario al otro lado: las decisiones están en
> «Supuestos». La configuración se lee desde un solo sitio que resuelve su ruta contra la raíz del proyecto, valida
> el YAML, tiene los valores por defecto de cada clave y es la fuente de los valores por defecto de la CLI. Se quitan
> las claves que nadie lee.

## Historia

Como persona que usa la app (desde un acceso directo o desde la terminal) y edita `config/settings.yaml` a mano,
quiero que la app use siempre la configuración del proyecto, sea cual sea la carpeta desde la que la lanzo, que un
error en el YAML me diga en qué archivo y en qué clave está en vez de mostrar un trazo de Python, y que la CLI
respete lo que pongo en el YAML salvo que pase la opción en la línea de órdenes, para no transcribir con otra
configuración sin darme cuenta ni tener que adivinar qué falló.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dada una carpeta de trabajo que no es la del proyecto y que tiene su propio
  `config/settings.yaml` con `transcripcion.beam_size: 1`, cuando se ejecuta la CLI sin `--config` con
  `reunion.m4a -o salida.txt`, entonces termina con código 0 y Whisper recibe el `beam_size` del
  `config/settings.yaml` del proyecto (hoy, 5), no el 1 de la carpeta de trabajo. Si se pasa `--config otro.yaml` con
  una ruta relativa, se interpreta desde la carpeta de trabajo, como cualquier ruta escrita en la terminal. En la
  ventana: al lanzar `run_ui.py` desde otra carpeta, la ventana se abre con las opciones y el historial del proyecto,
  y elegir otro modelo de IA en el selector cambia la línea `ia.modelo` del `config/settings.yaml` del proyecto.
  (antes: sin `--config`, la CLI y la ventana buscan `config/settings.yaml` en la carpeta de trabajo. Si no existe,
  `FileNotFoundError` con trazo de Python antes de transcribir o de abrir la ventana. Si existe otro, lo usan sin
  avisar.)
- [ ] [MODIFICA: sin spec] Configuración con errores o incompleta, pasada con `--config`. Ningún caso deja un trazo de
  Python:
  - Con una sangría rota en la línea 3, la CLI termina con código 1 sin cargar Whisper ni transcribir y escribe en
    `stderr` «Error: La configuración <ruta> no es un YAML válido (línea 3, columna 4).».
  - Con `transcripcion.beam_size: "cinco"`, termina con código 1 sin transcribir y escribe «Error: En la
    configuración <ruta>, `transcripcion.beam_size` debe ser un número entero mayor que 0 (vale «cinco»).». Un valor
    fuera de los permitidos da el mismo tipo de mensaje: `salida.formato: "pdf"` da «… `salida.formato` debe ser uno
    de txt, srt, vtt, json (vale «pdf»).».
  - Sin la sección `salida`, sin `transcripcion.idioma` y con `ia:` vacío, `reunion.m4a -o salida.txt` termina con
    código 0, Whisper recibe el idioma `es` y `salida.txt` sale en formato `txt` con marcas de tiempo
    (`[00:00:00 --> 00:00:02] Hola equipo.`). `--copilot-modelos` sin sesión responde «No has iniciado sesión…» con
    código 1. Cada clave que falta toma su valor por defecto, que está definido una sola vez y es el mismo para la CLI
    y la ventana.
  - En la ventana, con cualquiera de los dos primeros casos en el `config/settings.yaml` del proyecto, aparece un
    diálogo de error con el mismo texto y la ventana principal no se queda abierta. Con el tercer caso, la ventana
    arranca y genera documentos con los valores por defecto.

  (antes: un YAML mal formado da el trazo de `yaml.parser`. Si falta una clave de `modelo`, `transcripcion` o
  `salida`, hay `KeyError`, que en la CLI sale como «Error durante la transcripción: 'transcripcion'». Con `ia:`
  vacío, `AttributeError` en las órdenes de Copilot de la CLI y al generar en la ventana. Un archivo vacío da
  `TypeError`. Un tipo inválido falla dentro de faster-whisper después de cargar el modelo, y
  `ia.max_caracteres_bloque: 0` da `ZeroDivisionError` al generar.)
- [ ] [MODIFICA: sin spec] Dada una configuración con `transcripcion.idioma: "en"` y `salida.formato: "srt"`, cuando
  se ejecuta la CLI con `reunion.m4a -o salida.srt --config <esa configuración>`, sin `-l` ni `-f`, entonces Whisper
  recibe el idioma `en` y `salida.srt` está en SRT. Con la misma configuración y
  `reunion.m4a -o salida.vtt -l fr -f vtt`, Whisper recibe `fr` y `salida.vtt` está en VTT: la opción explícita gana
  al YAML. La ayuda de `-l` y `-f` dice «por defecto: el de la configuración». (antes: `-l` vale `es` y `-f` vale
  `txt` por defecto de `argparse`, y la CLI no lee `transcripcion.idioma`, `salida.formato`,
  `salida.incluir_timestamps` ni `salida.palabra_por_palabra`.)

### Cómo se verifican

- **Con tests, sin ventana ni red** (`./venv/bin/python -m pytest -q`): la CLI se ejecuta dentro del proceso, como
  en `tests/test_cli.py`, con la carpeta de trabajo cambiada a una carpeta temporal. Whisper es el doble
  `modelo_whisper_falso` de `tests/conftest.py`, que guarda los argumentos con los que se le llama (`language`,
  `beam_size`). El criterio 1 lee el `beam_size` esperado del `config/settings.yaml` real del proyecto, sin
  escribirlo. Las órdenes de Copilot usan las rutas de token aisladas (`rutas_aisladas` de `tests/test_copilot.py`).
  Para comprobar que los tests muerden: volver a leer la ruta relativa a la carpeta de trabajo, dejar `-l` con
  `es` fijo y quitar un valor por defecto. Con cada rotura debe fallar al menos un test.
- **A mano, solo la ventana:** desde una carpeta que no sea la del proyecto, `python <raíz>/run_ui.py`. Comprobar
  que la ventana abre, que el historial muestra las entradas del proyecto y que, al elegir otro modelo de IA,
  `git diff config/settings.yaml` muestra solo la línea `ia.modelo` (y deshacerla después). Después, con un YAML
  mal formado y con `transcripcion.beam_size: "cinco"`, comprobar el diálogo de error, y con `ia:` vacío, que se
  genera un resumen.
- **Claves que nadie lee:** `grep` de `sample_rate`, `chunk_duration` y `task` en `config/settings.yaml` no
  encuentra nada, y una configuración que todavía las contenga se carga sin error.

## Plan

- Un único punto de carga: resuelve la ruta por defecto contra la raíz del proyecto, como ya hace el historial; lee
  el archivo en UTF-8; parte de una tabla con el valor por defecto y la comprobación de cada clave usada; completa
  con ella lo que falte y valida tipos y valores permitidos. Los fallos son un error propio, con un mensaje que nombra
  el archivo, la clave, lo esperado y el valor recibido.
- La ventana y la CLI toman todos los valores de ese punto, sin valores por defecto propios. La ventana muestra el
  error en un diálogo y no arranca. La CLI lo escribe en `stderr` y sale con código 1 antes de cargar Whisper. La
  reescritura de `ia.modelo` usa la misma ruta resuelta.
- En la CLI, idioma, formato, marcas de tiempo y marcas por palabra dejan de tener valor fijo en `argparse`: si no se
  pasan, valen los de la configuración. La ayuda lo dice.
- Quitar del YAML las tres claves que nadie lee. Actualizar la guía de configuración, las instrucciones para agentes
  y los contratos donde dicen que la configuración obliga a ejecutar desde la raíz o que la CLI ignora el YAML.
- Tests de los tres criterios. El test de carga actual se reescribe para que no dependa de la carpeta de trabajo.

## Fuera de alcance

- Guardar el modelo de IA fuera del repo (Salud #11, A-19): `ia.modelo` se sigue reescribiendo en el YAML, ahora
  en la ruta resuelta.
- Sacar los flujos de la clase Tk (Salud #5, A-15).
- Validar la combinación de formato y salida antes de transcribir y unificar el serializador de la CLI (Salud #9,
  A-10). Ojo: con `salida.formato: "srt"` en el YAML y sin `-o`, la CLI transcribe todo y después pide `--salida`,
  igual que hoy con `-f srt`. El YAML versionado trae `txt`, así que no cambia nada si no se toca.
- Una sola lista de modelos de Whisper (Salud #13, A-21): la validación de `modelo.nombre` usa la lista que ya existe.
- Panel de configuración (Backlog #5).
- `--ui` ignora `--config` y `--log` (A-28, descartado).
- Poder lanzar la CLI desde cualquier carpeta sin `PYTHONPATH` (punto de entrada instalable). Hoy
  `python -m src.main` fuera de la raíz da `No module named 'src'`, y `python <raíz>/src/main.py` también falla. Lo
  pide A-08 solo para la configuración, no para el arranque.
- Cambiar el modelo de IA por defecto (`gpt-4.1` frente a `claude-haiku-5.5`): es un pendiente abierto de
  `AGENTS.md`, fuera del backlog.
- Añadir una opción `--timestamps` para reactivar las marcas de tiempo cuando el YAML las desactiva.
- Los valores por defecto de los parámetros de `TranscriptorAudio` y `AsistenteIA` (por ejemplo,
  `condition_on_previous_text=True` o `temperatura=0.3`). La app deja de depender de ellos porque siempre los pasa,
  pero las firmas no cambian.
- La exclusión de familias de modelos (regla 7) se sigue aplicando al enviar, no al cargar la configuración.
- Probar la lectura en UTF-8 en Windows (A-08, escenario C, «posible»): se lee en UTF-8, pero no se verifica en
  Windows.

## Sugerencias

- **Seguir el patrón del historial**, que ya resuelve una ruta relativa contra la raíz del proyecto. Es la señal
  concreta en el código: la misma regla, en dos sitios, con resultados distintos.
- **Una tabla clave → valor por defecto y comprobación**, en vez de un `if` por clave. Hay 21 claves usadas y
  los mismos valores por defecto repetidos en tres sitios (la ventana, `AsistenteIA` y `argparse`).
- **Booleanos frente a enteros:** en Python, `True` es un `int`. Sin una comprobación explícita,
  `beam_size: true` pasaría como 1.
- **Implementarla después de cerrar la historia 04**, que está cambiando ahora la generación en la ventana y en
  `AsistenteIA`, las mismas funciones que leen la sección `ia:`.
- Si se quiere más: registrar en el log las claves desconocidas, para que una errata como `idoma:` no pase
  inadvertida, y listar todas las claves inválidas en un solo mensaje. Ninguna de las dos la pide un criterio.

## Supuestos

Decididos por el agente, sin usuario al otro lado. El orquestador debe validarlos.

1. **Claves de `config/settings.yaml` y quién las lee** (`grep` en `src/` el 2026-11-22; las líneas de `src/ui.py`
   pueden moverse, así que se cita la función):

   | Clave | Quién la lee hoy | Propuesta |
   |---|---|---|
   | `modelo.nombre`, `.dispositivo`, `.compute_type` | Ventana con `[]` (`AppTranscriptor.__init__`); CLI con `[]` si no se pasa `-m`/`-d`/`-c` (`main`, `src/main.py:135-137`) | Se conservan |
   | `audio.sample_rate` | Nadie (los `sample_rate` de `src/utils.py` y `src/ui.py` son metadatos de `ffprobe`) | **Quitar** |
   | `audio.chunk_duration` | Nadie (`chunk_duration` es un parámetro de `transcribir_archivo_largo`, que no tiene llamadores, y no lee el YAML) | **Quitar** (y con ella la sección `audio`) |
   | `transcripcion.idioma` | Ventana con `[]` (`AppTranscriptor.__init__`); la CLI la ignora (`-l` con `es`) | Se conserva; la CLI pasa a leerla |
   | `transcripcion.task` | Nadie: la ventana fija `task="transcribe"` (`_procesar_transcripcion`) y la CLI usa `-t` | **Quitar**. Si la leyera la CLI, `translate` traduciría por la CLI y no en la ventana |
   | `transcripcion.beam_size`, `best_of`, `temperature`, `condition_on_previous_text`, `compression_ratio_threshold`, `logprob_threshold`, `no_speech_threshold` | Ventana con `[]` (`_procesar_transcripcion`); CLI con `[]` (`main`, `src/main.py:164-170`) | Se conservan |
   | `salida.formato` | Ventana con `[]` (`AppTranscriptor.__init__`); la CLI la ignora (`-f` con `txt`) | Se conserva; la CLI pasa a leerla |
   | `salida.incluir_timestamps` | Ventana con `[]` (`AppTranscriptor.__init__`); la CLI la ignora (`--no-timestamps`) | Se conserva; la CLI pasa a leerla |
   | `salida.palabra_por_palabra` | Ventana con `[]` (`_procesar_transcripcion`); la CLI la ignora (`--word-timestamps`) | Se conserva; la CLI pasa a leerla |
   | `ia.modelo` | Ventana con `.get` y `MODELO_POR_DEFECTO` (`_modelo_ia_configurado`); escrita por `guardar_modelo_ia` (`_al_cambiar_modelo_ia`) | Se conserva |
   | `ia.copilot_enterprise_url` | Ventana con `.get` (`_generar_documento_ia`, `_cargar_modelos_ia`, `_iniciar_sesion_copilot`); CLI con `.get` (`src/main.py:115`) | Se conserva |
   | `ia.temperatura`, `max_caracteres_bloque`, `peticiones_paralelas`, `revision_fidelidad` | Ventana con `.get` y valores por defecto propios (`_generar_documento_ia`) | Se conservan |
   | `historial.ruta` | Ventana con `.get` (`AppTranscriptor.__init__` → `Historial`, que la resuelve contra la raíz) | Se conserva |

   Una configuración antigua que todavía tenga las claves quitadas, u otra clave desconocida, se carga sin error: se
   ignora.
2. **Qué significa «validar».** Lo mínimo, sin librerías (no se usa `pydantic`, que nadie importa y que Salud #12
   propone quitar):
   - Cada sección es un mapa o está vacía (`ia:` vacío = sección sin claves).
   - Solo se comprueban las 21 claves usadas, por tipo y por valores permitidos, y los valores permitidos salen de
     listas que ya existen en el código:
     - `modelo.nombre`: uno de la lista de modelos de Whisper de la app.
     - `modelo.dispositivo`: `cpu`, `cuda` o `auto`.
     - `modelo.compute_type`: `int8`, `int16`, `float16` o `float32`.
     - `salida.formato`: `txt`, `srt`, `vtt` o `json`.
     - `beam_size`, `best_of`, `ia.max_caracteres_bloque` e `ia.peticiones_paralelas`: enteros mayores que 0 (el 0
       de `max_caracteres_bloque` divide por cero hoy).
     - `transcripcion.temperature` e `ia.temperatura`: números mayores o iguales que 0.
     - Los tres umbrales: números.
     - `condition_on_previous_text`, `incluir_timestamps`, `palabra_por_palabra` y `revision_fidelidad`: booleanos.
     - `transcripcion.idioma` e `historial.ruta`: texto no vacío.
     - `ia.modelo` y `ia.copilot_enterprise_url`: texto, que puede estar vacío. El modelo vacío ya tiene su error,
       según la spec «Modelo sin configurar».
   - No se inventan rangos que el código no necesita, como un máximo de temperatura o un umbral entre 0 y 1.
3. **Valores por defecto.** Regla: donde hoy el código ya tiene un valor por defecto, se conserva, para no cambiar
   el comportamiento cuando falta la clave. Donde hoy revienta con `KeyError`, se usa el valor del
   `config/settings.yaml` versionado. Resultado:
   - `modelo`: `large-v3-turbo`, `cpu`, `int8`.
   - `transcripcion`: `idioma` `es`, `beam_size` 5, `best_of` 5, `temperature` 0.0,
     `condition_on_previous_text` `false`, umbrales 2.4, -1.0 y 0.6.
   - `salida`: `txt`, `incluir_timestamps` `true`, `palabra_por_palabra` `false`.
   - `ia`: `modelo` `gpt-4.1` (`MODELO_POR_DEFECTO`), `copilot_enterprise_url` vacío, `temperatura` 0.3,
     `max_caracteres_bloque` 60000, `peticiones_paralelas` 3, `revision_fidelidad` `true`.
   - `historial.ruta`: `data/historial.db`.

   **Decisión pendiente del usuario:** el YAML versionado trae `temperatura: 0.2` y `revision_fidelidad: false`,
   distintos de los valores por defecto del código, que se conservan (0.3 y `true`). Solo importan si se borra la
   línea.
4. **Rutas.** Sin `--config`, se usa `<raíz del proyecto>/config/settings.yaml`, y un `config/settings.yaml` en la
   carpeta de trabajo se ignora: es el caso que más duele, usar otra configuración en silencio. Con `--config`, una
   ruta relativa se interpreta desde la carpeta de trabajo. Si el archivo no existe, sea el de por defecto o el
   indicado, es un error: «No se encontró la configuración <ruta>.» con código 1, nunca todos los valores por
   defecto en silencio. Un archivo existente pero vacío equivale a un YAML sin claves: todo toma su valor por defecto.
   Un YAML cuya raíz no es un mapa es un error.
5. **Qué ve el usuario de la ventana ante un error de configuración:** un diálogo de error con el mismo mensaje que
   la CLI, la misma línea en la consola y la aplicación se cierra. No arranca con los valores por defecto, porque eso
   sería usar otra configuración en silencio.
6. **La CLI desde otra carpeta** solo se puede lanzar con el paquete importable (`PYTHONPATH=<raíz>`): se comprobó
   que `python -m src.main` fuera de la raíz da `No module named 'src'`. Por eso el criterio 1 se prueba dentro del
   proceso con la carpeta de trabajo cambiada, y el arranque sin `PYTHONPATH` queda fuera de alcance.
   `--listar-modelos` sigue sin cargar la configuración. Las órdenes `--copilot-*` sí la cargan y la validan, como
   hoy.
7. **Marcas `[MODIFICA: sin spec]`.** Los tres comportamientos existen en el código y ninguno tiene spec:
   `docs/specs/cli.md` solo fija «Transcribir a un archivo», que pasa `-f srt` explícito y no cambia. `/cerrar`
   decide si añade estos comportamientos a `cli.md` o crea un dominio `configuracion`.
8. **Quitar las claves que nadie lee entra en esta historia** y no se separa. Son tres líneas del YAML y la
   documentación que las menciona. Se comprueba con `grep`, sin criterio propio, porque no cambia nada observable:
   nadie las lee.
9. **Los textos de los mensajes** y los datos de los criterios (`reunion.m4a`, `beam_size: 1`, `"cinco"`, `"pdf"`,
   `en`, `fr`) son ejemplos elegidos para que el resultado sea concreto. Lo que se exige es que el mensaje nombre
   el archivo, la clave, lo esperado y el valor, y que no haya trazo de Python. La línea y la columna del YAML mal
   formado son las que da PyYAML (comprobado: `line 3, column 4` con una sangría rota en la línea 3).
10. **Los tests de hoy.** El YAML de `tests/test_cli.py` no tiene `transcripcion.idioma` ni la sección `salida`.
    Hoy funciona porque la CLI no lee esas claves; después funcionará por los valores por defecto (`es`, `txt`).
    `tests/test_basico.py::test_cargar_configuracion` depende de la carpeta de trabajo y del YAML real, y se
    reescribe.

## Historias derivadas (para el backlog)

- Como usuario que pone en `transcripcion.idioma` un código que Whisper admite pero que no está en el selector de la
  ventana (por ejemplo `nl`), quiero que la ventana no lo cambie en silencio por «Auto-detectar», para transcribir
  en el idioma que configuré. Hoy `AppTranscriptor.__init__` hace `IDIOMAS_DISPONIBLES.get(idioma_cfg,
  "Auto-detectar")` y la CLI pasa el código tal cual: el mismo YAML da resultados distintos en la ventana y en la
  CLI. Hallazgo nuevo de este refinamiento, no está en la auditoría. — carril S.

## Cierre

Cerrada con `/cerrar` el 2026-11-22. Tests: `./venv/bin/python -m pytest -q`, 149 pasan. Revisión del orquestador
sobre el módulo nuevo y los cambios de la CLI: listo para commit. Delta aplicado en `docs/specs/configuracion.md`
(dominio nuevo, cuatro comportamientos; `Origen` apunta a esta historia). `docs/specs/cli.md` no cambia: su único
comportamiento usa `-f srt` explícito y no lo contradice.

| # | Marca | Criterio | Evidencia con test y `ruta:línea` | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Desde otra carpeta, la CLI usa el `beam_size` del proyecto; `--config` relativo se resuelve desde la carpeta de trabajo; la ventana usa la configuración y el historial del proyecto; cambiar el modelo reescribe `ia.modelo` | CLI: `tests/test_cli.py:66` (`test_cli_desde_otra_carpeta_usa_la_configuracion_del_proyecto`). Carga: `tests/test_configuracion.py:9` y `:20`. Reescritura de `ia.modelo`: `tests/test_configuracion.py:167`, `tests/test_basico.py:46`. Ventana: verificación visual (apertura, historial). Cambio de modelo en el selector: no verificado en pantalla | cumple en la CLI y en la apertura de la ventana (tests y verificación visual del 2026-11-22). Pendiente aceptado: cambio de modelo en el selector |
| 2 | [MODIFICA: sin spec] | YAML mal formado, valor de tipo inválido, valor no permitido y archivo inexistente: mensajes exactos, código 1 sin transcribir, y diálogo en la ventana sin abrirla | CLI: `tests/test_cli.py:85` (YAML, código 1, sin transcribir), `:99` (valor no permitido, código 1, sin transcribir). Mensajes: `tests/test_configuracion.py:27` (inexistente), `:40` (YAML con línea y columna), `:95` (tipo), `:108` (valor no permitido), `:187` (`modelo.nombre` fuera de la lista de Whisper), `:221` (parametrizado: resto de claves). Booleano que no vale como entero: `:121`. Ventana: verificación visual | cumple (tests y verificación visual del 2026-11-22) |
| 3 | [MODIFICA: sin spec] | Claves ausentes toman su valor por defecto (igual en CLI y ventana); claves desconocidas se ignoran; `ia:` vacío no rompe la CLI | Archivo vacío: `tests/test_configuracion.py:52`. `ia:` vacío: `:72`. Clave ausente: `:84`. Claves desconocidas: `:154`. CLI con configuración incompleta: `tests/test_cli.py:114`. `--copilot-modelos` con `ia:` vacío: `tests/test_cli.py:161`. Ventana con `ia:` vacío, resumen generado con los valores por defecto: verificación visual | cumple (tests y verificación visual del 2026-11-22) |
| 4 | [MODIFICA: sin spec] | Sin `-l`/`-f`, la CLI usa `transcripcion.idioma` y `salida.formato`; con ellas, ganan las opciones | `tests/test_cli.py:128` (sin opciones) y `:144` (la opción explícita gana). Ayuda de `-l`, `-f`: `src/main.py:97` y `:99` («por defecto: el de la configuración») | cumple |

Claves que nadie lee: `tests/test_configuracion.py:178` comprueba que el YAML del proyecto es válido y no contiene
`audio` ni `transcripcion.task`.

**Pendientes aceptados:**

- Decisión del usuario pendiente: los valores por defecto del código para `ia.temperatura` (0.3) y
  `ia.revision_fidelidad` (activada) difieren de los del YAML versionado (0.2 y desactivada). Solo importan si se borra
  la línea del YAML.
- El cambio de modelo desde el selector de la ventana no se verificó en pantalla (sí por test,
  `tests/test_configuracion.py:167`).
- `python -m src.main` sigue necesitando ejecutarse desde la raíz (o con `PYTHONPATH`) para importar el paquete. No se
  probó la lectura en UTF-8 en Windows.
- Las marcas de tiempo y el modo palabra por palabra de la CLI leen la configuración pero no tienen test propio
  (comprobado a mano).

### Verificación visual (2026-11-22)

Hecha por el orquestador sobre la ventana real, lanzada desde una carpeta que no es la del proyecto y que tenía su
propio `config/settings.yaml` señuelo (`beam_size: 77`).

- YAML mal formado: diálogo «Configuración» con «La configuración <ruta> no es un YAML válido (línea 3, columna 4).»;
  la ventana principal no se construye y el proceso sale con código 1.
- `transcripcion.beam_size: "cinco"`: diálogo «Configuración» con «En la configuración <ruta>,
  `transcripcion.beam_size` debe ser un número entero mayor que 0 (vale «cinco»).»; sin ventana principal, código 1.
- Sin tocar nada: la ventana arranca con el `beam_size` del proyecto (5, no 77) y con el historial del proyecto
  (`<raíz>/data/historial.db`).
- Con `ia:` vacío y sin las claves de `transcripcion` ni `salida`: la ventana arranca, Whisper recibe idioma `es`, y se
  genera un resumen con los valores por defecto (`gpt-4.1`, temperatura 0.3, 60000, 3 peticiones, revisión activada).
- No verificado en la ventana (solo por test del módulo): que elegir otro modelo en el selector reescribe la línea
  `ia.modelo` del YAML del proyecto. No se pulsó para no modificar la configuración real. Pendiente aceptado.
