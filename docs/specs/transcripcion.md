# Transcripción

## Propósito
Qué pasa con el resultado de una transcripción hecha desde la interfaz gráfica: dónde queda guardado, qué ve la persona
cuando algo falla y cuándo puede abrir la carpeta del archivo.

## Comportamiento

### Guardado de la transcripción antes de exportarla
- Given un audio en una carpeta donde no se puede escribir y un historial disponible, when termina la transcripción,
  then la transcripción aparece en el historial con su texto y sus segmentos, y se ve en la pestaña Texto con «Copiar»,
  «Guardar como…» y los botones de generar resumen y minuta habilitados.
- Given el caso anterior, when termina la transcripción, then aparece un diálogo de advertencia que indica
  `<nombre>_transcripcion.<formato>` y el motivo, y la misma línea queda en la pestaña Registro.
- Given un historial que falla al guardar y un audio en una carpeta donde sí se puede escribir, when termina la
  transcripción, then el archivo `<nombre>_transcripcion.<formato>` se exporta junto al audio, la transcripción se ve
  en pantalla y aparece un diálogo de advertencia con el motivo del fallo del historial.

Origen: docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md

### Abrir carpeta
- Given una transcripción en pantalla cuyo archivo se exportó, when termina la transcripción, then «Abrir carpeta»
  está habilitado.
- Given una transcripción en pantalla cuyo archivo no se exportó, when termina la transcripción, then «Abrir carpeta»
  está deshabilitado.

Origen: docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md

### Aviso cuando el resultado no queda guardado en ningún sitio
- Given un historial no disponible o que falla al guardar, y un audio en una carpeta donde no se puede escribir, when
  termina la transcripción, then la transcripción sigue en pantalla con «Copiar» y «Guardar como…» habilitados, y el
  aviso dice «El resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para conservarlo.».

Origen: docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md
