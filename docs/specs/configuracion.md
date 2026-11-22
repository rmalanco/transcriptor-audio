# Configuración

## Propósito
Qué configuración usa la app: siempre `config/settings.yaml` del proyecto, salvo que se indique otra con `--config`, y
con valores por defecto para las claves que falten. Qué pasa cuando el archivo falta o está mal, y qué manda entre el
YAML y las opciones de la CLI.

## Comportamiento

### Configuración del proyecto desde cualquier carpeta
- Given una carpeta de trabajo que no es la del proyecto y que tiene su propio `config/settings.yaml` con
  `transcripcion.beam_size: 1`, when se ejecuta la CLI sin `--config` con `reunion.m4a -o salida.txt`, then termina con
  código 0 y Whisper recibe el `beam_size` del `config/settings.yaml` del proyecto, no el 1 de la carpeta de trabajo.
- Given la misma carpeta de trabajo, when se ejecuta la CLI con `--config otro.yaml`, then `otro.yaml` se busca en la
  carpeta de trabajo.
- Given que `run_ui.py` se lanza desde una carpeta que no es la del proyecto, when se abre la ventana, then usa la
  configuración y el historial (`data/historial.db`) del proyecto.

Origen: docs/historias/hechas/2026-11-22-05-modulo-de-configuracion.md

### Configuración con errores
- Given un `--config` con una sangría rota en la línea 3, when se ejecuta la CLI, then termina con código 1 sin cargar
  Whisper ni transcribir y escribe en la salida de error «Error: La configuración <ruta> no es un YAML válido (línea 3,
  columna 4).».
- Given un `--config` con `transcripcion.beam_size: "cinco"`, when se ejecuta la CLI, then termina con código 1 sin
  transcribir y escribe «Error: En la configuración <ruta>, `transcripcion.beam_size` debe ser un número entero mayor
  que 0 (vale «cinco»).».
- Given un `--config` con `salida.formato: "pdf"`, when se ejecuta la CLI, then termina con código 1 sin transcribir y
  escribe «Error: En la configuración <ruta>, `salida.formato` debe ser uno de txt, srt, vtt, json (vale «pdf»).».
- Given un `--config` con una ruta que no existe, when se ejecuta la CLI, then termina con código 1 y escribe «Error: No
  se encontró la configuración <ruta>.».
- Given que el `config/settings.yaml` del proyecto tiene uno de los errores anteriores, when se lanza `run_ui.py`, then
  aparece un diálogo «Configuración» con el mismo mensaje, la ventana principal no se abre y el proceso termina con
  código 1.

Origen: docs/historias/hechas/2026-11-22-05-modulo-de-configuracion.md

### Claves ausentes
- Given un YAML con `ia:` vacío y sin la sección `salida` ni la clave `transcripcion.idioma`, when se ejecuta la CLI con
  `reunion.m4a -o salida.txt`, then termina con código 0, Whisper recibe el idioma `es` y `salida.txt` sale en formato
  `txt` con marcas de tiempo (`[00:00:00,000 --> 00:00:02,000] Hola equipo.`).
- Given un archivo de configuración vacío, when se carga, then todas las claves toman su valor por defecto.
- Given una clave que falta, when se carga la configuración en la CLI o en la ventana, then toma el mismo valor por
  defecto en las dos.
- Given un YAML con claves que la app no usa (por ejemplo `audio.sample_rate`), when se carga, then esas claves se
  ignoran sin error.
- Given `ia:` vacío y ninguna sesión de GitHub Copilot iniciada, when se ejecuta `--copilot-modelos`, then escribe «No
  has iniciado sesión…» y termina con código 1 sin trazo de Python.

Origen: docs/historias/hechas/2026-11-22-05-modulo-de-configuracion.md

### Las opciones de la CLI ganan al YAML
- Given una configuración con `transcripcion.idioma: "en"` y `salida.formato: "srt"`, when se ejecuta la CLI con
  `reunion.m4a -o salida.srt --config <esa configuración>` sin `-l` ni `-f`, then Whisper recibe el idioma `en` y
  `salida.srt` está en formato SRT.
- Given la misma configuración, when se ejecuta la CLI con `reunion.m4a -o salida.vtt -l fr -f vtt`, then Whisper
  recibe el idioma `fr` y `salida.vtt` está en formato VTT.

Origen: docs/historias/hechas/2026-11-22-05-modulo-de-configuracion.md
