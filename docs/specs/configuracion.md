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
  configuración del proyecto (con las preferencias guardadas encima, si las hay) y el historial (`data/historial.db`)
  del proyecto.

Origen: docs/historias/hechas/2026-11-22-05-modulo-de-configuracion.md
Origen: docs/historias/hechas/2026-11-22-17-preferencias-ganan-al-yaml.md

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
- Given un YAML sin `ia.temperatura` ni `ia.revision_fidelidad`, when se carga la configuración, then `ia.temperatura` vale 0.2 y la revisión de fidelidad está desactivada, los mismos valores que el `config/settings.yaml` del proyecto.
- Given una clave que falta, when se carga la configuración en la CLI o en la ventana, then toma el mismo valor por
  defecto en las dos.
- Given un YAML con claves que la app no usa (por ejemplo `audio.sample_rate`), when se carga, then esas claves se
  ignoran sin error.
- Given `ia:` vacío y ninguna sesión de GitHub Copilot iniciada, when se ejecuta `--copilot-modelos`, then escribe «No
  has iniciado sesión…» y termina con código 1 sin trazo de Python.

Origen: docs/historias/hechas/2026-11-22-05-modulo-de-configuracion.md
Origen: carril S, 2026-11-22: valores por defecto de la IA, temperatura 0.2 y revisión de fidelidad desactivada, como el YAML del proyecto (decisión del usuario; no tenía punto en el backlog)

### Las opciones de la CLI ganan al YAML
- Given una configuración con `transcripcion.idioma: "en"` y `salida.formato: "srt"`, when se ejecuta la CLI con
  `reunion.m4a -o salida.srt --config <esa configuración>` sin `-l` ni `-f`, then Whisper recibe el idioma `en` y
  `salida.srt` está en formato SRT.
- Given la misma configuración, when se ejecuta la CLI con `reunion.m4a -o salida.vtt -l fr -f vtt`, then Whisper
  recibe el idioma `fr` y `salida.vtt` está en formato VTT.

Origen: docs/historias/hechas/2026-11-22-05-modulo-de-configuracion.md

### Preferencias del usuario al abrir la ventana
- Given un `preferencias.json` con ajustes bajo `configuracion` (por ejemplo `{"configuracion": {"salida": {"formato":
  "srt"}}}`), when se abre la ventana, then esos valores ganan a los de `config/settings.yaml`, el YAML no cambia (mismo
  contenido y misma fecha de modificación) y la CLI sigue usando solo el YAML.
- Given que no existe `preferencias.json`, when se abre la ventana, then usa exactamente los valores del YAML y Registro
  no muestra avisos de preferencias.
- Given ajustes inválidos, no finitos, de claves que la configuración no tiene, `ia.modelo` dentro de `configuracion` o
  secciones que no son objetos, when se abre la ventana, then cada ajuste toma el valor del YAML, la ventana abre igual
  y Registro muestra un aviso por cada uno, con el texto de su caso (`<ruta>` es la de `preferencias.json`):
  - valor inválido: «En <ruta>, `transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «cinco»); se usa
    el valor de config/settings.yaml.» (el texto cambia con la clave, igual que en el YAML)
  - valor no finito en una clave que admite cualquier número: «En <ruta>, `transcripcion.compression_ratio_threshold`
    debe ser un número (vale «inf»); se usa el valor de config/settings.yaml.»
  - clave desconocida: «En <ruta>, `audio.sample_rate` no es una clave de la configuración; se ignora.»
  - `ia.modelo` dentro de `configuracion`: «En <ruta>, `ia.modelo` no se guarda en «configuracion» (el modelo elegido va
    en «modelo_ia»); se ignora.»
  - sección que no es un objeto: «En <ruta>, la sección `salida` no es un objeto; se ignora.»
- Given un `preferencias.json` cuyo `configuracion` trae un valor fuera de los topes del panel, un `historial.ruta`
  dentro de la carpeta del proyecto (salvo `data/`) o un `ia.copilot_enterprise_url` que no es un nombre de dominio,
  when se abre la ventana, then cada uno toma el valor del YAML, la ventana abre igual y Registro muestra un aviso por
  cada uno. Los topes son: `transcripcion.beam_size` y `transcripcion.best_of` entre 1 y 20; `transcripcion.temperature`
  e `ia.temperatura` entre 0 y 2; `transcripcion.no_speech_threshold` entre 0 y 1; `ia.peticiones_paralelas` entre 1 y 8;
  `ia.max_caracteres_bloque` entre 5000 y 500000. Los avisos son, por ejemplo, «En <ruta>, `transcripcion.beam_size`
  debe ser un número entero entre 1 y 20 (vale «50»); se usa el valor de config/settings.yaml.», «En <ruta>,
  `historial.ruta` no puede estar dentro de la carpeta del proyecto salvo en data/ (vale «src/historial.db»); se usa el
  valor de config/settings.yaml.» y «En <ruta>, `ia.copilot_enterprise_url` debe ser un nombre de dominio sin https://
  ni barras, como empresa.ghe.com, o estar vacío (vale «https://empresa.ghe.com/»); se usa el valor de
  config/settings.yaml.». `config/settings.yaml` y la CLI no tienen esos topes: un `beam_size: 50` en el YAML se carga
  como antes.
- Given un `preferencias.json` con un carácter nulo dentro de `historial.ruta` (`a` + carácter nulo + `b`), when se
  abre la ventana, then el historial toma la ruta de config/settings.yaml, la ventana abre igual y Registro muestra
  «En <ruta>, `historial.ruta` no es una ruta válida (vale «a\0b»); se usa el valor de config/settings.yaml.».
- Given un `preferencias.json` que no es JSON (por ejemplo `{`) o cuyo JSON no es un objeto (por ejemplo una lista), when
  se abre la ventana, then se abre con los valores del YAML y Registro muestra un único aviso: «Las preferencias <ruta>
  no son un JSON válido; se usan los valores de config/settings.yaml. Al guardar se reemplazará el archivo.»
- Given un `preferencias.json` cuyo `configuracion` no es un objeto (por ejemplo `3`), when se abre la ventana, then se
  abre con los valores del YAML y Registro muestra «En <ruta>, «configuracion» no es un objeto; se ignora.»
- Given un `preferencias.json` que no se puede leer (por ejemplo, es una carpeta), when se abre la ventana, then se abre
  con los valores del YAML y Registro muestra «Las preferencias <ruta> no se pudieron leer (<motivo>); se usan los
  valores de config/settings.yaml.»

Origen: docs/historias/hechas/2026-11-22-17-preferencias-ganan-al-yaml.md
Origen: docs/historias/hechas/2026-11-22-18-validar-formulario.md
Origen: carril S, 2026-11-22: code review del panel, un carácter nulo en `historial.ruta` ya no impide abrir la ventana

### Modelo de IA elegido en la ventana
- Given que se elige un modelo en el selector de la ventana, when se elige, then el modelo se recuerda en
  `~/.local/share/transcriptor-audio/preferencias.json` con la clave `modelo_ia` y `config/settings.yaml` no cambia.
- Given una preferencia guardada en `preferencias.json`, when se abre la ventana, then el selector usa ese modelo en vez
  de `ia.modelo`.
- Given que `preferencias.json` no existe o no se puede leer, when se abre la ventana, then se usa `ia.modelo`, sin
  error. Si el archivo existe pero no es JSON válido o no se puede leer, Registro muestra un aviso (ver «Preferencias del
  usuario al abrir la ventana»).
- Given que `preferencias.json` existe pero no se puede leer en ese momento, when se elige otro modelo en el selector, then
  el archivo no se reescribe (no se pierden las demás preferencias) y Registro dice que el modelo vale solo para esta
  sesión. Escribir el archivo es atómico: si la escritura falla a mitad, el archivo queda como estaba.
- Given que se elige en el selector del lateral un modelo de una familia no autorizada (por ejemplo
  `Mistral-Large-3`), when se elige, then `preferencias.json` no se crea ni se modifica, Registro anota «Modelo de IA:
  Mistral-Large-3 (solo para esta sesión; no se pudo guardar en preferencias.json)» y no se envía nada con ese modelo.

Origen: docs/historias/hechas/2026-11-22-17-preferencias-ganan-al-yaml.md
Origen: docs/historias/hechas/2026-11-22-19-guardar-y-restablecer.md
Origen: carril S, 2026-11-22: el modelo de IA elegido en el selector se guarda fuera del repo y gana a `ia.modelo`; la app ya no reescribe `config/settings.yaml` (A-19)
Origen: carril S, 2026-11-22: code review del panel, un modelo de familia no autorizada no se guarda como preferencia (regla 7)

### Vista Configuración
La vista tiene los grupos Transcripción (con el bloque plegado «Avanzado»), Salida, IA (con la sesión de GitHub Copilot primero, luego «Modelo de IA» y su «Avanzado» plegado) e Historial. El panel lateral sigue siendo «para esta transcripción»: guardar desde la vista solo cambia los controles del lateral de las claves guardadas.

- Given el YAML del proyecto (`salida.formato: "txt"`, `modelo.nombre: "large-v3-turbo"`), sin `preferencias.json` y con
  el modelo de Whisper del panel lateral cambiado a mano a `tiny`, when se abre «⚙ Configuración» con `Ctrl+3` (o con el
  botón de la barra), se elige `srt` en «Formato de salida» y se pulsa «Guardar», then el pie de la vista dice
  «Configuración guardada», `preferencias.json` queda exactamente `{"configuracion": {"salida": {"formato": "srt"}}}`,
  `config/settings.yaml` no cambia (mismos bytes y misma fecha de modificación), y al volver con `Ctrl+1` el selector de
  formato del lateral muestra `srt` y el de modelo sigue en `tiny`. La vista muestra los grupos «Transcripción» (Modelo
  de Whisper, Idioma, Dispositivo, Precisión) y «Salida» (Formato de salida, Incluir marcas de tiempo, Marcas por
  palabra); desde la historia 22, también «Historial» y «Avanzado»; desde la historia 23, el grupo «IA» (ver «Grupo IA de la vista Configuración»); cada campo con su clave del YAML debajo; mientras se ve, no se ven las pestañas de resultado. Abrir la ventana no lee el token ni hace
  ninguna petición de red; mostrar la vista lee la sesión de GitHub Copilot del disco una vez, sin red (antes: abrirla no
  leía el token ni hacía ninguna petición de red, y la vista no tenía sesión).
- Given «Idioma» con `nl` escrito a mano, when se pulsa «Guardar», then `preferencias.json` guarda `transcripcion.idioma`
  = `nl` y el selector de idioma del lateral muestra `nl` y lo ofrece al final de su lista; y si después se cambia
  «Formato de salida» a `vtt` sin guardar, se va a Transcribir (`Ctrl+1`) y se vuelve (`Ctrl+3`), el campo vuelve a
  mostrar el valor guardado (`srt`), el lateral no cambió y `preferencias.json` tampoco.
- Given una transcripción o una generación en curso, o «↻» (del lateral o de la vista) consultando la lista de modelos, o
  el diálogo «Iniciar sesión en GitHub Copilot» abierto, y «Formato de salida» cambiado a `srt` en la vista, when se pulsa
  «Guardar» o «Restablecer valores del proyecto», then aparece el diálogo «Configuración» con «Espera a que termine el
  proceso en curso.» (con un proceso), «Espera a que termine la consulta de modelos de IA.» (con la consulta) o «Termina o
  cancela el inicio de sesión en GitHub Copilot.» (con el inicio de sesión), sin preguntar antes «Restablecer
  configuración»; el pie de la vista muestra ese mismo texto, `preferencias.json` no cambia (ni se crea), y los controles
  del lateral y el selector de modelo de IA conservan sus valores. Mientras «↻» consulta, el «↻» de la vista está
  deshabilitado como el del lateral, y en cuanto termina el proceso, llega la lista (o falla) o se cierra el diálogo,
  «Guardar» funciona como en el primer criterio de «Modelo de IA en la vista Configuración». (antes: «Guardar» y
  «Restablecer» solo se rechazaban con una transcripción o una generación en curso; con «↻» en curso guardaban, y con el
  diálogo de inicio de sesión abierto también.)
- Given el YAML del proyecto (`transcripcion.beam_size: 5`, `transcripcion.no_speech_threshold: 0.6`) y sin
  `preferencias.json`, when se abre «⚙ Configuración», then el grupo «Transcripción» muestra sus cuatro campos y un
  «▶ Avanzado» plegado que oculta los siete de decodificación (Haz de búsqueda, Candidatos, Temperatura de Whisper,
  Usar el texto anterior como contexto, Umbral de compresión, Umbral de probabilidad, Umbral de silencio); y si se
  despliega, se escribe `cinco` en «Haz de búsqueda» y `0,5` en «Umbral de silencio» y se pulsa «Guardar», bajo «Haz de
  búsqueda» aparece «`transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «cinco»).», bajo «Umbral de
  silencio» no hay error, el pie dice «No se guardó nada: corrige 1 valor.» y `preferencias.json` no se crea; al
  corregir a `3` y guardar, el pie dice «Configuración guardada» y el archivo es exactamente `{"configuracion":
  {"transcripcion": {"beam_size": 3, "no_speech_threshold": 0.5}}}`.
- Given el grupo «Historial» con «Archivo del historial (relativo a la carpeta del proyecto)» en `data/historial.db` y
  la nota «Se aplica al reiniciar la app.», when se cambia a otra ruta válida (por ejemplo `data/otro.db` o una ruta
  absoluta fuera del proyecto) y se pulsa «Guardar», then el pie dice «Configuración guardada · el historial nuevo se
  abrirá al reiniciar la app», la vista Historial (`Ctrl+2`) sigue mostrando las mismas entradas de la base de antes y lo
  que se transcriba o genere hasta reiniciar se guarda en ella, y el archivo nuevo no se crea; al cerrar y abrir la
  ventana, el Historial usa la ruta nueva.
- Given un `preferencias.json` con `{"x": 1, "modelo_ia": "claude-sonnet-5.5", "configuracion": {"salida": {"formato":
  "srt"}, "transcripcion": {"beam_size": 50}}}` (la vista muestra arriba el aviso de `beam_size` inválido), el modelo de
  Whisper del lateral cambiado a mano a `tiny` y una generación anterior que dejó notas conservadas, when se pulsa
  «Restablecer valores del proyecto» y se confirma el diálogo «Restablecer configuración», then el archivo queda `{"x":
  1}`, el pie dice «Se restablecieron los valores de config/settings.yaml», desaparece el recuadro de avisos, los campos
  muestran los valores del YAML, en el lateral el formato vuelve a `txt` y el modelo de Whisper sigue en `tiny`, el
  selector de modelo de IA y la línea de estado de las pestañas Resumen y Minuta muestran `claude-haiku-5.5` (el del
  YAML), y la siguiente generación vuelve a pedir todas las partes (las notas conservadas se pierden, como al cambiar de
  modelo). Si se responde «No», nada cambia; y si la escritura falla (carpeta de preferencias sin permiso de escritura),
  aparece el diálogo «Configuración» con «No se pudo restablecer la configuración: <motivo>.», el archivo no cambia y no
  cambia nada en la vista, el lateral ni el selector de modelo de IA.
- Given `config/settings.yaml` con `transcripcion.beam_size: 50` (fuera de los topes del panel) y sin
  `preferencias.json`, when se abre «⚙ Configuración», se elige `srt` en «Formato de salida» y se pulsa «Guardar», then
  el pie dice «Configuración guardada», `preferencias.json` queda exactamente `{"configuracion": {"salida": {"formato":
  "srt"}}}` y bajo «Haz de búsqueda» no aparece ningún error. «Guardar» solo envía los campos que el usuario cambió
  desde que se pintó la vista (antes: enviaba todos, y el `50` del YAML impedía guardar cualquier otro campo).
- Given «Haz de búsqueda» con miles de dígitos pegados, when se pulsa «Guardar», then bajo «Haz de búsqueda» aparece
  «`transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «9999…»).», con el valor recortado a 40
  caracteres seguidos de «…», el pie dice «No se guardó nada: corrige 1 valor.» y no sale ninguna excepción de Python
  (antes: la excepción no se traducía a un error del campo).
- Given «Archivo del historial» con un carácter nulo entre `a` y `b`, when se pulsa «Guardar», then bajo el campo aparece
  «`historial.ruta` no es una ruta válida (vale «a\0b»).», el pie dice «No se guardó nada: corrige 1 valor.» y
  `preferencias.json` no se crea.
- Given la ventana baja y un campo con error dentro de «Avanzado» (por ejemplo «Haz de búsqueda» con `cinco`), when se
  pulsa «Guardar», then «Avanzado» se despliega y la vista se desplaza hasta el primer campo con error, en el orden de la
  vista, de modo que ese campo queda visible (antes: podía quedar fuera de la pantalla).

Origen: docs/historias/hechas/2026-11-22-21-vista-configuracion.md
Origen: docs/historias/hechas/2026-11-22-22-avanzado-historial-restablecer.md
Origen: docs/historias/hechas/2026-11-22-24-modelo-ia-en-la-vista.md
Origen: docs/historias/hechas/2026-11-22-27-sesion-en-la-vista.md
Origen: carril S, 2026-11-22: code review del panel, «Guardar» solo envía lo cambiado y la vista se desplaza al primer error

### Modelo de IA en la vista Configuración
- Given el YAML del proyecto (`ia.modelo: "claude-haiku-5.5"`, `salida.formato: "txt"`), sin `preferencias.json`, con
  sesión de Copilot y una generación anterior que dejó creado el asistente, when se abre «⚙ Configuración», then el grupo
  «IA» empieza con «Modelo de IA» (clave `ia.modelo` en gris) en `claude-haiku-5.5`, sin aviso, con las mismas opciones
  que el selector del lateral (`auto` y `claude-haiku-5.5`), y abrirla no hace ninguna petición de red.
- Given la vista con «Modelo de IA» en `claude-haiku-5.5`, when se pulsa su «↻» y llega la lista (`auto`, `gpt-4.1`,
  `claude-haiku-5.5`), then el campo y el selector del lateral ofrecen esa misma lista, sin perder lo que el formulario
  tuviera escrito sin guardar.
- Given `gpt-4.1` elegido en «Modelo de IA» y «Formato de salida» en `srt`, when se pulsa «Guardar», then el pie dice
  «Configuración guardada», `preferencias.json` queda exactamente `{"modelo_ia": "gpt-4.1", "configuracion": {"salida":
  {"formato": "srt"}}}` en una sola escritura, `config/settings.yaml` no cambia, el selector del lateral muestra
  `gpt-4.1`, la línea de estado de Resumen y de Minuta dice «Modelo: GitHub Copilot · gpt-4.1», Registro anota
  «Configuración guardada: ia.modelo, salida.formato» (y no «Modelo de IA: gpt-4.1»), y la siguiente generación crea un
  asistente nuevo con `gpt-4.1`.
- Given `gpt-4.1` elegido en «Modelo de IA» sin guardar, when se va a Transcribir (`Ctrl+1`) y se vuelve (`Ctrl+3`), then
  el selector del lateral sigue en el modelo anterior, el archivo no se crea y el campo vuelve a mostrar el modelo
  guardado.

Origen: docs/historias/hechas/2026-11-22-24-modelo-ia-en-la-vista.md

### Modelo no autorizado en la vista Configuración
- Given `"modelo_ia": "Mistral-Large-3"` en `preferencias.json` (o `ia.modelo: "Mistral-Large-3"` en el YAML sin
  preferencia), when se abre la vista, then bajo «Modelo de IA», en rojo, aparece «El modelo configurado «Mistral-Large-3»
  es de la familia «mistral», que no está autorizada por la empresa: no se enviará. Elige otro.»; el campo muestra
  `Mistral-Large-3` pero no lo ofrece entre sus opciones (ni antes ni después de «↻») y no admite texto libre.
- Given lo mismo, when se pulsa «Guardar» sin cambiar el modelo, then bajo el campo aparece «El modelo «Mistral-Large-3»
  es de la familia «mistral», que no está autorizada por la empresa. Elige otro modelo.», el pie dice «No se guardó
  nada: corrige 1 valor.» y `preferencias.json` no cambia.
- Given lo mismo, when se elige `auto` y se pulsa «Guardar», then `preferencias.json` tiene `"modelo_ia": "auto"`, el
  selector del lateral muestra `auto` y el aviso rojo desaparece. Con un modelo autorizado no hay aviso.

Origen: docs/historias/hechas/2026-11-22-24-modelo-ia-en-la-vista.md

### Grupo IA de la vista Configuración
- Given el YAML del proyecto (`ia.copilot_enterprise_url: ""`, `revision_fidelidad: false`, `temperatura: 0.2`,
  `max_caracteres_bloque: 60000`, `peticiones_paralelas: 3`) y sin `preferencias.json`, when se abre «⚙ Configuración»,
  then entre «Salida» e «Historial» hay un grupo «IA» con «Dominio de GitHub Enterprise (vacío = github.com)» vacío,
  «Revisión de fidelidad» apagado y un «▶ Avanzado» plegado con «Temperatura de la IA» `0.2`, «Caracteres por parte»
  `60000` y «Partes a la vez» `3`, cada campo con su clave del YAML en gris (el campo «Modelo de IA», primero del grupo, es el de «Modelo de IA en la vista Configuración»).
- Given esa vista con `https://empresa.ghe.com/` en el dominio y `9` en «Partes a la vez», when se pulsa «Guardar», then
  bajo el dominio aparece «`ia.copilot_enterprise_url` debe ser un nombre de dominio sin https:// ni barras, como
  empresa.ghe.com, o estar vacío (vale «https://empresa.ghe.com/»).», «Avanzado» se despliega y bajo «Partes a la vez»
  aparece «`ia.peticiones_paralelas` debe ser un número entero entre 1 y 8 (vale «9»).», el pie dice «No se guardó nada:
  corrige 2 valores.» y `preferencias.json` no se crea.
- Given el dominio vacío, «Temperatura de la IA» `0,5`, «Partes a la vez» `2` y «Revisión de fidelidad» encendido, when
  se pulsa «Guardar», then el pie dice «Configuración guardada», `preferencias.json` queda exactamente
  `{"configuracion": {"ia": {"revision_fidelidad": true, "temperatura": 0.5, "peticiones_paralelas": 2}}}` (el orden de
  las claves no importa) y `config/settings.yaml` no cambia.

Origen: docs/historias/hechas/2026-11-22-23-grupo-ia.md

### Sesión de GitHub Copilot en la vista Configuración
- Given la ventana recién abierta, sin sesión (ni opencode, ni variable `COPILOT_GITHUB_TOKEN`, ni archivo propio), when
  se muestra «⚙ Configuración», then al principio del grupo «IA», antes de «Modelo de IA», hay una sección «Sesión de
  GitHub Copilot» con el texto «No has iniciado sesión en GitHub Copilot.», «Iniciar sesión» habilitado y «Cerrar sesión»
  deshabilitado; mostrar la vista lee la sesión del disco una vez y no hace ninguna petición de red.
- Given la ventana recién abierta y solo una sesión de opencode, when se muestra «⚙ Configuración», then la sección dice
  «Se usa la sesión de opencode. La app no la cierra: ciérrala desde opencode. La sesión se comprueba al usarla.», con
  «Iniciar sesión con la app» habilitado y «Cerrar sesión» deshabilitado, y no hace ninguna petición de red.
- Given la ventana recién abierta, la variable `COPILOT_GITHUB_TOKEN` definida y un archivo propio de sesión, when se
  muestra «⚙ Configuración», then la sección dice «Se usa el token de la variable de entorno COPILOT_GITHUB_TOKEN. La app
  no puede cerrarlo: quita la variable para usar otra sesión. Hay además una sesión guardada por la app que ahora no se
  usa. La sesión se comprueba al usarla.», con el botón de iniciar deshabilitado y «Cerrar sesión» habilitado; ningún
  texto de la sección contiene el token.
- Given cualquiera de esas sesiones y el campo «Dominio de GitHub Enterprise» con `empresa.ghe.com` escrito sin guardar,
  when se escribe el dominio, then los dos botones se deshabilitan y el texto de la sección termina en «Guarda primero el
  dominio.»; when se borra lo escrito (el campo vuelve al dominio guardado) o se va a Transcribir y se vuelve a
  «⚙ Configuración», then la sección vuelve a ser la de la sesión.
- Given el mismo campo con `empresa.ghe.com` escrito sin guardar, when se pega el dominio con el ratón o el menú
  contextual en lugar de escribirlo, then la sección avisa igual que al escribirlo.

Origen: docs/historias/hechas/2026-11-22-27-sesion-en-la-vista.md

### Iniciar sesión desde la vista Configuración
- Given la sección «No has iniciado sesión en GitHub Copilot.» y una generación anterior que dejó creado el asistente,
  when se pulsa «Iniciar sesión» y se autoriza en el diálogo «Iniciar sesión en GitHub Copilot», then la sección dice
  «Sesión iniciada con la app. La sesión se comprueba al usarla.», «Iniciar sesión» queda deshabilitado y «Cerrar sesión»
  habilitado, Registro anota «Sesión de GitHub Copilot iniciada», la siguiente generación crea un asistente nuevo (las
  notas conservadas se pierden), una lista de «↻» pedida antes de iniciar sesión y que llega después se descarta
  (Registro anota «Se descarta una lista de modelos de una sesión o un dominio anteriores») y el selector de modelo no se
  recarga solo.
- Given la misma sección y una generación anterior que dejó creado el asistente, when se pulsa «Iniciar sesión» y se
  cancela el diálogo, then la sección no cambia, la barra de estado dice «Inicio de sesión en GitHub Copilot cancelado»,
  el asistente sigue siendo el mismo y no se crea el archivo de sesión.
- Given un inicio de sesión que termina bien desde cualquier acción que lo abre, también «↻» sin sesión en la lista de
  modelos, when termina, then la sección de la vista se repinta con la sesión nueva.
- Given el diálogo «Iniciar sesión en GitHub Copilot» ya abierto, when se pulsa «Iniciar sesión» otra vez, then no se
  abre otro diálogo.

Origen: docs/historias/hechas/2026-11-22-27-sesion-en-la-vista.md

### Cerrar sesión desde la vista Configuración
- Given un archivo propio de sesión de Copilot y una sesión de opencode, when se pulsa «Cerrar sesión» y se responde «Sí»
  al diálogo «Cerrar sesión» («¿Cerrar la sesión de GitHub Copilot guardada por la app? La de opencode y la variable de
  entorno no se tocan.»), then el archivo propio deja de existir, el de opencode queda igual (mismos bytes y misma fecha
  de modificación), la sección dice «Se usa la sesión de opencode. La app no la cierra: ciérrala desde opencode. La sesión
  se comprueba al usarla.» con «Cerrar sesión» deshabilitado e «Iniciar sesión con la app» habilitado, el selector de
  modelo del lateral y el campo «Modelo de IA» ofrecen solo `auto` y el modelo configurado, la siguiente generación crea
  un asistente nuevo, una lista de «↻» en vuelo se descarta al llegar y Registro anota «Sesión de GitHub Copilot
  cerrada».
- Given lo mismo, when se responde «No» al diálogo, then nada cambia.
- Given un archivo propio de sesión que no se puede borrar (carpeta sin permiso de escritura), when se responde «Sí», then
  aparece el diálogo «Sesión de GitHub Copilot» con «No se pudo cerrar la sesión:» y el motivo, y el archivo, la sección,
  el selector de modelo y el asistente no cambian.

Origen: docs/historias/hechas/2026-11-22-27-sesion-en-la-vista.md

### Sesión de GitHub Copilot durante un proceso
- Given una transcripción o una generación en curso, when se pulsa «Iniciar sesión» o «Cerrar sesión» en la vista, then
  aparece el diálogo «Sesión de GitHub Copilot» con «Espera a que termine el proceso en curso.», sin preguntar, sin
  borrar nada y sin abrir el inicio de sesión.

Origen: docs/historias/hechas/2026-11-22-27-sesion-en-la-vista.md

### Cambio del dominio de GitHub Enterprise en la vista
- Given «↻» pulsado con el dominio vacío (github.com) y todavía sin respuesta, when se pulsa «Guardar» con
  `empresa.ghe.com` en el dominio, then no se guarda nada y el pie dice «Espera a que termine la consulta de modelos de
  IA.» (ver «Vista Configuración»): desde la vista, el dominio no cambia con una consulta en curso.
- Given una lista de modelos pedida con una época de la IA anterior a la actual, when llega (o falla, o no hay sesión),
  then no se pinta, no se abre el inicio de sesión, «↻» vuelve a estar habilitado y Registro anota «Se descarta una
  lista de modelos de una sesión o un dominio anteriores». «Guardar» no cambia la época mientras consulta; iniciar o
  cerrar sesión desde la vista sí la cambia, y entonces la lista que llega después se descarta (ver «Sesión de GitHub
  Copilot en la vista Configuración»). (antes: con «↻» en curso,
  guardar `empresa.ghe.com` cambiaba la época y el selector del lateral se reiniciaba a `auto` y el configurado; la lista
  de github.com que llegaba después se descartaba.)
- Given el dominio guardado como `empresa.ghe.com`, when se pulsa «↻», se genera un resumen o una minuta o se abre el
  inicio de sesión de Copilot, then esas acciones usan `empresa.ghe.com`.
- Given «↻» sin consulta en curso, when se guarda un cambio de dominio, then el selector vuelve a ofrecer solo `auto` y
  el modelo configurado.

Origen: docs/historias/hechas/2026-11-22-23-grupo-ia.md
Origen: docs/historias/hechas/2026-11-22-24-modelo-ia-en-la-vista.md
Origen: docs/historias/hechas/2026-11-22-27-sesion-en-la-vista.md
