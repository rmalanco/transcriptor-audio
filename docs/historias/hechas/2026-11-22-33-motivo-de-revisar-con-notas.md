# 33 · Decir por qué la revisión fue contra las notas

> Origen: `BACKLOG.md`, «Salud del código» #23 (carril L), historia R3 del diseño (carril S, la última de la serie
> R1 → R4 → R6 → R2a → R2b → R3). Depende de R2b: su parte 32a ya tiene commit (`59ad79b`, rellena
> `FuenteRevision.motivo`) y la 32b (401 del catálogo) está en implementación. Reglas de oro 3, 4, 5 y 7 de
> `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin usuario al otro lado: un orquestador aprueba en su nombre (ver
> «Supuestos»).
>
> — Diseño: docs/disenos/07-revision-contra-el-original.md §R3

Líneas citadas: las de `HEAD` (`59ad79b`). La 32b mueve ahora `src/asistente_ia.py` y `tests/test_asistente_ia.py`:
manda el nombre de la función o del test.

## Historia

Como usuario que activa la revisión de fidelidad en reuniones largas, quiero que, cuando la transcripción completa no
cabe en el modelo y la revisión se hace contra las notas, la línea de estado y la nota del documento digan por qué
(los tokens estimados, el límite y el modelo, también en modo `auto`), para saber qué modelo elegir si quiero que la
revisión vea la transcripción entera.

## Qué hace hoy el código

- `AsistenteIA._fuente_de_revision` (`src/asistente_ia.py:1062-1085`), en la rama «no cabe», ya devuelve
  `FuenteRevision("notas", notas, (estimado, limite, modelo))` y registra en `INFO` «La revisión con la transcripción
  completa suma unos %d tokens y «%s» admite %d; se revisa con las notas de las %d partes.». El `modelo` sale de
  `AsistenteIA._limite_del_modelo` (`:1020`), que lo resuelve con `_modelo_para_peticion`: en `auto`, el de la sesión
  (`gpt-4.1`), no «auto» ni `modelo_usado` («auto → gpt-4.1», `:651`).
- `AsistenteIA._generar` (`:914`) solo copia `fuente.tipo` (`:984`); `fuente.motivo` no lo lee nadie. El progreso
  (`:986-988`) dice «Revisando fidelidad con las notas de las 2 partes…», sin motivo.
- `_Documento` (`:358`) no tiene `motivo_notas`. `_cita_de_partes(partes, revisado, *, fuente_revision="notas")`
  (`:478`), `notas_de_la_aplicacion(..., *, fuente_revision="notas")` (`:530`) y `nota_de_notas(partes, revisado, *,
  fuente_revision="notas")` (`:571`) no aceptan motivo: con `"notas"` y `revisado` la nota termina en « La revisión de
  fidelidad se hizo contra esas notas, no contra la transcripción.».
- `AsistenteIA._con_nota` (`:1087`) calcula `revisado = self.revision_fidelidad and not d.error_revision and not
  d.revision_descartada` y pasa `fuente_revision`.
- `tests/test_asistente_ia.py`: `_simular_auto(monkeypatch, sesiones, catalogo)` (`:640`) arma un catálogo con
  `{"id", "supported_endpoints"}` sin límites; `test_revision_que_no_cabe_vuelve_a_las_notas` (`:2031`) comprueba el
  progreso y la nota de hoy y el registro `INFO`.

## Criterios de aceptación

Escenario «no cabe» (el de R2b): `TEXTO2` (`:1077`, 1 439 caracteres; con `max_caracteres_bloque=900`, 2 partes de 720
y 719), notas simuladas «- Nota de una parte», `MINUTA_MODELO` como redacción y como revisión
(`_responder_minuta_o_notas`, `:2016`), `revision_fidelidad=True`, `UMBRAL_COMPROBAR_LIMITE` parcheado a 500 y límite
de entrada de `gpt-4.1` = 1 300 en el catálogo simulado. Con `estimar_tokens` (2,3 caracteres por token) la redacción
suma 1 021 tokens (cabe) y la revisión con la transcripción, **T** = `estimar_tokens(PROMPT_SISTEMA +
PROMPT_REVISION.format(texto=TEXTO2, documento=MINUTA_MODELO))` = **1 676** en `HEAD` (no cabe). Los tests calculan T,
no lo fijan, y comprueban `T > 1300`. BASE = `BASE_DOS_PARTES` (`:1078`). Números sin separador de miles.

- [ ] [MODIFICA: documentos-ia › Revisión de fidelidad con varias partes] Dado el escenario «no cabe» con el modelo
  fijo `gpt-4.1`, cuando genero la minuta, entonces el progreso incluye «Revisando fidelidad con las notas de las 2
  partes (la transcripción completa no cabe en «gpt-4.1»)…» y la minuta termina (`endswith`) con «\n\n---\n\n» + BASE +
  « La revisión de fidelidad se hizo contra esas notas y no contra la transcripción completa, que suma unos 1676 tokens
  y supera los 1300 que admite «gpt-4.1».». (antes: el progreso decía «Revisando fidelidad con las notas de las 2
  partes…» y la nota terminaba en « La revisión de fidelidad se hizo contra esas notas, no contra la transcripción.»,
  sin motivo)
- [ ] [MODIFICA: documentos-ia › Revisión de fidelidad con varias partes] Dado el escenario «no cabe» y una revisión
  contra las notas que falla (500 en sus 4 intentos) o se descarta (devuelve la minuta sin «## Próximos pasos»),
  cuando genero la minuta, entonces el progreso sigue diciendo «Revisando fidelidad con las notas de las 2 partes (la
  transcripción completa no cabe en «gpt-4.1»)…», pero la nota de las partes es BASE sola: la minuta lleva la nota de
  revisión no completada o descartada antes de la de las partes, termina en «…antes de darlo por bueno.» y no contiene
  «La revisión de fidelidad se hizo» ni «1300». (antes: progreso sin motivo; la nota ya era BASE sola)
- [ ] [MODIFICA: documentos-ia › Revisión de fidelidad con varias partes] Dado el escenario «no cabe» en modo `auto`,
  con una sesión que propone `kimi-k3` (familia excluida) y ofrece `gpt-4.1`, cuando genero la minuta, entonces todas
  las peticiones van a `gpt-4.1`, y el progreso y la nota dicen «no cabe en «gpt-4.1»» y «que admite «gpt-4.1»» con los
  mismos T y 1300; ni el progreso ni la minuta contienen «auto». (antes: en `auto`, el progreso y la nota no nombraban
  ningún modelo)

Caso que dolería (diseño, riesgo 1 y tabla del punto 4): que la nota dé el motivo del límite, y con él dé a entender
que el documento se revisó, cuando la revisión falló o se descartó; o que nombre «auto», que no le dice al usuario qué
modelo no tenía contexto suficiente. Lo cubren los criterios 2 y 3.

## Cómo se verifican

Todo sin red en `tests/test_asistente_ia.py` (regla 3), con los dobles de hoy: `_simular_chat` (`:981`),
`_simular_chat_con_estados` (`:1262`), `_simular_catalogo` y `_catalogo_con_limite` (`:1905-1920`), `_simular_auto`
ampliado, `_responder_minuta_o_notas`, `MINUTA_MODELO`, `TEXTO2`, `BASE_DOS_PARTES`, y `monkeypatch.setattr(asistente_ia,
"UMBRAL_COMPROBAR_LIMITE", 500)`.

**Doble que se amplía.** `_simular_auto(monkeypatch, sesiones, catalogo, limites: Optional[dict] = None)`: si se pasa
`limites`, cada modelo del catálogo que esté en `limites` lleva `"capabilities": {"limits": {"max_prompt_tokens":
limites[id]}}`; los demás, como hoy. Sin `limites`, el catálogo es idéntico al de hoy.

**Rojos** (fallan antes del cambio):

1. `test_revision_contra_las_notas_dice_el_motivo_del_limite` (criterio 1): modelo `gpt-4.1`, catálogo
   `_catalogo_con_limite("gpt-4.1", 1300)`; calcula T con `estimar_tokens` y comprueba `T > 1300`, el progreso exacto y
   el `endswith` con `f"…que suma unos {T} tokens y supera los 1300 que admite «gpt-4.1»."`.
2. `test_revision_contra_las_notas_fallida_o_descartada_no_da_motivo_ni_dice_revisada` (criterio 2), parametrizado:
   `"falla"` (`_simular_chat_con_estados` devuelve 500 a la petición que contiene «DOCUMENTO:»; `_esperar` parcheado a
   no esperar; la minuta contiene «la revisión de fidelidad no se pudo completar (») y `"descartada"` (la revisión
   devuelve `MINUTA_MODELO.split("## Próximos pasos")[0].rstrip()`; la minuta contiene «se descartó porque quitaba
   secciones obligatorias»). En los dos: progreso con motivo, `minuta.endswith("\n\n---\n\n" … BASE)` con la nota de
   la revisión antes, sin «La revisión de fidelidad se hizo» ni «1300». Es rojo por el progreso; la parte de la nota ya
   pasa hoy y queda como guarda de que `_con_nota` solo pasa el motivo si `revisado`.
3. `test_revision_contra_las_notas_en_auto_nombra_el_modelo_de_la_sesion` (criterio 3): `_simular_auto` con la sesión
   `{"available_models": ["kimi-k3", "gpt-4.1"], "selected_model": "kimi-k3", "session_token": "st", "expires_at":
   9999999999}`, catálogo `{"kimi-k3": ["/chat/completions"], "gpt-4.1": ["/chat/completions"]}` y `limites={"gpt-4.1":
   1300}`; `_simular_chat` registra el modelo de cada cuerpo. Comprueba `set(modelos) == {"gpt-4.1"}`, progreso y
   `endswith` como en el 1 (mismo T), y que ni el progreso ni la minuta contienen «auto»; `asistente.modelo_usado ==
   "auto → gpt-4.1"` sigue igual.
4. `test_nota_de_notas_con_motivo` (función pública): `nota_de_notas(2, True, motivo_notas=(70000, 64000,
   "gpt-4.1"))` termina en «bueno. La revisión de fidelidad se hizo contra esas notas y no contra la transcripción
   completa, que suma unos 70000 tokens y supera los 64000 que admite «gpt-4.1».»; `nota_de_notas(2, False,
   motivo_notas=(70000, 64000, "gpt-4.1")) == nota_de_notas(2, False)`; con `fuente_revision="transcripcion"` y el
   mismo motivo, la frase es la de «contrastó» (diseño, punto 7).

**Se ajusta:** `test_revision_que_no_cabe_vuelve_a_las_notas` (de R2b): el progreso pasa a «Revisando fidelidad con las
notas de las 2 partes (la transcripción completa no cabe en «gpt-4.1»)…» y el `endswith` a la frase con motivo (ya
calcula `estimado`, que se reutiliza); la consulta única, el cuerpo con las notas y el registro `INFO` no cambian.

**Guardas** (pasan antes y después, sin tocarlos): `test_nota_de_notas_dice_el_numero_de_partes`,
`test_nota_de_notas_con_revision_anade_la_frase_de_la_revision` (sin motivo, la frase de hoy),
`test_nota_de_notas_con_revision_contra_la_transcripcion`, todos los `test_auto_*` (llaman a `_simular_auto` sin
`limites`), `test_fallo_en_la_revision_con_varias_partes_no_dice_que_se_reviso`,
`test_revision_descartada_con_varias_partes_no_dice_que_se_reviso`,
`test_revision_con_varias_partes_usa_la_transcripcion_completa`,
`test_revision_que_cabe_consulta_el_catalogo_una_sola_vez`,
`test_catalogo_caido_se_consulta_una_vez_y_se_revisa_con_la_transcripcion`,
`test_catalogo_sin_el_modelo_revisa_con_la_transcripcion` y los de la 32b.

`./venv/bin/python -m pytest -q` en verde, sin red.

## Plan

- La generación guarda en el documento el motivo que la decisión de la fuente ya calcula (tokens estimados, límite y
  modelo) cuando la revisión va contra las notas.
- La línea de estado de la revisión contra las notas añade «(la transcripción completa no cabe en «modelo»)», con el
  modelo del motivo, que en `auto` es el de la sesión.
- La frase de la nota de las partes elige, si el documento se revisó: «contrastó» con la transcripción; con las notas y
  motivo, la frase con tokens, límite y modelo; con las notas sin motivo, la de hoy. Sin revisión completada no hay
  frase ni motivo.
- El parámetro nuevo es por palabra clave y con valor por defecto vacío en las tres funciones de la nota, así las
  llamadas y los tests de hoy no cambian.
- Tests: primero el doble de `auto` con límites y los rojos en el orden de los criterios; después el código; al final,
  ajustar el test de R2b.

Archivos del `/pair` (lista cerrada, la del diseño más `nota_de_notas`, ver «Discrepancias» 1): `src/asistente_ia.py`
(`_Documento.motivo_notas: Optional[tuple[int, int, str]] = None`, al final; `AsistenteIA._generar` copia
`fuente.motivo` y arma el progreso; `_cita_de_partes(partes, revisado, *, fuente_revision="notas", motivo_notas=None)`;
`notas_de_la_aplicacion(..., *, revision_descartada=None, repuestas=None, fuente_revision="notas",
motivo_notas=None)`; `nota_de_notas(partes, revisado, *, fuente_revision="notas", motivo_notas=None)`;
`AsistenteIA._con_nota` pasa `motivo_notas=d.motivo_notas`, que solo se usa si `revisado`) y `tests/test_asistente_ia.py`
(incluido `_simular_auto`). `_fuente_de_revision`, `FuenteRevision` y `src/copilot.py` no cambian. Si hace falta otro
archivo, se para y se vuelve al diseño.

Documentación que cambia (`/cerrar`): `docs/specs/documentos-ia.md` «Revisión de fidelidad con varias partes» (la que
deja R2b al cerrarse; hoy aún se llama «Revisión de fidelidad contra las notas», `:227-241`): la rama «no cabe» con el
progreso y la frase con motivo, y que sin revisión completada no hay motivo; `src/EGM.md` (`:298-310`, revisión con
varias partes: `_Documento.motivo_notas` y el parámetro `motivo_notas`). `BACKLOG.md` #23 pasa a ✅ si R2b ya está
cerrada.

## Fuera de alcance

- Cambiar cuándo se revisa contra las notas, `_fuente_de_revision`, `estimar_tokens`, `UMBRAL_COMPROBAR_LIMITE` o el
  registro `INFO` de R2b.
- Reintentar contra las notas ante un 400 por longitud; comprobar el límite con una sola parte.
- Mostrar `modelo_usado` («auto → …») en la nota o el progreso, o cambiar lo que guarda el historial.
- Sugerir en la nota otro modelo con más contexto (el error de la redacción sí lo hace; la nota no, según el diseño).
- El 401 del catálogo (32b) y cualquier cambio en `src/copilot.py`.
- Separador de miles en los números.

## Supuestos

1. El orquestador aprobó criterios, textos, firmas y plan del diseño en nombre del usuario; la historia no pregunta ni
   añade requisitos. «El caso que dolería» se toma del diseño.
2. La 32b se cierra antes de empezar esta historia y no toca `_generar`, `_cita_de_partes`, `notas_de_la_aplicacion`,
   `nota_de_notas`, `_con_nota` ni `_simular_auto`. Si los toca, manda su commit y se revisan las líneas citadas.
3. El progreso con motivo se emite también cuando la revisión falla o se descarta después (tabla del punto 4: «la de
   su caso»): se emite antes de enviar la revisión, y su resultado aún no se conoce.
4. Textos literales del diseño (plan técnico, punto 4, fila «N partes, no cabe (R3)»).

## Discrepancias entre diseño y código

1. **Lista cerrada sin `nota_de_notas`.** El diseño (§R3, «Archivos») no la nombra, pero su punto 7 le da
   `motivo_notas` y el test rojo `test_nota_de_notas_con_motivo` la llama con ese parámetro. Se añade a la lista (mismo
   archivo, sin archivo nuevo).
2. **Un «rojo» que ya pasa.** El criterio 2 del diseño solo habla de la nota, que ya es BASE sola en `HEAD` (R1 y
   32a): ese test pasaría antes del cambio. Para que sea rojo, comprueba también el progreso con motivo (que el diseño
   da como «la de su caso»).
3. **`_simular_auto` con `limites[id]`.** Con el `limites[id]` literal del diseño, un modelo del catálogo sin límite
   (como `kimi-k3` en el criterio 3) daría `KeyError`. Se precisa: solo llevan `capabilities` los modelos que estén en
   `limites`.
4. **Sesión de `auto`.** El diseño pide «misma forma de sesión que `test_auto_envia_todas_las_peticiones_al_modelo_autorizado`»
   pero que elija `gpt-4.1` (ese test elige `gpt-5.4`). Se usa la misma forma (propuesto excluido, otro compatible)
   con `kimi-k3` → `gpt-4.1`.
5. **Estimaciones.** El diseño («Dobles de test») da ≈ 1 585 / ≈ 1 700 tokens para la revisión con la transcripción;
   en `HEAD` `estimar_tokens` da 1 676 (lo que ya dice el comentario de `test_revision_que_no_cabe_vuelve_a_las_notas`).
   No cambia nada: los tests calculan T.
6. **El motivo ya nombra el modelo de la sesión.** `_limite_del_modelo` resuelve el modelo con `_modelo_para_peticion`,
   así que en `auto` `FuenteRevision.motivo` ya trae `gpt-4.1`. El criterio 3 protege que la implementación use el
   motivo y no `self.modelo` («auto») ni `modelo_usado`.
7. **Frase de hoy inalcanzable desde `_generar`.** Tras R3, toda revisión contra las notas lleva motivo; la frase sin
   motivo («…, no contra la transcripción.») solo sale llamando a las funciones públicas sin `motivo_notas` (guarda
   `test_nota_de_notas_con_revision_anade_la_frase_de_la_revision`). El diseño (punto 7) la conserva así.
8. **Líneas citadas del diseño.** `tests/test_asistente_ia.py:751-763` (tests de `nota_de_notas`) están hoy en
   `:947-968`; `_simular_auto` en `:640` (no `:444-450`); `src/EGM.md:297-302` es hoy `:298-310`. La sección de spec
   «Revisión de fidelidad con varias partes» aún no existe: la crea el `/cerrar` de R2b.

## Cierre

Spec: `docs/specs/documentos-ia.md`, «Revisión de fidelidad con varias partes» (`Origen`: esta historia). Contrato: `src/EGM.md`, `FuenteRevision.motivo`, `_Documento.motivo_notas` y el parámetro `motivo_notas` de `_cita_de_partes`, `notas_de_la_aplicacion` y `nota_de_notas`.

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: documentos-ia › Revisión de fidelidad con varias partes] | Escenario «no cabe» con `gpt-4.1`: el progreso dice «(la transcripción completa no cabe en «gpt-4.1»)…» y la minuta termina con la frase de tokens, límite y modelo | `tests/test_asistente_ia.py:2073` (`test_revision_contra_las_notas_dice_el_motivo_del_limite`); código: `src/asistente_ia.py:994`, `:998-999` (progreso), `:487-490` (frase) | cumple |
| 2 | [MODIFICA: documentos-ia › Revisión de fidelidad con varias partes] | Revisión contra las notas que falla o se descarta: el progreso sigue con el motivo; la nota de las partes es BASE sola, sin frase de revisión ni «1300» | `tests/test_asistente_ia.py:2094` (`test_revision_contra_las_notas_fallida_o_descartada_no_da_motivo_ni_dice_revisada`, parametrizado «falla» y «descartada»); código: `src/asistente_ia.py:1105` (`revisado` excluye fallos y descartes), `:487` (la frase con motivo solo si `revisado`) | cumple |
| 3 | [MODIFICA: documentos-ia › Revisión de fidelidad con varias partes] | En `auto`, con `kimi-k3` excluido y `gpt-4.1` autorizado: todas las peticiones van a `gpt-4.1`; progreso y nota nombran `gpt-4.1`; ni el progreso ni la minuta dicen «auto» | `tests/test_asistente_ia.py:2117` (`test_revision_contra_las_notas_en_auto_nombra_el_modelo_de_la_sesion`); código: `src/asistente_ia.py:1099` (`FuenteRevision` con el modelo de `_limite_del_modelo`) | cumple |

**Verificación**

- `./venv/bin/python -m pytest -q`: 533 pasan, sin red.
- `test_revision_que_no_cabe_vuelve_a_las_notas` (`tests/test_asistente_ia.py:2050`) se ajustó al motivo. La consulta única, el cuerpo con las notas y el registro `INFO` no cambian.
- Textos del escenario «no cabe», tal como los asertan `test_revision_que_no_cabe_vuelve_a_las_notas` y `test_revision_contra_las_notas_dice_el_motivo_del_limite`:
  - Progreso: «Revisando fidelidad con las notas de las 2 partes (la transcripción completa no cabe en «gpt-4.1»)…»
  - Nota: «> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento se redactó a partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, cifras y condiciones con la transcripción antes de darlo por bueno. La revisión de fidelidad se hizo contra esas notas y no contra la transcripción completa, que suma unos 1676 tokens y supera los 1300 que admite «gpt-4.1».»
- Desviaciones aceptadas: los tests de los criterios 2 y 3 se vieron rojos contra `HEAD` (el código del criterio 1 los cubría a la vez). El `endswith` del criterio 2 comprueba BASE con su nota de revisión antes, y el orden de las notas (`minuta.index(nota) < minuta.index(BASE_DOS_PARTES)`).

**Pendientes aceptados**

- El progreso con motivo sale antes de conocer el resultado de la revisión. Si la revisión falla o se descarta, la línea de estado ya dijo el motivo, y la nota no lo repite (supuesto 3 de la historia).
- `nota_de_notas(partes, revisado)` sin `motivo_notas` (la frase de hoy) ya no la alcanza `AsistenteIA._generar`. Se conserva como API y la cubre `test_nota_de_notas_con_revision_anade_la_frase_de_la_revision` (discrepancia 7).
