# 13 · El gestor de documentos lleva la generación vigente y el asistente

> Origen: `BACKLOG.md`, «Backlog» #12 (y «Salud del código» #5) — hallazgo A-15 — carril M (sexta de las siete
> historias del diseño).
> — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia D1
> (y §Plan técnico, punto 3, bloque «D1 y D2: el gestor (solo hilo principal)», viñetas «Las reglas del asistente se
> vuelven comprobables», «`crear_asistente` se inyecta», «`iniciar` no deja estado a medias» y «`terminar` existe para
> partir D en dos», y «Cómo queda la ventana», viñeta D1; §Riesgos 3; §Requisitos no funcionales, «Hilos»;
> §Revisión (2026-11-22), filas de la comprobación de hilo, de `fecha_de_la_reunion`/`iniciar` y de
> `_alternar_documento_ia`, `_generar_documento_ia` y el orden de creación del gestor).
> Reglas de oro 3, 5 y 9 de `AGENTS.md`. Depende de C2 (historia 12, en implementación): parte del estado en que la deja
> (ver «Supuestos»); D2 depende de esta.
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Criterios, tests y lista de archivos
> tomados del diseño, con los ajustes de su «Revisión», y comprobados contra el código de `7b2949c` en lo que no depende
> de C2.

## Historia

Como quien mantiene el código, quiero que un gestor de documentos lleve la generación vigente y el asistente, para
tener un solo sitio que sabe qué generación está activa.

Es un cambio interno. **Lo observable es para quien mantiene el código**: `src/flujo_documentos.py` gana
`GestorDocumentos`, un objeto sin Tk que guarda la generación vigente (`vigente`) y el asistente que se reutiliza entre
generaciones, y que concentra las reglas que hoy están repartidas por la ventana: crear el asistente solo cuando hace
falta, olvidarlo al cancelar y al cambiar de modelo, no dejar estado a medias si no se puede crear, y no admitir dos
generaciones a la vez. Además comprueba que solo se le llama desde el hilo en que se creó. Todo se prueba sin ventana,
sin red y con un `crear_asistente` falso que cuenta sus llamadas. En la ventana desaparecen `self._asistente` y
`self._generacion`.

**Para el usuario la app no cambia**: mismos textos, mismos diálogos, mismo inicio de sesión cuando falta, misma
cancelación y mismo descarte del resultado de una generación cancelada (`docs/specs/documentos-ia.md`, «Cancelar la
generación» y «Cerrar la ventana durante una generación»), y las notas conservadas tras el fallo de una parte se siguen
reutilizando y perdiendo en los mismos casos («Fallo de una parte»). Ninguna spec cambia.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dado un gestor con un `crear_asistente` falso que cuenta sus llamadas y una transcripción
  con los segmentos «Hola equipo.» y «Cerramos el punto.», cuando se inicia una minuta de `reunion.m4a`, se termina
  (`terminar` devuelve `True` y `vigente` queda en `None`) y se inicia un resumen, entonces las dos generaciones usan el
  mismo asistente y `crear_asistente` se llamó una vez; cada generación lleva su clave, el texto «Hola equipo.\nCerramos
  el punto.», la ruta junto al audio (`reunion.m4a_minuta.md` o `reunion.m4a_resumen.md`), la entrada del historial
  dada y la fecha (la del archivo en la minuta, `None` en el resumen); y tras `cancelar`, o tras `olvidar_asistente`, la
  siguiente generación usa un asistente nuevo (`crear_asistente` llamado otra vez). (antes: lo hace
  `AppTranscriptor._generar_documento_ia`, que crea `self._asistente` con `AsistenteIA(...)` solo si es `None` y calcula
  texto, ruta y fecha en el hilo principal; `_cancelar_documento_ia`, `_al_cambiar_modelo_ia` y `_recibir_documento_ia`
  (ante `ErrorSinSesionCopilot`) lo ponen a `None`; solo se puede comprobar con la ventana)
- [ ] [MODIFICA: sin spec] Dado un gestor sin generación vigente, cuando `crear_asistente` lanza
  `ErrorSinSesionCopilot` o `ErrorModeloIA` al iniciar, entonces sale ese mismo error, `vigente` sigue en `None` y la
  siguiente llamada a `iniciar` vuelve a llamar a `crear_asistente`; y dado un gestor con una generación vigente, cuando
  se inicia otra, entonces sale `ValueError`, `vigente` sigue siendo la anterior y `crear_asistente` no se vuelve a
  llamar. (antes: `_generar_documento_ia` crea el asistente dentro de un `try` antes de crear la generación, así que un
  fallo deja `self._generacion` en `None`; la doble generación la impide solo la guarda `_generando_ia()` al principio
  del método; ninguna de las dos cosas se comprueba sin ventana)
- [ ] [MODIFICA: sin spec] Dada una generación vigente G1, cuando se llama a `cancelar`, entonces devuelve G1 con su
  señal activada y `vigente` queda en `None`; si después se inicia G2, `terminar(G1)` devuelve `False` y no cambia ni
  `vigente` (sigue G2) ni el asistente; sin generación vigente, `cancelar` devuelve `None` y no cambia nada; y cuando se
  llama a `cancelar`, `iniciar`, `terminar`, `asistente` u `olvidar_asistente` desde otro hilo, entonces cada uno lanza
  `RuntimeError` sin cambiar `vigente` ni llamar a `crear_asistente`. (antes: `_cancelar_documento_ia` activa la señal
  y pone `self._generacion` y `self._asistente` a `None`, y vuelve sin hacer nada si no hay generación;
  `_recibir_documento_ia` compara por identidad con `self._generacion`; que todo ocurra en el hilo principal depende de
  que la ventana lo llame a través de `_en_ui`: nada lo comprueba)

El camino no feliz está en los criterios 2 (fallo al crear el asistente, doble generación) y 3 (otro hilo). El caso que
más dolería —cancelar, empezar otra generación y que el resultado tardío de la cancelada le quite a la nueva su estado
o su asistente— queda cubierto en el gestor por el criterio 3 (`terminar(G1)` no toca nada) y en la ventana por la
verificación manual; el descarte completo con `recibir` y el 401 abandonado son de D2.

### Cómo se verifican

- **Con tests sin red, sin ventana y sin `AsistenteIA` real** (regla 3), en `tests/test_flujo_documentos.py` (ya existe,
  de C1 y C2). El `crear_asistente` es una función del test que cuenta sus llamadas y devuelve un `AsistenteFalso`
  nuevo cada vez (el doble de C2) o lanza lo que se le diga. El historial no hace falta: el gestor se crea con
  `historial=None` (D1 no guarda). El audio es `tmp_path / "reunion.m4a"` con `os.utime` a una fecha fija, como en el
  test de `fecha_de_la_reunion` de C1. No importan `rutas_aisladas`, `_Stream` ni `_Respuesta` de otros archivos.
  - `test_gestor_reutiliza_el_asistente_entre_generaciones` (criterio 1): `iniciar("minuta", …)`, `terminar` (`True`,
    `vigente is None`), `iniciar("resumen", …)`; `generacion.asistente` es el mismo objeto (`is`) en las dos y el
    contador vale 1; comprueba los campos de cada `Generacion` (`clave`, `texto`, `ruta_salida`, `id_historial`,
    `fecha` de la minuta igual a `fecha_de_la_reunion(audio, None)` y `None` en el resumen).
  - `test_gestor_recrea_el_asistente_tras_cancelar_u_olvidar` (criterio 1), parametrizado con las dos vías: tras
    `cancelar()` (con una vigente) o tras `terminar` + `olvidar_asistente()`, la siguiente `iniciar` da un asistente
    distinto (`is not`) y el contador vale 2. La recreación tras «sin sesión» se prueba en D2, no aquí.
  - `test_iniciar_sin_asistente_no_deja_vigente` (criterio 2), parametrizado con `ErrorSinSesionCopilot` y
    `ErrorModeloIA`: `pytest.raises` con ese tipo y el mismo objeto (`is`), `vigente is None`, y una segunda
    `iniciar` (con un `crear_asistente` que ya no lanza) llama otra vez a `crear_asistente`.
  - `test_iniciar_con_otra_vigente_lanza_value_error` (criterio 2): con G1 vigente, `pytest.raises(ValueError)`,
    `vigente is G1` y el contador sigue en 1.
  - `test_cancelar_devuelve_la_cancelada_y_libera` (criterio 3): devuelve G1 (`is`), `G1.cancelar.is_set()`,
    `vigente is None`; tras `iniciar` G2, `terminar(G1) is False`, `vigente is G2` y `asistente()` es el de G2; con el
    gestor vacío, `cancelar() is None`.
  - `test_gestor_desde_otro_hilo_lanza_runtime_error` (criterio 3): un `threading.Thread` llama a `cancelar`, `iniciar`,
    `terminar`, `asistente` y `olvidar_asistente` y recoge las excepciones; las cinco son `RuntimeError`, `vigente` no
    cambió y `crear_asistente` no se llamó desde ese hilo.
  - En rojo, los seis fallan con `AttributeError` (`fd.GestorDocumentos` no existe). Ningún test existente cambia;
    `tests/test_importaciones.py` sigue pasando (el gestor no importa Tk). `./venv/bin/python -m pytest -q` en verde.
- **Verificación manual en la ventana real**, con un asistente simulado y lento (el guion de la historia 04) y un
  `_crear_asistente` que anota cada creación en Registro o en la consola (con el real, cada creación deja en el log de
  consola «Usando la sesión de GitHub Copilot de …»):
  - Cancelar (paso 1 de la historia 04): en menos de 1 s, «Generación cancelada», «Generación de la minuta cancelada»,
    la línea en Registro, «Generar» de las dos pestañas y el selector habilitados, «Transcribir» como estaba.
  - Sin esperar (paso 2): generar el resumen, cargar otro archivo y abrir una entrada del historial; ninguno dice
    «Espera a que termine el proceso en curso.».
  - Regenerar y cancelar (paso 3): una entrada con minuta, «↻ Regenerar», «■ Cancelar»; vuelve la minuta anterior con
    «Generación cancelada · se conserva la minuta anterior», y cuando el asistente simulado termina, Registro anota
    «Resultado de minuta descartado: la generación se canceló» y ni el historial ni `reunion.m4a_minuta.md` cambian.
  - Cerrar la ventana durante una generación (paso 5): con «No», la generación sigue; con «Sí», la ventana se cierra y
    el documento no queda en el historial.
  - El asistente: dos generaciones seguidas sin cancelar crean un solo asistente; tras cancelar, la siguiente crea uno
    nuevo; cambiar de modelo entre dos generaciones crea uno nuevo con el modelo elegido («Generando minuta con
    <modelo nuevo>» en Registro).
  - Sin sesión de Copilot, «✨ Generar minuta» abre el inicio de sesión; si se cancela el login, «Generar» sigue
    disponible y no aparece «Espera a que termine el proceso en curso.» (no quedó una generación a medias).
  - `grep -n "self\._asistente\b\|self\._generacion\b" src/ui.py` no devuelve nada.

## Plan

- En el módulo de documentos, un gestor que se crea con el historial y una función que crea el asistente, recuerda el
  hilo en que nace y, al entrar en cada método público, lanza `RuntimeError` si se le llama desde otro.
- El gestor guarda la generación vigente y el asistente: lo reutiliza o lo crea; lo olvida a petición; `iniciar`
  rechaza una segunda generación, calcula primero el asistente, el texto, la ruta y (solo la minuta) la fecha, y solo
  entonces crea la generación y la fija como vigente; `cancelar` activa su señal, la libera y olvida el asistente;
  `terminar` libera solo si es la vigente.
- En la ventana, un método propio que crea el asistente con la configuración de IA y el modelo elegido en ese momento;
  el gestor se crea en el constructor después del historial, y «¿se está generando?» pasa a mirar la vigente del
  gestor.
- Generar (con `iniciar` dentro del mismo `try`: sin sesión → login; otro error del asistente → diálogo), alternar,
  progreso, cancelar, cambiar de modelo y cerrar la ventana pasan por el gestor; recibir usa `terminar` para descartar
  por identidad antes de tocar la vista, olvida el asistente ante «sin sesión» y sigue guardando como hoy.
- Tests en el orden rojo → verde: los seis nuevos, luego el gestor, luego la ventana, la suite completa, el `grep` y la
  verificación manual.

## Fuera de alcance

- Historia D2: `Recepcion` y `GestorDocumentos.recibir` (el único punto de decisión sin ventana), que
  `_recibir_documento_ia` pinte según su estado, el borrado de `persistencia.persistir_documento_si_vigente` y de sus
  dos tests en `tests/test_persistencia.py`, la recreación del asistente tras «sin sesión» probada sin ventana, el caso
  del 401 abandonado (paso 4 de la historia 04) y el fallo de una parte con un `AsistenteIA` real. En esta historia
  `_recibir_documento_ia` sigue guardando con `persistir_documento_si_vigente(False, …)`.
- Reutilizar la sesión `auto` en el gestor (pendiente de `AGENTS.md`, «Mejoras futuras» del diseño).
- Abortar la petición HTTP abierta de una generación cancelada, o cambiar textos, diálogos o el log.
- Cambios en `src/asistente_ia.py`, `src/persistencia.py`, `src/historial.py`, `src/copilot.py`, `src/utils.py`,
  `src/ui_copilot.py`, `src/ui_historial.py`, `tests/conftest.py` o cualquier test existente.
- `_cargar_archivo`, `cargar_desde_historial`, `_limpiar_resultado`, `_seleccionar_archivo`, `_alternar_transcripcion`
  e `_iniciar_sesion_copilot`: no leen ni escriben `self._asistente` ni `self._generacion` (solo llaman a
  `_generando_ia()`, que conserva su nombre), así que no cambian.
- La documentación (`docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md`, `AGENTS.md`, `.context/*`, `docs/specs/`): la
  actualiza `/cerrar`, no el `/pair`.

**Archivos que puede tocar el `/pair` (lista cerrada):** `src/flujo_documentos.py` (añadir `GestorDocumentos` con
`vigente`, `asistente`, `olvidar_asistente`, `iniciar`, `cancelar`, `terminar` y la comprobación de hilo; ajustar el
docstring del módulo si hace falta), `src/ui.py` (`__init__`, `_crear_asistente` (nuevo), `_generando_ia`,
`_al_cerrar`, `_alternar_documento_ia`, `_generar_documento_ia`, `_progreso_documento_ia`, `_recibir_documento_ia`,
`_cancelar_documento_ia`, `_al_cambiar_modelo_ia`; y la cabecera de imports: añadir `GestorDocumentos` al
`from src.flujo_documentos import …` y quitar lo que quede sin uso), `tests/test_flujo_documentos.py`. Si hace falta
tocar otro, se para y se vuelve al diseño.

### Convivencia con C2

C2 (historia 12) se está implementando ahora y toca los mismos métodos de `src/ui.py` (`_generar_documento_ia`,
`_progreso_documento_ia`, `_recibir_documento_ia`, `_cancelar_documento_ia`) y `tests/test_flujo_documentos.py`. **El
`/pair` de D1 se implementa después de que C2 tenga commit**, partiendo de ese árbol, y no reescribe lo que C2 dejó:
`_restaurar_controles_ia`, `self._vista_previa_ia`, `procesar_generacion` como destino del hilo y el `AsistenteFalso`
de los tests se reutilizan tal cual. No quitar `AsistenteIA` del import de `src.asistente_ia` (lo usa
`_crear_asistente`), ni `persistir_documento_si_vigente` del de `src.persistencia` (hasta D2).

## Sugerencias

- **`vigente` como propiedad de solo lectura** sobre un atributo privado: la ventana la lee en `_generando_ia`,
  `_al_cerrar`, `_alternar_documento_ia` y `_progreso_documento_ia`, y así solo los métodos con comprobación de hilo
  pueden cambiarla. El diseño la escribe como atributo; leerla no necesita la comprobación.
- **`_comprobar_hilo()` como primera línea** de cada método público, antes de cualquier otra cosa, para que el test de
  otro hilo pueda afirmar que `crear_asistente` no se llamó.
- **Orden en `_recibir_documento_ia`:** `if not self._documentos.terminar(generacion)` → anotar el descarte y volver,
  **antes** de `_restaurar_controles_ia` (la regla de C2 sobre `self._vista_previa_ia`).
- **`_al_cerrar`** lee la clave de `self._documentos.vigente` antes de preguntar, como hoy lee `self._generacion.clave`.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **Estado de partida, tomado de la historia 12 (C2) y no comprobado en el código**, porque C2 se está implementando:
   `flujo_documentos` tiene `Generacion` (`clave`, `asistente`, `texto`, `fecha`, `ruta_salida`, `id_historial` y su
   propia `cancelar`, `eq=False`), `DocumentoGenerado`, `generar_documento` y `procesar_generacion`, e importa
   `src.asistente_ia`; la ventana crea una `Generacion` en `_generar_documento_ia` y la guarda en `self._generacion`,
   guarda la vista previa en `self._vista_previa_ia`, la restaura con `_restaurar_controles_ia(clave)`, lanza el hilo
   con `procesar_generacion`, `_recibir_documento_ia` tiene tres argumentos (generación, documento, error) y
   `_finalizar_documento_ia` ya no lee `self._asistente.modelo_usado`. Si C2 se cierra distinto, se revisa esta
   historia antes del `/pair`.
2. **`cancelar()` sin generación vigente devuelve `None` y no olvida el asistente.** El diseño dice «devuelve la
   cancelada (o None)» sin decir qué pasa con el asistente en ese caso; hoy `_cancelar_documento_ia` vuelve sin hacer
   nada si no hay generación. Se conserva.
3. **`iniciar` crea la `Generacion`** (con los mismos campos que hoy rellena la ventana en C2), en vez de recibirla; la
   ventana deja de construirla. Es lo que dice la firma del diseño (`iniciar(clave, resultado, archivo, id_historial,
   fecha_historial) -> Generacion`).
4. **Las tres marcas son `[MODIFICA: sin spec]`.** Los comportamientos existen hoy en la ventana y ninguna spec los
   describe en estos términos; la comprobación de hilo es nueva, pero va en el criterio 3 junto a `cancelar`, como en
   el diseño, y su «antes» dice que hoy nada lo comprueba. **Para `/cerrar`:** ninguna spec de `docs/specs/` cambia
   (ni «Cancelar la generación», ni «Cerrar la ventana durante una generación», ni «Fallo de una parte»); solo
   `00-actual.md`, `src/EGM.md` y la tabla de `src/`.
5. **Las notas conservadas siguen igual**: viven en el `AsistenteIA` (`_cache_notas`) y el gestor lo reutiliza y lo
   olvida en los mismos casos que hoy la ventana (cancelar, cambiar de modelo, «sin sesión» en `_recibir_documento_ia`).
   Su prueba con un `AsistenteIA` real es de D2.
6. **Los criterios añaden aserciones a los tests del diseño, no tests nuevos**: los campos de la `Generacion` que crea
   `iniciar` (criterio 1), `terminar(G1)` tras cancelar (criterio 3) y `cancelar()` sin vigente (criterio 3). No
   contradicen el diseño; cubren `iniciar` y `terminar`, que son nuevos.

### Discrepancias entre el diseño y el código actual

Ninguna que cambie la historia. Comprobado contra `7b2949c` (antes de que C2 cambie `src/ui.py`):
`self._asistente` y `self._generacion` se leen o escriben en `__init__`, `_al_cerrar` (`self._generacion.clave`),
`_generando_ia`, `_alternar_documento_ia`, `_generar_documento_ia`, `_progreso_documento_ia`, `_recibir_documento_ia`
(identidad y `self._asistente = None` ante `ErrorSinSesionCopilot`), `_cancelar_documento_ia`,
`_finalizar_documento_ia` (`self._asistente.modelo_usado`, que quita C2) y `_al_cambiar_modelo_ia`; en ningún otro
sitio. Matices:

- **`ErrorModeloIA` no sale hoy del constructor de `AsistenteIA`**: solo lanza `ErrorSinSesionCopilot` (sin token); el
  modelo vacío, excluido o un `auto` sin modelo válido fallan al generar. El criterio 2 lo prueba con un
  `crear_asistente` falso, que es lo que el gestor debe dejar pasar; la ventana captura `ErrorAsistenteIA`, la base de
  los dos, así que no cambia nada.
- **`_cargar_archivo`, `cargar_desde_historial`, `_limpiar_resultado`, `_iniciar_sesion_copilot`** no tocan
  `self._asistente` ni `self._generacion`; los tres primeros (y `_seleccionar_archivo`, `_alternar_transcripcion`) solo
  llaman a `_generando_ia()`. Coincide con la lista del diseño, que no los incluye.
- **Orden en `__init__`:** `self.historial` se crea antes que `self._modelo_preferido`; el gestor recibe
  `self._crear_asistente` como método y solo lo llama al generar, así que lee el modelo elegido en ese momento.
- **`_al_cambiar_modelo_ia`** usa hoy `self._modelo_preferido` y `guardar_modelo_preferido` (punto #11 de «Salud del
  código»), no `guardar_modelo_ia` como dice todavía `AGENTS.md` («Pendientes»). No afecta a D1; queda para `/cerrar` o
  `/deriva`.
- **Líneas.** El diseño cita las de `c59d0ac` (`:849`, `:933`, `:948`, `:1052` para las reglas del asistente); C2
  moverá `src/ui.py`. Mandan los nombres de las funciones.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 322 tests. Code review: revisión del orquestador, listo para commit; el orquestador añadió el caso borde `test_terminar_sin_generacion_no_da_por_terminada_ninguna` (`tests/test_flujo_documentos.py:335`: `terminar(None)` devuelve `False`). Delta de spec: ninguno. Es un cambio interno; la app no cambia para el usuario, y `docs/specs/` no se toca. Las marcas `[MODIFICA: sin spec]` quedan como registro del comportamiento anterior.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Con un `crear_asistente` falso, dos generaciones seguidas (minuta y resumen) comparten asistente y `crear_asistente` se llama una vez; cada generación lleva su clave, texto, ruta, entrada del historial y fecha (solo minuta); tras `cancelar` o `olvidar_asistente` se crea un asistente nuevo | tests `test_gestor_reutiliza_el_asistente_entre_generaciones` (`tests/test_flujo_documentos.py:213`) y `test_gestor_recrea_el_asistente_tras_cancelar_u_olvidar` (`tests/test_flujo_documentos.py:235`). Implementación: `src/flujo_documentos.py:117-121` (`asistente`), `:123-133` (`iniciar`), `:142-150` (`cancelar`), `:152-153` (`olvidar_asistente`) | cumple (tests y verificación manual) |
| 2 | [MODIFICA: sin spec] | Si `crear_asistente` lanza `ErrorSinSesionCopilot` o `ErrorModeloIA`, sale ese mismo error y `vigente` sigue en `None`; con una generación vigente, `iniciar` lanza `ValueError` y no cambia nada | tests `test_iniciar_sin_asistente_no_deja_vigente` (`tests/test_flujo_documentos.py:254`) y `test_iniciar_con_otra_vigente_lanza_value_error` (`tests/test_flujo_documentos.py:269`). Implementación: `src/flujo_documentos.py:123-133` | cumple (tests) |
| 3 | [MODIFICA: sin spec] | Tras `cancelar`, la cancelada tiene su señal activada y `vigente` queda en `None`; `terminar` de una cancelada devuelve `False` sin cambiar nada; sin vigente, `cancelar` devuelve `None`; desde otro hilo, `cancelar`, `iniciar`, `terminar`, `asistente` y `olvidar_asistente` lanzan `RuntimeError` | tests `test_cancelar_devuelve_la_cancelada_y_libera` (`tests/test_flujo_documentos.py:282`), `test_gestor_desde_otro_hilo_lanza_runtime_error` (`tests/test_flujo_documentos.py:302`) y `test_terminar_sin_generacion_no_da_por_terminada_ninguna` (`tests/test_flujo_documentos.py:335`). Implementación: comprobación de hilo `src/flujo_documentos.py:113-115`, `:135-140` (`terminar`), `:142-150` (`cancelar`) | cumple (tests) |

Apoyo: la ventana crea el asistente en `src/ui.py:817-827` (`_crear_asistente`), pide la generación con `self._documentos.iniciar` en `src/ui.py:833`, decide con `terminar` en `src/ui.py:874`, olvida el asistente ante «sin sesión» en `src/ui.py:887`, cancela con `cancelar` en `src/ui.py:895` y olvida el asistente al cambiar de modelo en `src/ui.py:1011`. No quedan `self._asistente` ni `self._generacion` en `src/ui.py`.

**Verificación (2026-11-22)**, hecha por el orquestador en la ventana real con un asistente simulado y sin red, repitiendo el guion de cancelar de la historia 04:

- La primera minuta se genera y se exporta como `reunion.m4a_minuta.md`.
- Al regenerar y cancelar, la ventana queda libre en 12 ms con «Generación cancelada · se conserva la minuta anterior».
- La petición abandonada que termina después con un documento no cambia ni la pestaña ni el archivo.
- La que termina con un 401 no abre el inicio de sesión.
- La siguiente generación crea un asistente nuevo y termina bien.
- Al cerrar con una generación en curso se pregunta; con «No», la generación sigue.

**Pendientes aceptados:**

- El guardado sigue en la ventana (`_recibir_documento_ia` llama a `persistir_documento_si_vigente`) hasta la historia 14.
- No se verificó en la ventana el cambio de modelo entre generaciones; el olvido del asistente al cambiar de modelo queda cubierto por `test_gestor_recrea_el_asistente_tras_cancelar_u_olvidar` (`tests/test_flujo_documentos.py:235`).
