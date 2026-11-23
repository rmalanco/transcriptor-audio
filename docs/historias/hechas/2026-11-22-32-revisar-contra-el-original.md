# 32 · Revisar contra la transcripción completa cuando cabe, y tratar el 401 del catálogo como falta de sesión

> Origen: `BACKLOG.md`, «Salud del código» #23 (carril L), historia R2b del diseño (carril M, la quinta de la serie
> R1 → R4 → R6 → R2a → R2b → R3). Depende de R2a (`docs/historias/31-una-consulta-al-catalogo.md`, aprobada y en
> implementación) y de R4 (`2a7a98b`); R1 (`22155b3`) y R6 (`5a6e024`) ya tienen commit. Reglas de oro 1, 3, 4, 5, 7 y
> 10 de `AGENTS.md`. Refinada con `/story` el 2026-11-22, sin usuario al otro lado: un orquestador aprueba en su nombre
> (ver «Supuestos»).
>
> — Diseño: docs/disenos/07-revision-contra-el-original.md §R2b

Líneas citadas: las de `HEAD` (`5a6e024`, con R6 y sin R2a). R2a está a medias en la copia de trabajo y mueve
`src/asistente_ia.py` (añade `_ConsultaDeLimite` y `_limite_del_modelo`) y `tests/test_asistente_ia.py`: manda el
nombre de la función o del test.

## Historia

Como usuario que activa la revisión de fidelidad en reuniones largas, quiero que la revisión compare la minuta o el
resumen con la transcripción completa siempre que quepa en el modelo, y que el documento diga contra qué se revisó,
para que un nombre, una cifra o una tarea que se coló al extraer las notas de cada parte se pueda corregir, y que un
token rechazado al consultar el catálogo me pida iniciar sesión en vez de seguir enviando la transcripción.

## Qué hace hoy el código

- `AsistenteIA._generar` (`src/asistente_ia.py:895-991`): con más de una parte, `texto, cortes_partes =
  self._notas_por_bloque(...)` (`:919`) **sustituye** la transcripción por las notas («Notas de la parte N:\n…», ver
  el `return` de `_notas_por_bloque`, `:893`). La revisión envía `PROMPT_REVISION.format(texto=texto,
  documento=documento)` (`:964`), es decir, las notas, y el progreso dice «Revisando fidelidad con las notas de las N
  partes…» (`:961-962`), antes del `try` de la revisión. Con una parte, «Revisando fidelidad con la transcripción…» y
  la revisión lleva la transcripción.
- `_cita_de_partes(partes, revisado)` (`:463-469`) añade, si `revisado`, « La revisión de fidelidad se hizo contra esas
  notas, no contra la transcripción.». `notas_de_la_aplicacion(...)` (`:512-549`, ya con `revision_descartada` y
  `repuestas` por palabra clave) la llama; `nota_de_notas(partes, revisado)` (`:552-555`, pública) envuelve a
  `notas_de_la_aplicacion`. `AsistenteIA._con_nota` (`:1023-1031`) calcula `revisado = self.revision_fidelidad and not
  d.error_revision and not d.revision_descartada`.
- `_Documento` (`:357-368`) no tiene `fuente_revision`. No existen `FuenteRevision` ni `_fuente_de_revision`.
- `AsistenteIA._comprobar_limite_de_entrada` (`:993-1021`) solo se llama para la redacción con varias partes. Tras R2a
  usa `_limite_del_modelo(consulta, cancelar)`, que captura `copilot.ErrorCopilot`, guarda `str(e)` en
  `consulta.error` y devuelve el límite `None` (la redacción sigue).
- `copilot._catalogo` (`src/copilot.py:324-334`) lanza `ErrorCopilot` (no `ErrorSesionCopilot`) ante un 401, con
  «La sesión de GitHub Copilot no es válida (401). Vuelve a iniciar sesión.». Por eso hoy un 401 del catálogo en la
  redacción solo deja un `WARNING` y se redacta (caso `"401"` de `test_sin_limite_conocido_se_redacta_como_hoy`).
  `ErrorSesionCopilot` ya existe (`:43-44`) y la lanza `abrir_sesion_auto` (`:460-461`), que lee `/models` por su
  cuenta y no pasa por `_catalogo`.
- `AsistenteIA._error_de_token_rechazado` (`src/asistente_ia.py:638-646`): con el token de la app u opencode invalida
  el propio y devuelve `ErrorSinSesionCopilot`; con `COPILOT_GITHUB_TOKEN` devuelve `ErrorAsistenteIA`.
  `_fallo_recuperable` trata `ErrorSinSesionCopilot` y `ErrorModeloIA` como no recuperables.
- Spec: `docs/specs/documentos-ia.md`, «Revisión de fidelidad contra las notas» (`:227-241`), «Notas que no caben en
  el modelo» (`:207-225`, tercer Given) y «Sesión rechazada por Copilot» (`:276-280`).

## Criterios de aceptación

Escenario común: `TEXTO2` = `"\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))` (1 439
caracteres; con `max_caracteres_bloque=900`, 2 partes de 720 y 719), notas simuladas «- Nota de una parte»,
`MINUTA_MODELO` como redacción, `revision_fidelidad=True`, modelo `gpt-4.1`. BASE = «> Nota de la aplicación: la
transcripción se procesó en 2 partes y este documento se redactó a partir de notas extraídas de cada parte, no de la
transcripción completa. Contrasta nombres, fechas, cifras y condiciones con la transcripción antes de darlo por
bueno.». Estimaciones con `estimar_tokens` (2,3 caracteres por token, medidas en `HEAD`): redacción de la minuta 1 021
tokens; revisión de la minuta con la transcripción 1 676; con las notas 1 086 (los tests las calculan, no las fijan).

- [ ] [MODIFICA: documentos-ia › Revisión de fidelidad contra las notas] Dado el escenario común sin red
  (`_prohibir_red`: la revisión, de 1 676 tokens, no llega al umbral de 32 000 y no consulta el catálogo), cuando genero
  la minuta, entonces el progreso incluye «Revisando fidelidad con la transcripción completa…», el cuerpo de la
  revisión (el que contiene «DOCUMENTO:») contiene cada línea de `TEXTO2` y no contiene «Notas de la parte», y la minuta
  termina (`endswith`) con BASE + « La revisión de fidelidad lo contrastó después con la transcripción completa, pero es
  automática: no sustituye a esa comprobación.». Lo mismo con el resumen que se genera después reutilizando las notas
  (2 peticiones nuevas: redacción y revisión). Si la revisión falla, se corta o se descarta, la nota de las partes es
  BASE sola, como hoy. Con una sola parte nada cambia («Revisando fidelidad con la transcripción…», sin nota). (antes:
  con varias partes la revisión recibía siempre las notas, el progreso decía «Revisando fidelidad con las notas de las
  2 partes…» y la nota terminaba en « La revisión de fidelidad se hizo contra esas notas, no contra la
  transcripción.»)
- [ ] [NUEVO] Dado el escenario común con `UMBRAL_COMPROBAR_LIMITE` parcheado a 500 (la redacción y la revisión
  consultan el límite), cuando genero la minuta:
  - con un catálogo de 100 000 tokens para `gpt-4.1`, el catálogo se consulta **una** vez en toda la generación y la
    revisión lleva la transcripción completa (criterio 1);
  - con 1 300 (la redacción, 1 021, cabe; la revisión con la transcripción, 1 676, no), la revisión lleva las notas
    («Notas de la parte 1», ninguna línea de `TEXTO2`), el progreso dice «Revisando fidelidad con las notas de las 2
    partes…», la minuta termina con BASE + « La revisión de fidelidad se hizo contra esas notas, no contra la
    transcripción.» y el registro (`INFO`) dice «La revisión con la transcripción completa suma unos T tokens y
    «gpt-4.1» admite 1300; se revisa con las notas de las 2 partes.», con T = la estimación de la revisión;
  - con un catálogo que falla por conexión (`httpx.ConnectError("sin conexión")`), el catálogo se consulta **una** vez
    en la generación (la redacción y la revisión comparten el fallo), la revisión lleva la transcripción y el registro
    contiene «No se pudo comprobar el límite de entrada de «gpt-4.1» para la revisión (No se pudo conectar con GitHub
    Copilot: sin conexión); se revisa con la transcripción completa.»; la generación siguiente vuelve a consultarlo (2
    en total);
  - con un catálogo sin el modelo (`_catalogo_con_limite("otro-modelo", 64000)`), una consulta, revisión con la
    transcripción y el registro «No se pudo comprobar el límite de entrada de «gpt-4.1» para la revisión: el catálogo no
    lo informa; se revisa con la transcripción completa.».
- [ ] [MODIFICA: documentos-ia › Notas que no caben en el modelo] Dado el escenario común con el token de la app y un
  catálogo que responde 401, cuando genero la minuta con el umbral parcheado a 1 200 (la redacción, 1 021, no consulta;
  la revisión, 1 676, sí), entonces sale `ErrorSinSesionCopilot` con «La sesión de GitHub Copilot caducó o fue revocada
  (401). Vuelve a iniciar sesión.», no se entrega documento y no se envía la revisión (3 cuerpos: 2 notas y la
  redacción); con el umbral a 500 sale la misma excepción **antes** de la redacción (2 cuerpos, solo notas). Fuera del
  asistente, `copilot.limites_de_entrada` ante un 401 lanza `copilot.ErrorSesionCopilot` con el texto de hoy, que
  sigue siendo un `ErrorCopilot`. (antes: un 401 del catálogo era un fallo más del catálogo: se registraba «No se pudo
  comprobar el límite de entrada…» y se redactaba como hoy)

Caso que dolería (tomado del diseño, riesgo 1 y hallazgo 2): que la nota diga «lo contrastó después con la
transcripción completa» sobre un documento cuya revisión no la recibió (fue contra las notas), falló o se descartó. Lo
cubren el criterio 2 (rama «no cabe» con la frase de hoy) y los guarda de revisión fallida y descartada con varias
partes, que comprueban con `endswith` que la nota termina en «…antes de darlo por bueno.».

## Cómo se verifican

Todo sin red en `tests/test_asistente_ia.py` y `tests/test_copilot.py` (regla 3). Dobles de
`tests/test_asistente_ia.py`: `_simular_chat` (`:973`), `_es_prompt_de_notas` (`:983`), `_prohibir_red` (`:45`),
`_simular_catalogo` (`:1866`, cuenta las consultas), `_catalogo_con_limite` (`:1879`), `_Respuesta({}, 401)` (`:8`),
`MINUTA_MODELO` y `RESUMEN_MODELO`. En los tests nuevos, la función `respuesta` de `_simular_chat` mira **primero** si el
último mensaje contiene «DOCUMENTO:» (la revisión, que desde R2b también lleva la transcripción) y, para ella, devuelve
`RESUMEN_MODELO` si el texto tras «DOCUMENTO:» contiene «## Resumen» y si no `MINUTA_MODELO`; después las notas
(`_es_prompt_de_notas`) y después «Redacta un resumen». El umbral se parchea con
`monkeypatch.setattr(asistente_ia, "UMBRAL_COMPROBAR_LIMITE", …)`; los registros, con `caplog` en el logger
`transcriptor.ia`.

- **Rojos** (fallan antes del cambio):
  - `test_revision_con_varias_partes_usa_la_transcripcion_completa` (criterio 1; **sustituye** a
    `test_revision_con_varias_partes_dice_que_revisa_contra_las_notas`, `:1069`, que se borra): progreso, cuerpo de la
    revisión con las 40 líneas de `TEXTO2` y sin «Notas de la parte», `endswith` de BASE + «contrastó».
  - `test_resumen_con_notas_reutilizadas_revisa_contra_la_transcripcion` (criterio 1): minuta y después resumen con el
    mismo asistente; del resumen, `len(nuevas) == 2`, ninguna de notas, la revisión con las líneas de `TEXTO2` y el
    `endswith` de BASE + «contrastó».
  - `test_nota_de_notas_con_revision_contra_la_transcripcion` (criterio 1, función pública):
    `nota_de_notas(2, True, fuente_revision="transcripcion")` termina en «bueno. La revisión de fidelidad lo contrastó
    después con la transcripción completa, pero es automática: no sustituye a esa comprobación.» y
    `nota_de_notas(2, False, fuente_revision="transcripcion")` es igual a `nota_de_notas(2, False)`.
  - `test_revision_que_cabe_consulta_el_catalogo_una_sola_vez` (criterio 2): umbral 500, límite 100 000,
    `len(consultas) == 1`, revisión con la transcripción.
  - `test_revision_que_no_cabe_vuelve_a_las_notas` (criterio 2): umbral 500, límite 1 300; cuerpo, progreso y
    `endswith` como hoy, y el `INFO` literal con `T == estimar_tokens(PROMPT_SISTEMA + PROMPT_REVISION.format(texto=TEXTO2,
    documento=MINUTA_MODELO))`. Es rojo **por el registro**: sin él pasaría hoy (ver «Discrepancias» 2).
  - `test_catalogo_caido_se_consulta_una_vez_y_se_revisa_con_la_transcripcion` (criterio 2): umbral 500, conexión
    caída; `len(consultas) == 1` tras la minuta, revisión con la transcripción, el `WARNING` literal; un
    `generar_resumen` después deja `len(consultas) == 2`.
  - `test_catalogo_sin_el_modelo_revisa_con_la_transcripcion` (criterio 2): umbral 500, `"otro-modelo"`; una consulta,
    revisión con la transcripción, el `WARNING` literal.
  - `test_401_del_catalogo_en_la_revision_es_falta_de_sesion_y_no_envia_la_revision` (criterio 3): umbral 1 200,
    `ErrorSinSesionCopilot` con su texto, `len(cuerpos) == 3`, ninguno con «DOCUMENTO:», `len(consultas) == 1`.
  - `test_401_del_catalogo_en_la_redaccion_es_falta_de_sesion` (criterio 3): umbral 500, misma excepción,
    `len(cuerpos) == 2` y los dos de notas.
  - En `tests/test_copilot.py`: `test_catalogo_con_401_es_error_de_sesion` (criterio 3): `httpx.get` simulado con
    `_Respuesta({}, 401)`; `copilot.limites_de_entrada(copilot.Sesion("gho_x"))` lanza `copilot.ErrorSesionCopilot`,
    `isinstance(e, copilot.ErrorCopilot)` y el texto «La sesión de GitHub Copilot no es válida (401). Vuelve a iniciar
    sesión.».
- **Se ajusta:** `test_sin_limite_conocido_se_redacta_como_hoy` (`:1977-1998`) pierde el parámetro `"401"` (pasa de 9
  a 8 casos): ahora es falta de sesión.
- **Se borra:** `test_revision_con_varias_partes_dice_que_revisa_contra_las_notas` (sustituido; su escenario revisa
  ahora con la transcripción).
- **Guarda** (pasan antes y después sin tocarlos): `test_una_sola_parte_no_lleva_nota_y_revisa_contra_la_transcripcion`
  (`:1088`), `test_nota_de_notas_dice_el_numero_de_partes` y `test_nota_de_notas_con_revision_anade_la_frase_de_la_revision`
  (`:947-959`, la frase de hoy con el valor por defecto), `test_401_durante_la_revision_no_entrega_documento` (`:882`),
  `test_fallo_en_la_revision_con_varias_partes_no_dice_que_se_reviso` (`:850`) y
  `test_revision_descartada_con_varias_partes_no_dice_que_se_reviso` (`:301`) (el caso que dolería), `test_la_nota_no_se_envia_a_copilot`
  (`:1028`, 4 cuerpos), `test_lo_repuesto_no_se_envia_a_copilot` (`:337`), `test_cancelar_durante_la_revision_no_entrega_documento`
  (`:868`), `test_auto_con_catalogo_caido_tambien_salta_las_familias_excluidas` (`:726`), `test_modelo_excluido_no_depende_del_catalogo`
  (`:623`), el resto del bloque de límite (`:1883-2018`) con los de R2a (incluida su guarda
  `test_registro_de_la_redaccion_sin_limite_no_cambia`), y en `tests/test_copilot.py` los que capturan
  `copilot.ErrorCopilot` (`test_listar_modelos_*`, `test_limites_de_entrada_del_catalogo`).
- Suite completa: `./venv/bin/python -m pytest -q` en verde; respecto a lo que deje R2a, +9 funciones de test (10 rojos
  menos el borrado) y +8 casos en el recuento de pytest (el parámetro `"401"` quitado resta uno).

**Verificación manual con Copilot simulado** (la hace `/pair` al terminar; sin red):

1. `TRANSCRIPTOR_LOG=DEBUG ./venv/bin/python - <<'EOF'` con un guion que: construye una transcripción **sintética** de
   al menos 160 000 caracteres (3 partes con el límite de 60 000) con la fecha «jueves» en una sola línea del centro;
   parchea `asistente_ia.httpx.stream` para que las notas devuelvan «- Luis enviará el informe el martes» en la parte de
   esa línea y la revisión devuelva la minuta recibida tras «DOCUMENTO:» con «martes» cambiado por «jueves»; parchea
   `asistente_ia.httpx.get` con un catálogo `{"claude-haiku-5.5": 936000, "gpt-4.1": 64000}`; y genera la minuta con
   `AsistenteIA(api_key="x", modelo=…, revision_fidelidad=True, max_caracteres_bloque=60000)`, imprimiendo el progreso.
2. Con `claude-haiku-5.5`: el registro muestra «Petición a GitHub Copilot (claude-haiku-5.5): N caracteres» con N ≥
   160 000 en la revisión, el progreso «Revisando fidelidad con la transcripción completa…», la minuta dice «jueves» y
   termina con la frase «contrastó».
3. Con `gpt-4.1`: la revisión estimada (unos 72 000 tokens) supera 64 000; el registro trae el `INFO` «…admite 64000;
   se revisa con las notas de las 3 partes.», el progreso «…con las notas de las 3 partes…», la petición de revisión no
   pasa de unos 10 000 caracteres y hay una sola consulta al catálogo.

**Comprobación real (opcional, pendiente de autorización):** la del diseño (transcripción sintética de ≥160 000
caracteres, `claude-haiku-5.5`, revisión activa; ver en el registro unos 165 000 caracteres y `tokens: entrada N`, y si
la minuta corrige el dato). Necesita **5** peticiones (3 notas, redacción y revisión) más la consulta al catálogo; el
usuario solo tiene autorizada una, reservada. No se hace sin una autorización nueva; sus resultados responden a las
preguntas abiertas 1 y 2 del diseño.

## Plan

- La generación conserva la transcripción original aparte de las notas; la redacción sigue usando las notas.
- Antes de revisar, y dentro del manejo de errores de la revisión, se decide la fuente: con una parte, la
  transcripción; con varias, se estima la revisión con la transcripción y, si pasa del umbral, se pregunta el límite
  con la misma consulta de la generación (R2a): cabe o sin dato → transcripción (con su registro); no cabe → notas,
  guardando estimación, límite y modelo para R3. El mensaje de progreso sale después de decidir.
- El documento recuerda la fuente con la que se revisó, y la nota de las partes elige la frase: «contrastó» con la
  transcripción, la de hoy con las notas, ninguna si no se revisó. Los parámetros nuevos son por palabra clave y con
  valor por defecto «notas», así los tests y las llamadas de hoy no cambian.
- El catálogo distingue el 401 como falta de sesión, y la pieza que pregunta el límite lo convierte en el error de
  token rechazado de siempre, antes de tratar cualquier otro fallo del catálogo: vale para la redacción y la revisión.
- Tests: primero los rojos en el orden de los criterios, después el código; borrar el test sustituido y quitar el caso
  `"401"`; los guarda sin tocar.

Archivos del `/pair` (lista cerrada, la del diseño): `src/asistente_ia.py` (`@dataclass class FuenteRevision` con
`tipo: str`, `texto: str`, `motivo: Optional[tuple[int, int, str]] = None`; `AsistenteIA._fuente_de_revision(self,
original: str, notas: str, documento: str, partes: int, consulta: _ConsultaDeLimite, cancelar:
Optional[threading.Event]) -> FuenteRevision`; `AsistenteIA._limite_del_modelo` con `except
copilot.ErrorSesionCopilot` → `raise self._error_de_token_rechazado() from e` antes del `except copilot.ErrorCopilot`;
`AsistenteIA._generar`; `_Documento.fuente_revision: str = "notas"` al final; `_cita_de_partes(partes, revisado, *,
fuente_revision: str = "notas")`; `nota_de_notas(partes, revisado, *, fuente_revision: str = "notas")`;
`notas_de_la_aplicacion(..., *, revision_descartada=None, repuestas=None, fuente_revision: str = "notas")`;
`AsistenteIA._con_nota`), `src/copilot.py` (`_catalogo`: 401 → `ErrorSesionCopilot`), `tests/test_asistente_ia.py`,
`tests/test_copilot.py`. `motivo_notas` (R3) **no** se añade a ninguna firma todavía. Si hace falta otro archivo, se
para y se vuelve al diseño.

Documentación que cambia (`/cerrar`): `docs/specs/documentos-ia.md` «Revisión de fidelidad contra las notas»
(`:227-241`, pasa a «Revisión de fidelidad con varias partes»: cabe o sin dato → transcripción y frase «contrastó»; no
cabe → notas y frase de hoy; su tercer Given deja de decir que el progreso «sigue diciendo …con las notas de las 2
partes…»), «Notas que no caben en el modelo» (`:220-222`: el 401 ya no redacta como hoy) y «Sesión rechazada por
Copilot» (`:276-280`: también al consultar el catálogo de límites); `src/EGM.md` (`:297-305`, «la revisión de
fidelidad compara contra esas notas», y la entrada de `copilot.py`, `:131-137` y `:254-256`: `_catalogo` lanza
`ErrorSesionCopilot` ante un 401). `BACKLOG.md` #23 sigue abierto (🟡) hasta R3.

## Fuera de alcance

- **R3:** decir en el progreso y en la nota **por qué** la revisión fue contra las notas (tokens, límite y modelo),
  `_Documento.motivo_notas` y el parámetro `motivo_notas`. En R2b `FuenteRevision.motivo` se rellena pero nadie lo lee.
- Reintentar contra las notas si Copilot rechaza (400) la revisión con la transcripción: sale la nota «no se pudo
  completar», como hoy (diseño, plan técnico, punto 3).
- Comprobar el límite con una sola parte, cambiar `UMBRAL_COMPROBAR_LIMITE`, `estimar_tokens` o el texto del error de
  la redacción.
- Recordar el fallo del catálogo entre generaciones; limitar los reintentos de `_completar` en la revisión grande.
- Activar `revision_fidelidad` por defecto (D6), la vista Configuración y la CLI.

## Supuestos

1. El orquestador aprobó criterios, firmas, textos y plan del diseño en nombre del usuario; esta historia no pregunta
   ni añade requisitos. «El caso que dolería» se toma del diseño.
2. R2a se toma de su historia (`docs/historias/31-una-consulta-al-catalogo.md`), aprobada y aún sin commit:
   `_ConsultaDeLimite(error: Optional[str] = None)`, `_limite_del_modelo(consulta, cancelar) -> tuple[str,
   Optional[int]]` (comprueba la cancelación, resuelve el modelo con `_modelo_para_peticion` y regla 7, guarda en
   `consulta.error` el `str(e)` del fallo) y `_generar` crea `consulta = _ConsultaDeLimite()`. Si el commit de R2a
   cambia algo de esto, manda R2a y se revisa esta historia antes del `/pair`.
3. El 401 se comprueba solo con el token de la app (`api_key="x"`, `rutas_aisladas`). Con `COPILOT_GITHUB_TOKEN`,
   `_error_de_token_rechazado` devuelve un `ErrorAsistenteIA` que la revisión trata como recuperable: el documento se
   entrega con «la revisión de fidelidad no se pudo completar (…)», igual que hoy con un 401 de `/chat/completions` en
   la revisión; en la redacción falla con el texto de la variable. No se añade test (ver «Discrepancias» 4).
4. Los textos de registro y de nota son los del diseño (plan técnico, puntos 3 y 4), literales; los números van sin
   separador de miles.

## Propuesta de división (a decidir por el orquestador)

La historia está en el límite: 10 tests rojos (más de ~8) y 3 firmas cambiadas (`_cita_de_partes`, `nota_de_notas`,
`notas_de_la_aplicacion`, todas por palabra clave). Los criterios son 3 y la lista de archivos es cerrada, así que
puede ir entera; si se prefiere un `/pair` más pequeño, se parte así, **en este orden**, con un commit cada una:

- **32a** (criterios 1 y 2; 7 rojos; solo `src/asistente_ia.py` y `tests/test_asistente_ia.py`): «Como usuario que
  activa la revisión de fidelidad en reuniones largas, quiero que la revisión compare el documento con la transcripción
  completa cuando cabe en el modelo, y con las notas cuando no, diciendo contra qué se revisó, para que lo inventado al
  extraer las notas se pueda corregir.»
- **32b** (criterio 3; 3 rojos y el ajuste del caso `"401"`; añade `src/copilot.py` y `tests/test_copilot.py`): «Como
  usuario con la sesión de Copilot caducada, quiero que un 401 al consultar el catálogo de límites me pida iniciar
  sesión en vez de seguir enviando la transcripción, para no gastar peticiones con un token que Copilot ya rechazó.»
  Entre 32a y 32b, un 401 del catálogo en la revisión se trata como catálogo caído (revisión con la transcripción), y
  el 401 de esa petición de chat ya da hoy `ErrorSinSesionCopilot`.

## Discrepancias entre diseño y código

1. **Líneas.** El diseño cita `8ded42a` (spec «Revisión de fidelidad contra las notas» 210-217, «Notas que no caben»
   204-206, «Sesión rechazada» 225-230; `test_revision_con_varias_partes_dice_que_revisa_contra_las_notas` `:873`;
   `test_sin_limite_conocido_se_redacta_como_hoy` `:1756`). En `HEAD` son `:227-241`, `:220-222`, `:276-280`, `:1069` y
   `:1988`; R2a las mueve otra vez. Manda el nombre.
2. **`test_revision_que_no_cabe_vuelve_a_las_notas` no sería rojo** con lo que el diseño le pide: la revisión contra las
   notas, su progreso y su frase son los de hoy, y el catálogo ya se consulta una vez (por la redacción). Se le añade el
   `INFO` literal del plan técnico (punto 3) para que falle antes del cambio.
3. **Estimación de la revisión con las notas.** El diseño da ≈ 995 tokens (prompt anterior a R4); con `HEAD` es 1 086.
   Sigue por debajo de 1 300, así que el escenario «no cabe» vale. Las demás coinciden: redacción 1 021, revisión con
   la transcripción 1 676 (el diseño, ≈ 1 700 con R4). Con el resumen: redacción 700, revisión 1 531 / 941.
4. **CUJ 6 y la variable de entorno.** El diseño dice que con un 401 del catálogo «la generación falla con el error de
   sesión de hoy (…), o el de la variable de entorno». En la revisión, el de la variable es `ErrorAsistenteIA`
   recuperable: no falla la generación, se entrega sin revisar con nota (igual que el 401 de chat de hoy, que es lo que
   el diseño toma como referencia). En la redacción sí falla. Ver «Supuestos» 3.
5. **Dos excepciones con nombre parecido.** El criterio 3 del diseño nombra `ErrorSinSesionCopilot` (de
   `asistente_ia`) y el plan `ErrorSesionCopilot` (de `copilot`): no es una errata, son dos clases y las dos existen; la
   primera sale de la segunda por `_error_de_token_rechazado`.
6. **Momento del progreso.** Hoy «Revisando fidelidad…» sale antes del `try`; como el texto depende de la fuente, pasa a
   salir después de decidirla. Mientras se consulta el catálogo (hasta 30 s de `timeout`) sigue visible el mensaje
   anterior, y si la decisión falla (401) no se llega a mostrar. El diseño no lo dice; no cambia ningún texto.
7. **`nota_de_notas` con `fuente_revision`.** El diseño fija la firma pero no le da test en R2b (R3 sí tiene
   `test_nota_de_notas_con_motivo`); se añade `test_nota_de_notas_con_revision_contra_la_transcripcion` por ser función
   pública.
8. **Efectos del 401 fuera del asistente.** `_catalogo` también lo usa `listar_modelos` (CLI `--copilot-modelos` y
   «↻» vía `cargar_opciones_de_modelo` → `modelos_economicos`); los dos capturan `ErrorCopilot` o `Exception` y muestran
   el mismo texto, así que no cambian. Nuevo efecto lateral en la generación: un 401 del catálogo invalida el token
   propio guardado (`copilot.invalidar_token`), como ya hace el 401 de chat.

## Sugerencias (a decidir)

- Las 7 funciones `respuesta` de los tests nuevos repiten la misma decisión («DOCUMENTO:» → minuta o resumen; notas;
  «Redacta un resumen»). Un auxiliar de test `_responder_con_revision(cuerpo)` junto a `_simular_chat` evitaría siete
  copias; hay señal concreta (hoy ya se repite en `:301`, `:337`, `:850`, `:892`).
- Un test con `COPILOT_GITHUB_TOKEN` y el catálogo con 401 en la revisión fijaría la discrepancia 4 (documento sin
  revisar con nota). No lo pide el diseño.

## Cierre

Spec: `docs/specs/documentos-ia.md`, «Revisión de fidelidad con varias partes» (sustituye a «contra las notas»), «Notas que no caben en el modelo», «Notas de la aplicación juntas» y «Sesión rechazada por Copilot» (`Origen`: esta historia). Historia dividida en 32a (criterios 1 y 2, commit `59ad79b`) y 32b (criterio 3, este commit).

| # | Marca | Criterio | Evidencia (`ruta:línea`) | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: documentos-ia › Revisión de fidelidad contra las notas] | Con varias partes, la revisión recibe la transcripción completa cuando cabe: progreso, cuerpo sin notas y nota con «lo contrastó» (también en el resumen con las notas reutilizadas); una sola parte no lleva nota | `tests/test_asistente_ia.py:1083` (`test_revision_con_varias_partes_usa_la_transcripcion_completa`), `:1100` (`test_resumen_con_notas_reutilizadas_revisa_contra_la_transcripcion`), `:962` (`test_nota_de_notas_con_revision_contra_la_transcripcion`), `:1127` (`test_una_sola_parte_no_lleva_nota_y_revisa_contra_la_transcripcion`) | cumple |
| 2 | [NUEVO] | Con el límite: si cabe, o no hay dato, revisa con la transcripción; si no cabe, con las notas y su frase de hoy; el catálogo se consulta una vez por generación; con catálogo caído o sin el modelo, transcripción y registro | `tests/test_asistente_ia.py:2020` (`test_revision_que_cabe_consulta_el_catalogo_una_sola_vez`), `:2031` (`test_revision_que_no_cabe_vuelve_a_las_notas`), `:2052` (`test_catalogo_caido_se_consulta_una_vez_y_se_revisa_con_la_transcripcion`), `:2068` (`test_catalogo_sin_el_modelo_revisa_con_la_transcripcion`) | cumple |
| 3 | [MODIFICA: documentos-ia › Notas que no caben en el modelo] | Un 401 del catálogo es falta de sesión, en la redacción y en la revisión: no se envía la petición pendiente y sale `ErrorSinSesionCopilot`; `copilot.limites_de_entrada` lanza `ErrorSesionCopilot` (sigue siendo `ErrorCopilot`) | `tests/test_asistente_ia.py:2167` (`test_401_del_catalogo_en_la_revision_es_falta_de_sesion_y_no_envia_la_revision`), `:2180` (`test_401_del_catalogo_en_la_redaccion_es_falta_de_sesion`), `tests/test_copilot.py:313` (`test_catalogo_con_401_es_error_de_sesion`); se ajusta `:2092` (`test_sin_limite_conocido_se_redacta_como_hoy`, sin el caso `"401"`) | cumple |

**Verificación**

- `./venv/bin/python -m pytest -q`: 528 pasan.
- Minuta de 2 partes revisada contra la transcripción completa. La nota final dice:

  > Nota de la aplicación: la transcripción se procesó en 2 partes y este documento se redactó a partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, cifras y condiciones con la transcripción antes de darlo por bueno. La revisión de fidelidad lo contrastó después con la transcripción completa, pero es automática: no sustituye a esa comprobación.

  Progreso: «Revisando fidelidad con la transcripción completa…».
- Mutante del orquestador (revisión siempre contra las notas): fallan los 6 tests de los criterios 1 y 2.
- Petición real del diseño 07 («Comprobación real», 2026-11-22, unos 165 000 caracteres): el modelo acepta y lee una petición de ese tamaño. No se hicieron más peticiones reales.
- Desviaciones aceptadas: algunos tests de 32a se vieron rojos solo contra el `HEAD` anterior; los dos tests de asistente de 32b se escribieron juntos (ambos vistos en rojo antes del código).

**Pendientes aceptados**

- `FuenteRevision.motivo` se rellena pero no lo lee nadie: lo usará R3 (`motivo_notas`).
- El 401 con `COPILOT_GITHUB_TOKEN` en la revisión no tiene test: la revisión lo entrega como nota de «la revisión de fidelidad no se pudo completar», no como error.
- El mensaje de progreso sale después de decidir la fuente. Mientras dura la consulta al catálogo (hasta 30 s) sigue visible el mensaje anterior, y si la decisión falla con 401 no llega a salir.
