# 20 · Componer el guardado y los valores laterales sin ventana

> Origen: `BACKLOG.md`, «Backlog» #5 (panel de configuración, carril L), cuarta de sus historias — Diseño:
> docs/disenos/06-panel-de-configuracion.md §Historia A3 (con «Plan técnico», 3 y el pseudocódigo de
> `guardar_configuracion` y `aplicar_guardado` del 5; «Decisiones tomadas», en especial la de producto 3 y las
> técnicas 2 y 5; «Revisión (2026-11-22)», fila «Más lógica probable sin ventana» y la desviación «`claves_cambiadas` y
> `REQUIEREN_REINICIO` van en una historia nueva, A3») — carril S. Reglas de oro 3, 5, 7 y 9 de `AGENTS.md`. Refinada
> con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Parte del estado que dejan la historia 17
> (A1, hecha: `leer_ajustes`, `combinar`), la 18 (A2a, en cierre: `validar_formulario`, `resumen_errores`) y la 19
> (A2b, aprobada y **aún sin implementar**: `guardar_ajustes`); C1 y C2 se apoyan en esta.

## Historia

Como usuario de la ventana, quiero que pulsar «Guardar» en el futuro panel de configuración me diga en una línea si se
guardó, por qué no o si algo pide reiniciar, y que en el panel lateral cambien solo los controles cuyos valores por
defecto acabo de cambiar, para no perder lo que elegí a mano para esta transcripción ni quedarme con un estado a medias
si el disco falla.

Historia **interna**: no hay vista todavía; el pie de la vista, los diálogos y el refresco del panel lateral llegan con
`guardar_configuracion` y `aplicar_guardado` en C1 (y Restablecer en C2). Aquí solo se compone el resultado del
guardado sin Tk y se mueven los ayudantes de idioma a un módulo sin Tk; el selector de idioma de la ventana no cambia.

## Criterios de aceptación

- [ ] [NUEVO] Dado un YAML en `tmp_path` y un `preferencias.json` con `{"x": 1}`, cuando se llama a
  `guardar_formulario` con `transcripcion.beam_size` = «cinco» y `salida.formato` = «srt», entonces el resultado trae
  `efectiva` y `modelo_preferido` en `None`, `cambiadas` vacío, `errores` con solo `transcripcion.beam_size` (el texto
  de A2a), `mensaje` «No se guardó nada: corrige 1 valor.», y `preferencias.json` conserva sus bytes (el formato
  válido tampoco se guarda). Y si, con un formulario válido, la escritura falla con `OSError` (permiso denegado),
  `errores` está vacío, `efectiva` es `None`, `cambiadas` vacío, `mensaje` es «No se pudo guardar la configuración:
  Permission denied.» y el archivo no cambia.
- [ ] [NUEVO] Dado un YAML con `salida.formato: "txt"` y `ia.modelo: "gpt-4.1"`, y un `preferencias.json` que no es
  JSON (`{`), cuya lectura al abrir dio el aviso de archivo ilegible, cuando se guarda un formulario válido que pone
  `salida.formato` = «srt» e `historial.ruta` = una ruta absoluta en `tmp_path`, con `anterior` = la efectiva de antes
  y sin modelo de IA, entonces `efectiva` tiene `srt` y la ruta nueva, `cambiadas` es exactamente
  `{("salida", "formato"), ("historial", "ruta")}`, `avisos` está vacío (el aviso de archivo ilegible desaparece),
  `modelo_preferido` es `None` y `mensaje` es «Configuración guardada · el historial nuevo se abrirá al reiniciar la
  app»; si solo cambia el formato, `mensaje` es «Configuración guardada». Si además se guarda con
  `modelo_ia="claude-sonnet-5.5"` y `preferido_anterior=None`, `modelo_preferido` es `"claude-sonnet-5.5"` y
  `("ia", "modelo")` está en `cambiadas`; volver a guardar lo mismo da `cambiadas` vacío. `config/settings.yaml` no
  cambia en ningún caso.
- [ ] [NUEVO] Dado `cambiadas` con `transcripcion.idioma`, `salida.formato` y `transcripcion.beam_size`, y una
  configuración con `idioma` `nl` y `formato` `srt`, cuando se piden los valores laterales, entonces son exactamente
  `var_idioma` «nl», `opciones_idioma` = la lista del selector con «nl» al final y `var_formato` «srt», y nada para
  `beam_size` (no tiene control lateral) ni para claves que no están en `cambiadas`; con `idioma` `es`, `var_idioma`
  es «Español» y las opciones no incluyen «es». Los ayudantes de idioma viven en un módulo sin Tk y `from src.ui
  import IDIOMAS_DISPONIBLES, codigo_de_idioma, opciones_de_idioma` sigue funcionando.

Cómo se verifican — **solo con tests, sin red, sin ventana y sin esperas**, en `tests/test_configuracion.py`
(`RUTA_PREFERENCIAS` aislada por el fixture autouse `preferencias_aisladas` de `tests/conftest.py`; el proyecto sale de
`cargar_configuracion` de un YAML en `tmp_path`, y `anterior` de `combinar(proyecto, leer_ajustes())`; los archivos se
comparan por sus bytes y el YAML también por `st_mtime_ns`). El fallo de escritura se simula con `monkeypatch` sobre
`configuracion.guardar_ajustes` para que lance `PermissionError(errno.EACCES, "Permission denied")` (A2b ya prueba la
atomicidad; aquí solo importa que `guardar_formulario` no devuelva estado). Una ruta en `tmp_path` pasa la regla 8 y
la comprobación de disco de A2a sin crear carpetas.

- `test_guardar_formulario_con_errores_no_escribe` (criterio 1).
- `test_guardar_formulario_con_fallo_de_escritura_no_devuelve_efectiva` (criterio 1).
- `test_guardar_formulario_devuelve_cambiadas_avisos_y_mensaje` (criterio 2: el caso del archivo ilegible con formato
  y ruta, el de solo formato y el del modelo de IA con su repetición).
- `test_claves_cambiadas_solo_las_de_la_tabla` (criterio 2): dos configuraciones que difieren en `salida.formato` y en
  una clave ajena a `_tabla()` (`salida.extra`, o una sección `audio`) dan solo `{("salida", "formato")}`; dos
  iguales, el conjunto vacío.
- `test_valores_laterales_solo_de_las_claves_cambiadas` (criterio 3), importando los ayudantes de idioma de
  `src.idiomas`.
- `tests/test_importaciones.py`: `src.idiomas` añadido a `MODULOS` (antes de `src.configuracion`, que pasa a
  importarlo) y a `SIN_TK`; `test_ningun_modulo_carga_faster_whisper_al_importarse` comprueba que no carga `tkinter`
  ni `customtkinter` (criterio 3).
- Siguen pasando **sin cambios** `tests/test_ui.py::test_idiomas_disponibles`,
  `test_idioma_configurado_fuera_del_selector_se_ofrece_y_se_usa_tal_cual`,
  `test_idioma_del_selector_se_muestra_con_su_nombre` y el de «Auto-detectar», que importan de `src.ui` (criterio 3),
  y todos los de las historias 17, 18 y 19.

Paso rojo: con el código de hoy, los tests de `tests/test_configuracion.py` fallan porque `guardar_formulario`,
`claves_cambiadas`, `valores_laterales` y `src.idiomas` no existen, y `test_ningun_modulo_carga_faster_whisper_al_importarse`
falla al importar `src.idiomas`.

## Plan

- Un módulo de idiomas sin Tk con la tabla de idiomas, las opciones del selector, el código de una opción y el nombre
  de un código (lo que hoy hace a mano el constructor de la ventana); la ventana los importa de ahí y los sigue
  exportando con el mismo nombre, y su constructor usa el nombre de un código para el idioma inicial.
- Qué claves de la tabla de configuración difieren entre dos configuraciones, y cuáles piden reiniciar
  (`historial.ruta`).
- Componer el guardado: validar (si hay errores, devolverlos con su resumen sin escribir); escribir con el guardado
  atómico de A2b (si falla, devolver solo el mensaje); releer y combinar las preferencias como al abrir; calcular las
  claves cambiadas, más el modelo de IA si cambió el efectivo; y el mensaje del pie, con la nota de reinicio si toca.
- Traducir las claves cambiadas con control lateral (modelo de Whisper, dispositivo, precisión, idioma con sus
  opciones, formato y marcas de tiempo) a los valores de las variables del panel lateral, sin tocar Tk.

Archivos del `/pair` (lista cerrada, la del diseño): `src/idiomas.py` (crear: `IDIOMAS_DISPONIBLES`,
`opciones_de_idioma`, `codigo_de_idioma`, `nombre_de_idioma`), `src/ui.py` (importa los tres nombres de `src.idiomas`
en lugar de definirlos y usa `nombre_de_idioma` en `AppTranscriptor.__init__`), `src/configuracion.py`
(`claves_cambiadas`, `REQUIEREN_REINICIO`, `ResultadoGuardado`, `guardar_formulario`, `valores_laterales`),
`tests/test_configuracion.py`, `tests/test_importaciones.py`. Si hace falta otro, se para y se vuelve al diseño. El
delta de spec y el resto de la documentación (`EGM.md`, `src/EGM.md`, tabla de `AGENTS.md`) los escribe `/cerrar`.

## Fuera de alcance

- `restablecer_formulario` y su mensaje «Se restablecieron los valores de config/settings.yaml»: el diseño los pone en
  **C2** («Plan técnico», 3: `# historia C2`; lista cerrada y tests de C2), no en A3.
- `guardar_configuracion`, `aplicar_guardado`, aplicar los valores laterales a las variables Tk, refrescar
  `var_modelo_ia`, `_modelo_preferido`, olvidar el asistente, `_epoca_ia`, `motivo_para_no_guardar` y cualquier diálogo
  (C1, C2, D1, D2).
- El selector de modelo de IA del lateral: `("ia", "modelo")` puede estar en `cambiadas`, pero `valores_laterales` no
  lo traduce (lo aplica `aplicar_guardado` en C2 con `modelo_preferido`).
- Cambiar los otros usos de `IDIOMAS_DISPONIBLES.get(...)` en `src/ui.py` (el idioma detectado en
  `_finalizar_ok`, `:724`, y en `cargar_desde_historial`, `:1155`): el diseño solo pide `nombre_de_idioma` en
  `__init__`; siguen funcionando porque `src.ui` sigue teniendo el nombre.
- Reabrir el historial al cambiar `historial.ruta` (alternativa E): solo se avisa en el mensaje.
- Cambiar `guardar_ajustes`, `validar_formulario`, `combinar` o sus mensajes.

## Sugerencias (a tu criterio)

- Para «No se pudo guardar la configuración: <motivo>.» el diseño usa `motivo_de_error(e)`, que vive en
  `src/persistencia.py` (`:17-24`). Importarlo arriba en `src/configuracion.py` haría que cargar la configuración
  cargue `src.utils` y la librería `ffmpeg`. Dos salidas igual de simples: importarlo dentro de `guardar_formulario`
  (como ya se hace con `copilot` en `validar_formulario`), o usar `e.strerror or str(e)`, que es lo que ya hace
  `leer_ajustes` (`src/configuracion.py:227`). Cualquiera da «Permission denied» en el criterio 1.
- `ResultadoGuardado` puede ser `@dataclass(frozen=True)` como `AjustesLeidos`: la vista solo lo lee.
- En `valores_laterales`, una tabla `(sección, clave) → nombre de variable` para las cinco claves directas y un caso
  aparte para el idioma deja la función en pocas líneas.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es que la ventana aplique un guardado que no se escribió (el usuario cree que lo guardó y
   al reiniciar no está), o que cambie un control lateral que el usuario había ajustado a mano para esta
   transcripción. Lo cubren el criterio 1 (`efectiva` `None` en los dos fallos) y el 3 (solo claves cambiadas).
2. **Firma.** Se sigue la del diseño: `guardar_formulario(proyecto, anterior, valores_widget, modelo_ia=None,
   preferido_anterior=None) -> ResultadoGuardado`, con `ResultadoGuardado(errores, efectiva, modelo_preferido, avisos,
   cambiadas, mensaje)` en ese orden. (El encargo la citaba con `preferido_anterior` antes de los valores; el
   pseudocódigo de `guardar_configuracion` en «Plan técnico», 5, la llama en el orden del diseño.)
3. **Dependencia de A2b (sin implementar).** Se toma de la historia 19: `guardar_ajustes(proyecto, valores,
   modelo_ia=None) -> list[str]` devuelve los avisos de descarte (un solo aviso o ninguno), lanza `OSError` sin tocar
   el archivo ni dejar el temporal, reemplaza sin aviso un archivo que no es JSON, quita `modelo_ia` si es el del YAML
   y da `ValueError` con un modelo excluido (que aquí no llega: `validar_formulario` ya lo rechaza, regla 7). Si A2b se
   cierra con otra firma, esta historia sigue a la que quede. Los `avisos` del resultado son los descartes de
   `guardar_ajustes` seguidos de los de `combinar` tras releer.
4. **`cambiadas` y el modelo.** `claves_cambiadas(anterior, efectiva)` recorre solo `_tabla()` (incluida
   `ia.modelo`, que en la efectiva siempre es la del YAML porque nunca va en `configuracion`); se añade `("ia",
   "modelo")` si `modelo_ia_efectivo(anterior, preferido_anterior) != modelo_ia_efectivo(efectiva,
   leer_modelo_preferido())`. Con `modelo_ia=None` se conserva el `modelo_ia` que hubiera en el archivo, así que no
   cambia.
5. **`REQUIEREN_REINICIO`** es `frozenset({("historial", "ruta")})` y el sufijo del mensaje es literal
   «Configuración guardada · el historial nuevo se abrirá al reiniciar la app» (sin punto final, como en el diseño y
   en el criterio 2 de C2).
6. **Errores de validación.** Con errores no se llama a `guardar_ajustes` ni se lee el archivo; `errores` es el dict de
   `validar_formulario` tal cual (orden de entrada) y `avisos` va vacío.
7. **`valores_laterales` devuelve un dict** cuyas claves son los nombres de atributo de la ventana (`var_modelo` es el
   modelo de **Whisper**, `src/ui.py:162`; el de IA es `var_modelo_ia` y no está aquí) más `opciones_idioma` para el
   `combo_idioma` (`:275-277`). Para el idioma: `var_idioma` = `nombre_de_idioma(codigo)` y `opciones_idioma` =
   `opciones_de_idioma(codigo)`; `nombre_de_idioma(c)` = `IDIOMAS_DISPONIBLES.get(c, c)`, lo mismo que hoy hace
   `AppTranscriptor.__init__` (`src/ui.py:163`).
8. **Dirección de las importaciones.** `src.configuracion` importa `src.idiomas` (para `valores_laterales`);
   `src.idiomas` no importa nada del proyecto. `src.ui` importa de `src.idiomas` y deja de definir los tres nombres.
9. **Marcas.** Los tres criterios son `[NUEVO]`: hoy nada compone un guardado ni calcula valores laterales
   (`docs/specs/configuracion.md` no tiene comportamiento de guardado desde un formulario). Mover los ayudantes de
   idioma no cambia nada observable: la spec «idioma configurado fuera del selector» de
   `docs/specs/transcripcion.md` sigue igual.
10. **Líneas** (commit `0ebd42e` más la A2a sin commitear en la copia de trabajo; manda el nombre si se mueven, y A2b
    las moverá): `src/configuracion.py`: `leer_modelo_preferido` `:176-185`, `modelo_ia_efectivo` `:196-198`,
    `AjustesLeidos` `:201-205`, `leer_ajustes` `:221-247`, `combinar` `:250-268`, `validar_formulario` `:340-364`,
    `resumen_errores` `:367-369`; `src/ui.py`: importación de `src.configuracion` `:28-29`, `IDIOMAS_DISPONIBLES`
    `:43-56`, `opciones_de_idioma` `:59-65`, `codigo_de_idioma` `:68-70`, `AppTranscriptor.__init__` `:115` (variables
    del lateral `:161-167`), `_codigo_idioma` `:610-611`; `tests/test_importaciones.py`: `MODULOS` `:15-19`, `SIN_TK`
    `:22`; `tests/test_ui.py`: importaciones `:5-10` y `:40`, `:47`, `:55`.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa (417 tests). Code review: revisión del orquestador, listo para commit. Delta de spec: ninguno (historia interna: no hay vista ni comportamiento observable nuevo; el guardado se verá con la vista de C1).

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | `guardar_formulario` con errores devuelve el resumen del pie y no escribe; con un `OSError` al guardar devuelve solo el mensaje, sin `efectiva` ni cambios | Tests: `tests/test_configuracion.py:942` (errores), `:967` (fallo de escritura). Implementación: `src/configuracion.py:481`, `:486` (errores), `:490` (`OSError`) | cumple (tests) |
| 2 | [NUEVO] | Tras guardar, `cambiadas` trae solo las claves de la tabla que cambiaron (con `ia.modelo` si cambió el efectivo), los avisos van tras releer, y el mensaje pide reiniciar si cambia `historial.ruta` | Tests: `tests/test_configuracion.py:890` (`claves_cambiadas`), `:993` (formato y ruta, solo formato, modelo y repetición). Implementación: `src/configuracion.py:347`, `:467` (`REQUIEREN_REINICIO`), `:481`, `:500` | cumple (tests) |
| 3 | [NUEVO] | `valores_laterales` devuelve solo los controles de las claves cambiadas, con las opciones de idioma del código configurado; los ayudantes de idioma viven en `src/idiomas.py` sin Tk y `src.ui` los sigue exportando | Tests: `tests/test_configuracion.py:907`; `tests/test_importaciones.py:55` (sin `tkinter` ni `customtkinter` en `src.idiomas`); `tests/test_ui.py:19`, `:39`, `:46` (imports desde `src.ui`). Implementación: `src/configuracion.py:352`, `src/idiomas.py`, `src/ui.py:27-28` | cumple (tests) |

**Verificación (2026-11-22):** `./venv/bin/python -m pytest -q` pasa (417). Tras mover los ayudantes de idioma a `src/idiomas.py`, el orquestador comprobó la ventana real: abre igual con preferencias (formato `srt` sin marcas de tiempo; idioma inglés desde preferencias; tres avisos con preferencias inválidas). La vista de configuración aún no existe, así que el guardado no se ve en la ventana todavía.

**Pendientes aceptados:**

- Un `OSError` sin `strerror` ni texto daría «No se pudo guardar la configuración: .» (`src/configuracion.py:491`): el mensaje usa `e.strerror or str(e)`, como `leer_ajustes`. Sin test; se cubre al hacer la vista (C1).
- Los helpers de test `_proyecto_19` y `_ruta_preferencias_19` (`tests/test_configuracion.py:618`, `:626`) conservan el nombre de la historia 19 y se reutilizan aquí a propósito.
