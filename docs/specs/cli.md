# CLI

## Propósito
Transcribir un audio o video desde la terminal (`python -m src.main`) y guardar el resultado en un archivo.

## Comportamiento

### Transcribir a un archivo
- Given un audio `reunion.m4a` en el que se detecta «Hola equipo.» (0–2 s) y «Cerramos el punto.» (3–5 s), when se ejecuta la CLI con `reunion.m4a -o salida.srt -f srt`, then termina con código 0, escribe en la salida estándar «Transcripción guardada en: <ruta de salida.srt>» y `salida.srt` contiene los segmentos numerados, cada uno con su línea de tiempos `HH:MM:SS,mmm --> HH:MM:SS,mmm` y su texto.

Origen: docs/historias/hechas/2026-11-22-02-dependencias-y-tests-del-flujo.md
