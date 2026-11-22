# CLI

## Propósito
Transcribir un audio o video desde la terminal (`python -m src.main`) y guardar el resultado en un archivo.

## Comportamiento

### Transcribir a un archivo
- Given un audio `reunion.m4a` en el que se detecta «Hola equipo.» (0–2 s) y «Cerramos el punto.» (3–5 s), when se ejecuta la CLI con `reunion.m4a -o salida.srt -f srt`, then termina con código 0, escribe en la salida estándar «Transcripción guardada en: <ruta de salida.srt>» y `salida.srt` contiene los segmentos numerados, cada uno con su línea de tiempos `HH:MM:SS,mmm --> HH:MM:SS,mmm` y su texto.

Origen: docs/historias/hechas/2026-11-22-02-dependencias-y-tests-del-flujo.md

### Formatos que necesitan archivo
- Given el formato `srt` o `vtt` (pasado con `-f` o tomado de `salida.formato`) y ninguna salida con `-o`, when se ejecuta la CLI, then termina con código 1 sin cargar Whisper ni transcribir y escribe en la salida de error «Error: el formato srt necesita un archivo de salida: añade -o <archivo>.» (con `vtt`, el mismo texto con `vtt`).

Origen: carril S, 2026-11-22: la CLI valida la combinación de formato y salida antes de cargar Whisper (A-10)

### Transcribir a la salida estándar
- Given el formato `txt` o `json` y ninguna salida con `-o`, when se ejecuta la CLI, then la salida estándar contiene exactamente el mismo texto que se escribiría en el archivo con `-o` (en `txt`, con las marcas `[HH:MM:SS,mmm --> HH:MM:SS,mmm]`; en `json`, con las palabras cuando se pide `--word-timestamps`), y los mensajes informativos de `--verbose` van a la salida de error.

Origen: carril S, 2026-11-22: la salida estándar usa el mismo serializador que el archivo y `--verbose` escribe en la salida de error (A-10)

### Rechazos
- Given un archivo que no existe, when se ejecuta la CLI con `reunion.m4a` inexistente, then termina con código 1, escribe en la salida de error «Error: Archivo no encontrado: <ruta>» y no carga Whisper.
- Given un archivo con una extensión no admitida (por ejemplo `notas.pdf`), when se ejecuta la CLI con ese archivo, then termina con código 1, escribe en la salida de error «Error: Formato no soportado: .pdf. Soportados: <extensiones admitidas>» y no carga Whisper.
- Given un audio válido y un fallo durante la transcripción, when se ejecuta la CLI con `reunion.m4a -o salida.txt`, then termina con código 1 y no queda ningún archivo `salida.txt`.

Origen: carril S, 2026-11-22: rechazos de la CLI cubiertos con tests (A-16)

### Sesión de Copilot desde la CLI
- Given una sesión de GitHub Copilot guardada por la app y otra sesión en opencode, when se ejecuta `--copilot-logout`, then escribe «Sesión cerrada», la sesión de la app deja de existir, la de opencode no se toca y termina con código 0.
- Given que la app no tiene una sesión propia guardada, when se ejecuta `--copilot-logout`, then escribe «No había sesión guardada por esta app» y termina con código 0.
- Given que la app no tiene una sesión propia guardada, when se ejecuta `--copilot-modelos`, then escribe en la salida de error «No has iniciado sesión. Ejecuta: python -m src.main --copilot-login» y termina con código 1.
- Given una sesión de Copilot cuyo catálogo incluye modelos de familias no autorizadas, when se ejecuta `--copilot-modelos`, then no lista esos modelos y escribe al final «Se omite 1 modelo de una familia no autorizada por la empresa.» si omite uno, o «Se omiten <n> modelos de familias no autorizadas por la empresa.» si omite varios.

Origen: carril S, 2026-11-22: órdenes de sesión de la CLI cubiertas con tests y `--copilot-modelos` sin familias excluidas (A-12, A-16)
