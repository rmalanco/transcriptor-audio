# 12 · La generación de fondo fuera de la ventana

> Origen: `BACKLOG.md`, «Backlog» #11 (y «Salud del código» #5) — hallazgo A-15 — carril M (quinta de las siete
> historias del diseño).
> — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia C2 — La generación de fondo fuera de la ventana
> (y §Plan técnico, punto 3, bloque «C2: la generación de fondo», viñeta «El modelo que se muestra sale del documento»
> y «Cómo queda la ventana», viñeta C2; §Alternativa G; §Riesgos 1; §Revisión (2026-11-22), filas de las dos
> identidades, de `_recibir_documento_ia` y `modelo_usado`, del docstring de `procesar_generacion`, de la entrega única y
> de la restauración de botones).
> Reglas de oro 3, 5 y 9 de `AGENTS.md`. Depende de C1 (historia 10, cerrada en `ebb77c3`); D1 depende de esta. Toca
> `src/ui.py`, que también toca B2 (historia 11, en curso): ver «Convivencia con B2».
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Criterios, tests y lista de archivos
> tomados del diseño, con los ajustes de su «Revisión», y comprobados contra el código de `ebb77c3`.

## Historia

Como quien mantiene el código, quiero que la generación de fondo viva fuera de la ventana, para que la cancelación y
la vista no dependan de Tk.

Es un cambio interno. **Lo observable es para quien mantiene el código**: `src/flujo_documentos.py` gana
`Generacion` (una generación con su propia señal de cancelación, comparada por identidad), `DocumentoGenerado`
(contenido, modelo usado y segundos), `generar_documento` y `procesar_generacion` (el destino del hilo de fondo, que
entrega el resultado exactamente una vez), y todo eso se prueba sin ventana, sin red y con un asistente falso. En la
ventana desaparecen `_GeneracionIA` y `_procesar_documento_ia`; el estado previo de los botones vive en
`self._vista_previa_ia` y se restaura en un único método, `_restaurar_controles_ia`.

**Para el usuario la app no cambia**: mismos textos de estado («Listo en N s con <modelo> · …», «Generación
cancelada», «Generación cancelada · se conserva la minuta anterior»), misma fecha en la minuta, mismo modelo mostrado
(el que se guarda en el historial, que hoy ya es el mismo valor), y la cancelación y su descarte siguen como dice
`docs/specs/documentos-ia.md` («Cancelar la generación» y «Cerrar la ventana durante una generación»), sin cambios.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dada una `Generacion` de minuta con el texto «Hola equipo.\nCerramos el punto.», la fecha
  «5 de marzo de 2026 (fecha del archivo)» y un asistente falso que devuelve «# Minuta» y cuyo `modelo_usado` pasa de
  «auto» a «auto → gpt-5.4» al generar, cuando se llama a `generar_documento(generacion, on_progreso)`, entonces el
  asistente recibe en `generar_minuta` ese texto, esa fecha, ese `on_progreso` y la señal `generacion.cancelar`, y el
  `DocumentoGenerado` lleva «# Minuta», «auto → gpt-5.4» y `segundos >= 0`; con una `Generacion` de resumen se llama a
  `generar_resumen`, que no recibe fecha. (antes: lo hace el hilo `AppTranscriptor._procesar_documento_ia`, dentro de
  la ventana: elige `generar_resumen` o una lambda sobre `generar_minuta(t, fecha=fecha, …)`, mide `time.monotonic()`
  alrededor de la llamada y pasa `contenido`, `asistente.modelo_usado` y los segundos como argumentos sueltos a
  `_recibir_documento_ia`; `_finalizar_documento_ia` vuelve a leer el modelo de `self._asistente.modelo_usado` para la
  línea de estado; solo se puede comprobar con la ventana)
- [ ] [MODIFICA: sin spec] Dado un asistente falso que devuelve un documento, o que lanza `ErrorAsistenteIA`,
  `InterruptedError` o `ValueError`, cuando se llama a `procesar_generacion(generacion, on_progreso, entregar)`,
  entonces no lanza y `entregar` se llama exactamente una vez, con `(generacion, documento, None)` o con
  `(generacion, None, error)` (el mismo objeto de error); y dado un `entregar` que lanza `RuntimeError`, la excepción
  sale de `procesar_generacion` y `entregar` se ha llamado una sola vez. (antes: `_procesar_documento_ia` hace la
  entrega, `self._en_ui(self._recibir_documento_ia, …)`, **dentro** del `try`; si esa entrega lanzara, el `except
  Exception` entregaría por segunda vez con el error; hoy no pasa porque `_en_ui` traga `RuntimeError` y
  `tk.TclError`, pero nada lo garantiza fuera de la ventana)
- [ ] [MODIFICA: sin spec] Dadas dos generaciones creadas una tras otra con los mismos datos, cuando se activa la señal
  de cancelación de la primera, entonces la de la segunda sigue sin activar, y las dos no son la misma generación
  (`is not`) aunque sus campos coincidan. (antes: `_GeneracionIA`, un `@dataclass` privado de `src/ui.py` con
  `cancelar = field(default_factory=threading.Event)`, ya da una señal propia a cada generación; la ventana las
  compara con `is`)

El camino no feliz está en el criterio 2 (tres errores y un `entregar` que lanza). El caso que más dolería —cancelar,
empezar otra generación y que el resultado tardío de la cancelada pise la vista o los botones de la nueva— solo se ve
en la ventana: lo cubre la verificación manual, porque `_recibir_documento_ia` debe descartar por identidad **antes** de
tocar `self._vista_previa_ia`.

### Cómo se verifican

- **Con tests sin red y sin ventana** (regla 3), en `tests/test_flujo_documentos.py` (ya existe, de C1). Se añade un
  doble propio, `AsistenteFalso` (con `generar_resumen`, `generar_minuta` y `modelo_usado`; anota lo que recibe y
  devuelve o lanza lo que se le diga; puede cambiar su `modelo_usado` al generar), como dice el diseño en «Dobles de
  test que usan los archivos nuevos». No importa `rutas_aisladas`, `_Stream` ni `_Respuesta` de otros archivos, ni crea
  un `AsistenteIA` real. Los tests llaman a `procesar_generacion` en el propio hilo del test (sin `threading.Thread`):
  - `test_generar_documento_minuta_pasa_fecha_senal_y_progreso` (criterio 1): comprueba que `generar_minuta` recibió
    exactamente el texto, la fecha, el mismo `on_progreso` (`is`) y `cancelar is generacion.cancelar`, y que el
    documento es `("# Minuta", "auto → gpt-5.4", segundos >= 0)`. El `modelo_usado` del falso vale «auto» antes de
    generar, para demostrar que se lee **después**.
  - `test_generar_documento_resumen_sin_fecha` (criterio 1): con `clave="resumen"` y `fecha=None`, se llama a
    `generar_resumen` (no a `generar_minuta`) y no recibe ningún argumento `fecha`.
  - `test_procesar_generacion_entrega_una_vez` (criterio 2), parametrizado con documento, `ErrorAsistenteIA`,
    `InterruptedError` y `ValueError`: un `entregar` que anota sus llamadas; una sola llamada, con la misma
    `generacion` (`is`) y o bien `(DocumentoGenerado, None)` o bien `(None, error)` con el error que lanzó el falso
    (`is`).
  - `test_procesar_generacion_entregar_que_lanza_no_reentrega` (criterio 2): `entregar` anota y lanza
    `RuntimeError`; `pytest.raises(RuntimeError)` alrededor de `procesar_generacion` y una sola llamada anotada.
    Conviene un caso con documento y otro con error del asistente, para cubrir las dos ramas.
  - `test_cada_generacion_tiene_su_propia_senal` (criterio 3).
  - En rojo, los cinco fallan con `AttributeError` (`fd.Generacion`, `fd.generar_documento`… no existen). Ningún test
    existente cambia; `tests/test_importaciones.py` sigue pasando (con `src.flujo_documentos` ya en `MODULOS` y
    `SIN_TK` desde C1). `./venv/bin/python -m pytest -q` en verde con la suite que deje B2.
- **Verificación manual en la ventana real (la que pide el diseño)**, con un asistente simulado:
  - Generar un resumen y una minuta: la línea de estado de cada pestaña dice «Listo en N s con <modelo> · …» con el
    modelo del documento (con `auto`, «auto → <modelo>»), y el botón pasa a «↻ Regenerar» (también en la primera
    generación: `_restaurar_controles_ia` va **antes** de que `_finalizar_documento_ia` ponga «↻ Regenerar»).
  - La línea `**Fecha:**` de la minuta es la del archivo.
  - Cancelar una vez: «Generación cancelada», «Generar» de las dos pestañas y el selector de modelo habilitados,
    «Transcribir» en su estado anterior y la pestaña Registro anota la cancelación.
  - Regenerar un documento ya guardado y cancelar: vuelve el documento anterior con «Generación cancelada · se
    conserva la minuta anterior».
  - Cancelar y que llegue después el documento (o un error) de la cancelada, también con otra generación ya en curso:
    Registro anota «Resultado de <clave> descartado: la generación se canceló», no se guarda nada, no aparece ningún
    diálogo, y los botones y la pestaña de la generación en curso no cambian.
  - Un error de generación («No se pudo generar: …» y el diálogo) deja «Generar» de las dos pestañas y el selector
    habilitados, como hoy.
  - `grep -n "_GeneracionIA\|_procesar_documento_ia\|_asistente.modelo_usado" src/ui.py` no devuelve nada.

## Plan

- En el módulo de documentos, una generación comparada por identidad (tipo, asistente, texto, fecha, ruta de salida,
  entrada del historial y su propia señal, sin nada de la vista) y un documento generado con contenido, modelo usado y
  segundos.
- Una función que llama al asistente según el tipo (la fecha solo para la minuta), mide el tiempo dentro y lee el
  modelo usado después de generar; y el destino del hilo de fondo, que la envuelve, convierte cualquier fallo en error y
  entrega una sola vez fuera del `try`, con un docstring que diga desde qué hilos llegan el progreso (también los de
  las partes en paralelo) y la entrega, y que ninguno puede tocar widgets.
- En la ventana, crear directamente esa generación al pulsar «Generar», guardar aparte el estado previo de la vista
  (contenido, texto del botón y estado de «Transcribir») y lanzar el hilo con el destino nuevo, envolviendo progreso y
  entrega con `_en_ui`; borrar la clase privada de la generación y el hilo viejo.
- Un solo método que restaura los controles (texto del botón, «Generar» de las dos pestañas, selector de modelo,
  «Transcribir») y limpia el estado previo, usado al recibir y al cancelar; recibir pasa a tres argumentos, descarta
  por identidad antes de tocar nada, y el final de la generación toma modelo y segundos del documento.
- Tests en el orden rojo → verde: los cinco nuevos, luego el módulo, luego la ventana, la suite completa y la
  verificación manual.

## Fuera de alcance

- Historias D1 y D2: `GestorDocumentos` (`vigente`, `asistente`, `olvidar_asistente`, `iniciar`, `cancelar`,
  `terminar`, `recibir`), `Recepcion`, la comprobación de hilo y el borrado de
  `persistencia.persistir_documento_si_vigente`. En esta historia `self._asistente` y `self._generacion` siguen en la
  ventana (`self._generacion` pasa a guardar una `flujo_documentos.Generacion`), `_recibir_documento_ia` sigue
  decidiendo y guardando con `persistir_documento_si_vigente(False, …)`, y las reglas del asistente (olvidarlo al
  cancelar, tras «sin sesión» y al cambiar de modelo) siguen donde están.
- Historia B2 (`transcribir_y_persistir`, `_procesar_transcripcion`, `_finalizar_ok`, borrado de `tests/test_flujo.py`)
  y la antigua historia E (la CLI con `OpcionesTranscripcion`), que no tiene historia.
- Cambiar lo que pasa al cancelar o su descarte (`docs/specs/documentos-ia.md`, «Cancelar la generación» y «Cerrar la
  ventana durante una generación»), abortar la petición HTTP abierta de una generación cancelada, o cambiar textos de
  estado, diálogos o el log.
- Cambios en `src/asistente_ia.py` (firmas de `generar_resumen`/`generar_minuta`), `src/persistencia.py`,
  `src/historial.py`, `src/utils.py`, `tests/conftest.py` o cualquier test existente.
- `_al_cerrar` y `_alternar_documento_ia`: solo leen `self._generacion.clave`, que `Generacion` también tiene; no
  cambian (pasan al gestor en D1).
- La documentación (`docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md`, `AGENTS.md`, `.context/*`, `docs/specs/`): la
  actualiza `/cerrar`, no el `/pair`.

**Archivos que puede tocar el `/pair` (lista cerrada):** `src/flujo_documentos.py` (añadir `Generacion`,
`DocumentoGenerado`, `generar_documento`, `procesar_generacion`; ajustar el docstring del módulo, ver «Supuestos» 1),
`src/ui.py` (borrar `_GeneracionIA` y `_procesar_documento_ia`; añadir `_VistaPreviaIA`/`self._vista_previa_ia` y
`_restaurar_controles_ia`; cambiar `__init__` (solo la anotación de `self._generacion` y el nuevo
`self._vista_previa_ia = None`), `_generar_documento_ia`, `_progreso_documento_ia`, `_recibir_documento_ia` (tres
argumentos), `_cancelar_documento_ia` y `_finalizar_documento_ia` (recibe el `DocumentoGenerado`); y la cabecera de
imports: `from src.flujo_documentos import …` y quitar `field` de `from dataclasses import …` si queda sin uso),
`tests/test_flujo_documentos.py`. Si hace falta tocar otro, se para y se vuelve al diseño.

### Convivencia con B2

B2 (historia 11) se está implementando ahora y toca `src/ui.py` (`_procesar_transcripcion`, `_finalizar_ok` y sus
imports). No hay métodos en común con C2, pero sí la cabecera de imports (`from src.flujo_transcripcion …`,
`from src.persistencia …` en B2; `from src.flujo_documentos …` y `from dataclasses …` en C2). **El `/pair` de C2 se
implementa después de que B2 tenga commit**, partiendo de ese árbol, y no reescribe lo que B2 haya cambiado. No quitar
del import de `persistencia` `persistir_documento_si_vigente` (lo sigue usando `_recibir_documento_ia` hasta D2) ni
`Persistencia` si `_finalizar_documento_ia` la sigue anotando. `time` y `threading` siguen en uso tras borrar
`_procesar_documento_ia` (cronómetro, `_log`, `threading.Thread`, `threading.Event` de `cancelar_flag`).

## Sugerencias

- **`_VistaPreviaIA` como dataclass privado de `ui.py`** (el diseño admite también un dict): da nombres a los tres
  campos y deja `dataclass` en uso al borrar `_GeneracionIA`.
- **`_finalizar_documento_ia(clave, documento, persistencia, error=None)`** con `documento: Optional[DocumentoGenerado]`:
  en el camino de error se pasa `None` y no hace falta el `segundos=0` de hoy.
- **Orden dentro de `_cancelar_documento_ia`:** leer `contenido` de `self._vista_previa_ia` y reescribir la pestaña
  (o `_reiniciar_tab_ia`) **antes** de llamar a `_restaurar_controles_ia`, que la limpia; y llamar a
  `_restaurar_controles_ia` después de `_reiniciar_tab_ia`, que deshabilita «Generar» de esa pestaña.
- **Docstring de `procesar_generacion`** con el texto del diseño casi literal: `on_progreso` desde el hilo que la
  ejecuta y desde los hilos «ia-parte» de `AsistenteIA._notas_por_bloque`; `entregar`, una vez, desde el hilo que la
  ejecuta; ninguno toca widgets (la ventana los envuelve en `_en_ui`); si `entregar` lanza, la excepción sale (la
  registra `threading.excepthook`) y no se reintenta.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **`src/flujo_documentos.py` importa `AsistenteIA` de `src.asistente_ia` y su docstring cambia.** El docstring de C1
   dice «No importa tkinter, customtkinter, faster_whisper, httpx ni src.asistente_ia», pero `Generacion.asistente` es
   un `AsistenteIA` y el diseño («Estructura») ya dice `flujo_documentos → asistente_ia (ErrorSinSesionCopilot, tipo
   AsistenteIA)`; D2 necesitará `ErrorSinSesionCopilot` de todos modos. Importar `src.asistente_ia` carga `httpx`
   (comprobado) pero no `tkinter`, `customtkinter` ni `faster_whisper`, y `tests/test_importaciones.py` no vigila
   `httpx`: el test sigue pasando. El docstring pasa a decir que no importa Tk ni `faster_whisper`. (La otra opción,
   `TYPE_CHECKING`, mantiene el docstring pero se deshace en D2; no se elige.)
2. **Las tres marcas son `[MODIFICA: sin spec]`.** Los tres comportamientos existen hoy dentro de la ventana
   (`_procesar_documento_ia`, `_GeneracionIA`) y ninguna spec los describe en estos términos; las specs de
   `documentos-ia.md` que sí tocan la zona («Cancelar la generación», «Cerrar la ventana durante una generación»,
   «Estado de un documento generado») no cambian. **Para `/cerrar`:** ninguna spec cambia; solo `00-actual.md`,
   `src/EGM.md` y la tabla de `src/` (nada de esto es observable para el usuario).
3. **«El modelo mostrado no cambia».** Hoy la línea de estado lee `self._asistente.modelo_usado` y el historial guarda
   `asistente.modelo_usado` leído por el hilo al terminar. Son el mismo objeto y el mismo valor: el selector de modelo
   está deshabilitado durante la generación y `self._asistente` solo se pone a `None` al cancelar (el resultado se
   descarta) o tras «sin sesión» (rama de error, que no muestra modelo). Pasar a `documento.modelo_usado` no cambia lo
   que ve el usuario; quita la dependencia de que `self._asistente` siga vivo.
4. **`Generacion` lleva `texto` y `fecha`**, que hoy son argumentos sueltos del hilo (`args=(generacion, texto,
   fecha)`), y **no** lleva el estado de la vista (alternativa G rechazada en la revisión).
5. **El caso que duele** se toma del diseño (Riesgo 1, regresión visual que los tests no ven) y de la historia 04: el
   resultado tardío de una generación cancelada no puede tocar la vista de la siguiente. No hay test automático (la
   ventana no se prueba); queda en la verificación manual y en el orden «comparar identidad → `_restaurar_controles_ia`».

### Discrepancias entre el diseño y el código actual

Ninguna que cambie la historia. Comprobado contra `ebb77c3` (`src/ui.py` leído antes de que B2 lo empezara a tocar en el árbol):
`_GeneracionIA` (`src/ui.py:87-98`, `@dataclass` con `contenido_previo`, `texto_boton_previo`,
`estado_transcribir_previo` y `cancelar = field(default_factory=threading.Event)`); `self._asistente` y
`self._generacion` (`__init__`, `:146-147`); `_al_cerrar` (`:503`, lee `self._generacion.clave`);
`_generando_ia` (`:770`); `_alternar_documento_ia` (`:819`, compara `self._generacion.clave`); `_generar_documento_ia`
(`:825`; crea el asistente, calcula texto, ruta y fecha en el hilo principal desde C1 y lanza el hilo en `:872` con
`args=(generacion, texto, fecha)`); `_procesar_documento_ia` (`:874-888`; la entrega, dentro del `try`);
`_progreso_documento_ia` (`:890`, filtra por `is self._generacion`); `_recibir_documento_ia` (`:894-917`, cinco
argumentos; restaura el texto del botón y «Transcribir» pero deja «Generar» y el selector a `_finalizar_documento_ia`);
`_cancelar_documento_ia` (`:919-942`, restaura todo él mismo); `_finalizar_documento_ia` (`:944`; `self._asistente.modelo_usado`
en `:964`); `_en_ui` (`:1267`, traga `RuntimeError` y `tk.TclError` y no hace nada si `_cerrando`). En
`src/asistente_ia.py`: `modelo_usado` (`:375`, propiedad), `_notas_por_bloque` (`:560`, `ThreadPoolExecutor` con
`thread_name_prefix="ia-parte"` en `:610`, que llama a `on_progreso` desde esos hilos), `generar_resumen(texto,
on_progreso=None, cancelar=None)` (`:721`) y `generar_minuta(texto, on_progreso=None, cancelar=None, fecha=None)`
(`:724`). Matices:

- **Restauración repartida hoy.** El diseño la unifica en `_restaurar_controles_ia`. Hoy, en el camino de éxito, el
  texto del botón se restaura en `_recibir_documento_ia` y luego `_finalizar_documento_ia` lo pisa con «↻ Regenerar»;
  con el método único hay que conservar ese orden (ver la verificación manual).
- **`eq`.** `_GeneracionIA` es un `@dataclass` con `eq=True` por defecto; el diseño pide `eq=False` para `Generacion`.
  Ningún código compara generaciones con `==` (todo es `is`), así que no cambia nada.
- **Docstring del módulo** (supuesto 1): el de C1 excluye `src.asistente_ia`; el diseño lo permite.
- **Estado de la suite.** Al refinar, el árbol tenía la B2 en su paso rojo (`tests/test_flujo_transcripcion.py`
  modificado y `tests/test_flujo.py` borrado sin commit), y `pytest` daba un error de colección. No es de esta historia:
  C2 parte del commit de B2 con la suite en verde.
- **Líneas.** El diseño cita las de `c59d0ac`; las de arriba son de `ebb77c3`. B2 moverá `src/ui.py`: mandan los
  nombres de las funciones.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 313 tests. Code review: revisión del orquestador, listo para commit. Delta de spec: ninguno. Es un cambio interno; la app no cambia para el usuario, y `docs/specs/` no se toca. Las marcas `[MODIFICA: sin spec]` quedan como registro del comportamiento anterior.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | `generar_documento` llama a `generar_minuta` con texto, fecha, progreso y señal propios, y devuelve el documento con el modelo leído después de generar; con resumen no pasa fecha | tests `test_generar_documento_minuta_pasa_fecha_senal_y_progreso` (`tests/test_flujo_documentos.py:88`) y `test_generar_documento_resumen_sin_fecha` (`tests/test_flujo_documentos.py:111`). Implementación: `src/flujo_documentos.py:72-82` | cumple (tests y verificación manual) |
| 2 | [MODIFICA: sin spec] | `procesar_generacion` no lanza y entrega exactamente una vez, con documento o con error; si `entregar` lanza, la excepción sale sin reentregar | tests `test_procesar_generacion_entrega_una_vez` (`tests/test_flujo_documentos.py:127`) y `test_procesar_generacion_entregar_que_lanza_no_reentrega` (`tests/test_flujo_documentos.py:150`). Implementación: `src/flujo_documentos.py:85-98` | cumple (tests y verificación manual) |
| 3 | [MODIFICA: sin spec] | Dos generaciones con los mismos datos tienen señales distintas y no son la misma generación | test `test_cada_generacion_tiene_su_propia_senal` (`tests/test_flujo_documentos.py:166`). Implementación: `src/flujo_documentos.py:53-63` (comparación por identidad, `eq=False` en `:53`) | cumple (test) |

Apoyo: la ventana crea la `Generacion` y lanza `procesar_generacion` con `_en_ui` en `src/ui.py:846-869`; compara por identidad con la generación vigente en `src/ui.py:873` y `:880`; guarda su estado previo en `_vista_previa_ia` (`src/ui.py:849`) y lo restaura en un solo método, `_restaurar_controles_ia` (`src/ui.py:922-931`).

**Verificación (2026-11-22)**, hecha por el orquestador en la ventana real con un asistente simulado y sin red, repitiendo el guion de cancelar de la historia 04:

- La primera minuta se genera y se exporta como `reunion.m4a_minuta.md`.
- Al regenerar, el botón pasa a «■ Cancelar» y se deshabilitan el resumen, «Transcribir» y el selector de modelo.
- Al cancelar, la ventana queda libre en 12 ms con «Generación cancelada · se conserva la minuta anterior», «Generación de la minuta cancelada», «↻ Regenerar» y todos los controles habilitados.
- Cuando la petición abandonada termina después con un documento, la pestaña y el archivo siguen con la minuta anterior.
- Cuando termina con un 401, no se abre el inicio de sesión.
- La siguiente generación crea un asistente nuevo y termina bien.
- Al cerrar con una generación en curso se pregunta «Hay una generación de la minuta en curso. ¿Cancelarla y salir?»; con «No», la generación sigue.
