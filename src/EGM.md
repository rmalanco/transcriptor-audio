# src

## Overview

Paquete único de la aplicación. Contiene la transcripción local con faster-whisper, la generación de resumen y
minuta con GitHub Copilot, el historial en SQLite, la interfaz gráfica (CustomTkinter) y la CLI. No tiene
subpaquetes: sus diecisiete archivos `.py` se importan entre sí como `src.<módulo>`.

Dependencias entre módulos (quién importa a quién):

| Módulo | Usa |
|---|---|
| `__init__.py` | nada (solo `__version__`) |
| `main.py` | `transcriber`, `utils`, `registro`, `configuracion`; `copilot` solo en las órdenes de sesión; `ui` solo con `--ui` |
| `ui.py` | `transcriber`, `utils`, `asistente_ia`, `copilot`, `configuracion`, `idiomas`, `historial`, `persistencia`, `registro`, `ui_copilot`, `ui_configuracion`, `flujo_transcripcion`, `flujo_documentos`; `ui_historial` al mostrar el historial por primera vez |
| `ui_copilot.py` | `copilot` |
| `ui_historial.py` | `historial`, y métodos de `AppTranscriptor` (incluidos privados) |
| `ui_configuracion.py` | `configuracion` e `idiomas`; pinta con CustomTkinter |
| `asistente_ia.py` | `copilot`, `registro` |
| `persistencia.py` | `utils`; `historial` y `transcriber` solo como tipos |
| `historial.py` | `transcriber` (solo las dataclasses de resultado) |
| `transcriber.py` | `registro`, `utils` |
| `flujo_transcripcion.py` | `transcriber`, `utils`, `historial`, `persistencia`; sin Tk ni `faster_whisper` al importarse |
| `flujo_documentos.py` | `transcriber`, `utils` y `asistente_ia` (importarlo carga `httpx`); sin Tk ni `faster_whisper` al importarse |
| `idiomas.py` | nada: nombres y códigos de idioma del selector, sin Tk |
| `configuracion.py` | `idiomas` |
| `copilot.py`, `registro.py`, `utils.py` | ningún módulo hermano |

## Interface

### Puntos de entrada

- `main.py:main` — CLI (`python -m src.main`). Argumentos: `archivo` (posicional), `-o/--salida`, `-m/--modelo`,
  `-d/--dispositivo`, `-c/--compute-type`, `-l/--idioma`, `-t/--task`, `-f/--formato`, `--no-timestamps`,
  `--word-timestamps`, `--config`, `--listar-modelos`, `--copilot-login`, `--copilot-logout`, `--copilot-modelos`,
  `--ui`, `-v/--verbose`, `--log`. `--copilot-modelos` (`main.py:listar_modelos_copilot`) omite los modelos de `FAMILIAS_EXCLUIDAS`.
  `main.py:listar_modelos` lista los modelos de Whisper (no es `copilot.listar_modelos`).
- `ui.py:main` — interfaz gráfica (`python -m src.ui`, o `run_ui.py` en la raíz).
- `__init__.py` — no reexporta nada; `__version__ = "0.1.0"`.

### Transcripción — `transcriber.py`, `utils.py`

- `transcriber.py:TranscriptorAudio(modelo_nombre="base", dispositivo="cpu", compute_type="int8", cache_dir=None)`
  - `.modelo` — propiedad que carga el `WhisperModel` la primera vez que se usa.
  - `.transcribir(archivo, idioma, task, beam_size, best_of, temperature, condition_on_previous_text, …,
    word_timestamps, on_segmento, cancelar) -> ResultadoTranscripcion`
- `transcriber.py:SegmentoTranscripcion(inicio, fin, texto, palabras)` y
  `transcriber.py:ResultadoTranscripcion(texto_completo, segmentos, idioma_detectado, probabilidad_idioma, duracion_total)`.
- `transcriber.py:es_alucinacion_conocida(texto)` y el conjunto `ALUCINACIONES_CONOCIDAS`.
- `configuracion.py:RAIZ_PROYECTO`, `RUTA_POR_DEFECTO` (`<raíz del proyecto>/config/settings.yaml`), `RUTA_PREFERENCIAS`
  (`~/.local/share/transcriptor-audio/preferencias.json`), `ErrorConfiguracion`, y las listas `MODELOS_WHISPER` (la única
  de modelos de Whisper: la usan la CLI, la ventana y la validación), `DISPOSITIVOS`, `TIPOS_COMPUTO` y `FORMATOS`.
- `configuracion.py:cargar_configuracion(ruta=None) -> dict`: sin `ruta`, usa `RUTA_POR_DEFECTO`;
  una ruta relativa se interpreta desde la carpeta de trabajo. Devuelve todas las secciones y las 21 claves que usa la
  app, con sus valores por defecto, y valida cada una (por ejemplo, `modelo.nombre` contra `MODELOS_WHISPER`).
- `configuracion.py:leer_modelo_preferido() -> Optional[str]`, `guardar_modelo_preferido(modelo)` (lanza `OSError` si
  no puede escribir) y `modelo_ia_efectivo(configuracion, preferido) -> str`: el modelo de IA elegido en el selector
  gana a `ia.modelo`.
- `configuracion.py:guardar_ajustes(proyecto, valores, modelo_ia=None) -> list[str]` y `restablecer_ajustes()`: escriben
  `preferencias.json` en una sola escritura, conservando las claves ajenas; `guardar_ajustes` devuelve los avisos de lo
  descartado y lanza `ValueError` con un modelo de una familia excluida, sin escribir.
- `configuracion.py:leer_ajustes() -> AjustesLeidos`: lee el bloque `configuracion` de `preferencias.json` sin lanzar.
  `AjustesLeidos(valores, avisos, ilegible)`: `valores` es `(sección, clave) → valor`, `avisos` son los textos para Registro,
  e `ilegible` es verdadero solo si el archivo existe y no es JSON o no es un objeto. `configuracion.py:combinar(proyecto,
  ajustes) -> tuple[dict, list]` devuelve una copia del YAML con los valores válidos encima, más los avisos; no toca el YAML.
  `combinar` aplica los mismos topes que el formulario (`TOPES_PANEL`, dominio y `historial.ruta`), salvo la comprobación de disco.
- `configuracion.py:TOPES_PANEL`, `valor_desde_formulario(seccion, clave, valor_widget)` (convierte el texto de un campo y lanza
  `ErrorConfiguracion`), `validar_formulario(valores_widget, modelo_ia=None) -> tuple[dict, dict]` (convertidos y errores; `ia.modelo` va
  aparte y aplica la regla de familias excluidas) y `resumen_errores(n)` (texto del pie).
- `configuracion.py:guardar_formulario(proyecto, anterior, valores_widget, modelo_ia=None, preferido_anterior=None) -> ResultadoGuardado`:
  valida el formulario y, si hay errores, no escribe nada. Si no, guarda con `guardar_ajustes`, relee y combina las preferencias
  y devuelve `ResultadoGuardado(errores, efectiva, modelo_preferido, avisos, cambiadas, mensaje)` (`efectiva` es `None` si no se
  guardó; un `OSError` al escribir da solo el mensaje). Es un dataclass inmutable que la vista solo lee.
- `configuracion.py:restablecer_formulario(proyecto, anterior, preferido_anterior) -> ResultadoGuardado`: llama a `restablecer_ajustes()`
  (borra `configuracion` y `modelo_ia` de `preferencias.json`, conservando las claves ajenas) y devuelve lo del YAML con la misma forma
  que el guardado, sin modelo preferido y con la nota de reinicio si `historial.ruta` cambió. Si la escritura falla, `efectiva` es `None`
  y solo hay mensaje. El cálculo de cambios y del mensaje lo comparte con el guardado (`_resultado_tras_escribir`).
- `configuracion.py:claves_cambiadas(anterior, nueva) -> set`: claves de la tabla de configuración cuyo valor cambió.
- `configuracion.py:valores_laterales(cambiadas, configuracion) -> dict`: valores de los controles del panel lateral de las
  claves cambiadas, con las claves nombradas como las variables de la ventana (`var_modelo`, `var_formato`…); el idioma añade `opciones_idioma`. No toca Tk.
- `configuracion.py:REQUIEREN_REINICIO`: claves que piden reiniciar la app al cambiar (hoy, `historial.ruta`).
- `utils.py:validar_archivo(ruta)`, `utils.py:obtener_info_archivo(ruta) -> InfoArchivo` (sin `ffprobe` o si falla, devuelve el tamaño sin duración ni códec),
  `utils.py:serializar_transcripcion(resultado, formato="txt", incluir_timestamps=True) -> str` (único serializador, lo usan el archivo y la salida estándar) y `utils.py:guardar_transcripcion(resultado, ruta_salida, formato="txt", incluir_timestamps=True)`, que lo escribe en el archivo.
- `utils.py:formatear_duracion` (marcas de la interfaz), `formatear_tiempo`, `formatear_tiempo_srt`,
  `formatear_tiempo_vtt` (cada formato de salida); `filtros_seleccion_archivo`; `EXTENSIONES_AUDIO`, `EXTENSIONES_VIDEO`.

### Guardado sin interfaz — `persistencia.py`

- `persistencia.py:persistir_transcripcion(historial, archivo, resultado, modelo_whisper, ruta_salida, formato,
  incluir_timestamps) -> Persistencia`: guarda primero en el historial y después escribe el archivo. No lanza por un
  fallo de guardado: lo devuelve en `Persistencia.motivo_historial` o `motivo_exportacion`.
- `persistencia.py:persistir_documento(historial, id_historial, clave, contenido, modelo, ruta_salida)`. Quién guarda
  una generación lo decide `flujo_documentos.py:GestorDocumentos.recibir` (solo si es la vigente).
- `persistencia.py:Persistencia(id_historial, ruta_exportada, motivo_historial, motivo_exportacion)`,
  `motivo_de_error`, `texto_sin_guardado` y `texto_destino_documento` (los textos de aviso).

### Transcribir y persistir sin interfaz — `flujo_transcripcion.py`

- `flujo_transcripcion.py:transcribir_y_persistir(transcriptor, opciones, parametros, historial, *, on_fase, on_segmento,
  cancelar) -> TranscripcionPersistida`: avisa de `FASE_CARGANDO_MODELO` y `FASE_TRANSCRIBIENDO`, transcribe y guarda con
  `persistencia.py:persistir_transcripcion`. Lanza `InterruptedError` si se cancela (no guarda nada) y deja salir las
  excepciones del modelo; los fallos de guardado van en `TranscripcionPersistida.persistencia`. La ventana la llama desde
  el hilo de fondo (`ui.py:AppTranscriptor._procesar_transcripcion`) y solo pinta el resultado. Los parámetros de
  decodificación llegan como argumento: `ui.py:AppTranscriptor._iniciar_transcripcion` los copia de
  `self.configuracion["transcripcion"]` antes de lanzar el hilo, y el hilo no lee `self.configuracion`.

### Resumen y minuta — `asistente_ia.py`

- `asistente_ia.py:AsistenteIA(api_key=None, modelo=MODELO_POR_DEFECTO, temperatura=0.3, max_caracteres_bloque=60000,
  timeout=180.0, revision_fidelidad=True, peticiones_paralelas=3, enterprise_url=None)`
  - `.generar_resumen(texto, on_progreso=None, cancelar=None) -> str`
  - `.generar_minuta(texto, on_progreso=None, cancelar=None, fecha=None) -> str`
  - `.modelo_usado` — `"auto → <modelo>"` en modo auto con sesión abierta; si no, el modelo configurado.
- `asistente_ia.py:ErrorAsistenteIA` y sus subclases `ErrorSinSesionCopilot` (hay que iniciar sesión) y `ErrorModeloIA`
  (modelo vacío, de una familia no autorizada o sin ninguno válido en `auto`: no se envía nada).
- Funciones de apoyo: `dividir_texto`, `limpiar_respuesta`, `normalizar_tabla_tareas`, `secciones_faltantes`,
  `notas_de_la_aplicacion`, `nota_de_notas`.
- Constantes: `NOMBRE_PROVEEDOR = "GitHub Copilot"`, `MODELO_POR_DEFECTO = "gpt-4.1"`, `LIMITE_NOTAS_EN_CACHE = 64`,
  `TOPE_RETRY_AFTER = 60`, `MAX_MOTIVO_NOTA = 120`, `PROMPT_SISTEMA`, `PROMPT_RESUMEN`, `PROMPT_MINUTA`,
  `PROMPT_REVISION`, `PROMPT_NOTAS_BLOQUE`, `SECCIONES_RESUMEN`, `SECCIONES_MINUTA`.

### Acceso a GitHub Copilot — `copilot.py`

- Sesión y token: `leer_token(enterprise_url=None) -> Optional[Sesion]` (un archivo propio mal formado —no JSON, no UTF-8,
  token o dominio que no son texto— cuenta como ausente), `guardar_token`, `cerrar_sesion`, `cerrar_sesion_propia(enterprise_url=None) -> EstadoSesion` (borra solo el archivo propio y devuelve el estado resultante; un error de borrado sube tal cual), `invalidar_token`.
- Origen de la sesión, sin red y sin escribir: `estado_sesion(enterprise_url=None) -> EstadoSesion` (origen
  `ORIGEN_VARIABLE`, `ORIGEN_APP`, `ORIGEN_OPENCODE` o `None`, y `hay_token_propio`) y
  `describir_sesion(estado) -> DescripcionSesion` (`texto`, `puede_iniciar`, `texto_iniciar`, `puede_cerrar`).
- Login: `iniciar_login(enterprise_url=None) -> CodigoDispositivo`, `esperar_login(codigo, …) -> str`.
- Modelos: `listar_modelos(sesion)`, `limites_de_entrada(sesion) -> dict[str, int]`, `precio_entrada(modelo)`, `modelos_economicos(sesion)`,
  `familia_excluida(id_modelo) -> Optional[str]`, `opciones_de_modelo(modelos, configurado)`,
  `cargar_opciones_de_modelo(sesion, actual) -> list[str]` (una sola consulta a `/models`, sin sesión `auto`) y
  `abrir_sesion_auto(sesion) -> SesionAuto`.
- HTTP: `url_api(enterprise_url=None)`, `cabeceras(token, iniciador="user")`, `normalizar_dominio(url)`.
- Tipos: `Sesion(token, enterprise_url, origen)` (el `token` no sale en el `repr`), `EstadoSesion`, `DescripcionSesion`, `CodigoDispositivo`, `SesionAuto` (con `.vigente()`), `ErrorCopilot` y sus subclases `ErrorSesionCopilot` (401 de GitHub: hay que iniciar
  sesión) y `ErrorModeloCopilot` (el modo `auto` no ofrece ningún modelo utilizable).
- Constantes: `ORIGEN_VARIABLE`, `ORIGEN_APP`, `ORIGEN_OPENCODE`, `RUTA_TOKEN` (`~/.local/share/transcriptor-audio/copilot.json`), `RUTA_AUTH_OPENCODE`
  (`~/.local/share/opencode/auth.json`), `VARIABLE_ENTORNO = "COPILOT_GITHUB_TOKEN"`, `CLIENT_ID`, `API_VERSION`,
  `USER_AGENT`, `ESPERA_EXTRA`, `PRECIO_MAX_ECONOMICO = 50`, `FAMILIAS_EXCLUIDAS = ("kimi", "mistral", "codestral", "devstral", "ministral", "pixtral", "magistral")`,
  `MODELO_AUTO = "auto"`, `MARGEN_RENOVACION_AUTO` (300 s).

### Historial — `historial.py`

- `historial.py:Historial(ruta=None)` con `crear(archivo_ruta, resultado, modelo_whisper=None, titulo=None) -> int`,
  `guardar_documento(id_, tipo, contenido, modelo=None)`, `renombrar(id_, titulo)`, `eliminar(id_)`,
  `listar(busqueda="", limite=500)`, `obtener(id_)`.
- `historial.py:EntradaHistorial` — dataclass con la propiedad `archivo_existe` y el método `a_resultado()`.
- `historial.py:normalizar(texto)`, `historial.py:titulo_desde_minuta(minuta)`.
- Constantes: `RUTA_POR_DEFECTO` (`<raíz del proyecto>/data/historial.db`), `VERSION_ESQUEMA = 1`, `ESQUEMA`,
  `DOCUMENTOS = ("resumen", "minuta")`.

### Interfaz gráfica — `ui.py`, `ui_copilot.py`, `ui_historial.py`, `ui_configuracion.py`

- `ui.py:AppTranscriptor` — ventana principal. Usa como `configuracion` la efectiva (YAML + preferencias,
  `configuracion.py:combinar`) y guarda la del proyecto en `configuracion_proyecto`; los avisos de las preferencias van a
  Registro. Lo que usa `PanelHistorial`: `cargar_desde_historial(id_historial) -> bool`,
  `historial_eliminado(id_historial)`, el atributo `id_historial` y los métodos privados `_configurar_estilos_markdown`,
  `_insertar_markdown` y `_mostrar_titulo`. `mostrar_vista(vista)` alterna entre las tres vistas de la barra de navegación (Transcribir, Historial y Configuración). `guardar_configuracion(valores_widget, modelo_ia=None)` guarda lo que pide la vista Configuración (`modelo_ia` es el campo «Modelo de IA»: va en la misma escritura; no escribe si hay un proceso en curso, una consulta de «↻» o un inicio de sesión abierto) y `restablecer_configuracion()` (pulsación de «Restablecer valores del proyecto»: rechaza con esos mismos motivos, pide confirmación, muestra el error si la escritura falla y, si va bien, aplica el resultado) y `aplicar_guardado(resultado)` pone la configuración nueva y cambia en el lateral solo las claves guardadas; si cambió `("ia", "modelo")` en `cambiadas`, repone el selector de modelo de IA y sus opciones, la línea de estado de las pestañas que mostraban el modelo anterior; olvida el asistente (`GestorDocumentos.olvidar_asistente`) si cambian sus argumentos (`flujo_documentos.py:argumentos_asistente`, comparados antes y después del guardado); si cambió `("ia", "copilot_enterprise_url")`, sube `_epoca_ia` y devuelve el selector a `auto` y al configurado. `_epoca_ia` y `_consultando_modelos` (en `__init__`) y `ui.py:_cerrar_consulta_de_modelos` cierran las respuestas de «↻»: una de otra época se descarta. `_login_abierto` (en `__init__`; `_iniciar_sesion_copilot` lo pone al abrir el diálogo y `al_terminar` lo quita; si ya está puesto, no abre otro diálogo) marca el inicio de sesión abierto. `_iniciar_sesion_copilot` al terminar bien repinta la sección de sesión de la vista (`PanelConfiguracion.refrescar_sesion`). `iniciar_sesion_desde_la_vista()` es la pulsación de «Iniciar sesión» de la vista: avisa y no abre nada durante un proceso (`motivo_para_no_guardar`); si no, abre el inicio de sesión y, al terminar bien, avanza `_epoca_ia` y olvida el asistente. `_cerrar_sesion_copilot() -> EstadoSesion | None` es «Cerrar sesión» de la vista: rechaza durante un proceso, pregunta, llama a `copilot.cerrar_sesion_propia` (un `OSError` avisa y no cambia nada) y, si va bien, avanza `_epoca_ia`, olvida el asistente, repone el selector del lateral y el campo de la vista a `auto` y al configurado, anota Registro y devuelve el estado para que la vista lo pinte. `_marcar_cargar_modelos(app, estado)` habilita o deshabilita a la vez el «↻» del lateral y el de la vista (`_panel_de_modelos`, con `getattr`), y `_mostrar_modelos_ia` reparte la lista también al campo de la vista.
- `ui.py:_VistaPreviaIA` — lo que tenían los controles de IA antes de una generación; `_restaurar_controles_ia` lo devuelve al recibir el resultado o al cancelar.
- `ui_copilot.py:DialogoLoginCopilot(master, enterprise_url, al_terminar)` — diálogo modal de login.
- `ui_historial.py:PanelHistorial(master, app, historial)` con `refrescar()`; `LIMITE_LISTA = 200`.
- `ui_configuracion.py:CAMPOS` — los veintiún campos: en Transcripción cuatro y siete en su «Avanzado» (`avanzado=True`); tres de Salida; en IA, «Modelo de IA» (control `modelo_ia`, primero del grupo, sin texto libre y fuera de `valores_widget`), el dominio y la revisión de fidelidad, y tres en su «Avanzado»; y `historial.ruta` (control `texto`, con `Campo.nota`). Cada grupo con «Avanzado» tiene el suyo (`ui_configuracion.py:PanelConfiguracion._crear_avanzado`, `_desplegar_avanzado(grupo, abierto)`), plegado; se despliega solo si uno de sus campos trae un error. `ui_configuracion.py:PanelConfiguracion(master, app)` con `refrescar()` (repinta el recuadro de avisos de las preferencias y la sección de sesión), `refrescar_sesion()` (lee la sesión del disco con el dominio guardado, sin red, y la pinta con `_pintar_sesion(descripcion)`), `_cerrar_sesion()` (pulsación de «Cerrar sesión»; repinta con el estado que devuelve `_cerrar_sesion_copilot`), `_construir_seccion_sesion` (la sección «Sesión de GitHub Copilot» al principio del grupo IA, antes de «Modelo de IA»), `_restablecer()` (pie de «Restablecer valores del proyecto») y `ui_configuracion.py:motivo_para_no_guardar(transcribiendo, generando, consultando_modelos, login_abierto)` decide si no se puede guardar ahora, con cuatro motivos en ese orden (proceso, consulta de «↻», inicio de sesión abierto). `ui_configuracion.py:aviso_modelo(modelo)` da el aviso rojo de una familia excluida. `ui_configuracion.py:seccion_de_sesion(descripcion, dominio_escrito, dominio_guardado) -> SeccionSesion` decide el texto y los botones de la sección de sesión (sin Tk): si el dominio escrito no es el guardado, los dos botones se deshabilitan y el texto pide «Guarda primero el dominio.»; el campo del dominio tiene una traza (`trace_add`, `_al_escribir_dominio`) que repinta esa sección también al pegar. `PanelConfiguracion._refrescar_modelo()` repone el campo «Modelo de IA» con el modelo efectivo y deshabilita su «↻» mientras `_consultando_modelos`; `mostrar_modelos_ia(opciones)` pone las opciones que llegan de «↻».
- `ui.py:DOCUMENTOS_IA` — define los sufijos `_resumen.md` y `_minuta.md`.

### Registro — `registro.py`

- `registro.py:configurar_logging(nivel=None)` y `registro.py:latido(descripcion, cada=15.0, logger=log)` (context manager).
- `VARIABLE_NIVEL = "TRANSCRIPTOR_LOG"`.

## Invariants

### Hilos e interfaz gráfica

- Los widgets solo se tocan desde el hilo principal. Los hilos de fondo pasan por `ui.py:AppTranscriptor._en_ui`,
  que usa `self.after(0, …)` y no hace nada si la ventana se está cerrando.
- Solo hay una transcripción a la vez (`ui.py:AppTranscriptor._transcribiendo`) y una generación de IA a la vez
  (`flujo_documentos.py:GestorDocumentos.vigente`); no se genera un documento mientras se transcribe
  (`ui.py:AppTranscriptor._generar_documento_ia`) ni se transcribe mientras se genera
  (`ui.py:AppTranscriptor._alternar_transcripcion`).
- La cancelación de la transcripción es cooperativa: un `threading.Event` (`cancelar_flag`) que
  `transcriber.py:TranscriptorAudio.transcribir` revisa tras cada segmento aceptado (no tras los descartados como
  alucinación, ni durante la carga del modelo ni la preparación con VAD); al activarse, devuelve lo transcrito hasta
  ahí, pero la ventana lo descarta: no escribe el archivo ni guarda en el historial.
- `flujo_documentos.py:GestorDocumentos` lleva la generación vigente (`vigente`) y el asistente que se reutiliza entre
  generaciones. Solo se usa desde el hilo principal y lo comprueba (`RuntimeError` desde otro hilo). Su `recibir(generacion,
  documento, error)` es el punto de decisión y devuelve una `flujo_documentos.py:Recepcion` con `estado`: `descartada`,
  `lista` (con `documento` y `persistencia`), `error` o `sin_sesion` (con `mensaje`). El asistente lo crea
  `ui.py:AppTranscriptor._crear_asistente` con la configuración y el modelo elegidos en ese momento, y se olvida al
  cancelar, al cambiar de modelo, al guardar en la vista Configuración un cambio de sus argumentos y tras «sin sesión» de Copilot.
- Cada generación de IA es un `flujo_documentos.py:Generacion` (comparada por identidad) con su propio
  `threading.Event` (`cancelar`), así que cancelar una no afecta a la siguiente. El hilo de fondo ejecuta
  `flujo_documentos.py:procesar_generacion`, que llama a `AsistenteIA` (vía `generar_documento`) y entrega el resultado
  exactamente una vez: no toca widgets, historial ni archivos. El único punto de decisión es
  `flujo_documentos.py:GestorDocumentos.recibir`, al que `ui.py:AppTranscriptor._recibir_documento_ia` llega en el hilo
  principal con `_en_ui`. Si la generación ya no es la vigente (`terminar`, por identidad), devuelve «descartada»: no guarda,
  no toca el asistente y no abre el login, sea cual sea el resultado (documento, error o 401). Si es la vigente, guarda
  en el historial y después junto al audio («lista») o devuelve el error o la falta de sesión («error» y «sin_sesion»,
  que además olvida el asistente). La ventana solo pinta según el estado. `ui.py:AppTranscriptor._cancelar_documento_ia` devuelve la ventana al
  instante; la petición ya abierta no se aborta: el hilo abandonado termina al recibir la siguiente línea de la
  respuesta, o tras `AsistenteIA.timeout` sin datos.
- La ventana guarda aparte, en `self._vista_previa_ia`, lo que tenían los controles antes de la generación, y los
  restaura con `ui.py:AppTranscriptor._restaurar_controles_ia`, el único método que lo hace (al recibir y al cancelar).
- `Generacion.id_historial` es el `id_historial` vigente al pulsar el botón, así que el documento se guarda en esa
  entrada aunque después se abra otra; el guardado lo hace `GestorDocumentos.recibir` con
  `persistencia.py:persistir_documento`, solo si la generación es la vigente.
- La ventana reutiliza una instancia de `AsistenteIA` (y con ella la caché de notas) y la descarta al cambiar el
  modelo, al cancelar una generación y tras un `ErrorSinSesionCopilot`. La configuración se lee una sola vez al
  arrancar: cambiar `settings.yaml` exige reiniciar la ventana.
- Si `Historial` no se puede abrir, `self.historial` queda en `None` y la app sigue sin historial
  (`ui.py:AppTranscriptor.__init__`).

### Transcripción

- `utils.py:validar_archivo` lanza `FileNotFoundError` si la ruta no existe y `ValueError` si no es un archivo o su
  extensión no está en `EXTENSIONES_AUDIO` ni en `EXTENSIONES_VIDEO`.
- `transcriber.py:TranscriptorAudio.transcribir` usa siempre `vad_filter=True` con `min_silence_duration_ms=500`, y
  convierte `idioma == "auto"` en `language=None`.
- `transcriber.py:es_alucinacion_conocida` descarta un segmento solo si, en minúsculas y sin puntuación en los
  extremos, coincide entero con una frase de `ALUCINACIONES_CONOCIDAS`.
- `utils.py:serializar_transcripcion` (y, por tanto, `guardar_transcripcion`) lanza `ValueError` con un formato distinto de `txt`, `srt`, `vtt` o `json`.

### Guardado

- `persistencia.py` guarda primero en el historial y después el archivo junto al audio. Un fallo de uno no impide el
  otro y ninguno descarta el resultado: se devuelve como aviso (`Persistencia.motivo_historial`, `motivo_exportacion`) y
  la ventana lo muestra. Si no quedó ni en el historial ni como archivo, el aviso lo dice
  (`persistencia.py:texto_sin_guardado`).
- Un documento solo se guarda en el historial si `Historial` existe, hay `id_historial` y la entrada sigue existiendo
  (`Historial.obtener`); si el audio ya no existe, el documento solo va al historial.
- Una generación cancelada no guarda nada (`flujo_documentos.py:GestorDocumentos.recibir`, estado `descartada`).

### Configuración

- La CLI y la interfaz toman todos los valores de `configuracion.py:cargar_configuracion`, que devuelve el dict
  completo (las 21 claves con sus valores por defecto y validadas). No hay valores por defecto propios en `main.py` ni
  en `ui.py`. Un YAML con errores da `configuracion.py:ErrorConfiguracion`: la CLI sale con código 1 y
  `Error: <mensaje>` en `stderr` antes de cargar Whisper; la ventana muestra el mensaje en un diálogo y no arranca.
- Claves con valor `null` (por ejemplo `beam_size:` sin valor) se tratan como ausentes y toman su valor por defecto.
  Las claves desconocidas (incluidas `audio.*` y `transcripcion.task` de configuraciones antiguas) se ignoran sin error.
- En la CLI, `-l`, `-f`, `--no-timestamps` y `--word-timestamps` no tienen valor fijo: si no se pasan, valen
  `transcripcion.idioma`, `salida.formato`, `salida.incluir_timestamps` y `salida.palabra_por_palabra`. `-t` sigue con
  `transcribe` por defecto y no lee configuración. La interfaz lee esas claves y fija `task` en `"transcribe"`.
- La CLI no usa `AsistenteIA` ni `Historial`: no genera resumen ni minuta y no guarda en el historial.

### GitHub Copilot

- Orden de búsqueda del token en `copilot.py:leer_token`: variable `COPILOT_GITHUB_TOKEN`, luego `RUTA_TOKEN`, luego
  `RUTA_AUTH_OPENCODE` (clave `github-copilot`). Los archivos solo valen si su dominio coincide con el pedido; la
  variable de entorno no se compara con el dominio.
- `asistente_ia.py:AsistenteIA.__init__` lanza `ErrorSinSesionCopilot` si no hay token.
- `x-initiator`: la primera petición de cada documento va con `user` y las siguientes con `agent`
  (`asistente_ia.py:AsistenteIA._cabeceras`, `asistente_ia.py:AsistenteIA._generar`).
- `copilot.py:listar_modelos` acepta un modelo si `policy.state == "enabled"` o `model_picker_enabled`, si es de tipo
  `chat` y, cuando declara `supported_endpoints`, si incluyen `/chat/completions`. Lee el catálogo con `copilot.py:_catalogo`,
  igual que `copilot.py:limites_de_entrada` (`capabilities.limits.max_prompt_tokens` por id, sin filtrar por habilitados).
- `copilot.py:modelos_economicos` descarta los modelos sin precio, con precio de entrada mayor que
  `PRECIO_MAX_ECONOMICO` o de `FAMILIAS_EXCLUIDAS`; deja un solo modelo por `name` (el primero) y los ordena por precio
  de entrada.
- `copilot.py:abrir_sesion_auto` elige el primer modelo ofrecido (el `selected_model` del servidor, luego
  `available_models`) que admite `/chat/completions` y no es de una familia de `FAMILIAS_EXCLUIDAS`. Un modelo sin
  metadatos de endpoints cuenta como compatible, y todos lo son si falla el `GET /models`. Lanza `ErrorSesionCopilot`
  ante un 401 y `ErrorModeloCopilot` si falta `session_token`, no se ofrece ningún modelo o ninguno queda autorizado y
  compatible. Sin `expires_at`, la sesión caduca a la hora; `copilot.py:SesionAuto.vigente` la da por caducada 300 s
  antes. `listar_modelos` y `abrir_sesion_auto` salen siempre con `x-initiator: user`; las peticiones de generación en
  modo `auto` llevan además la cabecera `Copilot-Session-Token`.
- `copilot.py:familia_excluida` se comprueba al elegir el modelo de `auto` y justo antes de cada envío
  (`asistente_ia.py:AsistenteIA._modelo_para_peticion`): ni la transcripción ni ninguna parte sale hacia un modelo de
  `FAMILIAS_EXCLUIDAS`, tampoco con un modelo escrito a mano (`ErrorModeloIA`, sin enviar nada). Un modelo vacío da el
  mismo error. La familia se reconoce porque el id del modelo contiene su nombre, sin distinguir mayúsculas.
- `copilot.py:esperar_login` consulta cada `interval + 3` s; trata `slow_down` (sube el intervalo), `expired_token`,
  `access_denied` y `authorization_pending`, y lanza `InterruptedError` si se cancela. `iniciar_login` pide el
  scope `read:user`.
- `asistente_ia.py:AsistenteIA._completar` hace hasta 4 intentos en total (los reintentos que se describen abajo
  gastan intentos del mismo límite). Tras un error de red espera 1, 2 y 4 s; tras un 429 o 5xx, 2, 4 y 8 s, o el
  `Retry-After` en segundos si lo trae, hasta 60 s: por encima no reintenta y falla (`asistente_ia.py:_retry_after`,
  `TOPE_RETRY_AFTER`). Las esperas se cortan al activarse la cancelación. Un 400 que menciona `temperature` se reintenta
  sin ese campo; `model_not_supported` y 403 dan `ErrorAsistenteIA` con mensajes propios. El timeout de conexión es de
  30 s y el de lectura, `AsistenteIA.timeout`.
- Una respuesta que Copilot corta (`finish_reason` `length` o `content_filter`, o un stream sin `[DONE]` ni
  `finish_reason`) no falla: `AsistenteIA._completar` la devuelve con el motivo (`asistente_ia.py:_motivo_de_corte`,
  `_TextoDeCopilot.corte`) y se marca en el documento como nota (`asistente_ia.py:_nota_de_corte`). Una pasada posterior
  cortada (completar secciones o revisión) cuenta como fallo de esa pasada (`asistente_ia.py:_sin_cortar`).
- Un 401 fuera del modo auto pasa por `AsistenteIA._error_de_token_rechazado`: si el token viene de
  `COPILOT_GITHUB_TOKEN` lanza `ErrorAsistenteIA` sin abrir el login; si no, invalida el token guardado y lanza
  `ErrorSinSesionCopilot`. En modo `auto`, un 401 de `/chat/completions` primero descarta la sesión `auto` y abre otra
  (en los tres primeros intentos); un 401 en el último intento, o al abrir la sesión (`ErrorSesionCopilot`), sigue ese
  mismo camino.
- Las respuestas de GitHub con formato o tipos inesperados (`copilot.py:_datos_de`, `copilot.py:_lista_de_objetos`)
  lanzan `ErrorCopilot` con «GitHub devolvió una respuesta inesperada al <acción>.», para que el diálogo de login y la
  CLI no se queden colgados ni muestren un trazo.
- `copilot.py:invalidar_token` borra `RUTA_TOKEN` solo si el token guardado es el rechazado; nunca toca el archivo de
  opencode.

### Documentos generados

- Una transcripción vacía lanza `ErrorAsistenteIA` (`asistente_ia.py:AsistenteIA._generar`).
- Con más de un bloque, el documento se redacta a partir de notas por bloque, y la revisión de fidelidad compara
  contra esas notas, no contra la transcripción (`asistente_ia.py:AsistenteIA._generar`). Si la estimación de la petición
  de redacción (caracteres / 4) supera 32 000 tokens, antes de redactar se consulta una vez por asistente
  `copilot.py:limites_de_entrada`; si la estimación supera el límite del modelo, se lanza `ErrorAsistenteIA` y la redacción
  no se envía. Un fallo del catálogo, o un modelo sin límite, no bloquea: se redacta como hoy
  (`asistente_ia.py:AsistenteIA._comprobar_limite_de_entrada`). Con dos o más partes, la app añade al final del documento una nota que lo advierte, y el progreso de la revisión nombra la fuente real (`asistente_ia.py:AsistenteIA._con_nota`). Si además faltan secciones obligatorias, el documento puede terminar con una nota que las nombra, bajo la misma línea horizontal (`asistente_ia.py:notas_de_la_aplicacion`). Si falla la pasada de completar secciones o la revisión de fidelidad, por un error que no es cancelación, falta de sesión ni modelo no autorizado, el documento se entrega con la nota del motivo (`asistente_ia.py:AsistenteIA._generar`). Si Copilot corta la redacción, la minuta o el resumen llevan la nota del corte con su motivo, primero bajo la línea horizontal (`asistente_ia.py:notas_de_la_aplicacion`).
- Las notas de cada parte se guardan en memoria en cuanto esa parte termina, hasta 64 partes (o todas las de la generación en curso si son más). Al generar otra vez con el mismo modelo, solo se piden las que faltan (`asistente_ia.py:AsistenteIA._notas_por_bloque`). Si una parte falla, no se lanzan las que aún no han empezado, el error dice cuál es y cuántas notas se conservan, y el modelo se valida antes de enviar nada. Las notas de una parte que Copilot cortó no se guardan en esa caché: se usan en el documento en curso (con nota) y se vuelven a pedir al generar otra vez (`asistente_ia.py:AsistenteIA._notas_por_bloque`).
- Si faltan secciones de `SECCIONES_RESUMEN` o `SECCIONES_MINUTA`, se hace un solo reintento, que se acepta solo si
  faltan menos que antes. La revisión de fidelidad solo se acepta si no deja más secciones sin cubrir que el borrador y, en la minuta, si no deja menos filas en la tabla de tareas ni menos viñetas en Acuerdos (`asistente_ia.py:AsistenteIA._generar`, con `contar_filas_tareas` y `contar_vinetas_acuerdos`).
- La fecha de la minuta la pone la aplicación: `asistente_ia.py:AsistenteIA.generar_minuta` reescribe la línea
  `**Fecha:**` con la fecha recibida o con `No especificada`. La ventana la calcula en el hilo principal, al pulsar
  «Generar minuta», con `flujo_documentos.py:fecha_de_la_reunion`: la fecha de modificación del audio; si el audio ya no
  existe, `creado_en` de la entrada del historial; si no se puede leer, `No especificada`. El hilo de fondo la recibe
  como argumento y no lee la ventana.
- El texto que se envía a la IA son los segmentos de la transcripción unidos con saltos de línea, no `texto_completo`
  (`flujo_documentos.py:texto_para_ia`).

### Historial

- `historial.py:Historial.guardar_documento` solo admite `tipo` en `DOCUMENTOS`; si no, `ValueError`. Esa lista
  protege el nombre de columna, que se interpola en el SQL.
- Un título editado a mano no se reemplaza: el título tomado de la minuta se aplica solo donde `titulo_editado = 0`,
  y `historial.py:Historial.renombrar` pone `titulo_editado = 1`.
- `historial.py:Historial.renombrar` lanza `ValueError` si el título queda vacío. `Historial.crear` con `titulo` pone
  `titulo_editado = 1`.
- `historial.py:Historial.listar` ordena por `creado_en DESC, id DESC` y escapa los comodines de `LIKE`.
- Una ruta relativa se resuelve contra `RAIZ_PROYECTO`, no contra el directorio de trabajo
  (`historial.py:Historial.__init__`).
- La búsqueda ignora mayúsculas y acentos (`historial.py:normalizar`) y cubre `titulo`, `archivo_nombre`, `texto`,
  `resumen` y `minuta` (`historial.py:Historial.listar`).
- No hay migraciones: `PRAGMA user_version` se fija en cada apertura sin comparar el valor anterior.

## Side Effects

### Red

- `POST https://<dominio o github.com>/login/device/code` — `copilot.py:iniciar_login`.
- `POST https://<dominio o github.com>/login/oauth/access_token`, en bucle — `copilot.py:esperar_login`.
- `GET <url_api>/models` — `copilot.py:listar_modelos` y `copilot.py:abrir_sesion_auto`.
- `POST <url_api>/models/session` — `copilot.py:abrir_sesion_auto`: la llama `AsistenteIA` al generar con el modelo `auto` y
  la CLI con `--copilot-modelos`.
- `POST <url_api>/chat/completions` en streaming — `asistente_ia.py:AsistenteIA._completar`.
- `url_api` es `https://api.githubcopilot.com`, o `https://copilot-api.<dominio>` con GitHub Enterprise
  (`copilot.py:url_api`).
- Al pulsar «↻» junto al selector de modelo (o el de la vista Configuración), `ui.py:AppTranscriptor._cargar_modelos_ia` consulta una vez los modelos
  (`copilot.py:cargar_opciones_de_modelo`), sin abrir sesión auto. Al arrancar la ventana no hay tráfico con Copilot.
- Descarga del modelo de Whisper la primera vez que se usa — `transcriber.py:TranscriptorAudio.modelo`.

### Disco

- `~/.local/share/transcriptor-audio/copilot.json`: se crea con modo `0o600` (`copilot.py:guardar_token`) y se borra
  en `copilot.py:cerrar_sesion` y `copilot.py:invalidar_token`.
- `~/.local/share/opencode/auth.json`: solo lectura (`copilot.py:leer_token`).
- `~/.cache/faster-whisper`: caché de modelos (`transcriber.py:TranscriptorAudio.__init__`).
- `config/settings.yaml`: solo lectura con `yaml.safe_load` (`configuracion.py:cargar_configuracion`); la app no lo
  reescribe. La ruta se resuelve contra `RAIZ_PROYECTO`, no contra el directorio de trabajo.
- `~/.local/share/transcriptor-audio/preferencias.json`: modelo de IA elegido en el selector
  (`configuracion.py:guardar_modelo_preferido` y `leer_modelo_preferido`); gana a `ia.modelo`. Al abrir la ventana se lee
  también su bloque `configuracion` (`configuracion.py:leer_ajustes`), sin escribirlo; sus valores válidos ganan al YAML.
  Toda escritura (`guardar_modelo_preferido`, `guardar_ajustes`, `restablecer_ajustes`) es atómica: escribe un temporal y lo
  renombra encima con `os.replace` (`configuracion.py:_escribir_preferencias_atomico`). Un `OSError` al leer el archivo
  (distinto de «no existe») se propaga sin reescribirlo.
- Junto al audio: `<archivo>.<ext>_transcripcion.<formato>` (la ruta sale de `flujo_transcripcion.py:ruta_transcripcion` y la
  escribe `persistencia.py:persistir_transcripcion`), y `<archivo>.<ext>_resumen.md` y `<archivo>.<ext>_minuta.md` (la ruta sale de
  `flujo_documentos.py:ruta_documento` y la escribe `persistencia.py:persistir_documento`). Regenerar la misma grabación los sobrescribe
  sin preguntar; dos grabaciones con el mismo nombre no comparten archivos (`BACKLOG.md`, Salud del código #18).
- La CLI escribe en `stdout` o en el archivo de `-o`; los dos usan `utils.py:serializar_transcripcion`, y `--verbose` escribe en stderr. Con `srt` o `vtt` sin `-o`, termina con código 1 antes de cargar Whisper.

### Base de datos

- `historial.py:Historial.__init__` crea la carpeta de la base y ejecuta `CREATE TABLE IF NOT EXISTS transcripciones`
  y `CREATE INDEX IF NOT EXISTS idx_transcripciones_creado`.
- Columnas de `transcripciones`: `id`, `titulo`, `titulo_editado`, `archivo_nombre`, `archivo_ruta`, `creado_en`,
  `actualizado_en`, `duracion_segundos`, `idioma`, `probabilidad_idioma`, `modelo_whisper`, `texto`, `segmentos_json`,
  `resumen`, `resumen_modelo`, `resumen_en`, `minuta`, `minuta_modelo`, `minuta_en`.
- `INSERT` en `crear`, `UPDATE` en `guardar_documento` y `renombrar`, `DELETE` en `eliminar`. Cada operación abre su
  propia conexión.

### Procesos, hilos y sistema

- `ffprobe` mediante `ffmpeg.probe` (`utils.py:obtener_info_archivo`); es opcional: sin él, la carga sigue sin duración.
- `xdg-open`, `open` u `os.startfile` para abrir la carpeta de salida (`ui.py:AppTranscriptor._abrir_carpeta`).
- `webbrowser.open` y copia del código al portapapeles (`ui_copilot.py:DialogoLoginCopilot._abrir_github`).
- Hilos `daemon`: transcripción, generación de IA y consulta de modelos (`ui.py`), `login-copilot`
  (`ui_copilot.py`) y `latido` (`registro.py:latido`). Además, un `ThreadPoolExecutor` `ia-parte`
  (`asistente_ia.py:AsistenteIA._notas_por_bloque`) cuyos hilos no son `daemon`: el `with` los espera antes de salir.
- `registro.py:configurar_logging` reemplaza los manejadores del logger raíz por uno a `stderr` y asigna
  `threading.excepthook`.

## Verification

- Run: `./venv/bin/python -m pytest -q` (los tests están en `../tests/`; `pytest` figura en `requirements-dev.txt`).
