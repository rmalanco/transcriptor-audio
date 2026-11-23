# 31 · Una consulta al catálogo por generación (refactor)

> Origen: `BACKLOG.md`, «Salud del código» #23 (carril L), historia R2a del diseño (carril S, la cuarta de la serie
> R1 → R4 → R6 → R2a → R2b → R3). Depende de R6 (`docs/historias/30-estimar-tokens.md`, en implementación); R1
> (`22155b3`) y R4 (`2a7a98b`) ya tienen commit. Reglas de oro 3, 5 y 7 de `AGENTS.md`. Refinada con `/story` el
> 2026-11-22, sin usuario al otro lado: un orquestador aprueba en su nombre (ver «Supuestos»).
>
> — Diseño: docs/disenos/07-revision-contra-el-original.md §R2a

Líneas citadas: las de `HEAD` (`2a7a98b`), antes de R6. R6 mueve unas líneas de `src/asistente_ia.py` (añade
`estimar_tokens`) y unas 25 de `tests/test_asistente_ia.py` (dos tests nuevos en el bloque de límite): manda el nombre
de la función o del test.

## Historia

Como mantenedor de la generación de documentos, quiero que la consulta del límite de entrada del modelo al catálogo de
Copilot sea una pieza aparte con su estado por generación, para que en R2b la revisión de fidelidad pueda preguntar el
mismo límite que la redacción sin volver a consultar un catálogo que ya falló en esa generación, y sin que hoy cambie
nada de lo que ve el usuario.

## Qué hace hoy el código

- `AsistenteIA.__init__` (`src/asistente_ia.py:620-622`): `self._limites: Optional[dict[str, int]] = None` y
  `self._cerrojo_limites = threading.Lock()`; caché de límites **por asistente** (dura entre generaciones).
- `AsistenteIA._comprobar_limite_de_entrada(prompt, partes, cancelar)` (`:986-1013`), llamada solo desde
  `AsistenteIA._generar` (`:918`) y solo con dos o más partes, antes de la redacción. En este orden:
  1. estima los tokens (`:990`; R6 lo cambia a `estimar_tokens(PROMPT_SISTEMA + prompt)`) y vuelve si no supera
     `UMBRAL_COMPROBAR_LIMITE` (sin catálogo, sin sesión);
  2. si `cancelar` está activo, `InterruptedError`;
  3. `modelo, _ = self._modelo_para_peticion()` (`:660-673`: abre o reutiliza la sesión `auto` y comprueba
     `familia_excluida`, regla 7);
  4. con `_cerrojo_limites`, si `self._limites is None`, `copilot.limites_de_entrada(copilot.Sesion(self.api_key,
     self.enterprise_url))`. Si lanza `copilot.ErrorCopilot` (conexión, 401, 5xx, formato inesperado), registra
     `WARNING` «No se pudo comprobar el límite de entrada de «%s» (%s); se envía la redacción como hoy.» (modelo,
     excepción) y **vuelve sin recordar el fallo** (comentario «la siguiente generación vuelve a consultar»);
  5. `limite = self._limites.get(modelo)`: si es `None`, `WARNING` «No se pudo comprobar el límite de entrada de «%s»:
     el catálogo no lo informa; se envía la redacción como hoy.»; si `estimado > limite`, `ErrorAsistenteIA` con el
     texto de «Notas que no caben en el modelo».
- `copilot._catalogo` (`src/copilot.py:324-334`) lanza `ErrorCopilot` (no `ErrorSesionCopilot`) también ante un 401;
  `copilot.limites_de_entrada` (`:337-350`) omite los modelos sin `max_prompt_tokens` entero positivo.
- Hoy cada generación consulta el catálogo **como mucho una vez** porque solo la redacción lo pide. No existen
  `_ConsultaDeLimite` ni `_limite_del_modelo`.
- Spec: `docs/specs/documentos-ia.md`, «Notas que no caben en el modelo» (`:207-220`). `src/EGM.md:297-302`.

## Criterios de aceptación

Los dos primeros son el contrato interno nuevo que R2b necesita (el diseño los fija como criterios de R2a); no son
comportamiento que vea el usuario y `/cerrar` no los lleva a `docs/specs/` (diseño: «Documentación que cambia:
ninguna»).

- [ ] [NUEVO] Dado un asistente con `modelo="gpt-4.1"` y un catálogo que falla por conexión (`_simular_catalogo` con
  `httpx.ConnectError("sin conexión")`), cuando llamo dos veces a `asistente._limite_del_modelo(consulta, None)` con
  la misma `consulta = _ConsultaDeLimite()`, entonces el catálogo se consulta **una** vez, las dos llamadas devuelven
  `("gpt-4.1", None)` y `consulta.error` contiene el motivo («No se pudo conectar con GitHub Copilot: sin conexión»);
  y una tercera llamada con una `_ConsultaDeLimite()` nueva vuelve a consultarlo (2 consultas en total): el fallo no se
  guarda en el asistente.
- [ ] [NUEVO] Dado un catálogo que da 64 000 tokens de entrada a `gpt-4.1` (`_catalogo_con_limite("gpt-4.1",
  64000)`), cuando llamo a `_limite_del_modelo` con una consulta y después con **otra** consulta nueva, entonces las
  dos devuelven `("gpt-4.1", 64000)`, `consulta.error` sigue en `None` y el catálogo se consulta una sola vez (los
  límites se quedan en el asistente entre generaciones, como hoy).

**Criterio de no cambio** (guarda; sin marca de delta porque no cambia ningún comportamiento, ver «Supuestos» 2):

- [ ] Dada cualquier generación de hoy (una parte; varias bajo el umbral; varias que caben; varias que no caben;
  catálogo caído, con 401, 500, formato inesperado, sin el modelo o con un límite no válido; repetir tras un error;
  catálogo caído y después sano), cuando genero la minuta o el resumen, entonces se envían las mismas peticiones, el
  catálogo se consulta las mismas veces (como mucho una por generación, y ninguna más mientras el asistente tenga los
  límites), sale el mismo error con el mismo texto, y el registro de la redacción dice **literalmente** lo mismo:
  «No se pudo comprobar el límite de entrada de «gpt-4.1» (No se pudo conectar con GitHub Copilot: sin conexión); se
  envía la redacción como hoy.» con el catálogo caído, y «No se pudo comprobar el límite de entrada de «gpt-4.1»: el
  catálogo no lo informa; se envía la redacción como hoy.» con el modelo ausente. El 401 del catálogo sigue redactando
  como hoy (cambiarlo es R2b).

Caso que dolería (tomado del diseño, CUJ 5 y «Qué no cambia»): que un catálogo caído pase a bloquear la redacción, o
que se consulte el modelo después del catálogo y se salte la regla 7. Lo cubren el criterio 1 (fallo recordado solo en
la generación) y la guarda (mismo resultado y mismo orden: cancelación → modelo → catálogo).

## Cómo se verifican

Todo con tests sin red en `tests/test_asistente_ia.py` (regla 3): `_simular_catalogo` (`:1866`) parchea
`httpx.get` y cuenta las consultas; `_catalogo_con_limite` (`:1879`); `_Respuesta` (`:8`); `_simular_chat` (`:973`) y
`_es_prompt_de_notas` (`:983`); `_relleno` (`:1861`). Los dos rojos llaman al método privado directamente porque, hasta
R2b, ninguna generación pide el límite dos veces y el «una sola consulta por generación» no se puede observar desde
`generar_minuta`.

- **Rojos** (fallan antes del cambio: `_ConsultaDeLimite` y `_limite_del_modelo` no existen):
  - `test_limite_del_modelo_no_repite_un_catalogo_caido_en_la_misma_generacion` (criterio 1): `consultas ==` 1 tras
    las dos llamadas con la misma consulta, ambos resultados `("gpt-4.1", None)`, «sin conexión» en `consulta.error`;
    con una consulta nueva, `len(consultas) == 2`.
  - `test_limite_del_modelo_guarda_el_catalogo_entre_generaciones` (criterio 2): dos consultas distintas, ambos
    resultados `("gpt-4.1", 64000)`, `len(consultas) == 1`, `consulta.error is None`.
- **Guarda nueva** (se escribe **antes** del refactor y debe pasar en verde antes y después):
  - `test_registro_de_la_redaccion_sin_limite_no_cambia`, parametrizado con la conexión caída y el modelo ausente,
    con el escenario de `test_sin_limite_conocido_se_redacta_como_hoy` y `caplog`: comprueba los dos textos literales
    de la guarda (con `in caplog.text`). Hace falta porque hoy ningún test fija el texto: el existente solo busca «no
    se pudo comprobar el límite de entrada» en minúsculas, y el refactor mueve el `log.warning` de sitio.
- **Guarda** (pasan antes y después sin tocarlos; el bloque «Límite de entrada del modelo (historia 16)», ya con los
  ajustes de R6):
  - `test_notas_cortas_o_una_sola_parte_no_consultan_el_catalogo` (`:1883`), `test_notas_que_superan_el_limite_no_envian_la_redaccion`
    (`:1901`), `test_repetir_con_el_mismo_modelo_no_pide_nada_y_repite_el_error` (`:1920`),
    `test_notas_que_caben_consultan_el_catalogo_una_vez_y_redactan` (`:1939`),
    `test_sin_limite_conocido_se_redacta_como_hoy` (`:1963`, sus 9 casos, incluido `"401"`),
    `test_si_el_catalogo_falla_se_vuelve_a_consultar_en_la_siguiente_generacion` (`:1976`), y los dos de R6
    (`test_estimar_tokens_usa_la_relacion_medida`, `test_notas_que_cabian_con_cuatro_caracteres_por_token_ya_no_se_envian`).
  - Fuera del bloque: `test_modelo_excluido_no_depende_del_catalogo` (`:623`) y
    `test_auto_con_catalogo_caido_tambien_salta_las_familias_excluidas` (`:726`), por la regla 7.
- Suite completa: `./venv/bin/python -m pytest -q` en verde; +3 tests (6 contando los casos parametrizados: 2 rojos y
  la guarda nueva con 2 casos) respecto a lo que deje R6.
- **Verificación manual:** no hace falta ni hay peticiones reales autorizadas; no cambia nada observable.

## Plan

- Un estado pequeño por generación guarda si la consulta al catálogo falló y por qué; empieza vacío.
- Una pieza nueva del asistente devuelve el modelo de la próxima petición y su límite: comprueba la cancelación,
  resuelve el modelo con la regla 7 y la sesión `auto`, y lee los límites de la caché del asistente o, si no están y el
  estado no dice que ya falló, del catálogo (bajo el mismo cerrojo); ante un fallo anota el motivo en el estado y
  devuelve sin límite. No registra nada.
- La comprobación del límite de la redacción usa esa pieza (y crea su propio estado si no le dan uno); con el límite
  ausente, elige el registro de hoy según haya motivo de fallo o no; la estimación, el umbral y el error no cambian.
- La generación crea el estado al empezar y se lo pasa a la comprobación de la redacción (R2b se lo pasará también a
  la revisión).
- Tests: primero la guarda nueva en verde, después los dos rojos, después el refactor; los guarda sin tocar.

Archivos del `/pair` (lista cerrada, la del diseño): `src/asistente_ia.py` (`@dataclass class _ConsultaDeLimite` con
`error: Optional[str] = None`; `AsistenteIA._limite_del_modelo(self, consulta: _ConsultaDeLimite, cancelar:
Optional[threading.Event]) -> tuple[str, Optional[int]]`; `AsistenteIA._comprobar_limite_de_entrada(self, prompt,
partes, cancelar, consulta: Optional[_ConsultaDeLimite] = None)`; `AsistenteIA._generar` crea `consulta =
_ConsultaDeLimite()`), `tests/test_asistente_ia.py`. Si hace falta otro archivo, se para y se vuelve al diseño.

Documentación que cambia (`/cerrar`): ninguna en `docs/specs/` ni en `src/EGM.md` (sin cambio de comportamiento;
`src/EGM.md:299`, «se consulta una vez por asistente», sigue siendo cierto). `/cerrar` solo mueve la historia y deja
`BACKLOG.md` #23 abierto (🟡) hasta R3.

## Fuera de alcance

- **R2b:** pasar la consulta a la revisión, `FuenteRevision`, `_fuente_de_revision`, conservar la transcripción
  original, los textos de registro «para la revisión», y el 401 del catálogo como falta de sesión (`copilot._catalogo`
  → `ErrorSesionCopilot`, `_limite_del_modelo` → `_error_de_token_rechazado()`). En R2a el 401 sigue siendo un fallo
  del catálogo que no bloquea; `src/copilot.py` no se toca.
- **R3:** el motivo de por qué la revisión fue contra las notas.
- Recordar el fallo del catálogo entre generaciones, cambiar `UMBRAL_COMPROBAR_LIMITE`, la estimación (R6) o el texto
  del error de límite.
- Comprobar el límite con una sola parte (hoy no se comprueba; el diseño lo deja así).

## Supuestos

1. El orquestador aprobó los criterios, las firmas y el plan del diseño en nombre del usuario; esta historia no
   pregunta ni añade requisitos. «El caso que dolería» se toma del diseño.
2. El estándar de marcas no tiene una para «no cambia»: la guarda va aparte y sin marca para que `/cerrar` no toque la
   spec. Los criterios 1 y 2 llevan `[NUEVO]` por ser contrato nuevo, pero interno: no van a `docs/specs/`.
3. R6 está a medias en la copia de trabajo (`CARACTERES_POR_TOKEN = 2.3` y el test de `estimar_tokens` ya están;
   `estimar_tokens` y su uso en `_comprobar_limite_de_entrada` todavía no). R2a empieza después del commit de R6 y no
   toca la línea de la estimación.
4. `consulta.error` guarda `str(e)` de la `copilot.ErrorCopilot`, que es lo que hoy imprime el `%s` del registro: así
   el texto no cambia.
5. La guarda nueva (`test_registro_de_la_redaccion_sin_limite_no_cambia`) no está en la lista de tests del diseño; se
   añade porque el criterio 3 del diseño («el texto del registro de la redacción es el mismo») no tiene hoy ningún test
   que lo fije. Va en el archivo de tests de la lista cerrada.

## Discrepancias entre diseño y código

1. **Líneas de los tests.** El diseño cita las de `8ded42a` (`:1670-1685` para los dobles, guarda `:1687-1797`). En
   `HEAD` son `:1866-1882` y `:1883-1993`, y R6 las mueve otra vez (en la copia de trabajo, hasta `:2018`). Manda el
   nombre.
2. **«Una consulta por generación» ya se cumple hoy.** Con una sola petición de límite por generación (la redacción),
   el fallo no recordado no produce una segunda consulta; el cambio solo se nota desde R2b. Por eso los rojos son
   unitarios sobre `_limite_del_modelo` y no hay test de extremo a extremo nuevo.
3. **Dos `None` con registro distinto.** `_limite_del_modelo` devuelve `None` tanto si el catálogo falló como si no
   trae el modelo, pero el registro de la redacción los distingue; `_comprobar_limite_de_entrada` tiene que mirar
   `consulta.error`. El diseño no lo dice explícitamente, pero lo implica («el texto del registro no cambia» y
   `error: None si no se consultó o salió bien`).
4. **Cancelación.** La firma del diseño pasa `cancelar` a `_limite_del_modelo`; para no cambiar el comportamiento, la
   comprobación de `cancelar` va ahí, después de la estimación y antes de `_modelo_para_peticion`, como hoy. No hay
   hoy ningún test de cancelación en la ruta del límite (ver «Sugerencias»).
5. **401 del catálogo.** `copilot._catalogo` lanza hoy `ErrorCopilot` genérico ante un 401 («La sesión de GitHub
   Copilot no es válida (401)…») y la redacción sigue; el diseño cambia eso en R2b. En R2a el caso `"401"` de
   `test_sin_limite_conocido_se_redacta_como_hoy` es guarda.
6. **Spec.** El diseño no cita líneas de la spec para R2a. «Notas que no caben en el modelo» está en
   `docs/specs/documentos-ia.md:207-220` y su tercer Given («la siguiente generación vuelve a consultar el catálogo»)
   sigue siendo cierto tras R2a.

## Sugerencias (a decidir)

- Un test de cancelación en la ruta del límite (`cancelar` activo con notas por encima del umbral: `InterruptedError`,
  ni catálogo ni redacción) blindaría el orden de la discrepancia 4. No lo pide el diseño; si se añade, es otra guarda
  en el mismo archivo.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 520 tests (516 de R6 más 4 casos: dos tests de criterio y los dos casos de la guarda; la historia decía «+3 tests / 6 casos»). Code review: revisión del orquestador, listo para commit. Es un refactor sin cambio de comportamiento: `src/copilot.py` no se toca y ningún test existente cambió.

Delta de spec: ninguno. Los criterios 1 y 2 son contrato interno de `asistente_ia.py` y no van a `docs/specs/`; la guarda no cambia comportamiento. `src/EGM.md` (sección de `asistente_ia.py`) sí se actualiza para describir `_ConsultaDeLimite` y `_limite_del_modelo`.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [NUEVO] | Un catálogo caído se consulta una vez por generación: dos llamadas con la misma `_ConsultaDeLimite` no repiten la consulta, y una generación nueva sí vuelve a consultar (el fallo no se guarda en el asistente) | `tests/test_asistente_ia.py:2020` (`test_limite_del_modelo_no_repite_un_catalogo_caido_en_la_misma_generacion`) | cumple |
| 2 | [NUEVO] | Un catálogo que trae el límite se guarda en el asistente entre generaciones: dos consultas distintas, una sola consulta al catálogo y `consulta.error is None` | `tests/test_asistente_ia.py:2033` (`test_limite_del_modelo_guarda_el_catalogo_entre_generaciones`) | cumple |
| 3 | (guarda, sin marca) | Mismo comportamiento de la redacción: mismas peticiones, mismas consultas al catálogo, mismo error y mismo texto del registro («No se pudo comprobar el límite…», con catálogo caído y con modelo ausente) | `tests/test_asistente_ia.py:2011` (`test_registro_de_la_redaccion_sin_limite_no_cambia`, 2 casos), `:1988` (`test_sin_limite_conocido_se_redacta_como_hoy`, 9 casos), `:2043` (`test_si_el_catalogo_falla_se_vuelve_a_consultar_en_la_siguiente_generacion`) | cumple |

**Verificación:**

- `./venv/bin/python -m pytest -q`: 520 pasan.
- Los criterios 1 y 2 y la guarda se escribieron antes del refactor. La guarda pasó antes y después del cambio. El criterio 1 fue rojo antes del cambio (no existían `_ConsultaDeLimite` ni `_limite_del_modelo`).
- Desviación aceptada: el criterio 2 no fue rojo antes del cambio, porque la caché `self._limites` ya la exigían los tests existentes. Su criterio queda cubierto por `:2033`.
- Verificación manual: no hace falta. No cambia nada observable; los tests simulan `httpx`, sin peticiones reales.

**Pendientes aceptados:**

- La cancelación en la ruta del límite (`_limite_del_modelo` lanza `InterruptedError` si `cancelar` está activo, antes de resolver el modelo) no tiene test propio. Sería otra guarda en el mismo archivo, si se decide añadirla.
