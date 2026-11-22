# Transcripción

## Propósito
Qué pasa con el resultado de una transcripción hecha desde la interfaz gráfica: dónde queda guardado, qué ve la persona
cuando algo falla, cuándo puede abrir la carpeta del archivo y qué pasa al cargar otro archivo.

## Comportamiento

### Guardado de la transcripción antes de exportarla
- Given un audio en una carpeta donde no se puede escribir y un historial disponible, when termina la transcripción,
  then la transcripción aparece en el historial con su texto y sus segmentos, y se ve en la pestaña Texto con «Copiar»,
  «Guardar como…» y los botones de generar resumen y minuta habilitados.
- Given el caso anterior, when termina la transcripción, then aparece un diálogo de advertencia que indica
  `<archivo>.<ext>_transcripcion.<formato>` y el motivo, y la misma línea queda en la pestaña Registro.
- Given un historial que falla al guardar y un audio en una carpeta donde sí se puede escribir, when termina la
  transcripción, then el archivo `<archivo>.<ext>_transcripcion.<formato>` se exporta junto al audio, la transcripción se ve
  en pantalla y aparece un diálogo de advertencia con el motivo del fallo del historial.

Origen: docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md
Origen: carril S, 2026-11-22: los archivos junto al audio llevan el nombre completo del original (`reunion.m4a_transcripcion.<formato>`) (decisión del usuario, punto #18)

### Grabaciones con el mismo nombre
- Given `reunion.m4a` y `reunion.mp4` en la misma carpeta, when se transcriben y se generan sus documentos, then cada grabación tiene sus propios archivos (`reunion.m4a_…` y `reunion.mp4_…`) y ninguno sobrescribe al otro.

Origen: carril S, 2026-11-22: dos grabaciones con el mismo nombre en la misma carpeta ya no comparten archivos (decisión del usuario, punto #18)

### Abrir carpeta
- Given una transcripción en pantalla cuyo archivo se exportó, when termina la transcripción, then «Abrir carpeta»
  está habilitado.
- Given una transcripción en pantalla cuyo archivo no se exportó, when termina la transcripción, then «Abrir carpeta»
  está deshabilitado.
- Given una transcripción en pantalla, when «Guardar como…» escribe el archivo, then «Abrir carpeta» queda habilitado.

Origen: docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md
Origen: carril S, 2026-11-22: «Abrir carpeta» se habilita también tras un «Guardar como…» que escribe el archivo (A-27)

### Aviso cuando el resultado no queda guardado en ningún sitio
- Given un historial no disponible o que falla al guardar, y un audio en una carpeta donde no se puede escribir, when
  termina la transcripción, then la transcripción sigue en pantalla con «Copiar» y «Guardar como…» habilitados, y el
  aviso dice «El resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para conservarlo.».

Origen: docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md

### Cargar otro archivo
- Given una transcripción en pantalla, con o sin resumen y minuta, when se carga otro archivo, then la vista queda sin
  resultado: el texto, el título y el vínculo con el historial desaparecen, «Copiar», «Guardar como…» y «Abrir
  carpeta» quedan deshabilitados, y las pestañas Resumen y Minuta vuelven a su estado inicial con «Generar»
  deshabilitado.
- Given una transcripción o una generación de documento en curso, when se intenta cargar otro archivo, then no se carga
  y un aviso dice «Espera a que termine el proceso en curso.». Una generación cancelada deja de contar como
  proceso en curso.

Origen: carril S, 2026-11-22: al cargar otro archivo se invalida el resultado, las pestañas de IA y el vínculo con el historial (A-02)
Origen: docs/historias/hechas/2026-11-22-04-cancelar-generacion.md

### Descartar un resultado sin guardar
- Given una transcripción en pantalla que no quedó guardada ni en el historial ni como archivo, when se carga otro
  archivo o se abre una entrada del historial, then se pregunta «La transcripción en pantalla no quedó guardada en
  ningún sitio y se perderá al cargar otra. ¿Continuar?»; si se responde que no, la transcripción sigue en pantalla.

Origen: carril S, 2026-11-22: se pregunta antes de reemplazar un resultado que no quedó guardado en ningún sitio (A-02)

### Errores de Guardar como…
- Given un resultado en pantalla, when «Guardar como…» no puede escribir el archivo, then aparece un diálogo de error
  con «No se pudo guardar el archivo» y el motivo, y la misma información queda en la pestaña Registro.

Origen: carril S, 2026-11-22: los errores de «Guardar como…» se muestran en un diálogo y en Registro (A-27)

### Transcribir tras generar sin audio
- Given una entrada del historial cuyo audio ya no existe, abierta en la ventana, when se genera su resumen o su
  minuta, then «Transcribir» sigue deshabilitado al terminar.

Origen: carril S, 2026-11-22: «Transcribir» no se habilita tras generar un documento sin audio (A-26)

### Cargar un archivo sin metadatos
- Given un equipo sin `ffprobe` instalado, o un archivo del que `ffprobe` no puede leer los metadatos, when se carga un archivo de audio o vídeo admitido, then el archivo se carga igual y se muestra su tamaño con «duración desconocida».
- Given el diálogo de selección de archivo, when se abre, then ofrece las mismas extensiones de audio y vídeo que la app admite al validar un archivo (incluidas `.ts` y `.mts`).

Origen: carril S, 2026-11-22: los metadatos de ffprobe son opcionales (A-20)

### Idioma configurado fuera del selector
- Given `transcripcion.idioma` con un código que no está en el selector de idioma de la ventana (por ejemplo `nl`), when se abre la ventana, then el selector muestra ese código como opción seleccionada y la transcripción lo usa, igual que la CLI.

Origen: carril S, 2026-11-22: la ventana no cambia a «Auto-detectar» un idioma configurado que Whisper admite (hallazgo nuevo de la historia 05)
