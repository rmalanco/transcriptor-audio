# Informe de deriva — 2026-11-22

> Generado por /deriva (Tándem) sobre los contratos que escribió /analizar. Solo lista diferencias entre los
> documentos y el código. Un revisor en contexto limpio leyó `src/` completo; los hallazgos 🔴/🟡 de las tres
> primeras secciones se comprobaron después contra el código. No se encontró ningún 🔴.
>
> Severidad: 🟡 impreciso o incompleto · 🟢 detalle menor.

## src/EGM.md

- 🟡 **Interfaz gráfica, métodos que usa `PanelHistorial`.** El documento lista `mostrar_vista`. `PanelHistorial`
  no lo llama: usa `cargar_desde_historial`, `historial_eliminado`, los métodos privados
  `_configurar_estilos_markdown`, `_insertar_markdown` y `_mostrar_titulo`, y el atributo `id_historial`
  (`src/ui_historial.py:103`, `:236`, `:253-254`, `:260`, `:275`).
- 🟡 **Configuración, `KeyError` en la CLI.** El documento dice que la CLI lee `modelo.*` con `[]`. Solo lo hace
  cuando no se pasa `-m`, `-d` o `-c` (`src/main.py:135-137`).
- 🟡 **Configuración, claves sin valor por defecto.** Faltan en la lista `transcripcion.idioma`, `salida.formato`,
  `salida.incluir_timestamps` y `salida.palabra_por_palabra`: la interfaz las lee con `[]` y da `KeyError` si faltan
  (`src/ui.py:131-137`, `:623`).
- 🟡 **401 en modo auto.** El documento dice que un 401 «fuera del modo auto» invalida el token. En modo auto, un 401
  en el cuarto intento también llama a `invalidar_token` y lanza `ErrorSinSesionCopilot`. El reintento sin
  `temperature` y el reintento con sesión auto nueva gastan intentos del mismo límite de 4
  (`src/asistente_ia.py:286`, `:323-339`).
- 🟡 **`abrir_sesion_auto`.** El documento dice que elige el primer modelo «que admite `/chat/completions`». También
  cuenta como compatible un modelo sin metadatos de endpoints, y todos si falla el `GET /models`. Lanza
  `ErrorCopilot` además cuando falta `session_token` o no se ofrece ningún modelo (`src/copilot.py:305-319`).
- 🟢 **Bloqueo entre transcripción e IA.** El documento lo sitúa en `_generar_documento_ia`. El sentido «no
  transcribir mientras se genera» está en `_alternar_transcripcion` (`src/ui.py:527-529`).
- 🟢 **Cancelación.** Se revisa solo tras los segmentos aceptados, no tras los descartados como alucinación, y no
  durante la carga del modelo ni la preparación con VAD (`src/transcriber.py:104-120`, `:136-138`, `:156`).
- 🟢 **Hilos `daemon`.** El `ThreadPoolExecutor` `ia-parte` figura entre los hilos `daemon`; sus hilos no lo son
  (`src/asistente_ia.py:412`).
- 🟢 **Imports.** `__init__.py` usa imports relativos y depende de `transcriber` y `utils`; la tabla de dependencias
  no lo recoge (`src/__init__.py:3-4`).
- 🟢 **Consulta de modelos al arrancar.** Solo ocurre si hay sesión guardada, y se repite tras cada login
  (`src/ui.py:870-873`, `:918`).
- 🟢 **Salida de la CLI por `stdout`.** Solo funciona con `txt` y `json`; con `srt` o `vtt` sin `-o` termina con
  código 1. El formato difiere del de `guardar_transcripcion` (`src/main.py:188-207`).

## EGM.md

- 🟡 **«Los únicos destinos de red son GitHub y la API de Copilot».** La descarga del modelo de Whisper también usa
  la red (`src/transcriber.py:71-76`). El propio documento lo dice más abajo, así que se contradice. El invariante
  que sí se sostiene es que el audio no se envía a ningún servicio.
- 🟡 **«Los modelos que no admiten `/chat/completions` se descartan».** El modelo escrito en `ia.modelo` no pasa ese
  filtro: la interfaz lo conserva aunque no esté en la lista y `AsistenteIA` lo envía tal cual
  (`src/ui.py:888-893`, `src/asistente_ia.py:265-266`). Además se usan `GET /models` y `POST /models/session`.
- 🟢 **Procesos externos.** Falta la apertura del navegador con `webbrowser.open` (`src/ui_copilot.py:88`).

## docs/disenos/00-actual.md

- 🟢 **Alcance de la CLI.** El documento dice que «solo transcribe y gestiona la sesión de Copilot». También tiene
  `--listar-modelos` y `--ui` (`src/main.py:106-112`).
- 🟢 **Salida de la CLI.** Mismo matiz que arriba: `srt` y `vtt` exigen `-o` (`src/main.py:205-207`).
- 🟢 **Guardado del documento en el historial.** Solo ocurre si el historial se abrió y hay `id_historial`
  (`src/ui.py:814`).

## Cobertura (código no documentado)

- 🟡 **La generación con IA no se puede cancelar desde la interfaz.** `_procesar_documento_ia` no pasa `cancelar`, y
  al cerrar la ventana solo se pregunta por la transcripción (`src/ui.py:469-475`, `:811`).
- 🟡 **Una transcripción cancelada se descarta entera.** `transcribir` devuelve el resultado parcial, pero la
  interfaz lanza `InterruptedError` después y no escribe el archivo ni guarda en el historial (`src/ui.py:628-640`).
- 🟡 **En modo auto, un token revocado no abre el diálogo de login.** El 401 de `abrir_sesion_auto` llega como
  `ErrorAsistenteIA`, no como `ErrorSinSesionCopilot`, y no se invalida el token
  (`src/copilot.py:299-300`, `src/asistente_ia.py:251-254`, `src/ui.py:817-824`).
- 🟡 **Reglas de `_completar` sin documentar** (`src/asistente_ia.py:283-345`):
  - un 400 que menciona `temperature` se reintenta sin ese campo;
  - `model_not_supported` y 403 dan `ErrorAsistenteIA` con mensajes propios;
  - las esperas son de 1, 2 y 4 s tras errores de red, y de 2, 4 y 8 s tras 429 y 5xx;
  - el timeout de conexión es de 30 s y el de lectura, `self.timeout`.
- 🟡 **Dos cachés en memoria.** Las notas por bloque se guardan por SHA-256 (máximo 8) y se comparten entre resumen
  y minuta (`src/asistente_ia.py:391-424`). La interfaz reutiliza la instancia de `AsistenteIA` y solo la recrea al
  cambiar de modelo o tras un `ErrorSinSesionCopilot`, así que otros cambios en `ia.*` no se aplican hasta reiniciar
  (`src/ui.py:766-774`, `:819`, `:902`).
- 🟡 **`ffprobe` es obligatorio para cargar un archivo en la interfaz.** `obtener_info_archivo` solo captura
  `ffmpeg.Error`; si falta el binario, `_cargar_archivo` rechaza el archivo (`src/utils.py:42-61`, `src/ui.py:497-503`).
- 🟢 La revisión de fidelidad solo se acepta si no pierde secciones (`src/asistente_ia.py:473-475`).
- 🟢 La fecha de la minuta sale de la fecha de modificación del audio; si no existe, de `creado_en`; si no, es
  «No especificada» (`src/ui.py:925-937`).
- 🟢 El texto enviado a la IA son los segmentos unidos con saltos de línea, no `texto_completo` (`src/ui.py:783`).
- 🟢 Claves leídas con `.get` que la sección de configuración no menciona: `historial.ruta` (`src/ui.py:125`) e
  `ia.copilot_enterprise_url` (`src/ui.py:773`, `:867`, `:922`; `src/main.py:115`).
- 🟢 Modo auto: cabecera `Copilot-Session-Token`; `listar_modelos` y `abrir_sesion_auto` salen siempre con
  `x-initiator: user`; sin `expires_at`, la sesión caduca a la hora (`src/asistente_ia.py:268`, `src/copilot.py:214`,
  `:295`, `:310`, `:321`).
- 🟢 `esperar_login`: trata `slow_down`, `expired_token`, `access_denied` y `authorization_pending`, y lanza
  `InterruptedError` si se cancela; `iniciar_login` pide el scope `read:user` (`src/copilot.py:145`, `:172-202`).
- 🟢 `modelos_economicos` quita duplicados por `name` y ordena por precio (`src/copilot.py:253-264`).
- 🟢 `MODELOS_DISPONIBLES` está repetido en `src/main.py:13` y `src/ui.py:32`; `main.listar_modelos` comparte nombre
  con `copilot.listar_modelos` (`src/main.py:16`).
- 🟢 `Historial.crear` con `titulo` pone `titulo_editado = 1`; `listar` ordena por `creado_en DESC, id DESC` y escapa
  los comodines de `LIKE` (`src/historial.py:142`, `:192-198`).
- 🟢 El guardado automático sobrescribe sin preguntar `<nombre>_transcripcion.<formato>` (`src/ui.py:632-635`).

## Contexto de agentes

Documentos revisados: `README.md`, `EGM.md` (arriba) y `.context/inventario.md`.

- `README.md`, sección «Modelos disponibles»: la tabla lista `large`; el código solo acepta `large-v1`, `large-v2` y
  `large-v3`, que la tabla no menciona (`src/main.py:13`, `src/ui.py:32`). `--modelo large` se rechaza. Carril: cambio
  pequeño (carril S); no altera comportamiento, así que no necesita `/cerrar`.
- `.context/inventario.md`: No drift detected.
