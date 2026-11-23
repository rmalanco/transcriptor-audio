# 18 · Convertir y validar los valores del formulario

> Origen: `BACKLOG.md`, «Backlog» #5 (panel de configuración, carril L), segunda de sus historias — Diseño:
> docs/disenos/06-panel-de-configuracion.md §Historia A2a (con «Plan técnico», 2; «Decisiones tomadas»; «Fuera de
> alcance» y «Revisión (2026-11-22)») — carril S. Reglas de oro 3, 5, 7 y 8 de `AGENTS.md`. Refinada con `/story` el
> 2026-11-22, sin usuario al otro lado (ver «Supuestos»). Parte del estado en que la deja la historia 17 (A1, aún sin
> implementar); A2b y A3 se apoyan en esta.

## Historia

Como usuario de la ventana, quiero que lo que escriba en el futuro panel de configuración se convierta al tipo correcto
y se rechace con un mensaje claro si no sirve (fuera de rango, no finito, un dominio con `https://`, un historial
dentro del repositorio o un modelo no autorizado), y que mis preferencias guardadas sigan las mismas reglas, para no
poder dejar la app con valores absurdos o prohibidos.

Historia **interna**: no hay vista todavía; lo que el usuario verá (el mensaje bajo el campo y el pie «No se guardó
nada…») llega con la vista en C1. Lo único observable hoy es el aviso en Registro al abrir la ventana con un
`preferencias.json` escrito a mano (criterio 2).

## Criterios de aceptación

- [ ] [NUEVO] Dado un valor de un campo del formulario, cuando se convierte, entonces:
  - «3» en `transcripcion.beam_size` da `3`; « 0,6 » en `transcripcion.no_speech_threshold` da `0.6`; «-1» en
    `transcripcion.logprob_threshold` da `-1.0`; «» en `ia.copilot_enterprise_url` da `""` y «empresa.ghe.com» da
    `"empresa.ghe.com"`; `True` en `salida.incluir_timestamps` da `True`.
  - «cinco», «3.0» y «50» en `transcripcion.beam_size` se rechazan con «`transcripcion.beam_size` debe ser un número
    entero entre 1 y 20 (vale «cinco»).» (con su valor en cada caso); «nan» y «1e999» en `transcripcion.temperature`,
    con «`transcripcion.temperature` debe ser un número entre 0 y 2 (vale «nan»).»; «4000» en
    `ia.max_caracteres_bloque`, con «`ia.max_caracteres_bloque` debe ser un número entero entre 5000 y 500000 (vale
    «4000»).»; «» en `transcripcion.compression_ratio_threshold` (sin tope), con «`transcripcion.compression_ratio_threshold`
    debe ser un número (vale «»).»; «inf» en esa misma clave también se rechaza.
  - «https://empresa.ghe.com/» en el dominio se rechaza con «`ia.copilot_enterprise_url` debe ser un nombre de dominio
    sin https:// ni barras, como empresa.ghe.com, o estar vacío (vale «https://empresa.ghe.com/»).».
  - En `historial.ruta`, «src/historial.db» y «data/../src/historial.db» se rechazan con «`historial.ruta` no puede
    estar dentro de la carpeta del proyecto salvo en data/ (vale «src/historial.db»).» (con su valor en cada caso); una ruta cuya carpeta cuelga de
    un archivo regular, con «`historial.ruta` está en una carpeta que no se puede crear ni escribir (vale «<valor>»).»;
    y «data/sub/otro.db» y una ruta absoluta en una carpeta nueva de `tmp_path` son válidas **sin que se cree ninguna
    carpeta** (ni `data/`, ni `data/sub/`, ni la de `tmp_path`).
- [ ] [MODIFICA: configuracion › Preferencias guardadas que no sirven (historia 17)] Dado un `preferencias.json` cuyo
  `configuracion` trae `transcripcion.beam_size: 50`, `transcripcion.best_of: "cinco"`, `historial.ruta:
  "src/historial.db"` e `ia.copilot_enterprise_url: "https://empresa.ghe.com/"`, cuando se abre la ventana (se
  combina con el YAML), entonces se abre, las cuatro toman el valor del YAML y hay cuatro avisos con el texto del panel
  dentro del marco de la historia 17: «En <ruta>, `transcripcion.beam_size` debe ser un número entero entre 1 y 20
  (vale «50»); se usa el valor de config/settings.yaml.», «En <ruta>, `transcripcion.best_of` debe ser un número
  entero entre 1 y 20 (vale «cinco»); se usa el valor de config/settings.yaml.», «En <ruta>, `historial.ruta` no puede
  estar dentro de la carpeta del proyecto salvo en data/ (vale «src/historial.db»); se usa el valor de
  config/settings.yaml.» y «En <ruta>, `ia.copilot_enterprise_url` debe ser un nombre de dominio sin https:// ni
  barras, como empresa.ghe.com, o estar vacío (vale «https://empresa.ghe.com/»); se usa el valor de
  config/settings.yaml.». Una `historial.ruta` fuera del repo cuya carpeta no se puede crear ni escribir **sí** se
  acepta al abrir (no se mira el disco ni se crean carpetas), y `config/settings.yaml` sigue sin topes: un
  `beam_size: 50` en el YAML se carga como hoy, en la ventana y en la CLI. (antes, según la historia 17: las
  preferencias solo se validaban con la tabla del YAML y `math.isfinite`; `beam_size: 50`, `src/historial.db` y
  `https://empresa.ghe.com/` se aceptaban, y `"cinco"` en `beam_size` decía «debe ser un número entero mayor que 0».)
- [ ] [NUEVO] Dado el subconjunto `{transcripcion.beam_size: "cinco", salida.formato: "srt", transcripcion.best_of:
  "x"}` y `modelo_ia="Mistral-Large-3"`, cuando se valida el formulario, entonces devuelve como convertido solo
  `salida.formato` = `"srt"` y tres errores, en este orden: `transcripcion.beam_size`, `transcripcion.best_of` y, al
  final, `ia.modelo` con «El modelo «Mistral-Large-3» es de la familia «mistral», que no está autorizada por la
  empresa. Elige otro modelo.»; con `modelo_ia="claude-sonnet-5.5"` o sin `modelo_ia` no hay error de modelo; si
  `ia.modelo` viene entre los valores del formulario, es un error de programación (`ValueError`), no un error de
  usuario. El resumen para el pie es «No se guardó nada: corrige 1 valor.» con 1 error y «No se guardó nada: corrige 3
  valores.» con 3.

Cómo se verifican — **solo con tests, sin red y sin ventana**, en `tests/test_configuracion.py`
(`RUTA_PREFERENCIAS` aislada por el fixture autouse `preferencias_aisladas` de `tests/conftest.py`; para
`historial.ruta`, `monkeypatch` de `configuracion.RAIZ_PROYECTO` a una carpeta de `tmp_path` sin `data/`, para no
depender del repo real):

- `test_valor_desde_formulario_convierte` (parametrizado): los seis valores válidos del primer punto del criterio 1.
- `test_valor_desde_formulario_rechaza_con_topes_y_no_finitos` (parametrizado): `ErrorConfiguracion` con el texto
  literal completo (con punto final) para cada valor inválido del segundo punto del criterio 1.
- `test_dominio_enterprise_debe_ser_un_nombre_de_host`: `https://empresa.ghe.com/`, `empresa.ghe.com/` y
  `empresa ghe.com` se rechazan con el texto del criterio 1; `empresa.ghe.com` y `""` valen.
- `test_historial_ruta_fuera_del_repo_salvo_data_y_escribible`: los casos del cuarto punto del criterio 1, y al final
  comprueba que no existe ninguna de las carpetas que la ruta habría necesitado.
- `test_preferencias_aplican_los_topes_del_panel_y_las_reglas_de_ruta_y_dominio` (añadido por esta historia, ver
  «Supuestos», 1): las cuatro entradas del criterio 2 dan la efectiva del YAML y exactamente esos cuatro avisos; una
  `historial.ruta` absoluta bajo un archivo regular se acepta en la efectiva; un YAML con `beam_size: 50` se carga sin
  error con `cargar_configuracion` (criterio 2).
- `test_ajustes_invalidos_desconocidos_no_finitos_e_ia_modelo_se_ignoran_con_aviso` (de la historia 17) **cambia
  solo el literal** del aviso de `beam_size: "cinco"` a «… un número entero entre 1 y 20 (vale «cinco»); …»; los
  cinco avisos y el resto de sus textos no cambian (criterio 2).
- `test_validar_formulario_subconjunto_errores_en_orden_y_regla_7`: el criterio 3, comprobando el orden con
  `list(errores)`, y el `ValueError` con `ia.modelo` entre los valores.
- `test_resumen_errores_singular_y_plural`: `resumen_errores(1)` y `resumen_errores(3)` (criterio 3).
- Siguen pasando, sin cambios, los tests de `cargar_configuracion` (sus mensajes no cambian) y los demás de la
  historia 17.

## Plan

- Una tabla de topes solo del panel y de las preferencias, con su texto «esperado», que manda en el mensaje de esas
  siete claves en todos sus errores; la carga del YAML no la usa.
- Una función convierte el texto de un campo al tipo del valor por defecto de su clave (entero estricto, número con
  coma o punto y finito, texto sin espacios alrededor, booleano tal cual) y luego aplica una única comprobación: la de
  la tabla de claves, el tope, el dominio como nombre de host o vacío, y para el historial la carpeta del proyecto
  (salvo `data/`) y que la carpeta exista o se pueda crear y escribir, mirando el primer antecesor existente sin crear
  nada.
- La lectura de preferencias de la historia 17 reutiliza esa misma comprobación (sin la parte que mira el disco) para
  que lo que se acepta al abrir sea lo que el panel deja guardar.
- Una función valida un subconjunto de campos y devuelve convertidos y errores en el orden de entrada; el modelo de IA
  va aparte, se comprueba contra las familias excluidas importando la integración de Copilot dentro de la función, y su
  error va el último. Otra da el resumen «1 valor» / «N valores».
- Tests sin red de cada conversión, cada mensaje literal, el orden, la regla 7 y la ausencia de carpetas creadas.

Archivos del `/pair` (lista cerrada, la del diseño): `src/configuracion.py` (`TOPES_PANEL`, `valor_desde_formulario`,
`validar_formulario`, `resumen_errores`; y, por el criterio 2, `combinar` reutiliza la comprobación nueva: mismo
archivo, ver «Supuestos», 1), `tests/test_configuracion.py`. Si hace falta otro, se para y se vuelve al diseño. El
delta de spec (`docs/specs/configuracion.md`) y el resto de la documentación los escribe `/cerrar`.

## Fuera de alcance

- La vista «⚙ Configuración», los mensajes bajo cada campo y el pie (C1, C2, D1, D2); pasar del nombre del idioma del
  selector («Español») al código (`es`): lo hace la vista con `codigo_de_idioma` antes de llamar a
  `valor_desde_formulario`, que recibe el código.
- Guardar o restablecer (`guardar_ajustes`, `restablecer_ajustes`, escritura atómica: A2b) y componer el guardado
  (`guardar_formulario`, `ResultadoGuardado`: A3). Esta historia no escribe `preferencias.json`.
- Endurecer la validación del YAML (topes, `math.isfinite`, dominio, ruta): `cargar_configuracion` y la CLI no cambian
  (diseño, «Fuera de alcance» y «Revisión», desviaciones).
- Cambiar `copilot.normalizar_dominio`, que sigue tolerando `https://` y la barra final en el YAML y la CLI.
- Comprobar que `historial.ruta` no es una carpeta existente ni expandir `~` (`Historial` tampoco lo hace).
- Cambiar `FAMILIAS_EXCLUIDAS` o `familia_excluida`.
- Comprobar en `tests/test_importaciones.py` que `src.configuracion` no carga `httpx` (archivo fuera de la lista).

## Sugerencias (a tu criterio)

- Un solo ayudante privado «¿qué falla en este valor ya tipado?» que devuelva el mensaje sin punto (o `None`) y que
  usen `valor_desde_formulario` (añadiendo el punto) y `combinar` (con el marco «En <ruta>, …; se usa el valor…»),
  con un indicador para saltarse la parte que mira el disco. Señal concreta: las dos funciones necesitan exactamente
  las mismas reglas, y A2b las vuelve a necesitar para decidir qué claves previas conserva.
- `valor_desde_formulario` y la regla de la ruta deben leer `RAIZ_PROYECTO` del módulo en cada llamada (no capturarla
  en un valor por defecto) para que el `monkeypatch` de los tests funcione.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **Los topes valen también al leer las preferencias (pregunta abierta de la historia 17).** Se decide que sí,
   salvo la comprobación de disco de `historial.ruta`. Motivos: (a) el diseño lo dice dos veces: «los topes y
   `math.isfinite` solo valen en el panel y en las preferencias» («Fuera de alcance») y «… en el panel y en las
   preferencias, no en el YAML» («Revisión», desviaciones); (b) si `combinar` aceptara `beam_size: 50`, el panel lo
   mostraría y «Guardar», que valida todos los campos (decisión de producto 6), fallaría aunque el usuario no lo
   hubiera tocado; (c) regla 8 y requisito «Privacidad»: `historial.ruta` no puede apuntar dentro del repo salvo
   `data/`, y unas preferencias escritas a mano no deben saltárselo. La comprobación «la carpeta se puede crear o
   escribir» **no** se aplica al abrir: depende del estado del disco (un USB sin montar) y, con la regla «mismas
   reglas que `combinar`» de A2b, haría que el siguiente guardado borrara la preferencia; va contra la decisión
   técnica 3 («un fallo transitorio de lectura no borra preferencias»). Al abrir con esa carpeta inaccesible pasa lo de
   hoy con el YAML: la app abre sin historial y lo anota en el log (`AppTranscriptor.__init__`, `src/ui.py:151-155`);
   el panel sí rechazará guardar mientras siga inaccesible. Como `combinar` está en `src/configuracion.py`, no sale de
   la lista cerrada; el test de la historia 17 cambia un literal (el «esperado» del tope manda «en TODOS sus errores»,
   comentario de `TOPES_PANEL` en «Plan técnico», 2).
2. **Nombre del comportamiento en la marca `[MODIFICA]`.** La spec de la historia 17 aún no existe;
   «Preferencias guardadas que no sirven» es provisional. `/cerrar` debe usar el título que haya escrito el `/cerrar`
   de la historia 17 en `docs/specs/configuracion.md`.
3. **Qué muestra «vale».** En el formulario, el texto del campo sin espacios alrededor («1e999», no «inf»); en un
   booleano que no lo es, `str(valor)`. En las preferencias, el valor tal como vino del JSON (como en la historia 17).
   Los errores de `validar_formulario` llevan punto final (son `str(ErrorConfiguracion)`), como en el CUJ 2.
4. **Orden de los errores.** El diseño dice «en el orden de entrada»; el modelo no viene en `valores_widget`, así que
   su error va el último. Una clave que no está en la tabla entre los valores del formulario es, como `ia.modelo`, un
   error de programación (`ValueError`); el diseño solo fija el de `ia.modelo`.
5. **El caso que más duele** es que el panel permita guardar un historial dentro del repo (acabaría versionado: regla
   8) o un modelo de una familia excluida (regla 7). Los criterios 1, 2 y 3 los cubren; el criterio 1 cubre además los
   límites y los no finitos.
6. **Marcas.** Criterios 1 y 3, `[NUEVO]`: hoy no hay formulario ni conversión desde texto. Criterio 2, `[MODIFICA]`
   sobre lo que deja la historia 17. `docs/specs/configuracion.md` («Configuración con errores», «Claves ausentes») no
   cambia: el YAML sigue igual.
7. **El YAML del proyecto cabe en los topes** (comprobado en `config/settings.yaml`: `beam_size` 5, `best_of` 5,
   `temperature` 0.0, `no_speech_threshold` 0.6, `temperatura` 0.2, `max_caracteres_bloque` 60000,
   `peticiones_paralelas` 3), así que el panel no nacerá bloqueado con los valores de serie.
8. **Líneas** (estado previo a la historia 17, que las moverá; manda el nombre): `src/configuracion.py`:
   `RAIZ_PROYECTO` `:17`, `MODELOS_WHISPER` `:27`, `ErrorConfiguracion` `:30`, `_es_numero` `:50-51` (acepta `nan` e
   `inf`), `_es_numero_no_negativo` `:54-55` (rechaza `nan`, acepta `inf`), `_es_entero_positivo` `:58-59`, `_tabla`
   `:69-99`, `cargar_configuracion` `:114-137`. `src/copilot.py`: `FAMILIAS_EXCLUIDAS` `:305`, `familia_excluida`
   `:308-311` (devuelve la familia en minúsculas: «mistral»), `normalizar_dominio` `:99-104`. `src/historial.py`:
   `Historial.__init__` `:106-109` (ruta relativa contra `RAIZ_PROYECTO`, sin `resolve` ni `expanduser`, y crea la
   carpeta al abrir). `src/ui.py`: `IDIOMAS_DISPONIBLES` `:43`, `codigo_de_idioma` `:68-70`.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa (391 tests). Code review: revisión del
orquestador, listo para commit. Único test existente cambiado: el literal del aviso de `transcripcion.beam_size` «cinco» en
`test_ajustes_invalidos_desconocidos_no_finitos_e_ia_modelo_se_ignoran_con_aviso` (de «mayor que 0» a «entre 1 y 20»), previsto en
la historia. Delta de spec: `docs/specs/configuracion.md`, en «Preferencias del usuario al abrir la ventana», con `Origen` en esta
historia. El aviso de `beam_size` «cinco» de esa sección pasa a «entre 1 y 20» para seguir a los tests.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Un valor del formulario se convierte al tipo de su clave, o se rechaza con el mensaje del panel (topes, no finitos, dominio, `historial.ruta`) | Conversión: `tests/test_configuracion.py:427-435`. Rechazos con texto literal: `:444-462`. Dominio: `:471`. Ruta fuera del repo, carpeta no escribible y sin crear carpetas: `:484`. Implementación: `src/configuracion.py:271` (`valor_desde_formulario`), `:298` (`_motivo_de_rechazo`), `:318` (`_motivo_de_ruta`), `:32` (`TOPES_PANEL`) | cumple (tests) |
| 2 | [MODIFICA: configuracion › Preferencias del usuario al abrir la ventana] | Las preferencias respetan los topes del panel, las reglas de `historial.ruta` y de dominio, y se ignoran con aviso | Cuatro entradas, cuatro avisos exactos y `historial.ruta` bajo un archivo aceptada sin crear carpetas: `tests/test_configuracion.py:514`. YAML con `beam_size: 50` cargado sin tope: `:560`. Aviso «cinco» con el texto nuevo: `:341` (literal en `:358`). Implementación: `src/configuracion.py:250` (`combinar`), `:221` (`leer_ajustes`), `:211` (`_mensaje_invalido`) | cumple (tests) |
| 3 | [NUEVO] | Validar un subconjunto del formulario: errores en orden de entrada, modelo de una familia excluida al final, y resumen «1 valor» / «N valores» | Orden y regla 7: `tests/test_configuracion.py:567`. `ia.modelo` entre los valores lanza `ValueError`: `:591`. Resumen: `:598`. Implementación: `src/configuracion.py:340` (`validar_formulario`), `:367` (`resumen_errores`), `src/copilot.py:308` (`familia_excluida`) | cumple (tests) |

**Verificación (2026-11-22):** `./venv/bin/python -m pytest -q` pasa (391). Los tests de la CLI siguen en verde. El orquestador
comprobó que `config/settings.yaml` actual cumple todos los topes del panel (`beam_size` 5, `best_of` 5, `temperature` 0.0,
`no_speech_threshold` 0.6, `ia.temperatura` 0.2, `ia.max_caracteres_bloque` 60000, `ia.peticiones_paralelas` 3). El YAML y la CLI
no tienen esos topes, así que no cambian. Historia interna: no hay ventana todavía, así que no hubo verificación manual.

**Pendientes aceptados:**

- El formulario se ve con la vista C1 (mensaje bajo cada campo y pie «No se guardó nada…»); hasta entonces nada de esto se ve
  en la ventana.
- `valor_desde_formulario` lanza `KeyError` con una clave desconocida, y `validar_formulario` lanza `ValueError` con una clave
  desconocida; sin test propio. Solo está probado el `ValueError` de `ia.modelo` (`:591`).
