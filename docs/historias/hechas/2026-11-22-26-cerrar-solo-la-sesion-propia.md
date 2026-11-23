# 26 · Cerrar solo la sesión propia de Copilot

> Origen: `BACKLOG.md`, «Backlog» #6 (sesión de GitHub Copilot desde el panel, carril M), segunda de sus historias;
> punto 24 de la sección «Backlog» — Diseño: docs/disenos/06-panel-de-configuracion.md §Historia E1 (con «Plan
> técnico», 7: `cerrar_sesion_propia(enterprise_url) -> EstadoSesion`; «Fuera de alcance», «Cerrar la sesión de
> opencode o quitar `COPILOT_GITHUB_TOKEN`»; alternativa G; «Requisitos no funcionales», «Privacidad y secretos» y
> «Red»; «Dobles de test»; «Revisión (2026-11-22)», fila «E mezclaba lógica y vista») — carril S. Reglas de oro 1, 3, 5
> y 8 de `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin usuario al otro lado (ver «Supuestos»).
>
> **Requires: #23 (B, historia 25) — implementada en la copia de trabajo, sin cerrar.** `estado_sesion`,
> `EstadoSesion`, `ORIGEN_*` y `describir_sesion` ya están en `src/copilot.py` sin commit (ver «Supuestos», 1). E1 va
> después de B, en serie, porque las dos tocan `src/copilot.py` y `tests/test_copilot.py`. D2 (historia 24, en
> implementación) no toca esos archivos: no hay choque.

## Historia

Como quien mantiene el código, quiero cerrar solo la sesión propia de la app y dejar intacta la de opencode, para que
cerrar la sesión desde el panel no borre credenciales ajenas.

Historia **interna**: no hay nada visible nuevo. El botón «Cerrar sesión» que la usa llega con E2 (Backlog #25). Lo
único visible que roza es `--copilot-logout`, que no cambia.

## Criterios de aceptación

- [ ] [NUEVO] Dado un token propio guardado por la app y una sesión de opencode, cuando se cierra la sesión propia
  para github.com, entonces el archivo propio deja de existir, el de opencode queda igual byte a byte (mismo contenido
  y misma fecha de modificación), el estado devuelto es «origen opencode, sin sesión propia» y no se hace ninguna
  petición de red; cerrarla otra vez no da error y devuelve el mismo estado.
- [ ] [NUEVO] Dado `COPILOT_GITHUB_TOKEN` definida y un token propio guardado, cuando se cierra la sesión propia,
  entonces el archivo propio deja de existir, el estado devuelto es «origen variable, sin sesión propia» y la variable
  sigue definida con el mismo valor.
- [ ] [NUEVO] Dado un token propio guardado y que borrarlo falla con un error del sistema de archivos (por ejemplo,
  permiso denegado), cuando se cierra la sesión propia, entonces el error llega a quien llamó (no se devuelve ningún
  estado) y el archivo propio sigue ahí con su contenido.

El caso de error es el criterio 3; la acción repetida, el final del 1. El caso que más dolería (ver «Supuestos», 2) es
que se toque la sesión de opencode: criterio 1.

### Cómo se verifican

**Tests** (lo dice el diseño), en `tests/test_copilot.py`, con la fixture autouse `rutas_aisladas`
(`tests/test_copilot.py:14-18`, `rutas_aisladas`: `RUTA_TOKEN` y `RUTA_AUTH_OPENCODE` en `tmp_path`, sin
`COPILOT_GITHUB_TOKEN`). Ninguno hace red ni toca la sesión real:

- `test_cerrar_sesion_propia_no_toca_opencode` (criterio 1): token propio con `copilot.guardar_token("gho_app")` y
  opencode con `write_text` (como `_solo_opencode` de B); `copilot.httpx.get` y `copilot.httpx.post` parcheados con
  una función que lanza `AssertionError`; `read_bytes()` y `st_mtime_ns` de `RUTA_AUTH_OPENCODE` antes y después;
  `cerrar_sesion_propia(None) == EstadoSesion(ORIGEN_OPENCODE, False)`, `not RUTA_TOKEN.exists()`; segunda llamada,
  mismo estado y sin excepción.
- `test_cerrar_sesion_propia_con_la_variable_sigue_en_la_variable` (criterio 2): `monkeypatch.setenv` y
  `guardar_token`; estado `EstadoSesion(ORIGEN_VARIABLE, False)`, `os.environ[VARIABLE_ENTORNO]` sin cambios y el
  archivo propio borrado.
- `test_cerrar_sesion_propia_propaga_oserror` (criterio 3): `guardar_token`; `unlink` parcheado con `monkeypatch`
  sobre la clase de `copilot.RUTA_TOKEN` (`type(copilot.RUTA_TOKEN)`, `PosixPath` en Linux) para que lance
  `PermissionError`; `pytest.raises(OSError)`; después el archivo existe y `leer_token().token == "gho_app"`.
- Paso rojo: hoy los tres fallan con `AttributeError` (no existe `cerrar_sesion_propia`).
- Siguen pasando sin cambios `test_guardar_y_leer_token_con_permisos_600` (`tests/test_copilot.py:35`, usa
  `cerrar_sesion`), los de B, y en `tests/test_cli.py`
  `test_cli_copilot_logout_con_token_propio_lo_borra_y_no_toca_la_sesion_de_opencode` (`:328`) y
  `test_cli_copilot_logout_sin_token_propio_lo_dice_y_sale_con_codigo_0` (`:347`): la CLI no cambia.
- `./venv/bin/python -m pytest -q` en verde (regla 5).

**Verificación manual del orquestador** (no hay ventana; el diseño dice «solo tests; `--copilot-logout` sigue
igual»). Todo en la carpeta temporal de la sesión, nunca en el repo, sin la sesión real y sin imprimir ningún token.
Desde la raíz del repo:

1. Función nueva, con las rutas aisladas y la red rota. Script `<scratchpad>/e1.py`, ejecutado con
   `env -u COPILOT_GITHUB_TOKEN ./venv/bin/python <scratchpad>/e1.py`:

   ```python
   import hashlib, pathlib, tempfile, httpx
   def sin_red(*a, **k): raise AssertionError("red")
   httpx.get = httpx.post = httpx.stream = sin_red
   from src import copilot
   d = pathlib.Path(tempfile.mkdtemp(dir="<scratchpad>"))
   copilot.RUTA_TOKEN, copilot.RUTA_AUTH_OPENCODE = d / "app/copilot.json", d / "oc/auth.json"
   copilot.RUTA_AUTH_OPENCODE.parent.mkdir(parents=True)
   copilot.RUTA_AUTH_OPENCODE.write_text('{"github-copilot": {"refresh": "gho_oc"}}')
   copilot.guardar_token("gho_app")
   antes = hashlib.sha256(copilot.RUTA_AUTH_OPENCODE.read_bytes()).hexdigest()
   print(copilot.cerrar_sesion_propia(None))      # EstadoSesion(origen='opencode', hay_token_propio=False)
   print(copilot.RUTA_TOKEN.exists(), antes == hashlib.sha256(copilot.RUTA_AUTH_OPENCODE.read_bytes()).hexdigest())
   # False True
   print(copilot.cerrar_sesion_propia(None))      # mismo estado, sin excepción
   ```

   Ninguna línea contiene `gho_`.
2. La CLI sigue igual, con un `HOME` temporal (las rutas del token salen de `~` al importar `copilot`):

   ```bash
   H=<scratchpad>/home-e1; mkdir -p "$H/.local/share/transcriptor-audio" "$H/.local/share/opencode"
   printf '{"github-copilot": {"refresh": "gho_oc"}}' > "$H/.local/share/opencode/auth.json"
   printf '{"token": "gho_app", "enterprise_url": null}' > "$H/.local/share/transcriptor-audio/copilot.json"
   sha256sum "$H/.local/share/opencode/auth.json"
   env -u COPILOT_GITHUB_TOKEN HOME="$H" PYTHONDONTWRITEBYTECODE=1 ./venv/bin/python -m src.main --copilot-logout; echo $?
   # «Sesión cerrada», 0
   env -u COPILOT_GITHUB_TOKEN HOME="$H" PYTHONDONTWRITEBYTECODE=1 ./venv/bin/python -m src.main --copilot-logout; echo $?
   # «No había sesión guardada por esta app», 0
   sha256sum "$H/.local/share/opencode/auth.json"                  # el mismo que antes
   ```

   Comprobado antes de implementar (2026-11-22): con un `HOME` temporal vacío, la orden escribe «No había sesión
   guardada por esta app», sale con 0 y no crea nada en ese `HOME`.

## Plan

- Una función pública nueva en el módulo de Copilot que borra la sesión propia con el borrado de siempre (el mismo que
  usa `--copilot-logout`, que solo toca el archivo propio) y devuelve el estado de la sesión recalculado con la función
  de B para el dominio que se le pasa.
- Sin capturar errores: si el borrado falla, el error sube tal cual (E2 lo mostrará en un diálogo); sin red, sin
  escribir nada más y sin tocar el entorno.
- No cambia el borrado de siempre ni lo que devuelve: la CLI y la invalidación tras un 401 lo siguen usando igual.
- Tests primero (paso rojo), en el archivo de tests de Copilot, con la fixture de siempre, la red parcheada para que
  falle y el borrado parcheado para el caso de error.

Archivos del `/pair` (lista cerrada, la del diseño): `src/copilot.py` (`cerrar_sesion_propia`, junto a
`cerrar_sesion`, `src/copilot.py:227-233`), `tests/test_copilot.py`. Si hace falta otro, se para y se vuelve al
diseño. El delta de spec y el resto de la documentación (`src/EGM.md`, que en su línea 124 lista `guardar_token`,
`cerrar_sesion`…; `docs/disenos/00-actual.md`; `.context/*`) los escribe `/cerrar`. Como no hay nada visible hasta E2,
`/cerrar` puede anotar estos criterios en el mismo dominio que elija para B (propuesta de B: «Origen de la sesión de
Copilot» en `docs/specs/documentos-ia.md`); `docs/specs/cli.md`, «Sesión de Copilot desde la CLI», no cambia.

## Fuera de alcance

- **E2:** la sección «Sesión de GitHub Copilot» en la vista, el botón «Cerrar sesión» y su confirmación,
  `AppTranscriptor._cerrar_sesion_copilot`, el `showerror` con el `OSError`, la época `_epoca_ia`, olvidar el
  asistente, devolver el selector de modelo a `auto` y el configurado, y el registro «Sesión de GitHub Copilot
  cerrada»; llamar a `cerrar_sesion_propia` desde `src/ui.py` o `src/ui_configuracion.py`.
- Cerrar la sesión de opencode o quitar `COPILOT_GITHUB_TOKEN` (diseño, «Fuera de alcance» y alternativa G).
- Revocar el token en GitHub o comprobarlo contra la red: cerrar sesión solo borra el archivo local.
- Cambiar `cerrar_sesion` (su `exists()` + `unlink()`, su `bool` y su log), `invalidar_token`, `leer_token`,
  `estado_sesion` o `describir_sesion`.
- Cambiar `src/main.py` (`--copilot-logout` sigue llamando a `cerrar_sesion`, `src/main.py:131-136`, `main`) o
  `docs/specs/cli.md`.

## Sugerencias (a tu criterio)

- Escribirla en dos líneas sobre lo que ya existe (`cerrar_sesion()` y `return estado_sesion(enterprise_url)`), como
  dice el diseño, en vez de repetir el `unlink`: así la CLI, el 401 y el panel borran por el mismo sitio.
- Para el caso de error, parchear `unlink` en `type(copilot.RUTA_TOKEN)` y no en `pathlib.Path` a secas: es la clase
  real de la ruta y no depende de cómo herede `PosixPath` en cada versión de Python (el `venv` es 3.14).

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **B se toma de la copia de trabajo.** `EstadoSesion` (`src/copilot.py:155-158`), `_hay_token_propio` (`:161-169`),
   `estado_sesion` (`:172-178`) y `ORIGEN_*` (`:36`) existen sin commit, con sus tests en `tests/test_copilot.py`. Si
   B cambia al cerrarse (nombres o forma del estado), los criterios siguen valiendo y solo cambian los nombres de los
   tests. Las líneas citadas son las de esa copia; si se mueven, manda el nombre de la función.
2. **El caso que más duele** es borrar o modificar la sesión de opencode: es una credencial ajena (diseño,
   alternativa G). Lo cubre el criterio 1 con «byte a byte» y la fecha de modificación.
3. **Acción repetida en el criterio 1** («cerrarla otra vez no da error»): no está en los criterios del diseño, pero
   sale de lo que ya hace `cerrar_sesion` sin archivo propio (devuelve `False` sin error, `src/copilot.py:227-233`) y
   es lo que verá E2 si el archivo desaparece entre mostrar la vista y pulsar el botón. No añade código.
4. **Sesión propia de otro dominio.** Con el archivo propio guardado para `empresa.ghe.com` y la app en github.com,
   `cerrar_sesion_propia(None)` lo borra igualmente (el borrado de siempre no mira el dominio). Es coherente con la
   tabla de B (fila «ninguno / sí»: «Hay una sesión guardada por la app para otro dominio de GitHub», se puede
   cerrar). No se añade criterio: el diseño no lo pide y no hay código que decidir.
5. **«Sin red»** se comprueba solo en el criterio 1, con `httpx.get` y `httpx.post` como en «Dobles de test»:
   `cerrar_sesion_propia` no tiene ninguna rama que llame a la red.
6. **Errores de lectura en `estado_sesion`** tras borrar: no aplican (el archivo ya no existe, y `estado_sesion` no
   lanza con archivos mal formados desde B). Un `OSError` de `exists()` en `cerrar_sesion` también subiría; no se
   prueba aparte.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q tests/test_copilot.py tests/test_cli.py`
pasa (99) y `./venv/bin/python -m pytest -q` pasa (483). Code review: revisión del orquestador, listo para commit.

Desviación aceptada: los tests 2 y 3 nacieron verdes porque el código mínimo del test 1 ya los cumplía. Con la función
retirada, los tres fallan con `AttributeError`.

Delta de spec: `docs/specs/documentos-ia.md`, «Cerrar solo la sesión propia de Copilot» (cuatro comportamientos, uno
por criterio), con `Origen` en esta historia.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Dado un token propio y una sesión de opencode, cerrar la sesión propia borra el archivo propio, deja el de opencode igual (bytes y fecha), devuelve «origen opencode, sin sesión propia» sin red; repetirlo no da error | `tests/test_copilot.py:632` (`test_cerrar_sesion_propia_no_toca_opencode`). Código: `src/copilot.py:236` (`cerrar_sesion_propia`) | cumple |
| 2 | [NUEVO] | Dado `COPILOT_GITHUB_TOKEN` y un token propio, cerrar la sesión propia borra el archivo, devuelve «origen variable, sin sesión propia» y la variable sigue igual | `tests/test_copilot.py:652` (`test_cerrar_sesion_propia_con_la_variable_sigue_en_la_variable`) | cumple |
| 3 | [NUEVO] | Dado un token propio y un borrado que falla con `OSError`, el error llega a quien llamó, no se devuelve estado y el archivo sigue con su contenido | `tests/test_copilot.py:663` (`test_cerrar_sesion_propia_propaga_oserror`) | cumple |

**Verificación:** verificación manual del orquestador, con rutas aisladas, red rota y sin `COPILOT_GITHUB_TOKEN`:
`cerrar_sesion_propia(None)` con token propio y de opencode → `EstadoSesion(origen='opencode', hay_token_propio=False)`,
archivo propio borrado; repetirlo da lo mismo sin error; el archivo de opencode conserva el mismo sha256 y la misma
fecha. CLI con `HOME` temporal y archivos falsos: `--copilot-logout` → «Sesión cerrada», repetido → «No había sesión
guardada por esta app»; el archivo de opencode no cambia (los códigos de salida los cubren los tests de la CLI). Nada
visible cambia en la ventana todavía (llega con E2).

**Pendientes aceptados:**

- `cerrar_sesion_propia` también borra una sesión propia guardada para otro dominio (p. ej. `empresa.ghe.com` con la app
  en github.com). Es coherente con la tabla de «Origen de la sesión» (historia 25): se puede cerrar. No hay criterio
  porque el diseño no lo pide.
- No se revoca el token en GitHub ni se comprueba contra la red: cerrar sesión solo borra el archivo local.
