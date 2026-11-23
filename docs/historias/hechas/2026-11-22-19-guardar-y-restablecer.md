# 19 · Guardar y restablecer las preferencias en una escritura atómica

> Origen: `BACKLOG.md`, «Backlog» #5 (panel de configuración, carril L), tercera de sus historias — Diseño:
> docs/disenos/06-panel-de-configuracion.md §Historia A2b (con «Plan técnico», 2; «Decisiones tomadas», en especial
> la de producto 5 y las técnicas 1, 2, 3 y 5; «Riesgos» 1 y 2, y «Revisión (2026-11-22)») — carril S. Reglas de oro
> 3, 5, 7 y 8 de `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Parte
> del estado que dejan la historia 17 (A1, hecha: `leer_ajustes`, `combinar`, `AjustesLeidos`) y la 18 (A2a, en
> curso: las reglas de validez de las preferencias); A3 se apoya en esta.

## Historia

Como usuario de la ventana, quiero que guardar o restablecer mis valores por defecto escriba el archivo de
preferencias de una sola vez, sin dejarlo a medias ni borrar lo que ya tenía si algo falla, para no perder mis
preferencias (ni el modelo de IA elegido) por un disco lleno, un permiso o un archivo corrupto.

Historia **interna**: no hay vista todavía; «Guardar» y «Restablecer valores del proyecto» llegan con la vista en C1
y C2 (y el mensaje «No se pudo guardar la configuración: <motivo>.» con A3). Lo único que el usuario ya usa hoy es el
selector de modelo de IA del panel lateral (criterio 3), cuyo comportamiento visible no cambia.

## Criterios de aceptación

- [ ] [NUEVO] Dado un YAML con `salida.formato: "txt"`, `transcripcion.beam_size: 5`, `transcripcion.best_of: 5` e
  `ia.modelo: "gpt-4.1"`, y un `preferencias.json` con `{"modelo_ia": "gpt-4.1", "x": 1, "configuracion":
  {"transcripcion": {"best_of": 3, "beam_size": "x"}, "audio": {"a": 1}}}`, cuando se guardan `salida.formato` =
  `"srt"` y `transcripcion.beam_size` = `5` sin modelo de IA, entonces el archivo queda `{"modelo_ia": "gpt-4.1", "x":
  1, "configuracion": {"transcripcion": {"best_of": 3}, "salida": {"formato": "srt"}}}`, se devuelve un único aviso
  «Se descartaron de <ruta> claves que no sirven: `transcripcion.beam_size`, `audio.a`.» y no queda
  `preferencias.json.tmp`. Si después se guardan `salida.formato` = `"txt"` y `transcripcion.best_of` = `5` (los del
  YAML), la clave `configuracion` desaparece del archivo (no queda `{}`). Guardar con `modelo_ia="claude-sonnet-5.5"`
  escribe `modelo_ia` y `configuracion` con **una sola** llamada a `os.replace`; guardar después con el modelo del YAML
  (`"gpt-4.1"`) quita `modelo_ia`; y un modelo de una familia excluida (`"Mistral-Large-3"`) es un error de
  programación (`ValueError`) que no escribe nada (regla 7).
- [ ] [NUEVO] Dado un `preferencias.json` con `modelo_ia`, `configuracion` y otra clave `"x": 1`, cuando se
  restablece, entonces el archivo queda `{"x": 1}`, en una sola escritura. Y tanto al guardar como al restablecer:
  si leer el archivo da `OSError` (por ejemplo, permiso denegado), si falla la escritura del temporal a medias (disco
  lleno) o si falla el renombrado, se lanza ese `OSError`, `preferencias.json` conserva exactamente su contenido
  anterior y no queda `preferencias.json.tmp`; en cambio, si el archivo no es JSON (`{`) o su JSON no es un objeto
  (`[]`), se reemplaza: guardar `salida.formato` = `"srt"` lo deja en `{"configuracion": {"salida": {"formato":
  "srt"}}}` sin aviso de descarte.
- [ ] [MODIFICA: configuracion › Modelo de IA elegido en la ventana] Dado un `preferencias.json` con `{"x": 1,
  "configuracion": {"salida": {"formato": "srt"}}}`, cuando se elige `claude-haiku-5.5` en el selector lateral,
  entonces el archivo queda con esas dos claves intactas y `"modelo_ia": "claude-haiku-5.5"`, escrito con temporal y
  renombrado (sin `preferencias.json.tmp` al terminar); si leer el archivo da `OSError` o falla la escritura, el
  archivo no cambia, no queda el temporal y la ventana usa el modelo elegido y anota en Registro, como hoy, «Modelo de
  IA: claude-haiku-5.5 (solo para esta sesión; no se pudo guardar en preferencias.json)». Un archivo que no es JSON se
  sigue reemplazando por `{"modelo_ia": …}`. (antes: `guardar_modelo_preferido` leía con `_leer_preferencias`, que
  trata un `OSError` de lectura igual que un JSON inválido y devuelve `{}`, así que reescribía el archivo solo con
  `modelo_ia` y perdía las demás claves; y escribía directamente con `Path.write_text`, sin temporal: un fallo a mitad
  dejaba el archivo truncado.)

Cómo se verifican — **solo con tests, sin red, sin ventana y sin esperas**, en `tests/test_configuracion.py`
(`RUTA_PREFERENCIAS` aislada por el fixture autouse `preferencias_aisladas` de `tests/conftest.py`; el proyecto es un
dict construido en el test o `cargar_configuracion` de un YAML en `tmp_path`; los archivos se comparan por su
contenido en bytes antes y después). Dobles de fallo, todos con `monkeypatch`:

- **Lectura:** se parchea `Path.read_text` para que, solo con `RUTA_PREFERENCIAS`, lance `PermissionError`. (No vale
  `chmod 000`: no falla si los tests corren como root.)
- **Escritura del temporal:** se parchea `Path.write_text` para que, solo con `preferencias.json.tmp`, escriba la mitad
  del texto y lance `OSError(errno.ENOSPC, …)`.
- **Renombrado:** se parchea `configuracion.os.replace` para que lance `OSError`; para contar escrituras, con un
  envoltorio que anota cada llamada y llama al original.

Tests:

- `test_guardar_ajustes_solo_diferencias_y_descarta_lo_que_no_sirve`: el primer guardado del criterio 1, con el
  archivo resultante, el aviso literal y la ausencia del temporal (criterio 1).
- `test_guardar_ajustes_quita_configuracion_vacia`: el segundo guardado del criterio 1; `"configuracion" not in`
  el archivo y `x` y `modelo_ia` siguen (criterio 1).
- `test_guardar_ajustes_con_modelo_en_una_sola_escritura`: con el envoltorio de `os.replace`, exactamente una llamada
  y el archivo con `modelo_ia` y `configuracion` (criterio 1).
- `test_guardar_el_modelo_del_yaml_quita_modelo_ia` (criterio 1).
- `test_guardar_ajustes_rechaza_modelo_excluido_sin_escribir` (añadido por esta historia, ver «Supuestos», 6):
  `ValueError`, el archivo no cambia y `os.replace` no se llama (criterio 1).
- `test_restablecer_borra_ajustes_y_modelo_y_conserva_lo_demas`: queda `{"x": 1}` con una llamada a `os.replace`
  (criterio 2).
- `test_fallo_de_lectura_no_borra_las_preferencias`, parametrizado con `guardar_ajustes`, `restablecer_ajustes` y
  `guardar_modelo_preferido`: con el doble de lectura, se propaga el `OSError`, el archivo no cambia, `os.replace` no
  se llama y no hay temporal (criterios 2 y 3).
- `test_fallo_al_escribir_no_toca_el_archivo_ni_deja_temporal` (añadido por esta historia, ver «Supuestos», 2),
  parametrizado con las tres funciones y los dos fallos (temporal a medias y renombrado): se propaga el `OSError`, el
  archivo conserva sus bytes y no existe `preferencias.json.tmp` (criterios 2 y 3).
- `test_json_invalido_se_reemplaza_al_guardar`, parametrizado con `{` y `[]`: el archivo queda con solo lo guardado
  y la lista de avisos está vacía (criterio 2).
- `test_guardar_modelo_preferido_no_reescribe_si_no_puede_leer`: el caso del criterio 3 con el doble de lectura; el
  archivo con `x` y `configuracion` sigue igual (criterio 3). La parte de la ventana («solo para esta sesión») no
  cambia de código: `AppTranscriptor._al_cambiar_modelo_ia` (`src/ui.py:1016`) ya captura `OSError`.
- Siguen pasando sin cambios `test_guardar_y_leer_el_modelo_preferido`,
  `test_guardar_el_modelo_conserva_otras_preferencias`, `test_guardar_el_modelo_crea_la_carpeta`,
  `test_preferencias_corruptas_no_lanzan` y los de las historias 17 y 18.

Paso rojo: con el código de hoy, los tests de `guardar_ajustes` y `restablecer_ajustes` fallan porque no existen, y
los casos de `guardar_modelo_preferido` de los dos tests de fallo fallan porque hoy reescribe el archivo (lectura
tratada como vacía; escritura directa que no pasa por el temporal ni por `os.replace`).

## Plan

- Un lector «para escribir» del archivo de preferencias, estricto donde el de hoy es tolerante: si no existe parte de
  un objeto vacío; si no es JSON, es JSON demasiado anidado o no es un objeto, también (se reemplazará); si el sistema
  no deja leerlo, propaga el error para que nadie escriba encima.
- Un escritor atómico único: crea la carpeta, escribe el JSON entero (mismo formato que hoy) en un temporal junto al
  archivo y lo renombra encima; si algo falla, borra el temporal y propaga el error sin tocar el archivo anterior.
- Guardar parte de lo leído, conserva las claves ajenas y `modelo_ia`, se queda con las claves previas que siguen
  siendo válidas con las mismas reglas que la lectura al abrir (avisando de las que descarta), pone encima las nuevas,
  quita las que valen igual que el YAML, quita `configuracion` si queda vacía, resuelve `modelo_ia` (ninguno, igual
  al YAML, otro; un modelo excluido es un error de programación) y escribe una vez.
- Restablecer lee igual, quita `configuracion` y `modelo_ia`, conserva lo demás y escribe una vez.
- El guardado del selector lateral pasa a usar el mismo lector y el mismo escritor; la ventana no cambia, porque ya
  trata su `OSError` como «solo para esta sesión».

Archivos del `/pair` (lista cerrada, la del diseño): `src/configuracion.py` (`guardar_ajustes`, `restablecer_ajustes`,
`_leer_para_escribir`, `_escribir_preferencias`; `guardar_modelo_preferido` las usa; `import os` para
`os.replace`), `tests/test_configuracion.py`. Si hace falta otro, se para y se vuelve al diseño. El delta de spec
(`docs/specs/configuracion.md`) y el resto de la documentación los escribe `/cerrar`.

## Fuera de alcance

- Componer el guardado para la vista (`guardar_formulario`, `restablecer_formulario`, `ResultadoGuardado`,
  `claves_cambiadas`, `REQUIEREN_REINICIO`, `valores_laterales`: A3 y C2), el mensaje «No se pudo guardar la
  configuración: <motivo>.» y releer con `combinar` tras guardar (A3).
- La vista, los botones «Guardar» y «Restablecer valores del proyecto», aplicar el estado a la ventana solo tras una
  escritura correcta, olvidar `_modelo_preferido` o el asistente (C1, C2, D1, D2).
- Convertir y validar el formulario (`valor_desde_formulario`, `validar_formulario`, `TOPES_PANEL`: A2a).
  `guardar_ajustes` recibe valores ya convertidos y validados y no los vuelve a validar (salvo la regla 7 del modelo).
- Cambiar `_leer_preferencias`, `leer_modelo_preferido` (la lectura al abrir sigue tolerante) o `leer_ajustes`.
- `fsync` del temporal o de la carpeta, bloqueo entre dos ventanas abiertas (diseño, «Riesgos», 1: gana la última) y
  permisos especiales del archivo (no guarda secretos).
- Escribir `config/settings.yaml` (nunca) o que la CLI lea las preferencias (decisión de producto 4).

## Sugerencias (a tu criterio)

- Para «las mismas reglas que `combinar`» (paso 2 del pseudocódigo), reutilizar la comprobación que deje A2a (su
  sugerencia de un ayudante privado «¿qué falla en este valor?» sin la parte que mira el disco) en vez de copiarla: es
  la tercera vez que se necesita (al abrir, en el formulario y al guardar).
- Llamar a `os.replace` como atributo del módulo (`import os` y `os.replace(...)`, no `from os import replace`) y
  escribir el temporal con `Path.write_text`, como hoy: así los dobles de «Cómo se verifican» funcionan sin tocar
  `builtins.open`.
- Con `_leer_para_escribir` y el escritor en su sitio, `_leer_preferencias` solo queda para `leer_modelo_preferido`;
  unificar las lecturas no hace falta para los criterios.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es perder las preferencias que ya había (el modelo elegido o los ajustes) por un fallo
   pasajero o una escritura a medias. Lo cubren el criterio 2 (guardar y restablecer) y el 3 (selector lateral, que
   es lo único que el usuario ya usa).
2. **Limpieza del temporal al fallar.** El diseño fija temporal + `os.replace` y, en su criterio 1, que no quede
   `preferencias.json.tmp` tras guardar bien; no dice qué pasa con el temporal si la escritura falla. Se decide
   borrarlo (sin ocultar el error original) para que un fallo no deje basura que confunda al siguiente guardado, y se
   añade `test_fallo_al_escribir_no_toca_el_archivo_ni_deja_temporal`, que además es el que demuestra la atomicidad
   (el diseño solo cuenta las llamadas a `os.replace`). Si el temporal no se puede borrar, se propaga igualmente el
   error de la escritura.
3. **`guardar_modelo_preferido` usa el mismo ayudante** (decisión técnica 2 y última línea del pseudocódigo de
   `_escribir_preferencias`). Su comportamiento observable no cambia: sigue guardando la elección conservando las
   demás claves, sigue lanzando `OSError` si no puede, y la ventana sigue diciendo «solo para esta sesión»
   (`AppTranscriptor._al_cambiar_modelo_ia`, `src/ui.py:1016-1031`, captura `OSError` y no se toca). Lo único que
   cambia es que con un `OSError` de lectura ya no reescribe el archivo desde cero. No sanea `configuracion`: solo
   pone `modelo_ia`.
4. **Qué se reemplaza y qué no.** Igual que `leer_ajustes` marca `ilegible` (historia 17): JSON inválido, texto que
   no es UTF-8 (`UnicodeDecodeError` es `ValueError`), anidamiento extremo (`RecursionError`, capturado en
   `leer_ajustes` por el cierre de la 17) o un JSON que no es objeto → se parte de `{}`; `FileNotFoundError` → `{}`;
   cualquier otro `OSError` → se propaga. El supuesto 7 de la historia 17 decía que A2b usaría `ilegible`; el diseño
   no lo hace: `_leer_para_escribir` necesita el objeto entero (con `modelo_ia` y las claves ajenas), que
   `AjustesLeidos` no trae. `ilegible` queda para la vista (CUJ 5, C1).
5. **Texto y contenido del aviso de descarte.** «Se descartaron de <ruta> claves que no sirven: `a.b`, `c.d`.» (del
   diseño), un solo aviso con las claves en el orden del archivo, solo si hay alguna. Se nombran igual que las
   descarta `combinar`: una clave desconocida o con valor inválido por su `s.k`; `ia.modelo` dentro de
   `configuracion` como `ia.modelo`; una sección que no es objeto por su nombre (`salida`); y un `configuracion` que
   no es objeto como `configuracion`. Una clave inválida antes y que el formulario vuelve a enviar (`beam_size` en el
   criterio 1) se nombra igualmente: se descartó el valor viejo. Reemplazar un archivo ilegible no da aviso de
   descarte (el aviso de ilegible ya lo dio la lectura al abrir; A3 lo refresca).
6. **Regla 7 al guardar.** El pseudocódigo dice que un modelo de familia excluida da `ValueError` en
   `guardar_ajustes`, pero la lista de tests del diseño no lo cubre; se añade
   `test_guardar_ajustes_rechaza_modelo_excluido_sin_escribir`. La comprobación es antes de leer o escribir, con
   `copilot.familia_excluida` importada dentro de la función (como en A2a, para no cargar `httpx` al importar el
   módulo). Un `modelo_ia` vacío no llega aquí (el selector y el campo del panel no lo permiten); no se valida.
7. **Dependencia de A2a (en curso).** «Claves válidas con las mismas reglas que `combinar`» se toma tal como lo deja
   la historia 18: tabla de la configuración, `math.isfinite`, `TOPES_PANEL`, dominio como nombre de host y
   `historial.ruta` fuera del repo salvo `data/`, **sin** la comprobación de disco (su supuesto 1: así una carpeta de
   historial momentáneamente inaccesible no hace que guardar borre la preferencia). Si A2a se cierra con otras reglas,
   esta historia sigue a `combinar` tal como quede. Los ejemplos de los criterios no dependen de los topes:
   `beam_size: "x"` y `audio.a` se descartan con cualquiera de las dos versiones.
8. **Siempre una escritura.** Guardar o restablecer escriben aunque el resultado sea igual al archivo (o el archivo
   no existiera: restablecer sin archivo deja `{}`). Es lo más simple y lo que dice el diseño («una sola escritura
   atómica por acción»).
9. **Formato del archivo.** Se mantiene el de hoy (`json.dumps(..., ensure_ascii=False, indent=2)`, UTF-8). Las
   secciones nuevas se añaden al final de `configuracion`, por eso el criterio 1 compara por igualdad de objetos, no
   por texto.
10. **Marcas.** Criterios 1 y 2, `[NUEVO]`: hoy nada escribe `configuracion` ni restablece. Criterio 3, `[MODIFICA]`
    sobre «Modelo de IA elegido en la ventana» de `docs/specs/configuracion.md`, cuyo primer punto («se recuerda en
    `preferencias.json` con la clave `modelo_ia`») sigue siendo cierto; `/cerrar` debe añadir que no se pierden las
    demás preferencias si no se puede leer o escribir el archivo. El `(antes: …)` sale del código: `_leer_preferencias`
    (`src/configuracion.py:140-152`, `except (OSError, ValueError)` → `{}`) y `guardar_modelo_preferido`
    (`:167-172`, `RUTA_PREFERENCIAS.write_text`).
11. **Líneas** (commit `0ebd42e`; manda el nombre si se mueven, y A2a las moverá): `src/configuracion.py`:
    `RUTA_PREFERENCIAS` `:21`, `_tabla` `:70-100`, `_leer_preferencias` `:140-152`, `leer_modelo_preferido`
    `:155-164`, `guardar_modelo_preferido` `:167-172`, `modelo_ia_efectivo` `:175-177`, `AjustesLeidos` `:180-184`,
    `CLAVE_AJUSTES` `:187`, `_mensaje_invalido` `:190-191`, `leer_ajustes` `:194-220`, `combinar` `:223-241`; el
    módulo no importa `os` hoy. `src/ui.py`: importación `:29`, `_al_cambiar_modelo_ia` `:1016-1031`, `main` `:1290`.
    `tests/conftest.py`: `preferencias_aisladas` `:57-61`. `tests/test_configuracion.py`: tests de
    `guardar_modelo_preferido` `:230`, `:256`, `:270`.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa (412 tests). Code review: revisión del orquestador, listo para commit. Delta de spec: `docs/specs/configuracion.md`, en «Modelo de IA elegido en la ventana», con `Origen` en esta historia. «Guardar» y «Restablecer» del panel no están en la spec: llegan con la vista (C1 y C2).

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Guardar `salida.formato` y `transcripcion.beam_size` (solo diferencias, descarte con un único aviso, sin temporal), quitar `configuracion` si queda vacía, guardar con modelo en una sola escritura, quitar `modelo_ia` con el del YAML, y rechazar un modelo excluido sin escribir | Tests: `tests/test_configuracion.py:653`, `:674`, `:693`, `:710`, `:722`. Implementación: `src/configuracion.py:205` (`guardar_ajustes`), `:195` (`_leer_para_escribir`), `:256` (`_escribir_preferencias_atomico`) | cumple (tests) |
| 2 | [NUEVO] | Restablecer deja `{"x": 1}` en una sola escritura; ante `OSError` de lectura o de escritura (temporal a medias, renombrado) se propaga el error y el archivo no cambia; un archivo que no es JSON o no es un objeto se reemplaza sin aviso | Restablecer: `tests/test_configuracion.py:739`. Lectura: `:768`. Escritura: `:797`. JSON inválido (`{`, `[]`): `:829`. Implementación: `src/configuracion.py:249` (`restablecer_ajustes`), `:256` | cumple (tests) |
| 3 | [MODIFICA: configuracion › Modelo de IA elegido en la ventana] | Si `preferencias.json` no se puede leer, elegir un modelo no reescribe el archivo y el Registro dice «solo para esta sesión»; la escritura es atómica | No reescribe si no puede leer: `tests/test_configuracion.py:842`. Lectura y escritura de `guardar_modelo_preferido`: `:768` y `:797`. Implementación: `src/configuracion.py:188`, `:195`, `:256`. Ventana sin cambios: `src/ui.py:1016-1031` (`_al_cambiar_modelo_ia`, captura `OSError`) | cumple (tests); la ventana no se comprobó a mano (ver «Verificación») |

**Verificación (2026-11-22):** `./venv/bin/python -m pytest -q` pasa (412). Arreglo del orquestador: `guardar_ajustes` descartaba con `AttributeError` una sección que no es objeto, un `ia.modelo` dentro de `configuracion` o un `configuracion` que no es objeto; ahora se descartan con el aviso (`src/configuracion.py:216-226`). Lo cubre `test_guardar_ajustes_descarta_entradas_mal_formadas_sin_fallar` (`tests/test_configuracion.py:871`), con sus 3 casos. Historia interna: no hay vista, así que no hubo verificación en la ventana. Lo único visible hoy es el selector de modelo del panel lateral, y su comportamiento no cambia (si no se puede guardar, sigue avisando «solo para esta sesión»); no se comprobó en la ventana.

**Pendientes aceptados:**

- `guardar_modelo_preferido` no comprueba la familia del modelo: la regla 7 se aplica al enviar (`src/copilot.py:familia_excluida`) y el selector no ofrece modelos excluidos.
- `RecursionError` al leer en `_leer_para_escribir` (`src/configuracion.py:195`) no tiene test propio en la escritura.
- Al guardar el modelo, reemplazar un archivo que no es JSON no tiene test propio (`guardar_modelo_preferido` usa el mismo ayudante que `guardar_ajustes`, cubierto en `:829`).
