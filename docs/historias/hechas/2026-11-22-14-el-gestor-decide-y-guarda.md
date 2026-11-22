# 14 · El gestor decide y guarda lo que llega de cada generación

> Origen: `BACKLOG.md`, «Backlog» #13 (y «Salud del código» #5) — hallazgo A-15 — carril M (séptima y última de las
> siete historias del diseño).
> — Diseño: docs/disenos/05-flujos-fuera-de-la-ventana.md §Historia D2
> (y §Plan técnico, punto 3, bloque «D1 y D2: el gestor (solo hilo principal)» —`Recepcion` y
> `GestorDocumentos.recibir`—, viñetas «El punto de decisión sigue siendo único…», «Las reglas del asistente se
> vuelven comprobables» y «`terminar` existe para partir D en dos», y «Cómo queda la ventana», viñeta D2; §Decisiones
> abiertas 3; §CUJ 2; §Dobles de test; §Revisión (2026-11-22), filas «Secuencia exacta del 401 abandonado» y «C6
> duplicaba tests existentes; faltaba demostrar la caché de notas con el gestor»).
> Reglas de oro 3, 5, 6 y 9 de `AGENTS.md`. Depende de D1 (historia 13, aprobada y **sin implementar**): parte del
> estado en que la deje (ver «Supuestos»). C2 (historia 12) está cerrada en `fd8cfd9`.
> Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Criterios, tests y lista de archivos
> tomados del diseño, con los ajustes de su «Revisión», y comprobados contra el código de `fd8cfd9` en lo que no
> depende de D1.

## Historia

Como quien mantiene el código, quiero que el gestor decida y guarde lo que llega de cada generación, para que el único
punto de decisión sea un objeto sin interfaz.

Es un cambio interno. **Lo observable es para quien mantiene el código**: `GestorDocumentos` gana `recibir`, que toma
el resultado de una generación (documento o error) y devuelve una `Recepcion` con uno de cuatro estados:
«descartada» (la generación ya no es la vigente: no guarda, no toca el asistente, no pide login), «lista» (guardada
primero en el historial y después junto al audio, con su `Persistencia`), «error» y «sin_sesion» (además olvida el
asistente). La ventana deja de decidir: `_recibir_documento_ia` llama a `recibir` y pinta según el estado. Se borra
`persistencia.persistir_documento_si_vigente`, que ya nadie necesita, y sus dos tests pasan al gestor.

**Para el usuario la app no cambia**: mismo orden historial → archivo y mismos avisos («Guardado del documento antes
de exportarlo», «Estado de un documento generado», «Entrada eliminada durante la generación»), mismo descarte de una
generación cancelada con documento, error o 401 sin diálogos ni login («Cancelar la generación», «Cerrar la ventana
durante una generación»), y las notas conservadas tras el fallo de una parte se reutilizan y se pierden en los mismos
casos («Fallo de una parte»). Ninguna spec de `docs/specs/documentos-ia.md` cambia.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dado `reunion.m4a` en el historial (sin título editado) y una minuta vigente iniciada con el
  gestor, cuando llega a `recibir` su documento «# Minuta: Revisión de lanzamiento…» con el modelo «gpt-5.4»,
  entonces devuelve «lista» con ese documento y una `Persistencia` sin motivos, la entrada tiene esa minuta, el modelo
  «gpt-5.4» y el título «Revisión de lanzamiento», `reunion.m4a_minuta.md` contiene la minuta y `vigente` queda en
  `None`; si la entrada se eliminó entre `iniciar` y `recibir`, `motivo_historial` es «La entrada ya no está en el
  historial» y el archivo se escribe igual; si el audio ya no existía al iniciar, solo se guarda en el historial
  (`ruta_exportada` y `motivo_exportacion` en `None`). (antes: lo hace `AppTranscriptor._recibir_documento_ia`, que
  descarta por identidad con `terminar`, restaura los controles y llama a
  `persistir_documento_si_vigente(False, self.historial, generacion.id_historial, clave, documento.contenido,
  documento.modelo_usado, generacion.ruta_salida)`; solo se puede comprobar con la ventana)
- [ ] [MODIFICA: sin spec] Dado una entrada de `reunion.m4a` con la minuta «# Minuta anterior» en el historial y en
  `reunion.m4a_minuta.md`, y la secuencia `iniciar(G1)` (crea el asistente A), `cancelar()`, `iniciar(G2)` (crea el
  asistente B), cuando llega a `recibir` el resultado de G1 con un documento, con `ErrorAsistenteIA` o con
  `ErrorSinSesionCopilot`, entonces devuelve «descartada», el historial y `reunion.m4a_minuta.md` no cambian
  (contenido y `mtime`), `vigente` sigue siendo G2, `asistente()` sigue siendo B y `crear_asistente` se llamó 2 veces.
  (antes: `_recibir_documento_ia` compara con la vigente y, si no coincide, anota «Resultado de <clave> descartado: la
  generación se canceló» y vuelve; el no guardar de una cancelada se prueba con `persistir_documento_si_vigente(True,
  …)`, que la ventana nunca llama con `True`, y lo de no olvidar el asistente ni pedir login tras un 401 abandonado
  solo se ve en la ventana)
- [ ] [MODIFICA: sin spec] Dada una transcripción que se procesa en varias partes con un `AsistenteIA` real (`httpx`
  simulado) cuya parte 2 recibe un 403, cuando ese error llega a `recibir`, entonces devuelve «error» con el mensaje
  «falló la parte 2 de N: …» del asistente; al iniciar después el otro documento, Copilot recibe solo las peticiones
  de notas de las partes que no terminaron y la redacción; tras `cancelar` una generación, la siguiente vuelve a pedir
  todas las partes; y dado una generación vigente que termina con `ErrorSinSesionCopilot`, `recibir` devuelve
  «sin_sesion» con su mensaje y la siguiente generación crea otro asistente. (antes: la reutilización de las notas
  solo se prueba en `tests/test_asistente_ia.py` llamando dos veces al mismo `AsistenteIA`; que la ventana reutilice
  ese asistente tras un error, y lo descarte al cancelar o tras «sin sesión» (`_recibir_documento_ia` llama a
  `olvidar_asistente` desde D1), solo se ve en la ventana)

El camino no feliz está en los criterios 2 (resultado tardío de una cancelada, con documento, error o 401) y 3 (fallo
de una parte, «sin sesión»). El caso que más dolería —CUJ 2: cancelar una regeneración, volver a generar y que el 401
de la abandonada pise el historial o el archivo, abra el login o le quite el asistente a la nueva— es el criterio 2,
con la secuencia exacta de la Revisión del diseño.

### Cómo se verifican

- **Con tests sin red y sin ventana** (regla 3), en `tests/test_flujo_documentos.py` (ya existe, de C1, C2 y D1), con
  su fixture propio `historial` (`Historial(str(tmp_path / "historial.db"))`) y el audio `tmp_path / "reunion.m4a"`. Los
  tests llaman al gestor en el hilo del test. No importan `rutas_aisladas`, `_Stream` ni `_Respuesta` de otros
  archivos.
  - `test_recibir_vigente_guarda_y_devuelve_lista` (criterio 1): `crear_asistente` devuelve un `AsistenteFalso`; tras
    `iniciar("minuta", …)`, `recibir(G, DocumentoGenerado(…), None)`; comprueba estado, `documento is`, entrada
    (`minuta`, `minuta_modelo`, `titulo`), contenido del `.md` (`minuta + "\n"`), `persistencia.ruta_exportada`,
    `id_historial` y `vigente is None`.
  - `test_recibir_entrada_eliminada_exporta_y_avisa` (criterio 1): `historial.eliminar(id_)` entre `iniciar` y
    `recibir`; «lista», `motivo_historial == "La entrada ya no está en el historial"`, archivo escrito.
  - `test_recibir_sin_audio_solo_historial` (criterio 1): `iniciar` con un audio que no existe y una `fecha_historial`;
    «lista», entrada con el documento, `ruta_exportada is None` y `motivo_exportacion is None`, y ningún `.md` creado.
  - `test_recibir_cancelada_descarta_sin_guardar_ni_olvidar` (criterio 2), parametrizado con documento,
    `ErrorAsistenteIA` y `ErrorSinSesionCopilot`: `crear_asistente` devuelve un `AsistenteFalso` nuevo en cada llamada
    (A y B); la minuta anterior se siembra con `persistir_documento` antes de `iniciar(G1)` y se fija su `mtime` con
    `os.utime` a una fecha pasada; tras `recibir(G1, …)`: `estado == "descartada"`, `persistencia is None`, entrada y
    `.md` intactos (contenido y `st_mtime`), `vigente is G2`, `asistente() is B` y contador 2. **Sustituye a los dos
    tests de `persistir_documento_si_vigente`.**
  - `test_fallo_de_una_parte_reutiliza_notas_y_cancelar_las_pierde` (criterio 3): `crear_asistente` crea
    `AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=300, revision_fidelidad=False,
    peticiones_paralelas=1)`; un fixture autouse del archivo aísla el token (`copilot.RUTA_TOKEN`,
    `copilot.RUTA_AUTH_OPENCODE` en `tmp_path`, sin `COPILOT_GITHUB_TOKEN`) y el test parchea `asistente_ia.httpx.get` y
    `asistente_ia.httpx.post` con funciones que fallan (prohibidas) y `asistente_ia.httpx.stream` con un `_StreamFalso`
    propio, que responde 403 a la petición cuyo cuerpo contiene el texto de la parte 2 mientras un interruptor esté
    activo y, si no, un documento con todas las secciones de `SECCIONES_RESUMEN` y `SECCIONES_MINUTA`. Cada generación
    se ejecuta con `procesar_generacion` en el hilo del test, con un `entregar` que guarda el resultado, y después se
    pasa a `recibir`. Pasos: minuta → «error» con «falló la parte 2 de N»; se apaga el interruptor; resumen → las
    peticiones de notas son solo de las partes 2..N (contadas por el texto de cada parte) más una redacción, «lista»;
    `iniciar` + `cancelar`; minuta → `crear_asistente` llamado 2 veces y se piden las N partes.
  - `test_recibir_sin_sesion_vigente_olvida_el_asistente` (criterio 3): con un `AsistenteFalso`, `recibir(G, None,
    ErrorSinSesionCopilot("…"))` → «sin_sesion», `mensaje` igual a `str(error)`, `vigente is None`, y la siguiente
    `iniciar` da otro asistente (`is not`, contador 2). Es la recreación tras «sin sesión» que D1 dejó para aquí.
  - Una aserción más en el test de D1 `test_gestor_desde_otro_hilo_lanza_runtime_error`: `recibir` desde otro hilo
    también lanza `RuntimeError` sin tocar `vigente` (ver «Supuestos» 4).
  - En rojo, los seis nuevos fallan con `AttributeError` (`recibir` no existe) o `ImportError` (`fd.Recepcion`).
- **Tests existentes que cambian:** en `tests/test_persistencia.py` se borran
  `test_documento_de_generacion_cancelada_no_se_guarda_ni_se_exporta` y
  `test_documento_de_generacion_vigente_se_guarda_y_se_exporta`, y se quita `persistir_documento_si_vigente` del
  import. Lo que comprobaban queda en `test_recibir_cancelada_descarta_sin_guardar_ni_olvidar` y
  `test_recibir_vigente_guarda_y_devuelve_lista`. El resto de `tests/test_persistencia.py` (incluidos los de
  `persistir_documento` con carpeta bloqueada, historial lleno y entrada eliminada) no cambia, ni ningún otro test
  existente. `./venv/bin/python -m pytest -q` en verde.
- **Verificación manual en la ventana real**, con un asistente simulado (sin red), un historial temporal y un audio en
  una carpeta normal y otro en una de solo lectura:
  - Guion completo de la historia 04: (1) «✨ Generar minuta» y «■ Cancelar»: en menos de 1 s «Generación cancelada»,
    «Generación de la minuta cancelada», línea en Registro, texto inicial de la pestaña, «Generar» de las dos pestañas
    y selector habilitados, «Transcribir» como estaba, Texto sin cambios; (2) sin esperar, generar el resumen, cargar
    otro archivo y abrir una entrada del historial, sin «Espera a que termine el proceso en curso.»; (3) entrada con
    minuta, «↻ Regenerar», «■ Cancelar», y el asistente simulado termina **con documento**: vuelve la minuta anterior
    con «Generación cancelada · se conserva la minuta anterior», Registro anota «Resultado de minuta descartado: la
    generación se canceló», sin diálogos, y ni la entrada ni la fecha de modificación de `reunion.m4a_minuta.md`
    cambian; repetirlo con un asistente que termina **con un error**: igual, sin diálogo; (4) repetirlo con uno que
    termina **con un 401**: no se abre el inicio de sesión, y una generación nueva lanzada antes de que llegue el 401
    termina bien con su asistente; (5) cerrar con una generación en curso: con «No» sigue, con «Sí» se cierra y al
    reabrir el historial no tiene el documento nuevo; cancelar y cerrar en seguida no pregunta.
  - Guion de la historia 07: con un asistente que falla en una parte, la pestaña y el diálogo dicen «No se pudo
    generar: falló la parte N de M: … Se conservan las notas de las K partes que terminaron; al volver a generar solo
    se pedirán las que faltan.»; generar el otro documento sin cambiar de modelo: Registro muestra que solo se piden las
    partes que faltan.
  - Guion de la historia 01 para el guardado: minuta y resumen de un audio en carpeta de solo lectura (documento en la
    pestaña y en el historial, título tomado de la minuta, sin diálogo, la línea de estado dice que no se pudo exportar
    y que quedó en el historial) y con el historial no disponible al guardar (archivo exportado y «no se guardó en el
    historial: …»; si tampoco se exporta, «El resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para
    conservarlo.»).
  - Generación vigente que termina con «sin sesión»: diálogo de error y se abre el inicio de sesión, como hoy.
  - `grep -rn "persistir_documento_si_vigente" src/ tests/ --include=*.py` no devuelve nada (ver «Discrepancias»).

## Plan

- En el módulo de documentos, el resultado de recibir una generación: su estado (descartada, lista, error o sin
  sesión), la generación y, según el caso, el documento y lo guardado, o el mensaje del error.
- Recibir, en el gestor y con la comprobación de hilo: si la generación no es la vigente, se descarta sin guardar ni
  tocar el asistente; si trae documento, se guarda con la función de guardado de hoy (historial y después archivo);
  ante falta de sesión se olvida el asistente; cualquier otro error se devuelve tal cual.
- En la ventana, recibir pasa al gestor y solo pinta según el estado, con los mismos textos de hoy: descartada → la
  línea de Registro; lista → restaurar controles y pintar el documento; error y sin sesión → restaurar controles y
  pintar el error, y sin sesión abre además el inicio de sesión.
- Borrar la función de guardado condicional y sus dos tests, que pasan al gestor; quitarla de los imports.
- Tests en el orden rojo → verde: los seis nuevos, luego el gestor, luego la ventana, la suite completa, el `grep` y la
  verificación manual.

## Fuera de alcance

- Cambiar cualquier comportamiento de `docs/specs/documentos-ia.md`: el orden historial → archivo, los textos de
  estado y de Registro, el descarte de una cancelada, el login tras «sin sesión», las notas conservadas. Ninguna spec
  cambia.
- Abortar la petición HTTP abierta de una generación cancelada, conservar las notas tras cancelar o tras «sin
  sesión», reutilizar la sesión `auto` en el gestor («Mejoras futuras» del diseño).
- Cambios en `src/asistente_ia.py`, `src/historial.py`, `src/copilot.py`, `src/utils.py`, en `persistir_documento`,
  `texto_destino_documento` o el resto de `src/persistencia.py`, en `tests/test_asistente_ia.py` o `tests/conftest.py`.
- `PanelHistorial` y sus llamadas a métodos privados de la ventana; la CLI.
- La documentación (`docs/disenos/00-actual.md`, `EGM.md`, `src/EGM.md` —que nombra `persistir_documento_si_vigente`
  tres veces—, `AGENTS.md`, `.context/*`, `docs/specs/`): la actualiza `/cerrar`, no el `/pair`.

**Archivos que puede tocar el `/pair` (lista cerrada):** `src/flujo_documentos.py` (añadir `Recepcion` y
`GestorDocumentos.recibir`; importar `ErrorSinSesionCopilot` y `persistir_documento`/`Persistencia`),
`src/ui.py` (`_recibir_documento_ia` pinta según `Recepcion`; quitar `persistir_documento_si_vigente` del import de
`src.persistencia`), `src/persistencia.py` (borrar `persistir_documento_si_vigente`), `tests/test_flujo_documentos.py`
(seis tests nuevos, el fixture autouse del token, `_StreamFalso` y la aserción de `recibir` en el test de hilo de D1),
`tests/test_persistencia.py` (borrar los dos tests y el nombre del import). Si hace falta tocar otro, se para y se
vuelve al diseño.

### Convivencia con D1

D1 (historia 13) está aprobada y sin implementar; toca `src/flujo_documentos.py`, `src/ui.py`
(`_recibir_documento_ia` entre otros) y `tests/test_flujo_documentos.py`. **El `/pair` de D2 se implementa después
del commit de D1**, partiendo de ese árbol, y no reescribe lo que D1 deje: `GestorDocumentos` con `vigente`,
`asistente`, `olvidar_asistente`, `iniciar`, `cancelar`, `terminar` y `_comprobar_hilo`; `_crear_asistente` y
`self._documentos` en la ventana. `recibir` usa `terminar` y `olvidar_asistente`, no los duplica. Si D1 se cierra
distinto de su historia, se revisa esta antes del `/pair`.

## Sugerencias

- **Orden dentro de `recibir`:** `_comprobar_hilo()` primero; después `if not self.terminar(generacion)` → «descartada»
  sin más (llamar a `terminar` desde dentro repite la comprobación de hilo, que es inocua).
- **`_recibir_documento_ia` sigue con tres argumentos** (C2) y usa el `error` original para la línea de Registro
  «Error generando <clave>: <error>», como hoy; el texto que se pinta y el del diálogo es `recepcion.mensaje`. Así ni
  el log ni el diálogo cambian.
- **Orden en la ventana:** «descartada» vuelve **antes** de `_restaurar_controles_ia` (la regla de C2 sobre
  `self._vista_previa_ia`); en «sin_sesion», `_finalizar_documento_ia` con el mensaje y después
  `_iniciar_sesion_copilot(lambda: self._generar_documento_ia(clave))`, como hoy.
- **Test del criterio 3:** construir el texto con segmentos numerados («Segmento 001 …») y comprobar con
  `dividir_texto(texto, 300)` cuántas partes salen, como hace `tests/test_asistente_ia.py` con `TEXTO_OCHO_PARTES`;
  con 3 o 4 partes basta. Para el paso «lista» del resumen vale `historial=None` o el fixture `historial`: lo que se
  comprueba son las peticiones.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **Estado de partida, tomado de la historia 13 (D1) y no comprobado en el código**, porque D1 no está implementada:
   `GestorDocumentos(historial, crear_asistente)` con `vigente`, `asistente()`, `olvidar_asistente()`,
   `iniciar(clave, resultado, archivo, id_historial, fecha_historial) -> Generacion` (calcula asistente, texto, ruta y
   fecha antes de fijar `vigente`), `cancelar()` (activa la señal, libera y olvida el asistente; sin vigente devuelve
   `None`), `terminar(generacion) -> bool` y `_comprobar_hilo()` en cada método público; la ventana tiene
   `self._documentos` y `_crear_asistente`, y `_recibir_documento_ia` usa `terminar` y `olvidar_asistente` y sigue
   llamando a `persistir_documento_si_vigente(False, …)`. En los tests de D1 existen `AsistenteFalso` (de C2) y un
   `crear_asistente` que cuenta sus llamadas.
2. **«descartada» lleva `persistencia=None` y `documento=None`**, aunque llegue un documento: nada se guardó y la
   ventana no lo pinta. El diseño solo dice `Recepcion("descartada")`.
3. **`mensaje` es `str(error) or type(error).__name__`** en «error» y «sin_sesion», como hoy en `_recibir_documento_ia`;
   un `InterruptedError` de la vigente (que en la práctica no llega: cancelar la quita de vigente) da «error» con
   «InterruptedError», como dice el diseño.
4. **`recibir` también comprueba el hilo**, porque el diseño dice que «cada método público» lo hace y que el gestor
   lanza `RuntimeError` fuera del hilo en que se creó. Se cubre añadiendo `recibir` al test de otro hilo de D1, no con
   un test nuevo: no contradice el diseño (que no lista ese test en D2) y cubre el método nuevo.
5. **Las tres marcas son `[MODIFICA: sin spec]`.** Los comportamientos existen hoy en la ventana (y, el no guardar de
   una cancelada, en `persistir_documento_si_vigente`), y ninguna spec los describe en estos términos; las de
   `documentos-ia.md` que tocan la zona no cambian. **Para `/cerrar`:** ninguna spec cambia; sí `00-actual.md`
   («Modelo de concurrencia»: el punto de decisión pasa a `GestorDocumentos.recibir`), `src/EGM.md` (tres menciones a
   `persistir_documento_si_vigente`), la tabla de `src/` en `AGENTS.md` y, al ser la última historia, el estado del
   diseño 05 y el punto #5 de «Salud del código» en `BACKLOG.md`.
6. **El 403 del criterio 3 es un fallo de parte**: `AsistenteIA._completar` no reintenta un 403 y lanza
   `ErrorAsistenteIA` («GitHub Copilot rechazó la petición (403): …»), que `_notas_por_bloque` envuelve en «falló la
   parte 2 de N: …». Con `peticiones_paralelas=1` la parte 1 termina, las partes 3..N no se envían, y el mensaje dice
   «Se conserva la nota de la parte que terminó…». Las notas se guardan con una clave que incluye el modelo
   (`_clave_nota`), así que el otro documento con el mismo asistente las reutiliza, y un asistente nuevo (tras
   `cancelar`) empieza con la caché vacía.

### Discrepancias entre el diseño y el código actual

Ninguna que cambie los criterios. Comprobado contra `fd8cfd9`: `persistir_documento_si_vigente` está en
`src/persistencia.py` (las líneas 92-104 que cita el diseño siguen valiendo) y solo la llama
`_recibir_documento_ia`, con `False`; sus dos tests y el import están donde dice el diseño
(`tests/test_persistencia.py`). `persistir_documento` ya devuelve «La entrada ya no está en el historial» si la
entrada desapareció y, con `ruta_salida=None`, solo guarda en el historial. `_recibir_documento_ia` ya usa
`str(error) or type(error).__name__` y, ante `ErrorSinSesionCopilot`, pinta el error y abre el login.
`AsistenteIA(api_key="x", …)` no lee el token ni hace red al crearse, y con un modelo concreto (`gpt-4.1`) no consulta
el catálogo. Matices:

- **El `grep` del diseño no queda vacío tras el `/pair`.** `grep -n "persistir_documento_si_vigente" src/ tests/`
  encuentra también `src/EGM.md` (tres líneas), que solo actualiza `/cerrar`. En la verificación del `/pair` se usa
  `grep -rn … src/ tests/ --include=*.py`; tras `/cerrar`, el `grep` del diseño sí debe quedar vacío.
- **«No pide login» no es del gestor.** El gestor no abre diálogos: lo comprueba el estado «descartada» (la ventana
  solo anota en Registro). Que no se abra el login con un 401 abandonado queda en la verificación manual (paso 4).
- **Recreación tras «sin sesión».** Hoy, en `fd8cfd9`, la hace la ventana (`self._asistente = None` en
  `_recibir_documento_ia`); D1 la pasa a `olvidar_asistente()` sin test y D2 la mueve a `recibir` con test, como pide
  el diseño.
- **Líneas.** El diseño cita las de `c59d0ac`; D1 moverá `src/ui.py` y `src/flujo_documentos.py`. Mandan los nombres
  de las funciones.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 328 tests. Code review: revisión del orquestador, listo para commit (queda pendiente el code review de todo el diseño 05). Delta de spec: ninguno. Es un cambio interno; la app no cambia para el usuario, y `docs/specs/` no se toca. Las marcas `[MODIFICA: sin spec]` quedan como registro del comportamiento anterior.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | Vigente que llega a `recibir` con documento: «lista», con `Persistencia` sin motivos, entrada con minuta, modelo y título, `.md` escrito y `vigente` en `None`; entrada eliminada entre `iniciar` y `recibir`: `motivo_historial` y archivo igual; audio inexistente: solo historial | tests `test_recibir_vigente_guarda_y_devuelve_lista` (`tests/test_flujo_documentos.py:358`), `test_recibir_entrada_eliminada_exporta_y_avisa` (`tests/test_flujo_documentos.py:382`) y `test_recibir_sin_audio_solo_historial` (`tests/test_flujo_documentos.py:401`). Implementación: `src/flujo_documentos.py:167-179` (`recibir`), `:100-107` (`Recepcion`); `src/ui.py:870-885` (`_recibir_documento_ia` pinta según el estado) | cumple (tests y verificación manual) |
| 2 | [MODIFICA: sin spec] | Generación cancelada que llega a `recibir` con documento, `ErrorAsistenteIA` o `ErrorSinSesionCopilot`: «descartada», sin cambio en historial ni archivo (contenido y `mtime`), `vigente` sigue siendo la nueva, `asistente()` la del nuevo y `crear_asistente` se llamó 2 veces | test parametrizado `test_recibir_cancelada_descarta_sin_guardar_ni_olvidar` (`tests/test_flujo_documentos.py:422`, ids `documento`, `error`, `sin_sesion`). Implementación: `src/flujo_documentos.py:170-171` | cumple (tests y verificación manual) |
| 3 | [MODIFICA: sin spec] | Fallo de una parte con `AsistenteIA` real: «error» con «falló la parte 2 de N»; el siguiente documento solo pide las notas que faltan y la redacción; tras `cancelar` se piden todas; vigente con «sin sesión»: «sin_sesion» con su mensaje, olvida el asistente y la siguiente crea otro | tests `test_fallo_de_una_parte_reutiliza_notas_y_cancelar_las_pierde` (`tests/test_flujo_documentos.py:511`) y `test_recibir_sin_sesion_vigente_olvida_el_asistente` (`tests/test_flujo_documentos.py:450`). Implementación: `src/flujo_documentos.py:172-174` | cumple (tests; el fallo de una parte, solo tests: ver «Pendientes aceptados») |

Apoyo: la ventana crea el asistente en `src/ui.py` (`_crear_asistente`), pide la generación con `self._documentos.iniciar`, entrega el resultado con `recibir` en `src/ui.py:870-885` y el guardado condicional `persistir_documento_si_vigente` desaparece de `src/persistencia.py` (con sus dos tests, que pasan a `tests/test_flujo_documentos.py`). El test de hilo `test_gestor_desde_otro_hilo_lanza_runtime_error` (`tests/test_flujo_documentos.py:321`) comprueba también que `recibir` lanza `RuntimeError` desde otro hilo.

**Verificación (2026-11-22)**, hecha por el orquestador en la ventana real con un asistente simulado y sin red:

- (a) Guion de cancelar de la historia 04, completo: la ventana queda libre en 10 ms; la petición abandonada que termina después con un documento no cambia ni la pestaña ni el archivo; la que termina con un 401 no abre el inicio de sesión; la siguiente generación crea un asistente nuevo y termina bien; al cerrar con una generación en curso se pregunta y con «No» sigue.
- (b) Guardado de la minuta (historia 01): con la carpeta del audio de solo lectura, la pestaña dice «… no se pudo exportar reunion.m4a_minuta.md: Permission denied; guardado en el historial» y la minuta está en el historial. Con además el historial no disponible: «… no se guardó en el historial: Historial no disponible. El resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para conservarlo.»
- (c) Un error de Copilot en la generación vigente muestra el diálogo con el error; un «sin sesión» en la generación vigente muestra el error y abre el inicio de sesión.

**Pendientes aceptados:**

- El fallo de una parte con notas conservadas (historia 07) se verificó con el test `test_fallo_de_una_parte_reutiliza_notas_y_cancelar_las_pierde` (`tests/test_flujo_documentos.py:511`), con `AsistenteIA` real y `httpx` simulado, no en la ventana.
