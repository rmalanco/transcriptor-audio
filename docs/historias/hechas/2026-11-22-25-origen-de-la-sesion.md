# 25 · Saber de dónde sale la sesión de Copilot, sin red

> Origen: `BACKLOG.md`, «Backlog» #6 (sesión de GitHub Copilot desde el panel, carril M), primera de sus historias;
> punto 23 de la sección «Backlog» — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia B (con «Plan
> técnico», 7: `EstadoSesion`, `estado_sesion`, `DescripcionSesion`, `describir_sesion` y la tabla de siete textos;
> «Decisiones tomadas», técnica 8; «Fuera de alcance»; «Requisitos no funcionales», «Privacidad y secretos» y «Red»;
> «Dobles de test»; «Revisión (2026-11-22)», fila «Sesión: token propio corrupto, `repr` del token, textos
> incompletos») — carril S. Reglas de oro 1, 3, 5 y 8 de `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin usuario
> al otro lado (ver «Supuestos»).
>
> **Requires: Salud #26 — cumplido.** Es la historia 16 (límite de entrada), cerrada en
> `docs/historias/hechas/2026-11-22-16-limite-de-entrada.md` (commit `e474d38`, último que tocó `src/copilot.py`). B
> va después de ella y antes de E1, en serie, porque las tres tocan `src/copilot.py`. D1 (23) y D2 (24) no tocan
> `src/copilot.py` ni `tests/test_copilot.py`: esta historia no choca con ellas y no depende de ellas.

## Historia

Como quien mantiene el código, quiero que la app sepa de dónde sale la sesión de Copilot (ninguna, opencode, archivo
propio o variable de entorno) sin hacer red, para que la vista lo muestre sin leer ni mostrar el token.

Historia **interna**: no hay nada visible todavía. La sección «Sesión de GitHub Copilot» que pinta estos textos llega
con E2 (Backlog #25); cerrar la sesión propia, con E1 (#24).

## Criterios de aceptación

- [ ] [NUEVO] Dado cada una de estas situaciones en disco y entorno, cuando se pide el estado de la sesión para
  github.com, entonces el origen y si hay sesión propia guardada son:

  | Situación | Origen | Sesión propia |
  |---|---|---|
  | nada (ni variable, ni archivo propio, ni opencode) | ninguno | no |
  | solo la sesión de opencode | opencode | no |
  | archivo propio y sesión de opencode | app | sí |
  | `COPILOT_GITHUB_TOKEN` definida y archivo propio | variable | sí |
  | archivo propio que no es JSON válido, sin opencode | ninguno | no |
  | archivo propio guardado para `empresa.ghe.com`, sin opencode | ninguno | sí |

  En todos los casos no se hace ninguna petición de red, no se crea ni cambia ningún archivo ni carpeta, y el estado
  no lleva el token.
- [ ] [NUEVO] Dado cada una de las siete combinaciones de origen y sesión propia de la tabla de «Plan técnico», 7, del
  diseño, cuando se describe el estado, entonces el texto, si se puede iniciar sesión, el texto del botón de inicio
  («Iniciar sesión» o «Iniciar sesión con la app») y si se puede cerrar son exactamente los de esa fila. Por ejemplo:
  origen opencode con sesión propia da «Se usa la sesión de opencode. La app no la cierra: ciérrala desde opencode.
  Hay una sesión guardada por la app para otro dominio de GitHub. La sesión se comprueba al usarla.», se puede iniciar
  con «Iniciar sesión con la app» y se puede cerrar; origen variable sin sesión propia no permite ni iniciar ni cerrar.
- [ ] [MODIFICA: sin spec] Dado una sesión y un estado cuyo token es `gho_secreto` (archivo propio con ese token y la
  variable de entorno con ese mismo valor, por separado), cuando se piden la representación de la sesión, la del
  estado y todos los textos de su descripción, entonces ninguno contiene `gho_secreto`; la sesión sigue exponiendo el
  token a quien lo pide por su nombre y se sigue construyendo igual (token, dominio, origen). (antes: la
  representación de la sesión de `copilot.leer_token` mostraba el token: `Sesion(token='gho_secreto',
  enterprise_url=None, origen='…')`, comprobado con `src/copilot.py:49-53`, `Sesion`.)

El caso de error y de límite está en el criterio 1 (archivo propio ilegible; archivo propio de otro dominio, que no
da sesión pero sí cuenta como sesión propia). El caso que más dolería (ver «Supuestos», 1) es el criterio 3.

### Cómo se verifican

**Solo tests** (lo dice el diseño), en `tests/test_copilot.py`, con la fixture autouse `rutas_aisladas`
(`tests/test_copilot.py:14-18`, `rutas_aisladas`: `RUTA_TOKEN` y `RUTA_AUTH_OPENCODE` en `tmp_path` y sin
`COPILOT_GITHUB_TOKEN`). Ninguno hace red ni toca la sesión real del usuario:

- `test_estado_sesion_segun_el_origen_sin_red_ni_escritura` (criterio 1; parametrizado con las seis filas):
  `copilot.httpx.get` y `copilot.httpx.post` parcheados con `monkeypatch` por una función que lanza `AssertionError`;
  se prepara la situación con `copilot.guardar_token` (o `write_text` para el JSON inválido y para opencode, como
  `test_reutiliza_sesion_de_opencode`) y `monkeypatch.setenv` para la variable; se toma la lista de archivos de
  `tmp_path` con su contenido y `st_mtime_ns` antes y después de `estado_sesion(None)` y se comparan; se comprueban
  `origen` (`None`, `ORIGEN_OPENCODE`, `ORIGEN_APP`, `ORIGEN_VARIABLE`, `None`, `None`) y `hay_token_propio`. En «nada»
  se comprueba además que no existen ni `tmp_path/app` ni `tmp_path/opencode`.
- `test_describir_sesion_texto_y_botones` (criterio 2; parametrizado, siete filas): `describir_sesion
  (EstadoSesion(origen, hay_token_propio))` comparado campo a campo con la fila de la tabla, textos literales copiados
  del diseño.
- `test_el_token_no_aparece_en_repr_ni_en_los_textos` (criterio 3): `repr(copilot.leer_token())`, `repr(estado)` y
  `describir_sesion(estado).texto` / `.texto_iniciar` sin `gho_secreto`, con el token en el archivo propio y, aparte,
  en la variable; además `leer_token().token == "gho_secreto"`. Paso rojo: hoy `repr` lo muestra.
- Los tests que ya existen siguen pasando sin cambios, en especial `test_el_origen_del_token_se_informa`
  (`tests/test_copilot.py:61`) y `test_token_propio_tiene_prioridad_y_variable_de_entorno_sobre_todo` (`:52`).
- `./venv/bin/python -m pytest -q` en verde (regla 5).

**Comprobación rápida opcional del orquestador** (no hay ventana que mirar). Script en la carpeta temporal de la
sesión, nunca en el repo, que antes de importar nada útil aísla las rutas y quita la variable, para no leer la sesión
real ni imprimir un token:

```python
import os, pathlib, tempfile, httpx
os.environ.pop("COPILOT_GITHUB_TOKEN", None)
def sin_red(*a, **k): raise AssertionError("red")
httpx.get = httpx.post = httpx.stream = sin_red
from src import copilot
d = pathlib.Path(tempfile.mkdtemp(dir="<scratchpad>"))
copilot.RUTA_TOKEN, copilot.RUTA_AUTH_OPENCODE = d / "app/copilot.json", d / "oc/auth.json"
print(copilot.describir_sesion(copilot.estado_sesion(None)))       # «No has iniciado sesión…», sin carpetas nuevas en d
copilot.guardar_token("gho_secreto")
e = copilot.estado_sesion(None); print(e, copilot.describir_sesion(e), repr(copilot.leer_token()))
# ninguna línea contiene gho_secreto; origen 'app', hay_token_propio True
```

Se ejecuta desde la raíz del repo con `./venv/bin/python <script>`. `python -m src.main --copilot-logout` no se prueba
aquí: B no lo cambia (lo verifica E1).

## Plan

- Que la sesión que ya devuelve la búsqueda del token no muestre el token al representarse, sin cambiar cómo se
  construye ni cómo se lee el token.
- Tres constantes de origen y un estado inmutable sin token (origen y si hay sesión propia guardada). El origen sale
  de la búsqueda de siempre (variable, archivo propio, opencode, mismo orden y mismo filtro por dominio), comparando
  con las rutas vigentes en el momento de la llamada, no con copias tomadas al importar (la fixture las cambia).
- «Hay sesión propia» se decide aparte de la búsqueda: el archivo propio se puede leer, es un objeto y su token es
  texto no vacío, aunque la variable lo tape o sea de otro dominio; cualquier fallo de lectura o de forma cuenta como
  «no», sin excepciones y sin escribir.
- Una descripción inmutable (texto, puede iniciar, texto del botón, puede cerrar) que arma el texto con las frases de
  la tabla del diseño en su orden (origen; sesión propia que no se usa; «La sesión se comprueba al usarla.» si hay
  origen) y pone «puede cerrar» igual a «hay sesión propia».
- Tests primero (paso rojo), con la fixture de siempre y la red parcheada para que falle.

Archivos del `/pair` (lista cerrada, la del diseño): `src/copilot.py` (`Sesion.token` con `field(repr=False)`,
`ORIGEN_VARIABLE`, `ORIGEN_APP`, `ORIGEN_OPENCODE`, `EstadoSesion`, `estado_sesion`, `DescripcionSesion`,
`describir_sesion`), `tests/test_copilot.py`. Si hace falta otro, se para y se vuelve al diseño. El delta de spec y el
resto de la documentación (`src/EGM.md`, que hoy describe `Sesion(token, enterprise_url, origen)` en su línea 132;
`docs/disenos/00-actual.md`; `.context/*`) los escribe `/cerrar`. Como no hay nada visible hasta E2, `/cerrar` puede
dejar la spec de usuario para E2 y anotar solo los criterios en el dominio que elija (propuesta: una sección «Origen
de la sesión de Copilot» en `docs/specs/documentos-ia.md`, junto a «Sesión rechazada por Copilot»).

## Fuera de alcance

- **E1:** `cerrar_sesion_propia` y cualquier cambio en `cerrar_sesion` o en `--copilot-logout`.
- **E2:** la sección «Sesión de GitHub Copilot» en la vista, sus botones, `_cerrar_sesion_copilot`, la época y
  olvidar el asistente; llamar a `estado_sesion` desde `src/ui.py` o `src/ui_configuracion.py`.
- Comprobar contra GitHub que el token es válido (alternativa F del diseño): el texto dice «se comprueba al usarla».
- Cambiar el orden de búsqueda, el filtro por dominio o lo que `leer_token` acepta como token (ver «Supuestos», 3).
- Ocultar `session_token` en la representación de `SesionAuto`: el diseño solo pide `Sesion.token`.
- Cambiar `src/main.py` (`--copilot-modelos` sigue imprimiendo `sesión de <origen>`, que es una ruta o el nombre de la
  variable, nunca el token), `src/asistente_ia.py` (`AsistenteIA.__init__` sigue usando `sesion.origen` y
  `sesion.token`) o `src/ui_copilot.py`.

## Sugerencias (a tu criterio)

- Escribir `estado_sesion` sobre `leer_token` (como dice el diseño) y una función privada pequeña para «hay sesión
  propia», en vez de repetir el bucle de `leer_token`: así el orden y el filtro por dominio siguen en un solo sitio.
- Para el texto, una tabla de frases por origen y dos frases fijas («para otro dominio de GitHub» con origen `None` u
  opencode; «además … que ahora no se usa» con variable), en vez de siete cadenas completas: el test parametrizado ya
  fija las siete salidas literales.
- `EstadoSesion` y `DescripcionSesion` con `@dataclass(frozen=True)`, como pide el diseño; `Sesion` sigue sin
  `frozen` (`SesionAuto` y quien construye `Sesion` no cambian).

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es que el token acabe a la vista: en un log, en un `repr` en una traza de error o en el
   texto de la sección. Lo cubren el criterio 3 y el «sin token» del criterio 1.
2. **Sexta fila del criterio 1** (archivo propio de otro dominio → origen ninguno, sesión propia sí). No está en la
   lista del criterio 1 del diseño, pero sí en su definición de `hay_token_propio` («aunque … sea de otro dominio») y
   en la fila «None / sí» de la tabla; se añade para que esa fila tenga un estado real que la produzca.
3. **Token de solo espacios.** `leer_token` acepta `{"token": "   "}` como sesión propia (devuelve origen app con
   token vacío tras `strip`, comprobado). Para que la fila «app / no» no exista (la tabla no la tiene), «hay sesión
   propia» considera no vacío el texto **antes** de quitar espacios, igual que la condición de `leer_token`
   (`src/copilot.py:146`). No se cambia `leer_token`.
4. **«Sin red»** se comprueba con `httpx.get` y `httpx.post`, como dice «Dobles de test»; `src/copilot.py` no usa
   `httpx.stream`.
5. **Fallo previo de `leer_token`, fuera de esta historia.** Con un archivo propio cuyo `token` no es texto (por
   ejemplo `{"token": 5}`), `leer_token` lanza `AttributeError` en `token.strip()` (`src/copilot.py:147`, fuera del
   `try`; comprobado), y `estado_sesion`, que se apoya en ella, lo heredaría. El diseño no lo cubre; no se arregla aquí
   (ver «Fuera de alcance»). El orquestador decide si se añade con `/backlog` (carril S) antes de E2, cuando la vista
   llamará a `estado_sesion` al mostrarse.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q tests/test_copilot.py` pasa (77) y
`./venv/bin/python -m pytest -q` pasa (474). Code review: revisión del orquestador, listo para commit.

Corrección del Supuesto 5: queda superado por el criterio 4 (ampliación aprobada por el orquestador). Un token que no
es texto ya no lanza `AttributeError`: `leer_token` y `estado_sesion` lo tratan como «sin sesión propia».

Delta de spec:

- `docs/specs/documentos-ia.md`: «Archivo propio de sesión mal formado» y «Token de Copilot fuera de las
  representaciones», ambos con `Origen` en esta historia. La spec no describe la vista de la sesión: eso es E2.
  El segundo se limita a la representación de la sesión y a los textos de su estado; el token en registros o trazas
  no tiene test (ver «Pendientes aceptados»).

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Origen y sesión propia para las seis situaciones de disco y entorno, sin red, sin escribir y sin token en el estado | `tests/test_copilot.py:109` (`test_estado_sesion_segun_el_origen_sin_red_ni_escritura`, seis casos). Código: `src/copilot.py:172` (`estado_sesion`), `:161` (`_hay_token_propio`) | cumple |
| 2 | [NUEVO] | Texto, si se puede iniciar, texto del botón y si se puede cerrar, para las siete combinaciones de la tabla del diseño | `tests/test_copilot.py:165` (`test_describir_sesion_texto_y_botones`, siete casos). Código: `src/copilot.py:198` (`describir_sesion`) | cumple |
| 3 | [MODIFICA: sin spec] | El token no sale en `repr` de la sesión ni del estado ni en los textos; `leer_token().token` sigue siendo el token | `tests/test_copilot.py:175` (`test_el_token_no_aparece_en_repr_ni_en_los_textos`, dos casos). Código: `src/copilot.py:53` (`field(repr=False)`) | cumple |
| 4 | [NUEVO] (adicional, aprobado por el orquestador) | Archivo propio ilegible o mal formado (no UTF-8, token o dominio que no son texto) cuenta como «sin sesión»: no lanza y sigue con opencode | `tests/test_copilot.py:127` (`test_archivo_propio_con_token_que_no_es_texto_no_lanza`, dos casos), `:140` (`test_archivo_propio_mal_formado_no_lanza`, dos casos). Código: `src/copilot.py:145-151` (`leer_token`) | cumple |

**Verificación:** tests en verde (77 en `tests/test_copilot.py`, 474 en la suite completa). Comprobado por el
orquestador con un script en carpeta temporal, con `httpx` bloqueado, rutas aisladas y sin
`COPILOT_GITHUB_TOKEN`: sin sesión → «No has iniciado sesión en GitHub Copilot.», se puede iniciar y no cerrar;
solo opencode → «Se usa la sesión de opencode. La app no la cierra: ciérrala desde opencode.» y «Iniciar sesión con
la app»; sesión propia → «Sesión iniciada con la app.», se puede cerrar. Ni los estados, ni las descripciones ni
`repr(Sesion)` contienen el token. Nada visible cambia para el usuario todavía (llega con E2).

**Pendientes aceptados:**

- Efecto colateral de la ampliación: un `refresh` de opencode que no es texto también se ignora.
- Fuera de la evidencia: que el token no aparezca en registros ni trazas de la app. Solo se comprueban `repr` y los
  textos de estado; la spec lo dice así.
- No se comprueba el token contra GitHub (alternativa F del diseño): el texto dice «se comprueba al usarla».
