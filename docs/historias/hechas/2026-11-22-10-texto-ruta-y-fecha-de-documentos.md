# 10 · Texto, ruta y fecha de los documentos fuera de la ventana

> Origen: `BACKLOG.md`, «Backlog» #10 (y «Salud del código» #5) — hallazgo A-15 — carril M (cuarta de las siete
> historias del diseño).
> — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia C1 — Texto, ruta y fecha de los documentos fuera de
> la ventana (y §Plan técnico, punto 3, bloque «C1: funciones puras», viñeta «La fecha se calcula en el hilo
> principal» y «Cómo queda la ventana», viñeta C1; §Decisión abierta 1; §Revisión (2026-11-22), fila de
> `fecha_de_la_reunion`).
> Reglas de oro 3, 4, 5 y 9 de `AGENTS.md`. Depende de la historia A (08, `faster_whisper` perezoso, cerrada); C2
> depende de esta. Es independiente de B1 (09), que se implementa a la vez: ver «Convivencia con B1».
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Criterios, tests y lista de archivos
> tomados del diseño y comprobados contra el código de `f159ce5` (sin cambios de B1 todavía en el árbol; suite: 287
> tests en verde).

## Historia

Como quien mantiene el código, quiero sacar de la ventana el texto que se envía a Copilot, la ruta del documento junto
al audio y la fecha de la reunión, para probarlos sin interfaz gráfica.

Es un cambio interno. **Lo observable es para quien mantiene el código**: existe un módulo sin Tk,
`src/flujo_documentos.py`, con `SUFIJOS_DOCUMENTO`, `texto_para_ia`, `ruta_documento` y `fecha_de_la_reunion`, que se
importa y se prueba sin ventana ni red. **Para el usuario la app no cambia** en el caso normal: mismo texto enviado,
mismo nombre `reunion.m4a_minuta.md` / `reunion.m4a_resumen.md`, mismo «Guardar como…», misma línea `**Fecha:**`.

**Un detalle sí lo puede notar el usuario** (criterio 3): la fecha se calcula en el hilo principal, al pulsar
«Generar minuta», y un error al calcularla (el audio desaparece entre la comprobación y la lectura de su fecha, o una
fecha del historial mal formada) da «No especificada» en la línea `**Fecha:**` de la minuta, en vez de abortar la
generación con el diálogo «No se pudo generar: …». Es un caso raro (la app siempre escribe `creado_en` en ISO 8601),
pero cambia el resultado que ve el usuario, así que el criterio lo marca.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dado un resultado con los segmentos «Hola equipo.» y «Cerramos el punto.» y un
  `texto_completo` distinto («otra cosa»), cuando se pide `texto_para_ia(resultado)`, entonces es
  «Hola equipo.\nCerramos el punto.» (una línea por segmento, sin usar `texto_completo`). (antes:
  `AppTranscriptor._generar_documento_ia` arma el mismo texto con `"\n".join(seg.texto for seg in
  self.resultado_actual.segmentos)` dentro de la ventana; solo se puede comprobar con ella)
- [ ] [MODIFICA: sin spec] Dado `<carpeta>/reunion.m4a` existente, cuando se pide `ruta_documento(audio, "minuta")` y
  `ruta_documento(audio, "resumen")`, entonces son `<carpeta>/reunion.m4a_minuta.md` y `<carpeta>/reunion.m4a_resumen.md`
  (conserva la extensión del audio, punto #18); y si el audio no existe, las dos son `None` (el documento solo se
  guardará en el historial). (antes: `_generar_documento_ia` calcula `ruta_salida` con
  `ruta_junto_al_audio(self.archivo_actual, DOCUMENTOS_IA[clave]["sufijo"])` si `Path(self.archivo_actual).exists()` y
  `None` si no; los sufijos viven en `DOCUMENTOS_IA` de `src/ui.py`)
- [ ] [MODIFICA: sin spec] Dado un audio con fecha de modificación 5 de marzo de 2026 (fijada con `os.utime`), cuando
  se pide `fecha_de_la_reunion(audio, None)`, entonces es «5 de marzo de 2026 (fecha del archivo)»; sin audio y con
  `creado_en` «2026-04-07T10:00:00», «7 de abril de 2026 (fecha de transcripción)»; sin audio y sin fecha, «No
  especificada»; y sin audio con `creado_en` mal formado («ayer»), también «No especificada», sin lanzar. En la ventana,
  la fecha se calcula al pulsar «Generar minuta», en el hilo principal, y llega así a la línea `**Fecha:**` de la
  minuta. (antes: `AppTranscriptor._fecha_archivo` da los mismos tres textos, pero la llama el hilo de fondo
  `_procesar_documento_ia`, que lee `self.archivo_actual` y `self._fecha_historial` de la ventana; con un `creado_en` mal
  formado o un audio que desaparece entre `os.path.exists` y `os.path.getmtime` lanza `ValueError`/`OSError`, y la
  minuta no se genera: la pestaña dice «No se pudo generar: …» con el diálogo de error)

### Cómo se verifican

- **Con tests sin red y sin ventana** (regla 3), en `tests/test_flujo_documentos.py` (archivo nuevo). En esta historia
  no hace falta ningún doble de asistente ni el fixture `historial` del diseño (llegan con C2 y D1); no importa ningún
  doble privado de otros archivos de test:
  - `test_texto_para_ia_une_segmentos_con_salto_de_linea` (criterio 1): `ResultadoTranscripcion(texto_completo="otra
    cosa", segmentos=[SegmentoTranscripcion(0.0, 1.0, "Hola equipo."), SegmentoTranscripcion(1.0, 2.0, "Cerramos el
    punto.")], idioma_detectado="es", probabilidad_idioma=1.0, duracion_total=2.0)`; el resultado es exactamente
    `"Hola equipo.\nCerramos el punto."`.
  - `test_ruta_documento_conserva_la_extension_y_es_none_sin_audio` (criterio 2): crea `tmp_path / "reunion.m4a"`;
    comprueba `ruta_documento(str(audio), "minuta") == str(tmp_path / "reunion.m4a_minuta.md")` y lo mismo con
    `"resumen"` y `reunion.m4a_resumen.md`; con `str(tmp_path / "no-existe.m4a")`, las dos claves dan `None`.
  - `test_fecha_de_la_reunion_desde_archivo_historial_o_ninguna` (criterio 3), parametrizado con los cuatro casos:
    audio en `tmp_path` con `os.utime(audio, (t, t))`, donde `t = time.mktime((2026, 3, 5, 12, 0, 0, 0, 0, -1))`
    (mediodía local, para que la zona horaria no cambie el día) y `fecha_historial=None` → «5 de marzo de 2026 (fecha
    del archivo)»; audio inexistente con «2026-04-07T10:00:00» → «7 de abril de 2026 (fecha de transcripción)»; audio
    inexistente con `None` → «No especificada»; audio inexistente con «ayer» → «No especificada» (sin `pytest.raises`).
  - En `tests/test_importaciones.py`, se añade `"src.flujo_documentos"` a `MODULOS` y a `SIN_TK`. En `MODULOS` va
    **antes de `src.ui_copilot`**, el primero de la lista que carga `tkinter`/`customtkinter` (por ejemplo, justo
    después de `src.asistente_ia`). Así `test_ningun_modulo_carga_faster_whisper_al_importarse` demuestra que importar el
    módulo nuevo no carga `faster_whisper`, `tkinter` ni `customtkinter`.
  - En rojo, los tres tests nuevos fallan con `ImportError` (el módulo no existe) y el de importaciones falla al no
    poder importar `src.flujo_documentos`. Ningún test existente cambia, salvo las dos listas de
    `tests/test_importaciones.py`, y todos siguen pasando (`./venv/bin/python -m pytest -q`; 287 hoy, más los de B1 si
    ya está integrada).
- **Verificación manual en la ventana real (la que pide el diseño):**
  - Generar una minuta (con un asistente simulado) de un audio existente: la línea `**Fecha:**` dice «<d> de <mes> de
    <año> (fecha del archivo)» y aparece `reunion.m4a_minuta.md` junto al audio.
  - Generar una minuta de una entrada del historial cuyo audio ya no existe: la línea dice «(fecha de transcripción)» y
    no se escribe ningún archivo junto al audio (solo historial).
  - «Guardar como…» de un resumen y de una minuta propone `reunion.m4a_resumen.md` y `reunion.m4a_minuta.md`.
  - `grep -n "_fecha_archivo" src/ui.py` no devuelve nada, y el cuerpo de `_procesar_documento_ia` ya no menciona
    `self.archivo_actual` ni `self._fecha_historial` (el hilo de fondo ya no lee la ventana).

## Plan

- Crear el módulo sin interfaz de los documentos, con un docstring que diga que no toca widgets, con los sufijos de
  cada documento y tres funciones puras: el texto que se envía (una línea por segmento), la ruta junto al audio (o
  ninguna si el audio no existe) y la fecha de la reunión, que traga los errores de disco y de formato y devuelve «No
  especificada».
- Que la tabla de documentos de la ventana tome el sufijo de esos sufijos, para que el guardado automático y «Guardar
  como…» sigan proponiendo el mismo nombre.
- Que la ventana, al pulsar generar, calcule en el hilo principal el texto, la ruta y, solo para la minuta, la fecha,
  y pase la fecha al hilo de fondo como argumento; el hilo deja de leer atributos de la ventana y se borra el método de
  la fecha que queda sin uso.
- Tests en el orden rojo → verde: los tres nuevos y las dos listas de `tests/test_importaciones.py`, luego el módulo,
  luego la ventana, y la suite completa en verde.

## Fuera de alcance

- Historia C2: `Generacion`, `DocumentoGenerado`, `generar_documento`, `procesar_generacion`, `_vista_previa_ia`,
  `_restaurar_controles_ia` y los cambios de `_recibir_documento_ia`. En esta historia `_GeneracionIA` sigue igual y el
  hilo sigue siendo `_procesar_documento_ia`, solo con un argumento más (la fecha).
- Historias D1 y D2: `GestorDocumentos` (`iniciar`, `cancelar`, `recibir`, `terminar`), la comprobación de hilo y el
  borrado de `persistencia.persistir_documento_si_vigente`.
- Historias B1 y B2 (`src/flujo_transcripcion.py`, `transcribir_y_persistir`, borrado de `tests/test_flujo.py`) y la
  antigua historia E (la CLI con `OpcionesTranscripcion`), que no tiene historia.
- Cambiar el formato de la fecha, sus textos «(fecha del archivo)», «(fecha de transcripción)» y «No especificada», o
  cómo `AsistenteIA.generar_minuta` la mete en el prompt y en la línea `**Fecha:**`.
- Cambiar `utils.ruta_junto_al_audio` o el nombre de los archivos junto al audio (punto #18), o que «Guardar como…»
  (`_guardar_documento_ia`) use `ruta_documento`: debe seguir proponiendo un nombre aunque el audio ya no exista.
- Cambios en `src/asistente_ia.py`, `src/utils.py`, `src/persistencia.py`, `src/historial.py`, `src/transcriber.py`,
  `tests/conftest.py` o cualquier test existente salvo las dos listas de `tests/test_importaciones.py`.
- La documentación (`docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md`, `AGENTS.md` y su tabla de `src/`,
  `.context/*`, `docs/specs/`): la actualiza `/cerrar`, no el `/pair`.

**Archivos que puede tocar el `/pair` (lista cerrada):** `src/flujo_documentos.py` (crear: `SUFIJOS_DOCUMENTO`,
`texto_para_ia`, `ruta_documento`, `fecha_de_la_reunion`), `src/ui.py` (`_generar_documento_ia` calcula texto, ruta y
fecha en el hilo principal y pasa la fecha al hilo; `_procesar_documento_ia` recibe la fecha; `DOCUMENTOS_IA` toma el
sufijo de `SUFIJOS_DOCUMENTO`; borrar `_fecha_archivo`), `tests/test_flujo_documentos.py` (crear),
`tests/test_importaciones.py` (añadir `src.flujo_documentos` a `MODULOS` y a `SIN_TK`). Si hace falta tocar otro, se
para y se vuelve al diseño.

### Convivencia con B1

B1 (historia 09) se implementa a la vez y toca dos de estos archivos:

- **`src/ui.py`:** B1 toca `_iniciar_transcripcion`, `_procesar_transcripcion` y `_guardar_resultado`, y borra
  `_obtener_transcriptor` y `_generar_ruta_salida`; C1 toca `DOCUMENTOS_IA`, `_generar_documento_ia`,
  `_procesar_documento_ia` y borra `_fecha_archivo`. No hay métodos en común, pero sí la cabecera de imports: los dos
  añaden una línea `from src.flujo_… import …`, y B1 puede dejar sin uso `ruta_junto_al_audio` en el import de `utils`
  mientras C1 lo sigue necesitando en `_guardar_documento_ia`. **No quitar `ruta_junto_al_audio` del import.** Tampoco `os`
  ni `time`: tras borrar `_fecha_archivo` los siguen usando `_abrir_carpeta` (`os.startfile`), el cronómetro de la
  transcripción, `_procesar_documento_ia` (`time.monotonic`) y `_log` (`time.strftime`).
- **`tests/test_importaciones.py`:** los dos añaden su módulo a `MODULOS` y a `SIN_TK`. El resultado final debe tener
  los dos módulos antes de `src.ui_copilot` (por ejemplo, `…, "src.persistencia", "src.flujo_transcripcion",
  "src.copilot", "src.asistente_ia", "src.flujo_documentos", "src.main", "src.ui_copilot", …`) y
  `SIN_TK = ["src.flujo_transcripcion", "src.flujo_documentos"]`. El comentario de `SIN_TK` («Vacía en esta historia;
  B1 y C1 la llenan») se puede actualizar.
- El `/pair` de C1 parte del árbol con B1 ya integrado (o se integra después con un merge de esas dos zonas); no
  reescribe lo que B1 haya cambiado.

## Sugerencias

- Añadir un quinto caso al test parametrizado del criterio 3: audio existente con `os.path.getmtime` parcheado
  (`monkeypatch`) para lanzar `OSError` → «No especificada». Es la otra mitad de la captura `(OSError, ValueError)` que
  pide la revisión del diseño y sale gratis en el mismo test; no añade archivos.
- `fecha_de_la_reunion` puede conservar la estructura de `_fecha_archivo` (la lista `meses`, `time.localtime` con el
  `mtime` y `time.strptime(fecha_historial[:10], "%Y-%m-%d")`) con un solo `try/except (OSError, ValueError)` alrededor,
  para que el texto sea el mismo carácter a carácter.
- Calcular la fecha solo para la minuta (como dice el diseño y como hará `iniciar` en D1) y pasar `None` al hilo para
  el resumen; `generar_resumen` no la recibe.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **Las tres marcas son `[MODIFICA: sin spec]`.** Los tres comportamientos existen hoy dentro de la ventana y ninguna
   spec de `docs/specs/` los describe (no hay ningún comportamiento sobre la fecha de la minuta; la ruta junto al audio
   aparece en `documentos-ia.md`, «Guardado del documento antes de exportarlo», y no cambia). Las notas `(antes: …)`
   salen del código leído.
2. **Lo observable para el usuario es solo el camino de error del criterio 3.** En el caso normal la fecha es la misma
   («Se calcula milisegundos antes que hoy, con el mismo resultado», dice el diseño). Con un `creado_en` mal formado o un
   audio que desaparece justo entre `exists` y `getmtime`, hoy la minuta falla con «No se pudo generar: …» y después
   sale con «**Fecha:** No especificada». Por eso el criterio 3 lo incluye y se marca `MODIFICA`. **Propuesta para
   `/cerrar`:** añadir a `docs/specs/documentos-ia.md` un comportamiento «Fecha de la minuta» en términos de usuario
   (fecha del archivo, fecha de transcripción, «No especificada», y que un error al leerla no impide generar la
   minuta); los criterios 1 y 2 son internos y no cambian ninguna spec.
3. **El caso que duele** es que la minuta pierda la fecha correcta (o falle) por moverla de hilo, porque solo se ve
   leyendo la minuta: lo cubre el criterio 3 con los cuatro casos y la verificación manual. El camino no feliz es el
   mismo criterio («ayer» → «No especificada» sin lanzar) y el `None` del criterio 2.
4. **El test fija el `mtime` a mediodía local.** `fecha_de_la_reunion` usa `time.localtime`, como hoy; un `mtime` a
   medianoche UTC podría caer en otro día según la zona horaria del equipo.
5. **`ruta_documento` usa `Path(archivo).exists()`** como hoy `_generar_documento_ia`, y `fecha_de_la_reunion`
   `os.path.exists`, como hoy `_fecha_archivo`. Los dos dan lo mismo para una ruta de texto; no se unifican.

### Discrepancias entre el diseño y el código actual

Ninguna que cambie la historia. Comprobado contra `f159ce5`: `DOCUMENTOS_IA` (`src/ui.py:74-82`, sufijos `_resumen.md`
y `_minuta.md`); `_generar_documento_ia` (`:844`; texto en `:866`, `ruta_salida` en `:868-870`, hilo en `:891` con
`args=(generacion, texto)`); `_procesar_documento_ia` (`:893`; llama a `self._fecha_archivo()` en `:900`, **dentro
del hilo de fondo y dentro del `try`**, así que su excepción llega como error de generación); `_fecha_archivo`
(`:1075-1087`; formato exacto `f"{t.tm_mday} de {meses[t.tm_mon - 1]} de {t.tm_year} ({origen})"`, con `origen` «fecha
del archivo» o «fecha de transcripción», y «No especificada»); `_guardar_documento_ia` (`:1096`, `initialfile` con
`ruta_junto_al_audio(self.archivo_actual, DOCUMENTOS_IA[clave]["sufijo"])` en `:1103`); `cargar_desde_historial`
(`:1170`, `self._fecha_historial = entrada.creado_en` en `:1189`); `_limpiar_resultado` y `_finalizar_ok` lo ponen a
`None`; `historial._ahora()` escribe `creado_en` con `datetime.now().isoformat(timespec="seconds")` (hora local);
`utils.ruta_junto_al_audio` (`src/utils.py:174`) conserva la extensión; `AsistenteIA.generar_minuta(texto, …, fecha=None)`
(`src/asistente_ia.py:724`) sustituye `{fecha}` en el prompt y reescribe la línea `**Fecha:**` con `fecha or "No
especificada"`. Matices:

- **«Con el mismo resultado».** El diseño (Plan técnico, punto 3) dice que mover la fecha al hilo principal da el mismo
  resultado; es cierto en el caso normal, pero la captura `(OSError, ValueError)` que pide su propia «Revisión» cambia el
  camino de error (de «No se pudo generar» a «No especificada»). No es una contradicción de fondo: el criterio 3 lo dice
  explícitamente (supuesto 2).
- **El diseño enumera cuatro casos en el test de la fecha** y la captura cubre dos excepciones; el caso `OSError` solo
  se prueba si se añade la sugerencia del quinto caso.
- **Orden en `MODULOS`.** El diseño dice «antes de cualquier `src.ui*`»; lo exacto es antes de `src.ui_copilot`, el
  primero que carga Tk (comprobado en la historia 09; `src.main` no lo carga).
- **Líneas.** El diseño cita las de `c59d0ac`; en `f159ce5` `src/ui.py` no había cambiado y coinciden. B1 ya las está
  moviendo en el árbol de trabajo (al terminar de leer, `_fecha_archivo` estaba hacia la línea 1055): mandan los
  nombres de las funciones.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 298 tests. Code review: revisión del orquestador, listo para commit. Delta de spec: un comportamiento nuevo, «Fecha de la minuta», en `docs/specs/documentos-ia.md` (lo que ve la persona: fecha del archivo, fecha de transcripción o «No especificada»). Los criterios 1 y 2 son internos y no cambian ninguna spec.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | `texto_para_ia` une los segmentos con saltos de línea, sin usar `texto_completo` | test `test_texto_para_ia_une_segmentos_con_salto_de_linea` (`tests/test_flujo_documentos.py:13`). Implementación: `src/flujo_documentos.py:21`; la ventana la usa en `src/ui.py:847` | cumple (test y verificación manual) |
| 2 | [MODIFICA: sin spec] | `ruta_documento` conserva la extensión del audio y es `None` si no existe | test `test_ruta_documento_conserva_la_extension_y_es_none_sin_audio` (`tests/test_flujo_documentos.py:25`). Implementación: `src/flujo_documentos.py:26`, sufijos en `src/flujo_documentos.py:16`; la ventana la usa en `src/ui.py:849` y `DOCUMENTOS_IA` toma los sufijos en `src/ui.py:77` y `src/ui.py:80` | cumple (test y verificación manual) |
| 3 | [MODIFICA: sin spec] | `fecha_de_la_reunion` da la fecha del archivo, la de transcripción o «No especificada» sin lanzar; la ventana la calcula al pulsar «Generar minuta» en el hilo principal | test `test_fecha_de_la_reunion_desde_archivo_historial_o_ninguna` (`tests/test_flujo_documentos.py:40-47`, cinco casos). Implementación: `src/flujo_documentos.py:33`; cálculo en el hilo principal en `src/ui.py:851` y paso al hilo en `src/ui.py:872`; `_procesar_documento_ia` lo recibe en `src/ui.py:874` | cumple (test y verificación manual) |

Apoyo: el módulo nuevo figura en `MODULOS` (`tests/test_importaciones.py:17`) y en `SIN_TK` (`tests/test_importaciones.py:22`), comprobado por `test_ningun_modulo_carga_faster_whisper_al_importarse` (`tests/test_importaciones.py:55`). `_fecha_archivo` se borró de `src/ui.py` (`grep` no devuelve nada).

**Verificación (2026-11-22)**, hecha por el orquestador en la ventana real con un asistente simulado y sin red:

- La minuta de `reunion.m4a` (fecha de modificación fijada al 5 de marzo de 2026) lleva «**Fecha:** 5 de marzo de 2026 (fecha del archivo)», se exporta como `reunion.m4a_minuta.md` y el texto enviado es «Hola equipo.\nCerramos el punto.».
- La minuta de una entrada del historial cuyo audio se borró lleva «22 de noviembre de 2026 (fecha de transcripción)», no exporta archivo («guardado en el historial») y «Transcribir» sigue deshabilitado.
- «Guardar como…» propone `reunion.m4a_minuta.md`.

**Pendientes aceptados:** ninguno.
