# 30 · Estimar tokens con la relación medida de 2,3 caracteres por token

> Origen: `BACKLOG.md`, «Salud del código» #23 (carril L), historia R6 del diseño (carril S, la tercera de la serie
> R1 → R4 → R6 → R2a → R2b → R3). No depende de R1 (hecha, `22155b3`) ni de R4 (en implementación), pero va en serie
> detrás de R4 porque las dos tocan los mismos archivos. Reglas de oro 3 y 5 de `AGENTS.md`. Refinada con `/story` el
> 2026-11-22, sin usuario al otro lado: un orquestador aprueba en su nombre (ver «Supuestos»).
>
> — Diseño: docs/disenos/07-revision-contra-el-original.md §R6

Líneas citadas: las de `HEAD` (`22155b3`), antes de que se aplique R4. R4 no cambia `PROMPT_SISTEMA`, `PROMPT_MINUTA`
ni `PROMPT_RESUMEN` (su «Fuera de alcance»), así que las cifras de esta historia siguen valiendo después de R4, pero
las líneas se moverán: manda el nombre de la función o del test.

## Historia

Como usuario que genera la minuta o el resumen de una reunión larga, quiero que la app estime los tokens de la
redacción con la relación medida (2,3 caracteres por token) y no con 4, para que me avise antes de enviar una redacción
que Copilot rechazaría por no caber en el modelo, en lugar de enviarla y fallar con un error poco claro.

## Qué hace hoy el código

- `src/asistente_ia.py:27`: `CARACTERES_POR_TOKEN = 4  # estimación sin margen: con tokenizadores de Claude suele
  quedarse corta`. `UMBRAL_COMPROBAR_LIMITE = 32_000` (`:26`, tokens estimados).
- `AsistenteIA._comprobar_limite_de_entrada` (`:806-834`), llamada desde `AsistenteIA._generar` (`:738`) solo con dos
  o más partes, calcula `estimado = math.ceil((len(PROMPT_SISTEMA) + len(prompt)) / CARACTERES_POR_TOKEN)` (`:810`).
  Si `estimado <= UMBRAL_COMPROBAR_LIMITE`, vuelve sin consultar el catálogo; si no, consulta una vez por asistente
  `copilot.limites_de_entrada` y, si `estimado > limite`, lanza `ErrorAsistenteIA` con «las notas de las {partes}
  partes suman unos {estimado} tokens y el modelo «{modelo}» admite como máximo {limite} tokens de entrada, así que no
  se envió la redacción. Elige en el selector un modelo con más contexto y vuelve a generar; con otro modelo se pedirán
  de nuevo las notas de todas las partes.» (`:829-834`).
- No existe `estimar_tokens`. `math` se sigue usando en `dividir_texto` (`:248`) y en `:389`: el import se queda.
- La comprobación real del diseño («Comprobación real (2026-11-22)»): 164 993 caracteres enviados = 70 318 tokens de
  entrada en `claude-haiku-5.5`, ≈ 2,35 caracteres por token. Con 4, la app cree que la petición ocupa un 41 % menos.

**Cifras con los dobles de los tests** (calculadas al refinar, con `TEXTO_TRES_PARTES_LARGO` en 3 partes, notas
simuladas con `_relleno(n)` y el formato de `_notas_por_bloque`; caracteres = `PROMPT_SISTEMA` + plantilla con las
notas):

| Notas por parte | Pasada | Caracteres | Hoy (÷ 4) | Con `estimar_tokens` (÷ 2,3) |
|---|---|---|---|---|
| 40 000 | minuta | 122 333 | 30 584 (≤ umbral: no consulta) | **53 189** (> umbral, ≤ 64 000: consulta y redacta) |
| 40 000 | resumen | 121 595 | 30 399 | 52 868 |
| 60 000 | minuta | 182 333 | 45 584 (≤ 64 000: se envía) | **79 276** (> 64 000: no se envía) |
| 100 000 | minuta | 302 333 | 75 584 | **131 450** |
| 2 × «- Nota de una parte» (`TEXTO2`) | minuta | 2 348 | 587 | 1 021 (≤ umbral: no consulta) |

## Criterios de aceptación

Error de límite (literal de hoy, no cambia): «las notas de las N partes suman unos T tokens y el modelo «M» admite como
máximo L tokens de entrada, así que no se envió la redacción. Elige en el selector un modelo con más contexto y vuelve a
generar; con otro modelo se pedirán de nuevo las notas de todas las partes.»

- [ ] [MODIFICA: documentos-ia › Notas que no caben en el modelo] Dada una transcripción de 3 partes
  (`TEXTO_TRES_PARTES_LARGO`, `max_caracteres_bloque=1200`), notas de 60 000 caracteres por parte, el modelo `gpt-4.1`
  y un catálogo que le da 64 000 tokens de entrada, cuando genero la minuta, entonces no se envía la redacción (solo
  las 3 peticiones de notas), el catálogo se consulta una vez y el error de límite dice «las notas de las 3 partes suman
  unos T tokens…» con 78 000 ≤ T ≤ 81 000 (79 276 con los prompts de hoy). (antes: se estimaban 45 584 tokens, cabían
  en 64 000 y se enviaba una redacción que Copilot podía rechazar)
- [ ] [MODIFICA: documentos-ia › Notas que no caben en el modelo] Dada la misma transcripción con notas de 100 000
  caracteres por parte y el mismo catálogo, cuando genero la minuta, entonces el error de límite dice unos T tokens con
  129 000 ≤ T ≤ 134 000 (131 450), donde T son los caracteres de la petición de redacción (prompt de sistema más
  plantilla con las notas) entre 2,3, redondeados hacia arriba y sin error de coma flotante: 230 caracteres son 100
  tokens y 231 son 101. (antes: T eran esos caracteres entre 4, unos 75 584, en el rango 74 000-78 000)
- [ ] [MODIFICA: documentos-ia › Notas que no caben en el modelo] Dada la misma transcripción con notas de 40 000
  caracteres por parte (unos 53 000 tokens estimados) y el mismo catálogo, cuando genero la minuta y después el
  resumen, entonces el catálogo se consulta una sola vez y las dos redacciones se envían (3 notas + 2 redacciones);
  y con notas cortas (`TEXTO2`, 2 partes, unos 1 021 tokens) sigue sin consultarse el catálogo. El umbral sigue en
  32 000 tokens estimados, que ahora equivalen a unos 73 600 caracteres de petición. (antes: con 4 caracteres por token
  esas notas de 40 000 daban unos 30 584 tokens, quedaban bajo el umbral y se redactaba sin consultar el catálogo; el
  umbral equivalía a 128 000 caracteres)

Caso que dolería (tomado del diseño, riesgo 2 y defecto 4): una redacción que no cabe en `gpt-4.1` y aun así se envía
(criterio 1). El límite y la cifra exacta del redondeo los cubre el criterio 2.

## Cómo se verifican

Todo con tests sin red en `tests/test_asistente_ia.py` (regla 3): `_simular_catalogo` y `_catalogo_con_limite`
(`:1750-1764`) simulan `GET /models` y cuentan consultas; `_simular_chat` (`:857`) con `_es_prompt_de_notas` (`:867`)
simula `/chat/completions`; `_relleno(n)` (`:1745`) da notas de exactamente `n` caracteres; `_prohibir_red` (`:45`)
hace fallar cualquier `httpx.get`/`post`. Los tests que comparan cifras las calculan con rango (como hoy) o con
`estimar_tokens`, no las fijan a mano.

- **Rojos** (fallan antes del cambio):
  - `test_estimar_tokens_usa_la_relacion_medida` (criterio 2): `asistente_ia.CARACTERES_POR_TOKEN == 2.3`,
    `estimar_tokens("x" * 230) == 100`, `estimar_tokens("x" * 231) == 101` y `estimar_tokens("") == 0`. Hoy falla por
    import (`estimar_tokens` no existe).
  - `test_notas_que_cabian_con_cuatro_caracteres_por_token_ya_no_se_envian` (criterio 1): `_relleno(60_000)` en las
    notas, catálogo con 64 000 para `gpt-4.1`; `pytest.raises(ErrorAsistenteIA)`, T extraído con
    `re.search(r"unos (\d+) tokens", …)` y `78_000 <= T <= 81_000`, el mensaje completo con `==` (como el test de
    `:1785`), `len(cuerpos) == 3` y todas de notas, `len(consultas) == 1`. Hoy se envía la redacción (45 584 ≤ 64 000).
- **Se ajustan:**
  - `test_notas_que_superan_el_limite_no_envian_la_redaccion` (`:1785`; rango en `:1795`): `74_000 <= estimado <=
    78_000` → `129_000 <= estimado <= 134_000` y el comentario «el criterio dice unos 76 000 tokens» → «unos 131 000»
    (criterio 2).
  - `test_notas_que_caben_consultan_el_catalogo_una_vez_y_redactan` (`:1823`): `_relleno(60_000)` →
    `_relleno(40_000)` y el comentario de `:1829` «unos 46 000 tokens» → «unos 53 000 tokens» (criterio 3). Ojo: tras
    el ajuste este test es **rojo** antes del cambio (con 4, 30 584 ≤ 32 000 y no hay consulta: `len(consultas) == 0`),
    lo que confirma el criterio 3.
- **Guarda** (pasan antes y después, sin tocarlos):
  - `test_notas_cortas_o_una_sola_parte_no_consultan_el_catalogo` (`:1767`, criterio 3: notas cortas, 1 021 tokens, y
    una sola parte de 150 000 caracteres, que no se comprueba).
  - `test_repetir_con_el_mismo_modelo_no_pide_nada_y_repite_el_error` (`:1804`, notas de 100 000: sigue fallando y
    compara los mensajes con la cifra sustituida).
  - `test_sin_limite_conocido_se_redacta_como_hoy` (`:1847`, sus 9 casos) y
    `test_si_el_catalogo_falla_se_vuelve_a_consultar_en_la_siguiente_generacion` (`:1860`): notas de 100 000, ya por
    encima del umbral con 4 y con 2,3.
- Suite completa: `./venv/bin/python -m pytest -q` en verde; +2 tests respecto a lo que deje R4.
- **Verificación manual:** no hace falta ni hay peticiones reales autorizadas: lo observable (si se envía la
  redacción, cuántas veces se consulta el catálogo y el texto del error) lo cubren los tests con `httpx` simulado. La
  relación 2,3 ya se midió con la comprobación real del diseño; ajustarla con reuniones reales es la pregunta abierta 1
  del diseño, no esta historia.

## Plan

- La relación caracteres/token pasa de 4 a 2,3, con un comentario que cita la medición (164 993 caracteres = 70 318
  tokens en `claude-haiku-5.5`, ≈ 2,35).
- Una sola función pública y pura estima los tokens de un texto, redondeando hacia arriba con aritmética entera
  (caracteres × 10 entre la relación × 10), para que 230 caracteres den 100 y no 101 por coma flotante.
- La comprobación del límite de entrada de la redacción usa esa función sobre el prompt de sistema más la petición; el
  umbral, la consulta al catálogo, la caché de límites y el texto del error no cambian.
- Tests: primero los dos rojos, luego los dos ajustes; los guarda sin tocar.

Archivos del `/pair` (lista cerrada, la del diseño): `src/asistente_ia.py` (`CARACTERES_POR_TOKEN = 2.3`;
`estimar_tokens(texto: str) -> int`, módulo, `return -(-len(texto) * 10 // round(CARACTERES_POR_TOKEN * 10))`;
`AsistenteIA._comprobar_limite_de_entrada`, con `estimado = estimar_tokens(PROMPT_SISTEMA + prompt)`),
`tests/test_asistente_ia.py`. Si hace falta otro archivo, se para y se vuelve al diseño.

Documentación que cambia (`/cerrar`):

- `docs/specs/documentos-ia.md`, «Notas que no caben en el modelo» (`:196-209`): T es la estimación a 2,3 caracteres
  por token, redondeada hacia arriba; el umbral de 32 000 tokens estimados sigue igual.
- `src/EGM.md`, «Documentos generados» (`:297-302`; la cifra está en `:299`): «(caracteres / 4)» → «(caracteres / 2,3,
  `asistente_ia.py:estimar_tokens`)».
- `BACKLOG.md` #23 sigue abierto (🟡) hasta R3.

## Fuera de alcance

- **R2a:** `_ConsultaDeLimite` y `_limite_del_modelo` (una consulta al catálogo por generación). Esta historia no
  cambia cómo ni cuándo se guarda el catálogo, solo la estimación que decide si se consulta.
- **R2b:** usar `estimar_tokens` para decidir si la revisión cabe con la transcripción completa, y todo lo de la fuente
  de la revisión.
- **R3:** el motivo de por qué la revisión fue contra las notas.
- Cambiar `UMBRAL_COMPROBAR_LIMITE` (sigue en 32 000 tokens estimados), el texto del error de límite o la regla de
  que un catálogo caído no bloquea.
- Comprobar el límite con una sola parte (hoy no se comprueba; el diseño lo deja así).
- Ajustar 2,3 con registros de reuniones reales (pregunta abierta 1 del diseño).

## Supuestos

1. El orquestador aprobó los criterios, las cifras y el plan del diseño en nombre del usuario; esta historia no
   pregunta y no añade requisitos. «El caso que dolería» se toma del diseño (criterio 1).
2. Los rangos de T son los del diseño; las cifras exactas entre paréntesis se calcularon al refinar con los prompts de
   `22155b3` y pueden moverse unas decenas si cambia un prompt, por eso los tests usan rango.
3. `estimar_tokens("") == 0` no lo pide el diseño; se añade al test rojo como borde barato (la fórmula ya lo da).

## Discrepancias entre diseño y código

1. **Líneas de los tests.** El diseño cita las de `8ded42a`: `:1705`, `:1743` y el bloque `:1687-1797`. En `HEAD` son
   `:1785` (`test_notas_que_superan_el_limite_no_envian_la_redaccion`), `:1823`
   (`test_notas_que_caben_consultan_el_catalogo_una_vez_y_redactan`) y `:1745-1878`, y R4 las moverá otra vez. Manda el
   nombre.
2. **El test «ajustado» de 40 000 es rojo.** El diseño lo clasifica como ajuste, pero tras cambiar `_relleno(60_000)`
   por `_relleno(40_000)` falla antes del cambio (30 584 tokens con 4, bajo el umbral: 0 consultas). No contradice el
   diseño: es la prueba del criterio 3.
3. **Criterio 3 del diseño, «el error de hoy da 129 000 ≤ T ≤ 134 000».** «De hoy» se refiere al mismo test de hoy
   (notas de 100 000), no a la cifra de hoy, que es 75 584. Aquí se escribe como criterio 2.
4. **Criterio 1 del diseño (constante y función).** No es observable por el usuario; se conserva entero en el test
   rojo `test_estimar_tokens_usa_la_relacion_medida` y en el criterio 2 como regla de redondeo de T.
5. **Spec.** El diseño cita «Notas que no caben en el modelo» en `:195-208`; está en `:196-209`. Hoy la spec no nombra
   la relación caracteres/token, así que `/cerrar` la añade en vez de reemplazarla.
6. **Comentario de `:27`.** «estimación sin margen: con tokenizadores de Claude suele quedarse corta» deja de ser
   cierto; el diseño lo sustituye por el de la medición. El comentario de `:25` («historia 16») sigue valiendo.

## Cierre

Cerrada el 2026-11-22 con `/cerrar`. Tests: `./venv/bin/python -m pytest -q` pasa con 516 tests (514 de R4 más los dos tests nuevos). Code review: revisión del orquestador, listo para commit.

Delta de spec (`docs/specs/documentos-ia.md`, «Notas que no caben en el modelo», con `Origen` en esta historia): [MODIFICA]. Los tokens se estiman a 2,3 caracteres por token, redondeando hacia arriba; el umbral de 32 000 tokens sigue igual y equivale a unos 73 600 caracteres de petición. Con notas de 60 000 caracteres por parte, `gpt-4.1` ya no recibe la redacción.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: documentos-ia › Notas que no caben en el modelo] | Notas de 60 000 por parte con `gpt-4.1` (límite 64 000): no se envía la redacción, una sola consulta al catálogo, error con T entre 78 000 y 81 000 | `tests/test_asistente_ia.py:1927` (`test_notas_que_cabian_con_cuatro_caracteres_por_token_ya_no_se_envian`) | cumple |
| 2 | [MODIFICA: documentos-ia › Notas que no caben en el modelo] | Notas de 100 000 por parte: T entre 129 000 y 134 000, con la regla de redondeo (230 caracteres son 100 tokens, 231 son 101) | `tests/test_asistente_ia.py:1908` (`test_notas_que_superan_el_limite_no_envian_la_redaccion`), `:1883` (`test_estimar_tokens_usa_la_relacion_medida`) | cumple |
| 3 | [MODIFICA: documentos-ia › Notas que no caben en el modelo] | Notas de 40 000 por parte: el catálogo se consulta una vez y se envían la minuta y el resumen; notas cortas (2 partes) no consultan el catálogo; el umbral sigue en 32 000 tokens | `tests/test_asistente_ia.py:1964` (`test_notas_que_caben_consultan_el_catalogo_una_vez_y_redactan`), `:1890` (`test_notas_cortas_o_una_sola_parte_no_consultan_el_catalogo`) | cumple |

**Verificación:**

- `./venv/bin/python -m pytest -q`: 516 pasan.
- Los tests que deben ser rojos antes del cambio (`test_estimar_tokens_usa_la_relacion_medida`, `test_notas_que_cabian_con_cuatro_caracteres_por_token_ya_no_se_envian` y el de 40 000) no se volvieron a ejecutar en este cierre; el orquestador revisó el diff con los tests ya escritos.
- Verificación manual: no hace falta. Lo observable (si se envía la redacción, cuántas consultas al catálogo y el texto del error) lo cubren los tests con `httpx` simulado, sin peticiones reales.

**Pendientes aceptados:**

- `estimar_tokens` redondea `CARACTERES_POR_TOKEN` a una décima en la división entera. Si la constante pasa a tener dos decimales, hay que ajustar la función.
- La relación de 2,3 viene de una sola medición (164 993 caracteres = 70 318 tokens en `claude-haiku-5.5`, ≈ 2,35). Ajustarla con reuniones reales es la pregunta abierta 1 del diseño 07, no esta historia.
