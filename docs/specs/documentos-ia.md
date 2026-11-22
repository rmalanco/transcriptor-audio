# Documentos de IA

## Propósito
Qué pasa con el resumen y la minuta que genera Copilot a partir de una transcripción: dónde quedan guardados y qué ve
la persona en la pestaña correspondiente cuando el archivo o el historial fallan.

## Comportamiento

### Guardado del documento antes de exportarlo
- Given una transcripción en el historial y un audio en una carpeta donde no se puede escribir, when Copilot devuelve
  la minuta, then la minuta queda en la entrada del historial con el modelo usado y, si el título no se editó a mano,
  con el título que da la minuta.
- Given el caso anterior, when termina la generación, then la pestaña Minuta muestra el documento con «Copiar» y
  «Guardar como…» habilitados, su línea de estado avisa que no se pudo exportar `<nombre>_minuta.md` y el motivo, y
  no se pide otra generación. No aparece ningún diálogo; el aviso también queda en la pestaña Registro.
- Given una transcripción en el historial y un audio en una carpeta donde no se puede escribir, when Copilot devuelve
  el resumen, then se aplica lo mismo con `<nombre>_resumen.md`.

Origen: docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md

### Estado de un documento generado
- Given un documento generado, when termina la generación, then la línea de estado de la pestaña dice por separado qué
  pasó con el archivo («guardado como <nombre>» o «no se pudo exportar <nombre>: <motivo>») y qué pasó con el historial
  («guardado en el historial» o «no se guardó en el historial: <motivo>»), y la pestaña Registro recibe el mismo texto.
- Given un documento generado que no se pudo exportar ni guardar en el historial, when termina la generación, then la
  línea de estado dice «El resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para conservarlo.».

Origen: docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md

### Entrada eliminada durante la generación
- Given una entrada del historial que se elimina mientras Copilot genera su documento, when termina la generación, then
  el documento se muestra y se exporta junto al audio si se puede, y la línea de estado dice «no se guardó en el
  historial: La entrada ya no está en el historial»; si tampoco se pudo exportar, la línea de estado añade «El
  resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para conservarlo.».

Origen: carril S, 2026-11-22: avisa si la entrada del historial se eliminó mientras se generaba un documento (A-02)

### Errores de Guardar como… de un documento
- Given un resumen o una minuta generados, when «Guardar como…» no puede escribir el archivo, then aparece un diálogo de
  error con «No se pudo guardar el archivo» y el motivo, y la misma información queda en la pestaña Registro.

Origen: carril S, 2026-11-22: los errores de «Guardar como…» se muestran en un diálogo y en Registro (A-27)

### Pestañas sin restos
- Given un documento generado para una grabación, when se carga otro archivo, then la línea de estado de las pestañas
  Resumen y Minuta vuelve a mostrar el modelo de IA configurado, sin el mensaje del documento anterior.

Origen: carril S, 2026-11-22: al cargar otro archivo, las pestañas de IA quedan sin restos del documento anterior (A-02)
