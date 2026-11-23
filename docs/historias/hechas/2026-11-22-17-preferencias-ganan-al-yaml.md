# 17 · Las preferencias guardadas ganan al YAML al abrir la ventana

> Origen: `BACKLOG.md`, «Backlog» #5 (panel de configuración, carril L), primera de sus historias — Diseño:
> docs/disenos/06-panel-de-configuracion.md §Historia A1 (con «Plan técnico», 1; «Decisiones tomadas»; «Lo que dirá la
> spec» y «Revisión (2026-11-22)») — carril M. Reglas de oro 3, 5, 8 y 9 de `AGENTS.md`. Refinada con `/story` el
> 2026-11-22, sin usuario al otro lado (ver «Supuestos»). No depende de otras historias; A2a, A2b y A3 se apoyan en ella.

## Historia

Como usuario de la ventana, quiero que los valores que tenga guardados en mis preferencias ganen a los de
`config/settings.yaml` al abrir la app, y que un archivo de preferencias roto o con valores raros no me impida abrirla,
para poder tener mis propios valores por defecto sin editar el archivo versionado del proyecto.

## Criterios de aceptación

- [ ] [NUEVO] Dado un `config/settings.yaml` con `salida.formato: "txt"` y `transcripcion.beam_size: 5`, y un
  `preferencias.json` con `{"configuracion": {"salida": {"formato": "srt"}}}`, cuando se abre la ventana, entonces el
  selector de formato del panel lateral muestra `srt`, la transcripción usa `beam_size` 5, Registro no muestra ningún
  aviso de preferencias y `config/settings.yaml` no cambia (mismo contenido y misma fecha de modificación). Sin
  `preferencias.json`, la ventana usa exactamente los valores del YAML, sin avisos. La CLI sigue usando `txt`.
- [ ] [NUEVO] Dado un `preferencias.json` cuyo `configuracion` trae `transcripcion.beam_size: "cinco"`,
  `transcripcion.temperature: NaN`, `audio.sample_rate: 16000`, `ia.modelo: "x"` y una sección `salida: 3`, cuando se
  abre la ventana, entonces se abre, esas cinco entradas toman el valor del YAML y Registro muestra cinco avisos, entre
  ellos «En <ruta>, `transcripcion.beam_size` debe ser un número entero mayor que 0 (vale «cinco»); se usa el valor de
  config/settings.yaml.», «En <ruta>, `audio.sample_rate` no es una clave de la configuración; se ignora.», «En <ruta>,
  `ia.modelo` no se guarda en «configuracion» (el modelo elegido va en «modelo_ia»); se ignora.» y «En <ruta>, la
  sección `salida` no es un objeto; se ignora.», donde <ruta> es la de `preferencias.json`. Lo mismo vale para un
  número infinito en una clave que admite cualquier número (`transcripcion.compression_ratio_threshold: Infinity`). El
  modelo de IA sigue saliendo de `modelo_ia` o, si no hay, de `ia.modelo` del YAML, como hoy.
- [ ] [NUEVO] Dado un `preferencias.json` que no es JSON (por ejemplo `{`), o es una lista JSON, o tiene
  `"configuracion": 3`, o no se puede leer (es una carpeta), cuando se abre la ventana, entonces se abre con los valores
  del YAML y Registro muestra un único aviso de preferencias: «Las preferencias <ruta> no son un JSON válido; se usan los
  valores de config/settings.yaml. Al guardar se reemplazará el archivo.» en los dos primeros casos (y el archivo
  queda marcado como ilegible), «En <ruta>, «configuracion» no es un objeto; se ignora.» en el tercero, y «Las
  preferencias <ruta> no se pudieron leer (<motivo>); se usan los valores de config/settings.yaml.» en el cuarto (los
  dos últimos sin marcarlo como ilegible). Un `config/settings.yaml` inválido sigue impidiendo abrir la ventana con el
  diálogo de hoy.

Cómo se verifican:

- **Con tests sin red y sin ventana** (en `tests/test_configuracion.py`; `RUTA_PREFERENCIAS` aislada por el fixture
  autouse `preferencias_aisladas` de `tests/conftest.py`, o con `monkeypatch` a `tmp_path`; YAML en `tmp_path`; se
  prueban `leer_ajustes` y `combinar` directamente):
  - `test_un_ajuste_guardado_gana_al_yaml_sin_tocarlo`: la efectiva tiene `formato` `srt` y `beam_size` 5, la lista
    de avisos está vacía, y el YAML conserva contenido y `st_mtime_ns` (criterio 1).
  - `test_sin_preferencias_la_efectiva_es_la_del_yaml_sin_avisos`: sin archivo, la efectiva es igual a
    `cargar_configuracion(yaml)`, sin avisos e `ilegible` falso (criterio 1).
  - `test_ajustes_invalidos_desconocidos_no_finitos_e_ia_modelo_se_ignoran_con_aviso`: las cinco entradas del
    criterio 2 dan la efectiva del YAML y exactamente cinco avisos, con los textos literales del criterio (criterio 2).
  - `test_ajuste_infinito_en_clave_sin_tope_se_ignora` (añadido por esta historia, ver «Supuestos», 3):
    `compression_ratio_threshold: Infinity` da el valor del YAML y un aviso «… (vale «inf»); se usa el valor de
    config/settings.yaml.» (criterio 2).
  - `test_preferencias_ilegibles_dan_aviso_y_valores_del_yaml`, parametrizado: texto no JSON, lista JSON,
    `"configuracion": 3` y, añadido por esta historia, `RUTA_PREFERENCIAS` apuntando a una carpeta (`OSError` al
    leer); efectiva igual a la del YAML, un aviso con su texto e `ilegible` verdadero solo en los dos primeros
    (criterio 3).
  - Siguen pasando, sin cambios, los tests de `cargar_configuracion` (sus mensajes no cambian) y los de
    `leer_modelo_preferido`, `guardar_modelo_preferido` y `modelo_ia_efectivo`.
- **Verificación manual en la ventana real** (cambio visible para el usuario), sin tocar las preferencias reales:
  desde un guion en la carpeta temporal que, antes de llamar a `src.ui.main()`, apunta
  `src.configuracion.RUTA_PREFERENCIAS` a un `preferencias.json` temporal escrito a mano:
  1. Con `{"configuracion": {"salida": {"formato": "srt"}}}`, la ventana abre con `srt` en el selector de formato y
     Registro sin avisos de preferencias.
  2. Con `{` en el archivo, abre con `txt` y Registro muestra «Las preferencias <ruta> no son un JSON válido; …».
  3. Con el contenido del criterio 2, abre y Registro muestra los cinco avisos.
  4. `git status` no muestra `config/settings.yaml` y su `sha256sum` es el mismo antes y después.

## Plan

- La configuración aprende a leer las preferencias de configuración de forma tolerante: distingue archivo ausente,
  ilegible (no es JSON u objeto), no legible por el sistema y estructura rara (`configuracion` o una sección que no son
  objetos), y nunca lanza; cada problema es un aviso con el texto del diseño.
- Una función sin ventana combina la configuración del proyecto con esas preferencias sobre una copia: valida cada
  valor con la misma tabla y el mismo mensaje que el YAML (más «número finito»), ignora con aviso `ia.modelo`, las
  claves desconocidas y los valores inválidos, y deja el YAML intacto.
- El mensaje de valor inválido se extrae a un solo sitio, sin punto final, y la carga del YAML lo reutiliza con su
  texto de hoy, para que los dos caminos digan lo mismo.
- Al arrancar, la ventana carga el YAML (que sigue pudiendo impedir abrirla), lo combina con las preferencias, pasa
  cada aviso al log y a Registro, y se construye con la configuración efectiva, guardando también la del proyecto para
  las historias siguientes. El modelo de IA preferido y la CLI no cambian.
- Tests sin red de la lectura y la combinación, y verificación en la ventana real con un archivo de preferencias
  temporal.

Archivos del `/pair` (lista cerrada, la del diseño): `src/configuracion.py` (`CLAVE_AJUSTES`, `_mensaje_invalido`,
`AjustesLeidos`, `leer_ajustes`, `combinar`; `cargar_configuracion` solo para usar `_mensaje_invalido` con su texto de
hoy), `src/ui.py` (`main`; `AppTranscriptor.__init__` con `proyecto` y `avisos`), `tests/test_configuracion.py`. Si hace
falta otro, se para y se vuelve al diseño. El delta de spec (`docs/specs/configuracion.md`) y el resto de la
documentación los escribe `/cerrar`.

## Fuera de alcance

- Las demás historias del diseño 06: A2a (convertir y validar el formulario, `TOPES_PANEL`, `valor_desde_formulario`,
  `validar_formulario`, `resumen_errores`), A2b (`guardar_ajustes`, `restablecer_ajustes`, escritura atómica, que
  `guardar_modelo_preferido` use esa escritura), A3 (`guardar_formulario`, `claves_cambiadas`, `REQUIEREN_REINICIO`,
  `valores_laterales`), C0 (el hilo de la transcripción deja de leer `self.configuracion`), C1 y C2 (la vista
  «⚙ Configuración», `Ctrl+3`, Restablecer), D1 y D2 (grupo IA, `argumentos_asistente`, `_epoca_ia`, el modelo en el
  panel), B, E1 y E2 (estado y cierre de la sesión de Copilot).
- Escribir `preferencias.json` en esta historia: solo se lee. Escribir `config/settings.yaml` nunca.
- Que la CLI lea las preferencias (decisión de producto 4); `docs/specs/cli.md` no cambia.
- Aplicar a las preferencias los topes del panel o las comprobaciones extra de `historial.ruta` y del dominio
  Enterprise: llegan con A2a (ver «Supuestos», 4).
- Endurecer la validación del YAML (rechazar `.nan`, topes).
- Cambiar `leer_modelo_preferido`, `modelo_ia_efectivo` o el formato de `modelo_ia`.
- Mostrar los avisos en la vista Configuración (CUJ 5): la vista llega con C1.

## Sugerencias

- `_leer_preferencias` y `leer_ajustes` leen el mismo archivo con criterios distintos (la primera trata `OSError` como
  JSON inválido). No hace falta unificarlas para los criterios; A2b, que reescribe la escritura, es buen momento.
- Para no duplicar cada aviso en la consola (`main` lo pasa a `log.warning` y `_log` vuelve a escribirlo con
  `log.info`), el `/pair` puede escribir en Registro sin repetir en el log, si cabe sin salir de la lista de archivos.
  No es necesario para los criterios.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es que una preferencia escrita a mano o un archivo a medio escribir impida abrir la
   ventana o, peor, haga que se escriba `config/settings.yaml`. Los criterios 2 y 3 cubren lo primero y el criterio 1
   comprueba que el YAML no cambia.
2. **Marcas.** Los tres criterios son `[NUEVO]`: hoy `preferencias.json` solo aporta `modelo_ia` y no existe
   ninguna configuración guardada que gane al YAML. Dos comportamientos de `docs/specs/configuracion.md` siguen
   siendo ciertos y no se marcan, pero `/cerrar` debe matizarlos: «Configuración del proyecto desde cualquier carpeta»
   (la ventana usa la configuración del proyecto, ahora combinada con las preferencias) y «Modelo de IA elegido en la
   ventana» (un archivo ilegible se sigue tratando «sin error», pero ahora deja un aviso en Registro). «Configuración
   con errores» no cambia: el YAML se carga antes de combinar y sus errores siguen cerrando la app.
3. **NaN no prueba `math.isfinite`.** El criterio 2 del diseño usa `transcripcion.temperature: NaN`, pero esa clave
   ya rechaza `nan` sin `isfinite` (`_es_numero_no_negativo`: `nan >= 0` es falso, `src/configuracion.py:54`). Las
   claves validadas con `_es_numero` (`compression_ratio_threshold`, `logprob_threshold`, `no_speech_threshold`,
   `src/configuracion.py:86-88`) sí aceptarían `nan` o `inf`. Para que el test falle sin `isfinite`, se añade el caso
   `compression_ratio_threshold: Infinity` (Python lee `NaN` e `Infinity` con `json.loads`; comprobado). Se mantiene
   el NaN del diseño y su recuento de cinco avisos.
4. **Sin topes en A1.** El diseño dice que «los topes y `math.isfinite` solo valen en el panel y en las preferencias»,
   pero el pseudocódigo de `combinar` («Plan técnico», 1) solo aplica `isfinite` y la validación de `_tabla()`, y el
   mensaje esperado del criterio 2 es el del YAML («un número entero mayor que 0»). Esta historia sigue el
   pseudocódigo. Consecuencia: hasta A2a (y, si el diseño lo quiere, más allá), un `preferencias.json` escrito a mano
   puede fijar `historial.ruta` dentro del repo o un dominio Enterprise con esquema; solo el formulario los rechazará.
   Si `combinar` debe aplicar `TOPES_PANEL`, lo decide A2a.
5. **El caso `OSError`.** El diseño define su aviso y que no marca `ilegible`, pero su lista de tests no lo cubre; se
   añade como cuarto caso del test parametrizado, apuntando `RUTA_PREFERENCIAS` a una carpeta (`IsADirectoryError`).
   `FileNotFoundError` también es un `OSError` y debe seguir significando «no existe», sin aviso.
6. **Dónde se ven los avisos.** Según el plan del diseño, en la consola (`log.warning` desde `main`) y en Registro
   (`_log` tras `_construir_ui`). Con un archivo no JSON también sale en la consola el aviso de hoy de
   `_leer_preferencias` («no son un JSON válido; se ignoran»), porque `leer_modelo_preferido` no cambia; en Registro
   hay uno solo.
7. **`ilegible` no tiene consumidor en A1**: lo usará A2b para decidir si reemplazar el archivo. Se prueba ya porque el
   diseño lo fija aquí.
8. **Líneas.** El diseño cita el commit `3c79616`; hoy `src/ui.py` inicializa las variables de control en
   `AppTranscriptor.__init__` (`src/ui.py:158-167`), construye en `:169`, y `main` está en `:1284-1298`.
   `src/configuracion.py`: `RUTA_PREFERENCIAS` `:20`, `_tabla` `:69-99`, `cargar_configuracion` `:114-137` (mensaje de
   valor inválido en `:135-136`), `_leer_preferencias` `:140-152`, `leer_modelo_preferido` `:155-164`,
   `guardar_modelo_preferido` `:167-172`, `modelo_ia_efectivo` `:175-177`. El aislamiento es `preferencias_aisladas`
   en `tests/conftest.py`. Manda el nombre de la función si se mueven.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa (370 tests). Code review: revisión del
orquestador, listo para commit. El orquestador añadió `test_preferencias_con_anidamiento_extremo_no_impiden_abrir` y
capturó `RecursionError` en `leer_ajustes`: un JSON con anidamiento extremo ya no impide abrir la ventana. Delta de spec:
`docs/specs/configuracion.md`, comportamiento nuevo «Preferencias del usuario al abrir la ventana», y matices en «Configuración
del proyecto desde cualquier carpeta» y «Modelo de IA elegido en la ventana», con `Origen` en esta historia.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Un ajuste guardado gana al YAML sin tocarlo; sin preferencias, la ventana usa el YAML sin avisos | Sin preferencias: `tests/test_configuracion.py:304`. Gana al YAML y el YAML conserva contenido y `st_mtime_ns`: `:319`. Verificación en la ventana (1). Implementación: `src/configuracion.py:194` (`leer_ajustes`), `:223` (`combinar`), `src/ui.py:1303` (`main`) | cumple (tests y verificación). Pendiente aceptado: «la CLI sigue usando txt» sin test ni verificación (ver Pendientes) |
| 2 | [NUEVO] | Ajustes inválidos, no finitos, desconocidos, `ia.modelo` dentro de `configuracion` o secciones que no son objetos: toman el valor del YAML y dan aviso con el texto exacto | Cinco entradas, cinco avisos con sus textos: `tests/test_configuracion.py:341`. Infinito en clave sin tope: `:367`. Verificación en la ventana (2). Implementación: `src/configuracion.py:223` (`combinar`), `:190` (`_mensaje_invalido`) | cumple (tests y verificación) |
| 3 | [NUEVO] | Archivo que no es JSON, no es un objeto, tiene `configuracion` que no es un objeto o no se puede leer: la ventana abre con el YAML y un aviso | Parametrizado (texto no JSON, lista, `"configuracion": 3`, carpeta): `tests/test_configuracion.py:386-387`. Anidamiento extremo: `:418`. Verificación en la ventana (3). Implementación: `src/configuracion.py:194` | cumple (tests y verificación). Pendiente aceptado: «un YAML inválido sigue impidiendo abrir la ventana» sin test ni verificación (ver Pendientes) |

**Verificación (2026-11-22):** el orquestador comprobó la ventana real con `RUTA_PREFERENCIAS` apuntando a archivos temporales,
sin tocar las preferencias reales:

1. Con `{"configuracion": {"salida": {"formato": "srt", "incluir_timestamps": false}}}`, la ventana abre con formato `srt` y
   sin marcas de tiempo, sin avisos.
2. Con `beam_size: "cinco"`, `idioma: "en"`, `audio.sample_rate` e `ia.modelo`, se aplica el idioma inglés, `beam_size` sigue
   en 5 y Registro muestra tres avisos «En <ruta>, …».
3. Con un archivo que no es JSON, la ventana abre con los valores del YAML y un solo aviso «Las preferencias <ruta> no son un
   JSON válido; …».

En los tres casos `config/settings.yaml` no cambió y las preferencias reales del usuario no se tocaron. El caso de cinco avisos
con `transcripcion.temperature: NaN` y `salida: 3` no se hizo en la ventana: lo cubre el test `:341`.

**Pendientes aceptados:**

- Cada aviso aparece dos veces en la consola: `WARNING` de `main` e `INFO` de `_log`.
- `configuracion_proyecto` todavía no lo usa nadie; lo leerán las historias siguientes del diseño 06.
- Los topes del panel llegan con A2a. Hasta entonces, un `preferencias.json` escrito a mano puede fijar `historial.ruta` dentro
  del repo o un dominio Enterprise con esquema (Supuesto 4).
- Dos incisos sin test ni verificación manual: «la CLI sigue usando `txt`» (`src/main.py` no cambia en este cierre) y «un YAML
  inválido sigue impidiendo abrir la ventana» (el camino de `main` no cambia: `src/ui.py:1296-1299`).
