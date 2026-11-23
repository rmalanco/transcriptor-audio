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
  «Guardar como…» habilitados, su línea de estado avisa que no se pudo exportar `<archivo>.<ext>_minuta.md` y el motivo, y
  no se pide otra generación. No aparece ningún diálogo; el aviso también queda en la pestaña Registro.
- Given una transcripción en el historial y un audio en una carpeta donde no se puede escribir, when Copilot devuelve
  el resumen, then se aplica lo mismo con `<archivo>.<ext>_resumen.md`.

Origen: docs/historias/hechas/2026-11-22-01-guardar-antes-de-exportar.md
Origen: carril S, 2026-11-22: los archivos junto al audio llevan el nombre completo del original (`reunion.m4a_minuta.md`) (decisión del usuario, punto #18)

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
- Given `ia.modelo` escrito a mano con un modelo de una familia excluida (`kimi`, `mistral`, `codestral`, `devstral`, `ministral`, `pixtral` o `magistral`, reconocida porque el nombre
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
- Given `ia.modelo` configurado con un modelo de una familia no autorizada, when se carga la lista de modelos del selector de la ventana, then ese modelo no se añade a las opciones.

Origen: docs/historias/hechas/2026-11-22-03-familias-no-autorizadas.md
Origen: carril S, 2026-11-22: el selector de modelo de la ventana no ofrece modelos de familias no autorizadas (A-12)
Origen: carril S, 2026-11-22: la exclusión de Mistral AI cubre todos sus modelos, también los que no llevan «mistral» en el nombre (decisión del usuario, punto #21)

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
- Given una generación de la minuta o del resumen en curso, when cierro la ventana (o pulso «Salir» o `Ctrl+Q`) y respondo «no» a «Hay una generación
  de la minuta en curso. ¿Cancelarla y salir?» (o «del resumen»), then la ventana sigue abierta y la generación continúa.
- Given una generación de la minuta o del resumen en curso, when cierro la ventana (o pulso «Salir» o `Ctrl+Q`) y respondo «sí», then la generación
  se cancela, la ventana se cierra y el documento no se guarda en el historial ni junto al audio, aunque Copilot lo
  termine después.

Origen: docs/historias/hechas/2026-11-22-04-cancelar-generacion.md
Origen: carril S, 2026-11-22: botón «Salir» y atajo Ctrl+Q (Backlog #4)

### Nota de la aplicación en documentos redactados a partir de notas
- Given una transcripción que supera `ia.max_caracteres_bloque` y se procesa en N partes (N de 2 o más), when se genera
  la minuta o el resumen, then el documento que se muestra, se guarda en el historial y se exporta termina, tras una
  línea horizontal, con «> Nota de la aplicación: la transcripción se procesó en N partes y este documento se redactó a
  partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, cifras y
  condiciones con la transcripción antes de darlo por bueno.»; la nota la añade la app, no se envía a Copilot y no
  cambia el título, la fecha ni las secciones.
- Given una transcripción que supera `ia.max_caracteres_bloque` y se procesa en N partes, when el segundo documento
  (minuta o resumen) reutiliza las notas ya extraídas, then ese documento también termina con la nota.
- Given una transcripción que cabe en una sola parte, when se genera la minuta o el resumen, then el documento no lleva
  la nota.

Origen: docs/historias/hechas/2026-11-22-06-revision-de-fidelidad.md

### Aviso de secciones que faltan
- Given una minuta o un resumen al que le siguen faltando secciones obligatorias tras pedírselas de nuevo a Copilot, when
  termina la generación, then el documento que se muestra, se guarda en el historial y se exporta termina, tras una
  línea horizontal, con «> Nota de la aplicación: a este documento le faltan secciones obligatorias que Copilot no
  devolvió ni al pedírselas de nuevo: <secciones>. No lo des por completo: vuelve a generarlo o complétalo con la
  transcripción.», donde <secciones> son los títulos que faltan, sin «#» y separados por comas (por ejemplo «Tareas y
  pendientes, Próximos pasos»). La nota no se envía a Copilot.
- Given un documento que al final tiene todas sus secciones obligatorias, when termina la generación, then no lleva esa
  nota.

Origen: docs/historias/hechas/2026-11-22-07-documento-incompleto.md

### Respuesta cortada por Copilot
- Given una transcripción que cabe en una sola parte y una redacción que Copilot corta (`finish_reason` `length` o
  `content_filter`, o un stream que termina sin `[DONE]` ni `finish_reason`), when se genera la minuta o el resumen,
  then el documento que se muestra, se guarda en el historial y se exporta termina, tras una línea horizontal, con «>
  Nota de la aplicación: Copilot cortó su respuesta antes de terminarla (<motivo>); este documento puede estar
  incompleto. No lo des por completo: vuelve a generarlo o complétalo con la transcripción.», donde <motivo> es «límite
  de longitud del modelo», «filtro de contenido de Copilot» o «la respuesta terminó sin la marca de cierre», según
  corresponda. La nota no se envía a Copilot.
- Given una transcripción que se procesa en varias partes y una petición de notas de una o varias partes que Copilot
  corta, when se genera el documento, then el documento termina, tras la línea horizontal, con «> Nota de la
  aplicación: Copilot cortó antes de terminarlas las notas de la parte N de M (<motivo>); lo que se dijo en esa parte
  puede faltar en este documento.» si corta una parte, o con «> Nota de la aplicación: Copilot cortó antes de
  terminarlas las notas de las partes X (<motivo>) y Y (<motivo>) de M; lo que se dijo en esas partes puede faltar en
  este documento.» si corta varias. Las notas de esas partes no se guardan: when después se genera el resumen con el
  mismo modelo y sin cerrar la app, then Copilot recibe otra vez las peticiones de notas de esas partes y la redacción.
- Given una respuesta completa (`finish_reason` `stop`, con o sin `[DONE]`, o `[DONE]` sin `finish_reason`), when
  termina la generación, then el documento no lleva nota de respuesta cortada ni de notas de partes cortadas.
- Given una redacción cortada a la que una petición de completar las secciones que faltaban devuelve una respuesta
  completa que sustituye al borrador, when termina la generación, then el documento no lleva nota de respuesta cortada.

Origen: docs/historias/hechas/2026-11-22-15-respuesta-cortada.md

### Notas de la aplicación juntas
- Given un documento que lleva varias notas de la aplicación (respuesta cortada, notas de partes cortadas, secciones que
  no se pudieron pedir de nuevo o que faltan, revisión no completada y, si está redactado a partir de notas de varias
  partes, la de las partes), when termina la generación, then todas van bajo una sola línea horizontal, separadas por
  una línea en blanco, en este orden: respuesta cortada, notas de partes cortadas, secciones que no se pudieron pedir
  de nuevo, secciones que faltan, revisión no completada y, la última, la de las partes («> Nota de la aplicación: la
  transcripción se procesó en N partes…»); el título y la fecha no cambian.

Origen: docs/historias/hechas/2026-11-22-07-documento-incompleto.md
Origen: docs/historias/hechas/2026-11-22-15-respuesta-cortada.md

### Fallo de una parte
- Given una transcripción que se procesa en 8 partes y la parte 7 falla (por ejemplo, Copilot responde 429 en todos sus
  intentos), when se genera el documento, then no se envía la redacción, la pestaña muestra «No se pudo generar: falló
  la parte 7 de 8: <motivo>. Se conservan las notas de las N partes que terminaron; al volver a generar solo se pedirán
  las que faltan.» (el diálogo de error muestra el mismo texto), donde <motivo> es el motivo del fallo. Con una parte
  conservada la frase dice «Se conserva la nota de la parte que terminó; al volver a generar solo se pedirán las que
  faltan.»; con ninguna, «No se conserva ninguna nota: al volver a generar se pedirán todas las partes.».
- Given ese fallo, when se vuelve a generar el mismo documento o el otro (resumen o minuta) con el mismo modelo, sin
  cerrar la app y sin guardar en la vista Configuración una clave de IA, then Copilot recibe solo las peticiones de notas de las partes que no terminaron y después la
  redacción.
- Given ese fallo, when se guarda en la vista Configuración una clave de IA (temperatura, caracteres por parte, partes a la
  vez, revisión de fidelidad o dominio) y se vuelve a generar, then la generación usa los valores guardados y vuelve a
  pedir todas las partes (las notas conservadas se pierden). Una generación en curso termina con los valores con que
  empezó, y mientras dura «Guardar» se rechaza.
- Given ese fallo, when se guarda en la vista Configuración una clave que no es de IA (por ejemplo, «Formato de salida»
  a `srt`) y se vuelve a generar, then la generación conserva las notas y solo pide las partes que faltan.
- Given una transcripción de varias partes y un modelo de una familia no autorizada, vacío, o un modo `auto` sin modelo
  válido, when se pide el documento, then el error es el mismo que con una sola parte (los de «Modelos de familias no
  autorizadas» y «Modelo sin configurar»), sin mencionar partes ni notas, y no se envía nada.
- Las notas conservadas viven en memoria y se pierden al cancelar la generación, al cambiar de modelo, al restablecer la configuración si cambia el modelo, tras tener que
  iniciar sesión de nuevo, al cerrar la app o al guardar en la vista Configuración una clave de IA.

Origen: docs/historias/hechas/2026-11-22-07-documento-incompleto.md
Origen: docs/historias/hechas/2026-11-22-23-grupo-ia.md

### Notas que no caben en el modelo
- Given una transcripción en varias partes cuyas notas estimadas superan el límite de entrada del modelo (del catálogo
  de Copilot), when se genera el documento, then no se envía la redacción y aparece el error «las notas de las N partes
  suman unos T tokens y el modelo «M» admite como máximo L tokens de entrada, así que no se envió la redacción. Elige
  en el selector un modelo con más contexto y vuelve a generar; con otro modelo se pedirán de nuevo las notas de todas
  las partes.» (la pestaña lo muestra tras «No se pudo generar: »), donde T es la estimación sin separador de miles y L
  el límite del catálogo; repetir con el mismo modelo no consulta nada más y da el mismo error.
- Given notas que caben, o una sola parte, o notas por debajo del umbral de 32 000 tokens estimados, when se genera el
  documento, then se redacta como hoy; por debajo del umbral no se consulta el catálogo.
- Given que el catálogo no se puede consultar o no trae el límite del modelo, when se genera el documento, then se
  redacta como hoy y la pestaña Registro anota que no se pudo comprobar el límite de entrada; la siguiente generación
  vuelve a consultar el catálogo.

Origen: docs/historias/hechas/2026-11-22-16-limite-de-entrada.md

### Revisión de fidelidad contra las notas
- Given la revisión de fidelidad activada y una transcripción procesada en N partes, when se genera el documento, then
  durante la revisión la línea de estado dice «Revisando fidelidad con las notas de las N partes…» y la nota añade «La
  revisión de fidelidad se hizo contra esas notas, no contra la transcripción.».
- Given la revisión de fidelidad activada y una transcripción que cabe en una sola parte, when se genera el documento,
  then la línea de estado dice «Revisando fidelidad con la transcripción…».

Origen: docs/historias/hechas/2026-11-22-06-revision-de-fidelidad.md

### Revisión de fidelidad que borra tareas o acuerdos
- Given la revisión de fidelidad activada, when la revisión de una minuta deja la tabla de tareas con menos filas o la sección de acuerdos con menos viñetas, then se descarta y se conserva la minuta anterior a la revisión.
- Given la revisión de fidelidad activada y un resumen, when se revisa, then esta regla no aplica: la revisión se acepta mientras conserve las secciones.

Origen: carril S, 2026-11-22: una revisión de minuta que deja menos tareas o acuerdos se descarta y se conserva la anterior (decisión del usuario, punto #24)

### Sesión rechazada por Copilot
- Given que Copilot rechaza el token (401) al generar o al abrir la sesión del modo `auto`, when el token es el de la sesión guardada por la app o el de opencode, then se abre el inicio de sesión, sin borrar el token de opencode ni un token propio distinto del rechazado.
- Given que el token rechazado viene de la variable de entorno `COPILOT_GITHUB_TOKEN`, when Copilot lo rechaza (401) al generar o al abrir la sesión del modo `auto`, then no se abre el inicio de sesión y aparece el error «GitHub Copilot rechazó el token de la variable de entorno COPILOT_GITHUB_TOKEN. Corrígela o quítala para usar la sesión guardada con el inicio de sesión de la app.».

Origen: carril S, 2026-11-22: un 401 de la sesión `auto` se trata como falta de sesión, y el token de la variable de entorno avisa en vez de abrir el login en bucle (A-06, A-07)

### Copilot pide esperar
- Given que Copilot responde 429 o 5xx con `Retry-After` de N segundos (de 0 a 60), when se reintenta la petición, then la generación espera N segundos antes de reintentar; si se cancela durante esa espera, se corta en el acto.
- Given que Copilot responde 429 o 5xx sin `Retry-After`, o con un valor que no es un número no negativo, when se reintenta la petición, then se usan las esperas fijas de 2, 4 y 8 segundos.
- Given que Copilot responde 429 o 5xx con `Retry-After` mayor de 60 segundos, when se recibe esa respuesta, then no se espera, no se reintenta y la generación falla con «GitHub Copilot respondió <código>: <cuerpo>. Copilot pide esperar <N> s antes de reintentar.», donde <cuerpo> es el texto de la respuesta, hasta 300 caracteres, sin el punto final y <N> son los segundos pedidos.

Origen: carril S, 2026-11-22: los 429 y 5xx respetan `Retry-After`, con un tope de 60 s (A-11)

### Documento entregado aunque falle una pasada posterior
- Given que la redacción del documento terminó y falla la pasada de completar las secciones que faltaban, por un error que no es cancelación, falta de sesión ni modelo no autorizado, when termina la generación, then el documento se muestra, se guarda y se exporta con la nota «> Nota de la aplicación: no se pudieron pedir de nuevo a Copilot las secciones que faltaban (<motivo>).» tras una línea horizontal; si además siguen faltando secciones, la nota de secciones que faltan es «> Nota de la aplicación: a este documento le faltan secciones obligatorias: <secciones>. No lo des por completo: vuelve a generarlo o complétalo con la transcripción.» (sin la frase «que Copilot no devolvió ni al pedírselas de nuevo»).
- Given que la redacción del documento terminó y falla la revisión de fidelidad, por el mismo tipo de error, when termina la generación, then el documento se muestra, se guarda y se exporta con la nota «> Nota de la aplicación: la revisión de fidelidad no se pudo completar (<motivo>); este documento no está revisado.», y si el documento es de varias partes, su nota de las partes no dice que se revisó.
- Given una pasada posterior fallida, when el motivo se escribe en la nota, then va en una sola línea, recortado a 120 caracteres más «…» si es más largo.
- Given una redacción que terminó y una revisión de fidelidad o una petición de completar las secciones que faltaban que
  Copilot corta (`finish_reason` `length` o `content_filter`, o sin marca de cierre), when termina la generación, then
  esa pasada cuenta como fallo con el motivo «Copilot cortó la respuesta: <motivo>»: la revisión se descarta y el
  documento se entrega con la nota «> Nota de la aplicación: la revisión de fidelidad no se pudo completar (Copilot
  cortó la respuesta: <motivo>); este documento no está revisado.»; el borrador de la petición de secciones se entrega
  con la nota «> Nota de la aplicación: no se pudieron pedir de nuevo a Copilot las secciones que faltaban (Copilot
  cortó la respuesta: <motivo>).». Si la redacción también se cortó, el documento lleva además la nota de respuesta
  cortada.
- Given que al final no falta ninguna sección, when termina la generación, then no hay nota de secciones, aunque la pasada de completar haya fallado.
- Given que se cancela la generación durante una pasada posterior, when la cancelación se produce, then no se entrega ningún documento.

Origen: carril S, 2026-11-22: si falla la pasada de completar secciones o la revisión de fidelidad, el documento se entrega con una nota en vez de perderse (A-11)
Origen: docs/historias/hechas/2026-11-22-15-respuesta-cortada.md

### Lista de modelos bajo demanda
- Given que se abre la ventana, when se abre, then no se conecta a GitHub Copilot ni se lee el token, y el selector ofrece
  `auto` y el modelo configurado (salvo que sea de una familia no autorizada).
- Given una sesión de Copilot iniciada, when se pulsa «↻», then se consulta una vez la lista de modelos de Copilot sin
  abrir una sesión `auto`, el selector muestra `auto`, los modelos económicos y el configurado, y nunca uno de una
  familia no autorizada.
- Given que no hay sesión de Copilot, when se pulsa «↻», then se abre el inicio de sesión y, si termina bien, la lista
  se vuelve a cargar.
- Given que la consulta de «↻» falla, when termina, then la barra de estado dice «No se pudieron cargar los modelos de
  IA», el motivo queda en la pestaña Registro y «↻» vuelve a estar habilitado.

Origen: carril S, 2026-11-22: la ventana no consulta Copilot al arrancar y «↻» carga la lista de modelos una sola vez, sin sesión `auto` (A-13)

### Fecha de la minuta
- Given un audio que existe, when se genera la minuta, then la línea `**Fecha:**` lleva la fecha de modificación del audio con el formato «<día> de <mes> de <año> (fecha del archivo)», por ejemplo «5 de marzo de 2026 (fecha del archivo)».
- Given una entrada del historial cuyo audio ya no existe, when se genera la minuta, then la línea `**Fecha:**` lleva la fecha de creación de la entrada con el formato «<día> de <mes> de <año> (fecha de transcripción)».
- Given que la fecha no se puede leer (el archivo desaparece mientras se lee su fecha o la fecha guardada en el historial no es válida), when se genera la minuta, then la línea `**Fecha:**` dice «No especificada» y la minuta se genera igual.

Origen: docs/historias/hechas/2026-11-22-10-texto-ruta-y-fecha-de-documentos.md

### Archivo propio de sesión mal formado
- Given un archivo propio de sesión de Copilot que no es JSON, que no es UTF-8, o cuyo token o dominio no son texto, when la app busca la sesión, then lo trata como si no hubiera sesión propia: usa la sesión de opencode si la hay, y la app no falla.

Origen: docs/historias/hechas/2026-11-22-25-origen-de-la-sesion.md

### Token de Copilot fuera de las representaciones
- Given una sesión de Copilot guardada con un token, when se representa la sesión o se describe su estado, then el token no aparece en el texto que se obtiene.

Origen: docs/historias/hechas/2026-11-22-25-origen-de-la-sesion.md
