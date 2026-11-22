# Documentos de IA

## Propósito
Qué pasa con el resumen y la minuta que genera Copilot a partir de una transcripción: dónde quedan guardados y qué ve
la persona en la pestaña correspondiente cuando el archivo o el historial fallan. La transcripción solo se envía a
modelos de Copilot autorizados por la empresa: nunca a los de las familias excluidas, ni con el modelo escrito a mano
ni en modo `auto`.

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

### Modelos de familias no autorizadas
- Given `ia.modelo` escrito a mano con un modelo de una familia excluida (`kimi` o `mistral`, reconocida porque el nombre
  del modelo contiene el de la familia, sin distinguir mayúsculas; por ejemplo `Mistral-Large-3` o `kimi-k3-mini`), when
  se pide un resumen o una minuta de una transcripción larga, then no se envía ninguna petición a Copilot, aparece el
  error «El modelo «<modelo>» es de la familia «<familia>», que no está autorizada por la empresa. Elige otro modelo en
  el selector o en `ia.modelo` de config/settings.yaml.» y la pestaña no muestra ningún documento nuevo. El resultado es
  el mismo si el catálogo de modelos de Copilot no se puede consultar.
- Given `ia.modelo` en `auto` y una sesión en la que Copilot propone primero `kimi-k3` y ofrece también
  `mistral-medium-3` y `gpt-5.4`, los tres compatibles con `/chat/completions`, when se genera una minuta, then todas las
  peticiones con texto de la transcripción van a `gpt-5.4` y la línea de estado y el historial muestran «auto →
  gpt-5.4». Lo mismo vale cuando la sesión `auto` se renueva a mitad de la generación, por caducidad o tras un 401: el
  modelo de la sesión nueva tampoco puede ser de una familia excluida.
- Given `ia.modelo` en `auto` y una sesión que solo ofrece `mistral-medium-3` (compatible con `/chat/completions`) y
  `gpt-5.3-codex` (solo `/responses`), when se pide una minuta, then no se envía ninguna petición y aparece el error
  «El modo auto no ofrece ningún modelo autorizado y compatible con /chat/completions (<modelos ofrecidos>). Elige un
  modelo concreto en `ia.modelo`.»

Origen: docs/historias/hechas/2026-11-22-03-familias-no-autorizadas.md

### Modelo sin configurar
- Given `ia.modelo` vacío, when se pide un resumen o una minuta, then no se envía nada a Copilot y aparece el error «No
  hay ningún modelo de IA configurado. Elige uno en el selector o en `ia.modelo` de config/settings.yaml.»

Origen: docs/historias/hechas/2026-11-22-03-familias-no-autorizadas.md

### Cancelar la generación
- Given una generación de la minuta o del resumen en curso, when pulso «■ Cancelar» en la pestaña de ese documento,
  then en 1 segundo como máximo, aunque la petición a Copilot siga abierta, la línea de estado de la pestaña dice
  «Generación cancelada», la barra de estado dice «Generación de la minuta cancelada» (o «del resumen»), la pestaña
  Registro anota la cancelación, la transcripción no cambia, «Generar» de las dos pestañas y el selector de modelo
  quedan habilitados, «Transcribir» vuelve a su estado anterior, y puedo generar otra vez, cargar otro archivo o abrir
  el historial al momento.
- Given una regeneración cancelada de un documento ya guardado, when se cancela, then la pestaña vuelve a mostrar el
  documento anterior con «↻ Regenerar», «Copiar» y «Guardar como…» habilitados, y la línea de estado dice «Generación
  cancelada · se conserva la minuta anterior» (o «el resumen anterior»).
- Given una generación cancelada, when Copilot termina esa petición después, con un documento, con un error o con un
  401, then el documento no se guarda en el historial ni se exporta junto al audio, y no aparece ningún diálogo ni se
  abre el inicio de sesión en Copilot.
- Given una generación cancelada, when Copilot recibe peticiones después de la cancelación, then ninguna es de ese
  documento.

Origen: docs/historias/hechas/2026-11-22-04-cancelar-generacion.md

### Cerrar la ventana durante una generación
- Given una generación de la minuta o del resumen en curso, when cierro la ventana y respondo «no» a «Hay una generación
  de la minuta en curso. ¿Cancelarla y salir?» (o «del resumen»), then la ventana sigue abierta y la generación continúa.
- Given una generación de la minuta o del resumen en curso, when cierro la ventana y respondo «sí», then la generación
  se cancela, la ventana se cierra y el documento no se guarda en el historial ni junto al audio, aunque Copilot lo
  termine después.

Origen: docs/historias/hechas/2026-11-22-04-cancelar-generacion.md
