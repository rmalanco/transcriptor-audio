# Revisión de fidelidad contra la transcripción original

*   **Autor:** rmalanco
*   **Estado:** Implementado el 2026-11-22 (historias 28 a 33 de `docs/historias/hechas/`); R5 queda fuera (D5).
*   **Fecha:** 2026-11-22
*   **Origen:** `BACKLOG.md`, «Salud del código» #23 (carril L), hallazgo A-05 de `audit_report.md` (salida «revisar
    contra el original»), aceptado en `goldfish_review_report.md` (fila 10: «Afecta a la regla de fidelidad de la
    minuta»). Historia derivada de `docs/historias/hechas/2026-11-22-06-revision-de-fidelidad.md` («Supuestos» 2).

Las líneas citadas son las del commit `8ded42a`. Si las líneas se mueven, manda el nombre de la función.

--------------------------------------------------------------------------------

## Resumen

Con una transcripción de más de `ia.max_caracteres_bloque` caracteres (60 000 por defecto, unos 70 minutos de
reunión), la app extrae notas de cada parte, redacta la minuta o el resumen a partir de esas notas y, si
`ia.revision_fidelidad` está activa, revisa el documento **contra las mismas notas**. Un nombre, una cifra o una tarea
que el modelo inventó al extraer las notas llega a la minuta y la revisión no puede verlo, porque su fuente ya trae el
error. Hoy la app lo advierte con una nota al final del documento (historia 06), pero no lo corrige.

Este diseño hace que, con varias partes, la revisión reciba la **transcripción completa** cuando cabe en el límite
de entrada del modelo según el catálogo de Copilot (`max_prompt_tokens`), y que, cuando no cabe, revise contra las
notas y lo diga en el documento con el motivo. Según el catálogo del 2026-11-22, con `claude-haiku-5.5` (936 000
tokens de entrada) cabe una transcripción de unos 2,1 millones de caracteres; con `gpt-4.1` (64 000), de unos 140 000
(unas 2 h 40 min). Una petición real del 2026-11-22 confirmó que `claude-haiku-5.5` lee entera una petición de 165 000
caracteres y midió **unos 2,35 caracteres por token** («Comprobación real»), así que todas las estimaciones usan 2,3.

Añade tres arreglos que hoy faltan: una revisión descartada no cuenta como revisada; la revisión puede quitar tareas y
acuerdos que la transcripción no respalda, y la app **los repone marcados** para que el usuario los compruebe (ninguna
fila desaparece sin que lo vea); y la estimación de tokens de la redacción pasa de 4 a 2,3 caracteres por token, porque
la de hoy se queda corta.

## El problema

### Qué hace hoy el código

`AsistenteIA._generar` (`src/asistente_ia.py:703-793`):

1.  `dividir_texto(texto, max_caracteres_bloque)` parte la transcripción en bloques parejos (línea 721).
2.  Con más de un bloque, `_notas_por_bloque` pide en paralelo unas notas por parte y **sustituye `texto` por las
    notas** (línea 727: `texto, cortes_partes = self._notas_por_bloque(...)`). Desde ahí la transcripción original ya
    no existe dentro de `_generar`.
3.  Redacta el documento con `plantilla.format(texto=texto)`, es decir, con las notas (línea 731), tras comprobar que
    las notas caben en el modelo (`_comprobar_limite_de_entrada`, líneas 795-823).
4.  Si `revision_fidelidad` está activa, envía `PROMPT_REVISION.format(texto=texto, documento=documento)` (línea 770):
    otra vez las notas, bajo el título «TRANSCRIPCIÓN». El mensaje de progreso ya dice la verdad («Revisando fidelidad
    con las notas de las N partes…», línea 767) y `_con_nota` añade «La revisión de fidelidad se hizo contra esas
    notas, no contra la transcripción.» (`_cita_de_partes`, líneas 300-306).
5.  La revisión se acepta solo si no deja más secciones sin cubrir y, en la minuta, si no deja menos filas de tareas
    ni menos viñetas de acuerdos (líneas 779-787, punto #24). Si no se acepta, se conserva el documento anterior **sin
    registrar que se descartó**.

### Cuatro defectos, no uno

1.  **La fuente de la revisión es la copia, no el original** (A-05). Es lo que pide el punto #23.
2.  **Una revisión descartada cuenta como revisada.** `_con_nota` calcula `revisado = self.revision_fidelidad and not
    d.error_revision` (línea 828). Si la revisión se descartó, el documento no tiene ninguna corrección suya, pero la
    nota de las partes dice «La revisión de fidelidad se hizo contra esas notas»; con una sola parte no hay nota y el
    usuario no sabe nada. La historia 06 lo dejó como **pendiente aceptado** («La frase sobre la revisión aparece
    siempre que la revisión de fidelidad está activada, aunque su resultado se descartara por perder secciones»,
    `docs/historias/hechas/2026-11-22-06-revision-de-fidelidad.md`, «Pendientes aceptados»); este diseño lo cierra.
3.  **La revisión no puede quitar una tarea inventada.** `PROMPT_REVISION` (líneas 97-115) pide corregir «Datos que
    no aparecen en la transcripción (nombres, fechas, cifras, tareas)» y a la vez «no elimines secciones ni tareas».
    Y si el modelo la quita, la regla del punto #24 descarta la revisión entera. El caso que motiva el punto #23 (una
    nota de parte que atribuye a Ana una tarea que nadie dijo, criterio 2 de la historia 06) **no se arreglaría solo
    con cambiar la fuente**.
4.  **La estimación de tokens se queda corta.** `CARACTERES_POR_TOKEN = 4` (línea 27) decide si se consulta el
    catálogo y si la redacción cabe. La comprobación real midió unos 2,35 caracteres por token: con 4, la app cree
    que una petición ocupa un 41 % menos de lo que ocupa, y puede enviar una redacción que Copilot rechace.

### Comprobación real (2026-11-22)

Autorizada por el usuario y hecha por el orquestador: **una** petición a `claude-haiku-5.5` por `/chat/completions`
(streaming) con una transcripción **sintética** en español (nunca una reunión real) de 163 771 caracteres: 1 300 líneas
de diálogo con nombres, cifras y temas variados, y tres claves plantadas al principio, en medio y al final.

| Dato | Valor |
|---|---|
| Caracteres enviados (registro, con `PROMPT_SISTEMA` y la instrucción) | 164 993 |
| Respuesta | HTTP 200 en 3,9 s, `fin=stop`, sin corte |
| Contenido | «AZUL-17, VERDE-42, ROJO-93»: las tres claves, en orden |
| Uso | entrada **70 318 tokens**, salida 256 |
| Relación medida | **≈ 2,35 caracteres por token** |

Conclusiones: (1) el modelo leyó la petición entera, incluido el centro; eso prueba que la lee, no que detecte un dato
inventado en ella (pregunta abierta 2). (2) Ni el 4 de hoy ni el 3 del borrador sirven. El texto sintético tiene
muchas cifras y nombres, que tokenizan peor que el español corrido, así que una reunión real puede dar algo más de
2,35; se adopta **2,3** (un 2 % por debajo de lo medido) para la redacción y para la revisión, y la pregunta abierta 1
lo ajusta con registros reales.

### Tamaños y tokens

Datos del código: `PROMPT_SISTEMA` 1 030 caracteres, `PROMPT_NOTAS_BLOQUE` 350, `PROMPT_MINUTA` 1 235,
`PROMPT_RESUMEN` 505, `PROMPT_REVISION` 725 (medidos en `8ded42a`; R4 le añade unos 250). Divisiones medidas con
`dividir_texto` y el límite de 60 000: 80 000 caracteres dan 2 partes (40 023 y 39 977); 160 000 dan 3 (~53 300).
Supuestos **sin medir**, heredados de la historia 06: unas 890 letras por minuto de habla (90 min ≈ 80 000
caracteres), unas notas de ~8 000 caracteres por parte y una minuta de ~5 000. Tokens a 2,3 caracteres por token.

| Reunión | Partes | Revisión de hoy (contra notas) | Revisión contra la transcripción | Entrada de la minuta con revisión: hoy → propuesta |
|---|---|---|---|---|
| 90 min (80 000 car.) | 2 | ~22 800 car. (~9 900 tokens) | ~86 800 car. (~37 700 tokens) | ~53 900 → ~81 700 tokens (+52 %) |
| 3 h (160 000 car.) | 3 | ~30 800 car. (~13 400 tokens) | ~166 800 car. (~72 500 tokens) | ~96 200 → ~155 300 tokens (+61 %) |
| 4 h (215 000 car.) | 4 | ~38 800 car. (~16 900 tokens) | ~221 800 car. (~96 400 tokens) | — |

El número de peticiones **no cambia**: la revisión sigue siendo una sola petición. Lo que crece son los tokens de
entrada de esa petición. Con 2,3 caracteres por token, el umbral de `UMBRAL_COMPROBAR_LIMITE` (32 000 tokens) equivale
a unos 73 600 caracteres de petición: casi toda revisión de varias partes lo supera y consulta el catálogo, una vez por
asistente (el resultado se guarda en `self._limites`).

Dónde deja de caber la revisión entera (límite × 2,3, menos ~7 000 caracteres de prompts y documento):

| Modelo (catálogo del 2026-11-22) | `max_prompt_tokens` | Transcripción máxima aproximada |
|---|---|---|
| `claude-haiku-5.5`, `claude-sonnet-5.5` | 936 000 | ~2,1 millones de caracteres (~40 h) |
| `claude-haiku-4.5` | 128 000 | ~287 000 caracteres (~5 h 20 min) |
| `gpt-4.1` | 64 000 | ~140 000 caracteres (~2 h 40 min) |

**Coste.** El usuario no sabe si su cuenta factura por petición o por token, así que el diseño supone el caso caro:
**por token de entrada**. La app ya modela ese precio: `copilot.py:373-399` (`PRECIO_MAX_ECONOMICO`, `precio_entrada`)
lee `billing.token_prices.default.input_price` en unidades de Copilot por millón de tokens, con referencias gpt-4.1 =
0, claude-haiku-5.5 = 10, claude-sonnet-5.5 = 200. Coste de entrada de una minuta con la revisión activa (solo
entrada; la salida no cambia):

| Modelo | 90 min: hoy → propuesta | 3 h: hoy → propuesta | Solo la revisión, 3 h: hoy → propuesta |
|---|---|---|---|
| `gpt-4.1` (0) | 0 → 0 | 0 → 0 (la revisión no cabe: va contra las notas) | 0 → 0 |
| `claude-haiku-5.5` (10) | ~0,54 → ~0,82 | ~0,96 → ~1,55 | ~0,13 → ~0,73 |
| `claude-sonnet-5.5` (200) | ~10,8 → ~16,3 | ~19,2 → ~31,1 | ~2,7 → ~14,5 |

Si la cuenta factura por petición, el coste no cambia (misma cantidad de peticiones). Que las peticiones `agent` no
cuenten como premium lo dice `docs/integracion-copilot.md`, sin verificar; el diseño no se apoya en ello.

**Valor por defecto.** `config/settings.yaml` trae `revision_fidelidad: false` (y `configuracion.py` también usa
`False` sin la clave); el constructor de `AsistenteIA` tiene `True`, pero la ventana siempre pasa el de la
configuración (`flujo_documentos.argumentos_asistente`). Con la configuración de fábrica **ninguna** minuta se revisa,
y así sigue (D6): este diseño solo cambia algo para quien active la revisión, salvo R6 (estimación de tokens de la
redacción), que vale para todos.

## Objetivos

1.  Con varias partes, la revisión de fidelidad recibe la transcripción original completa siempre que la petición
    estimada quepa en el límite de entrada del modelo que se va a usar, según el catálogo.
2.  Cuando no cabe, la app no envía esa petición, revisa contra las notas y el documento dice que la revisión no fue
    contra la transcripción y por qué (tokens estimados, límite y modelo).
3.  Ningún documento dice que se revisó si la revisión falló, se cortó o se descartó.
4.  Lo que la revisión quitó de la tabla de tareas o de los acuerdos vuelve al documento, marcado, y una nota lo
    lista: ninguna fila desaparece sin que el usuario lo vea.
5.  La estimación de tokens usa la relación medida (2,3 caracteres por token).
6.  Todo se comprueba con tests sin red (`httpx.stream` y `httpx.get` simulados, regla 3).

## Fuera de alcance

*   Cambiar cómo se redacta el documento (notas por parte y redacción sobre las notas). Ver la alternativa D.
*   Revisar por partes, con trazabilidad bloque → dato o con citas literales en las notas (alternativas B, E y G):
    mejoras futuras.
*   La verificación sin IA de cifras, nombres y fechas (alternativa C, antes historia R5): fuera de esta ronda (D5);
    necesita medir antes sus falsos positivos.
*   **Tareas omitidas.** La revisión corrige y quita; no añade. Una tarea que se dijo y la minuta no recoge sigue
    faltando, con o sin este diseño.
*   **Secciones.** El aviso de lo repuesto cubre tareas y acuerdos. Una revisión que pierde secciones se descarta
    entera, como hoy, con la nota de R1.
*   Soporte de `/responses` (regla 10) y cualquier otro proveedor (regla 1).
*   Cambiar `UMBRAL_COMPROBAR_LIMITE` (sigue en 32 000 tokens estimados).
*   Activar `revision_fidelidad` por defecto (D6) y cambiar la vista Configuración: la revisión sigue siendo un solo
    interruptor.
*   Limitar los reintentos de `_completar` en la revisión grande (hallazgo 9 de la revisión: mejora futura).
*   La CLI, que no genera documentos. Rehacer documentos generados antes de este cambio.

## Preguntas abiertas

1.  **Relación real caracteres/token con reuniones reales.** Medida una vez con texto sintético (2,35). La app ya
    escribe en el registro `tokens: entrada N` de cada respuesta (`asistente_ia.py:583`) junto a los caracteres
    enviados (línea 517): con dos o tres registros de generaciones reales del usuario se ajusta `CARACTERES_POR_TOKEN`.
2.  **Si una revisión con 160 000 caracteres de contexto detecta un dato inventado** o lo pasa por alto. La
    comprobación real prueba que el modelo lee el centro, no que lo contraste. Se mide con la verificación manual de R2b.
3.  **Si la cuenta factura por petición o por token.** Se puede ver en la página de uso de Copilot del usuario; el
    diseño ya supone el caso caro.

## Recorridos críticos (CUJ)

### CUJ 1: reunión de 90 minutos con un modelo de contexto grande

*   **Given**: `claude-haiku-5.5`, `revision_fidelidad: true`, transcripción de 80 000 caracteres (2 partes); las
    notas de la parte 2 dicen «Luis enviará el informe el martes» y la transcripción dice «Luis enviará el informe el
    jueves».
*   **When**: genero la minuta.
*   **Then**: la revisión estimada (~37 700 tokens) supera el umbral, así que se consulta el catálogo (si no estaba ya
    en memoria): 936 000, cabe. La línea de estado dice «Revisando fidelidad con la transcripción completa…»; la
    petición de revisión contiene todas las líneas de la transcripción y no las notas; si Copilot corrige la fecha, la
    minuta dice «jueves» y termina con la nota de las partes que dice que la revisión «lo contrastó después con la
    transcripción completa, pero es automática».

### CUJ 2: reunión de 3 horas con `gpt-4.1`

*   **Given**: `gpt-4.1` (64 000 tokens de entrada), revisión activa, transcripción de 160 000 caracteres (3 partes).
*   **When**: genero la minuta.
*   **Then**: la redacción (notas de ~24 000 caracteres) cabe; no sale ninguna petición con la transcripción entera;
    la línea de estado dice «Revisando fidelidad con las notas de las 3 partes (la transcripción completa no cabe en
    «gpt-4.1»)…»; la nota de las partes dice que la revisión se hizo contra las notas porque la transcripción completa
    suma unos 72 500 tokens y «gpt-4.1» admite 64 000. El catálogo se consulta una sola vez en toda la generación.

### CUJ 3: la revisión quita una tarea

*   **Given**: revisión activa (con una o varias partes) y una minuta con las filas «Enviar las cifras de octubre |
    Ana» (que la transcripción no respalda) y «Revisar el plan | Luis».
*   **When**: la revisión devuelve la minuta sin la primera fila y con una condición corregida.
*   **Then**: la minuta lleva la corrección de la condición (la revisión se aplica), la fila vuelve al final de la
    tabla como «| Enviar las cifras de octubre [comprobar] | Ana | … |» y la minuta termina con «> Nota de la
    aplicación: la revisión de fidelidad quiso quitar de la minuta lo siguiente por no encontrarlo en la transcripción;
    la app lo ha repuesto marcado con «[comprobar]»: «Enviar las cifras de octubre (Ana)». Compruébalo con la
    transcripción y bórralo si no se dijo.».

### CUJ 4: la revisión está desactivada

*   **Given**: `revision_fidelidad: false` (el valor de fábrica).
*   **When**: genero la minuta de una transcripción de 2 partes.
*   **Then**: todo es como hoy: 3 peticiones, la nota de las partes sin frase de revisión. Solo cambia (R6) la
    estimación de tokens con la que se decide si la redacción cabe.

### CUJ 5: el catálogo no responde o no trae el dato

*   **Given**: revisión activa, 3 h de transcripción, y `GET /models` falla por conexión o un 5xx, o no trae
    `max_prompt_tokens` del modelo.
*   **When**: genero la minuta.
*   **Then**: (D3) la revisión se envía con la transcripción completa; si Copilot la rechaza (400 por longitud) o la
    corta, el documento se entrega con «> Nota de la aplicación: la revisión de fidelidad no se pudo completar
    (<motivo>); este documento no está revisado.», como hoy. El registro anota que no se pudo comprobar el límite. No
    hay una segunda consulta al catálogo en esa generación.

### CUJ 6: el catálogo responde 401

*   **Given**: revisión activa, una revisión que supera el umbral y `GET /models` responde 401.
*   **When**: genero la minuta.
*   **Then**: no se envía la revisión; la generación falla con el error de sesión de hoy («La sesión de GitHub Copilot
    caducó o fue revocada (401). Vuelve a iniciar sesión.», o el de la variable de entorno), igual que un 401 de la
    petición de revisión (`test_401_durante_la_revision_no_entrega_documento`).

## Plan técnico

### Forma general

```text
transcripción ──dividir_texto──► 1 parte ──► redacción ──► revisión(transcripción) ──┐
                                │                                                     │
                                └► N partes ──► notas ──► redacción(notas)            │
                                                              │ ¿revisión activa?     │
                                                              ▼                       │
                                 estimar revisión con la TRANSCRIPCIÓN ORIGINAL (2,3) │
                                                              │                       │
                         ≤ umbral, ≤ límite o sin dato (D3) ──┼── > límite ─► revisión(notas) + motivo (D2)
                         401 ─► error de sesión               ▼                       │
                                                  revisión(transcripción)             │
                                                              ▼                       ▼
                                pierde secciones ─► se descarta + nota «no está revisado» (R1)
                                quita tareas/acuerdos ─► se aplica, se reponen marcados + nota (R4)
                                                              ▼
                                                       notas de la app
```

### 1. Una sola relación caracteres/token (R6)

`CARACTERES_POR_TOKEN` pasa de 4 a 2.3 y se usa con una función nueva, pública y pura:

```python
CARACTERES_POR_TOKEN = 2.3  # medido el 2026-11-22: 164 993 car. = 70 318 tokens en claude-haiku-5.5 (2,35)

def estimar_tokens(texto: str) -> int:
    """Tokens estimados, redondeando hacia arriba. Aritmética entera: 230 / 2.3 da 100.00000000000001 en coma
    flotante y `math.ceil` lo convertiría en 101."""
    return -(-len(texto) * 10 // round(CARACTERES_POR_TOKEN * 10))
```

`_comprobar_limite_de_entrada` usa `estimar_tokens(PROMPT_SISTEMA + prompt)`. La revisión usa la misma función: el
borrador proponía una constante aparte (3) por una asimetría de costes, pero con la relación medida ambas pasadas
quieren la misma estimación, y dos constantes invitan a que diverjan.

### 2. Una consulta al catálogo por generación (R2a, sin cambio de comportamiento)

Hoy `_comprobar_limite_de_entrada` guarda los límites en `self._limites` si la consulta sale bien, y no recuerda el
fallo («la siguiente generación vuelve a consultar el catálogo»). Se extrae:

```python
@dataclass
class _ConsultaDeLimite:
    """Estado de la consulta al catálogo en una generación: si falló, no se repite en esa generación."""
    error: Optional[str] = None  # motivo del fallo; None si no se consultó o salió bien

def _limite_del_modelo(self, consulta: _ConsultaDeLimite,
                       cancelar: Optional[threading.Event]) -> tuple[str, Optional[int]]:
    """Modelo de la próxima petición (`_modelo_para_peticion`: regla 7 y sesión auto) y su límite de entrada, o None
    si el catálogo falló en esta generación o no lo trae."""
```

`_comprobar_limite_de_entrada(self, prompt, partes, cancelar, consulta: Optional[_ConsultaDeLimite] = None)` la usa
(sin `consulta` crea una propia). `_generar` crea `consulta = _ConsultaDeLimite()` al empezar y la pasa a la redacción
y, desde R2b, a la revisión. El texto del registro de la redacción no cambia.

### 3. Conservar la transcripción y decidir la fuente de la revisión (R2b)

`_generar` deja de reutilizar `texto` para las notas: guarda `original = texto.strip()` y usa `fuente_redaccion` para
lo que recibe la plantilla. Nuevo:

```python
@dataclass
class FuenteRevision:
    tipo: str  # "transcripcion" o "notas"
    texto: str  # lo que va en {texto} de PROMPT_REVISION
    motivo: Optional[tuple[int, int, str]] = None  # (estimado, límite, modelo) si la transcripción no cupo

def _fuente_de_revision(self, original: str, notas: str, documento: str, partes: int,
                        consulta: _ConsultaDeLimite, cancelar: Optional[threading.Event]) -> FuenteRevision:
```

*   Con una parte: `FuenteRevision("transcripcion", original)`, sin consultar nada.
*   Con varias: `estimado = estimar_tokens(PROMPT_SISTEMA + PROMPT_REVISION.format(texto=original,
    documento=documento))`. Si `estimado <= UMBRAL_COMPROBAR_LIMITE`: transcripción. Si no, `_limite_del_modelo`:
    *   límite `None` (catálogo caído, 5xx, formato inesperado, modelo ausente): transcripción (D3) y registro
        `WARNING`, con uno de estos dos textos:
        *   «No se pudo comprobar el límite de entrada de «%s» para la revisión (%s); se revisa con la transcripción
            completa.» (fallo; el segundo `%s` es `consulta.error`).
        *   «No se pudo comprobar el límite de entrada de «%s» para la revisión: el catálogo no lo informa; se revisa
            con la transcripción completa.»
    *   `estimado <= límite`: transcripción.
    *   `estimado > límite`: `FuenteRevision("notas", notas, (estimado, limite, modelo))` y registro `INFO` «La revisión
        con la transcripción completa suma unos %d tokens y «%s» admite %d; se revisa con las notas de las %d partes.».
*   **401 del catálogo** (D3, «sin sesión»): `copilot._catalogo` lanza `ErrorSesionCopilot` (subclase de
    `ErrorCopilot`, así que quien captura `ErrorCopilot` no cambia) y `_limite_del_modelo` la convierte en
    `self._error_de_token_rechazado()`. Vale para la redacción y para la revisión: no se envía nada más.
*   `_fuente_de_revision` se llama **dentro** del `try` de la revisión: un error suyo se trata como uno de la
    petición de revisión (recuperable → nota; sin sesión, modelo no autorizado o cancelación → como hoy).

**400 por longitud: sin reintento contra las notas** (hallazgo 6). Si Copilot rechaza la revisión con la
transcripción completa, el documento sale con la nota «no se pudo completar», como hoy. Motivos: reconocer «400 por
longitud» exige leer un cuerpo de error no documentado; con la estimación medida y el catálogo el caso queda para
cuando el catálogo no responde (D3); y un reintento automático sería una tercera forma de revisión que explicar en la
nota. Si los registros muestran que ocurre, se reabre.

### 4. Qué ve el usuario

Textos literales. `{N}` partes, `{M}` modelo, `{T}` tokens estimados y `{L}` límite, sin separador de miles (como el
error de la redacción). `BASE` = «> Nota de la aplicación: la transcripción se procesó en {N} partes y este documento
se redactó a partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas,
cifras y condiciones con la transcripción antes de darlo por bueno.» (la de hoy).

| Caso | Línea de estado durante la revisión | Nota de las partes |
|---|---|---|
| 1 parte | «Revisando fidelidad con la transcripción…» (como hoy) | Sin nota (como hoy) |
| N partes, cabe o sin dato (R2b) | «Revisando fidelidad con la transcripción completa…» | BASE + « La revisión de fidelidad lo contrastó después con la transcripción completa, pero es automática: no sustituye a esa comprobación.» |
| N partes, no cabe (R2b) | «Revisando fidelidad con las notas de las {N} partes…» (como hoy) | BASE + « La revisión de fidelidad se hizo contra esas notas, no contra la transcripción.» (como hoy) |
| N partes, no cabe (R3) | «Revisando fidelidad con las notas de las {N} partes (la transcripción completa no cabe en «{M}»)…» | BASE + « La revisión de fidelidad se hizo contra esas notas y no contra la transcripción completa, que suma unos {T} tokens y supera los {L} que admite «{M}».» |
| Revisión fallida o cortada | (la de su caso) | BASE (sin frase de revisión) + nota de revisión no completada (como hoy) |
| Revisión descartada (R1) | (la de su caso) | BASE (sin frase de revisión) + nota de revisión descartada |
| Revisión desactivada | — | BASE (como hoy) |

Nota de revisión descartada (R1), con `{motivo}` = «quitaba secciones obligatorias» o «quitaba tareas o acuerdos»
(este segundo solo existe entre R1 y R4):
«> Nota de la aplicación: la revisión de fidelidad se descartó porque {motivo}; este documento no está revisado.»
Si la revisión pierde secciones y además tareas, el motivo es el de secciones (precedencia).

Nota de lo repuesto (R4), con `{lista}` descrita en el punto 5:
«> Nota de la aplicación: la revisión de fidelidad quiso quitar de la minuta lo siguiente por no encontrarlo en la
transcripción; la app lo ha repuesto marcado con «[comprobar]»: {lista}. Compruébalo con la transcripción y bórralo
si no se dijo.»

**Orden de las notas** (spec «Notas de la aplicación juntas»): respuesta cortada, notas de partes cortadas, secciones
que no se pudieron pedir de nuevo, secciones que faltan, revisión no completada **o** descartada (nunca las dos), lo
repuesto, y la última, la de las partes. Los tests de R1 y R4 comprueban con `in` y el orden relativo, no con
`endswith`, salvo donde se diga.

### 5. Reponer lo que la revisión quitó (R4, decisión D4)

`PROMPT_REVISION` (completo, sustituye al de hoy; lo usa también el resumen):

```text
Revisa el DOCUMENTO comparándolo frase por frase con la TRANSCRIPCIÓN y corrige únicamente:
- Condiciones, matices o compromisos reformulados con otro sentido: reescríbelos con las palabras de la \
transcripción (por ejemplo, si se dijo "lo entrego el lunes si me llegan los datos", no puede quedar \
"entrega sujeta a validación de datos").
- Datos que no aparecen en la transcripción (nombres, fechas, cifras).
- Calificativos o valoraciones que nadie expresó.
- Tareas o acuerdos que nada de la transcripción respalda: quítalos. No quites los que se deducen de lo dicho: \
un acuerdo con responsable también es una tarea, y la fecha que alguien estima para su propio trabajo también lo es.

No cambies la estructura, los títulos, el orden ni el estilo; no elimines secciones. Si no hay nada \
que corregir, devuelve el documento igual. Responde solo con el documento completo.

TRANSCRIPCIÓN:
"""
{texto}
"""

DOCUMENTO:
"""
{documento}
"""
```

La última viñeta recoge el hallazgo 3: `PROMPT_MINUTA` pide convertir en tarea todo acuerdo con responsable y toda
fecha estimada para el propio trabajo; la revisión no debe tratar eso como inventado. En el resumen no hay tablas ni
sección de acuerdos: la viñeta no aplica, y el resumen no tiene la guarda de tareas (spec, «Revisión de fidelidad que
borra tareas o acuerdos», segundo punto); no cambia.

**Cuándo se calcula.** Solo en la minuta (`conservar_tareas_y_acuerdos=True`), solo si la revisión se aceptó por
secciones (si pierde secciones se descarta entera, R1) y solo para la sección que **baja de número**: si la tabla de
tareas tiene el mismo número de filas o más, no se repone nada aunque las celdas cambien (una tarea reescrita no es
una tarea quitada; hallazgo 8). Lo mismo con las viñetas de Acuerdos.

**Función nueva, pública y pura:** `reponer_lo_quitado(antes: str, despues: str) -> tuple[str, list[str]]` devuelve
`despues` con las filas y viñetas repuestas y la lista de elementos para la nota.

*   **Filas que cuentan:** las de datos de «## Tareas y pendientes» (sin cabecera ni separador) y las viñetas de
    «## Acuerdos» (`-` o `*`), sin las de relleno: la fila cuya primera celda es «Sin tareas» y la viñeta «Sin
    acuerdos explícitos» (sin mayúsculas ni punto final). Así, cambiar una tarea por «Sin tareas» cuenta como quitarla.
*   **Comparación:** cada fila o viñeta se normaliza (sin el marcador de viñeta, en minúsculas, espacios colapsados,
    sin punto final; en las filas, las celdas unidas por « | »). Si `despues` tiene `k` menos, se calcula la similitud
    `difflib.SequenceMatcher(None, a, b).ratio()` de cada par (fila de antes, fila de después), se ordenan los pares
    por (similitud descendente, índice de antes, índice de después) y se emparejan uno a uno en ese orden. Las `k`
    filas de antes que quedan sin pareja son las quitadas, en su orden original. Si `despues` añade filas nuevas, se
    emparejan igual; solo se repone lo que falta para no bajar del número de antes.
*   **Dónde se reponen:** las filas, al final de la tabla de `despues`, en su orden original, con la primera celda
    terminada en « [comprobar]» (`MARCA_REPUESTA = "[comprobar]"`); si `despues` no tiene tabla, se inserta la
    cabecera y el separador de `PROMPT_MINUTA` justo bajo el título de la sección. Las viñetas, tras la última viñeta
    de Acuerdos (o bajo el título si no hay ninguna), con su texto original y « [comprobar]» al final; la viñeta «Sin
    acuerdos explícitos», si estaba, se quita. La fila «Sin tareas» la quita ya `normalizar_tabla_tareas` en el
    post-proceso.
*   **Elementos de la nota:** tarea → «{tarea} ({responsable})», o «{tarea}» si el responsable está vacío o es «No
    asignado»; acuerdo → su texto sin marcador. Cada uno en una línea (`" ".join(texto.split())`) y, si pasa de
    `MAX_MOTIVO_NOTA` (120) caracteres, `texto[:120] + "…"`, **sin** `_motivo` (que quita el punto final). Primero las
    tareas, después los acuerdos.
*   **Lista:** cada elemento entre «»; 1 → «A»; 2 → «A» y «B»; de 3 a 5 → «A», «B», «C» y «D»; más de 5 → los 5
    primeros separados por comas y « y {n} más» (con 6: «A», «B», «C», «D», «E» y 1 más). Lista vacía → sin nota. El
    tope es solo de la nota: **todas** las filas quitadas vuelven a la minuta, marcadas.

`_Documento` gana `repuestas: list[str]`; la revisión se aplica, así que cuenta como revisada.

### 6. Revisión descartada (R1)

`_Documento` gana `revision_descartada: Optional[str]`; `_con_nota` calcula `revisado = self.revision_fidelidad and
not d.error_revision and not d.revision_descartada`.

### 7. Firmas fijadas para todas las historias

Todos los parámetros nuevos son **solo por palabra clave y con valor por defecto**: los tests de hoy
(`tests/test_asistente_ia.py:751-763`, `:929-952`) siguen pasando sin tocarlos.

```python
def notas_de_la_aplicacion(faltan, partes, revisado, error_secciones=None, error_revision=None, corte=None,
                           cortes_partes=None, *,
                           revision_descartada: Optional[str] = None,      # R1
                           repuestas: Optional[list[str]] = None,          # R4
                           fuente_revision: str = "notas",                 # R2b: "transcripcion" | "notas"
                           motivo_notas: Optional[tuple[int, int, str]] = None) -> str:  # R3
def _cita_de_partes(partes: int, revisado: bool, *, fuente_revision: str = "notas",
                    motivo_notas: Optional[tuple[int, int, str]] = None) -> str:  # R2b, R3
def nota_de_notas(partes: int, revisado: bool, *, fuente_revision: str = "notas",
                  motivo_notas: Optional[tuple[int, int, str]] = None) -> str:  # R2b, R3
```

`_cita_de_partes` solo añade frase de revisión si `revisado`; con `fuente_revision="transcripcion"` usa la de
«contrastó», con `"notas"` y `motivo_notas` la del motivo (R3), y con `"notas"` sin motivo la de hoy.

Campos nuevos de `_Documento`, al final y con valor por defecto: `revision_descartada: Optional[str] = None` (R1),
`repuestas: list[str] = field(default_factory=list)` (R4), `fuente_revision: str = "notas"` (R2b),
`motivo_notas: Optional[tuple[int, int, str]] = None` (R3).

### 8. Qué no cambia

*   El número de peticiones, `x-initiator` (la revisión sigue siendo `agent`), el endpoint (`/chat/completions`,
    regla 10), la comprobación de familias excluidas antes de cada envío (regla 7) y el texto que sale del equipo (la
    transcripción ya se envía entera, en partes; el audio nunca, regla 2).
*   La caché de notas, la cancelación (una revisión cancelada no entrega documento), los cortes por `length` (una
    revisión cortada cuenta como fallo, `_sin_cortar`), `Retry-After`, los reintentos de `_completar` y la persistencia
    (historial antes que archivo, regla 6): el documento sigue siendo un texto con su cola de notas.
*   La ventana: los mensajes de progreso llegan por `on_progreso`, que la interfaz pinta sin interpretarlos.

## Alternativas consideradas

Todas usan solo Copilot y `/chat/completions`. Costes en tokens de entrada (2,3 caracteres por token) para una
reunión de 3 h (160 000 caracteres, 3 partes) y para una de 90 min (80 000, 2 partes), con la revisión activa.

### A. Revisión con la transcripción entera cuando cabe; degradación explícita cuando no (elegida)

*   **Mecanismo:** el del «Plan técnico».
*   **Coste:** 0 peticiones más. 90 min: ~81 700 tokens por minuta (+27 800). 3 h: ~155 300 (+59 100). Una consulta
    al catálogo por asistente si sale bien, una por generación como mucho si falla.
*   **A favor:** corrige el defecto 1 en el caso típico con el modelo por defecto; la degradación conserva el valor de
    hoy; cambio local a `_generar`; los tests se hacen con los dobles que ya existen.
*   **En contra y cuándo falla:** no corrige un dato inventado si el modelo no lo ve en un contexto largo (la nota lo
    dice); con `gpt-4.1` y más de ~2 h 40 min degrada a las notas; la estimación sigue siendo una estimación; más
    latencia en la revisión (sin medir; la comprobación real tardó 3,9 s con 70 000 tokens y una respuesta corta).

### B. Revisión por partes con verificación de afirmaciones (mapa y reducción)

*   **Mecanismo:** 1 petición extrae del documento afirmaciones atómicas; N peticiones en paralelo, una por fragmento,
    responden «aparece», «contradice» o «no aparece»; la app marca las no respaldadas; 1 petición final corrige.
*   **Coste:** N + 2 peticiones (5 para 3 h); tokens de entrada parecidos a A (~82 000 para 3 h solo en la revisión);
    cabe en cualquier modelo.
*   **En contra:** una afirmación que la extracción no saca nunca se comprueba; las que unen datos de dos partes dan
    falsos positivos; depende de una lista con formato legible sin salida estructurada garantizada; 3 a 4 veces más
    peticiones y pasos que fallan. Carril L por sí sola.
*   **Motivo del rechazo:** con el catálogo de hoy, A cubre a los modelos de contexto grande con una petición; B solo
    aporta con modelos pequeños y reuniones largas. Mejora futura.

### C. Verificación determinista de cifras, nombres y fechas, sin IA

*   **Mecanismo:** la app busca en la transcripción normalizada los números, nombres propios y fechas del documento y
    avisa de los que no encuentra.
*   **Coste:** 0 peticiones, 0 tokens; llega también a quien tiene la revisión desactivada.
*   **En contra:** falsos positivos («doce mil» frente a «12 000», nombres corregidos), falsos negativos (tareas
    inventadas con palabras que sí están); solo avisa.
*   **Motivo:** fuera de esta ronda (D5). Mejora futura que necesita medir antes, en local, su tasa de falsos
    positivos con el historial del usuario.

### D. Subir `max_caracteres_bloque` o calcular las partes según el modelo

*   **Mecanismo:** si la transcripción entera cabe en el modelo, no hacer notas: una parte, redacción y revisión contra
    el original. Hoy ya se puede sin tocar código: la vista Configuración admite hasta 500 000 caracteres por parte.
*   **Coste, con el mismo rasero que A:** 90 min: 2 peticiones, redacción ~36 700 + revisión ~37 700 = ~74 400 tokens
    (A: 4 peticiones, ~81 700). 3 h: ~72 800 + ~72 500 = ~145 300 tokens (A: 5 peticiones, ~155 300). Es algo más
    barata que A en tokens y bastante en peticiones.
*   **A favor:** quita el defecto en su origen (no hay notas que introduzcan errores), la revisión es siempre contra
    el original y no necesita código para probarla.
*   **En contra y cuándo falla:** cambia la redacción de todas las reuniones largas, y no hay ninguna medición de si
    una redacción en una pasada de 160 000 caracteres omite más tareas que la de notas (el paso de notas existe para
    eso); pierde el paralelismo de las notas; y la ruta de una parte **no comprueba el límite de entrada**
    (`_comprobar_limite_de_entrada` solo se llama con varias partes): con `gpt-4.1` y 3 h (~72 800 tokens > 64 000)
    Copilot rechazaría la redacción con un error poco claro. Haría falta añadir esa comprobación y decidir qué hacer
    cuando no cabe (volver a las notas), que es casi el mecanismo de A aplicado a la redacción.
*   **Motivo del rechazo:** no porque cueste más (cuesta menos), sino porque cambia la calidad de la redacción sin
    datos y necesita su propia comprobación de límite. Mejora futura: medir con transcripciones sintéticas si una
    pasada pierde tareas; si no, reabrir el valor por defecto de `max_caracteres_bloque` con el límite del catálogo.

### E. Trazabilidad bloque → dato con etiquetas

*   **Mecanismo:** etiquetas de parte (`[P2]`) en notas y redacción; revisión de cada grupo contra su fragmento.
*   **Motivo del rechazo:** depende de que el modelo conserve etiquetas que contradicen «Cada celda contiene solo el
    dato» y «Responde únicamente con el documento»; las líneas que mezclan partes vuelven al problema de B; toca los
    tres prompts de los que depende la regla 4. Más riesgo para la fidelidad que el que quita.

### F. Revisión por partes en serie, cada una contra su fragmento

Descartada en la historia 06 («Supuestos» 2): quien revisa la parte 1 no ve la 2 y borraría datos ciertos de la otra
parte; si se le dice que ignore lo que no está en su fragmento, ya no detecta un dato inventado. Sin motivo nuevo.

### G. Notas con cita literal, comprobada sin IA (hallazgo 7)

*   **Mecanismo:** `PROMPT_NOTAS_BLOQUE` pide que cada viñeta con un nombre, una cifra, una fecha o una tarea termine
    con la frase del fragmento que la respalda, entre «»; la app comprueba, sin IA, que cada cita aparece en su bloque
    (normalizado: sin tildes, minúsculas, espacios colapsados) y marca o descarta las viñetas cuya cita no aparece
    antes de redactar.
*   **Coste:** 0 peticiones más; notas más largas (sin medir; quizá +30-50 %), que encarecen la redacción.
*   **A favor:** ataca el error donde nace (la nota de parte) y funciona con cualquier modelo y cualquier tamaño, sin
    depender del catálogo; la comprobación es determinista.
*   **En contra y cuándo falla:** que la cita exista no prueba que la viñeta diga lo mismo (el modelo puede citar
    bien y resumir mal, justo el caso de las condiciones reformuladas); Whisper mete ruido que obliga a una comparación
    difusa con su propio umbral; cambia `PROMPT_NOTAS_BLOQUE`, del que depende la regla 4, y la redacción tendría que
    quitar las citas sin romper «Cada celda contiene solo el dato»; invalida la caché de notas.
*   **Motivo:** complementaria a A, no sustituta, y con más incógnitas que A (tamaño de las notas, umbral de la
    comparación). Mejora futura, a medir con transcripciones sintéticas.

## Decisiones del usuario (cerradas el 2026-11-22)

*   **D1. La revisión puede enviar en una sola petición más que `ia.max_caracteres_bloque`:** sí. El límite de una
    petición es `max_prompt_tokens` del catálogo; `max_caracteres_bloque` decide cómo se parte la redacción.
*   **D2. Con varias partes, si la transcripción completa no cabe:** se revisa contra las notas y el documento dice por
    qué (R3).
*   **D3. Si el catálogo no responde o no trae el límite:** se intenta con la transcripción completa. Un 401 del
    catálogo es otra cosa («sin sesión»): no se envía nada y sale el error de sesión de hoy.
*   **D4. Tareas y acuerdos no respaldados: «corregir y reponer marcado».** La revisión puede quitarlos; la app aplica
    sus correcciones y **repone** las filas y viñetas que quitó, marcadas con «[comprobar]» y listadas en una nota.
    Cambia la regla del punto #24 de «se descarta la revisión» a «se aplica con las filas repuestas y marcadas», **solo
    para tareas y acuerdos**; una revisión que pierde secciones se sigue descartando entera (R1).
*   **D5. Verificación sin IA:** no entra en esta ronda; queda como mejora futura que necesita medición previa.
*   **D6. `revision_fidelidad` por defecto:** sigue desactivada; se decidirá tras medir. Ninguna historia toca
    `config/settings.yaml`.
*   **Facturación:** desconocida; el diseño supone facturación por token de entrada (el caso caro), con el análisis
    por modelo de «Coste».
*   **Comprobación real:** autorizada una petición con texto sintético; hecha (ver «Comprobación real»).

## Historias

Cada historia deja `./venv/bin/python -m pytest -q` en verde (hoy, 501 tests), sin red (regla 3), empieza por sus
tests **rojos** (fallan antes del cambio), mantiene los **guarda** (pasan antes y después) y tiene su lista **cerrada**
de archivos: si necesita otro, se para y se vuelve a este diseño. La documentación la actualiza `/cerrar`; cada
historia lista las secciones que cambian.

| Orden | Historia | Carril | Depende de |
|---|---|---|---|
| 1 | R1 — Una revisión descartada no cuenta como revisada | S | — |
| 2 | R4 — La revisión quita tareas y acuerdos; la app los repone marcados | M | R1 |
| 3 | R6 — Estimar tokens con la relación medida | S | — |
| 4 | R2a — Una consulta al catálogo por generación (refactor) | S | R6 |
| 5 | R2b — Revisar contra la transcripción completa cuando cabe | M | R2a, R4 |
| 6 | R3 — Decir por qué la revisión fue contra las notas | S | R2b |

Todas tocan `src/asistente_ia.py` y `tests/test_asistente_ia.py`: van **en serie**, en ese orden. R4 va antes que R2b
(hallazgo 2): sin R4, la nota diría «lo contrastó después con la transcripción completa» sobre una minuta que conserva,
sin marcar, la tarea inventada que la revisión quiso quitar. R6 va antes que R2a y R2b para que la revisión nazca con
la estimación medida. (La antigua R5, verificación sin IA, sale de la ronda por D5.)

### Dobles de test

Los de `tests/test_asistente_ia.py`:

*   `_simular_chat(monkeypatch, respuesta)` (`:777`) guarda el cuerpo de cada petición y contesta según
    `respuesta(cuerpo)`; `_es_prompt_de_notas(cuerpo)` reconoce las notas. **En los tests nuevos, la función
    `respuesta` mira primero si el último mensaje contiene «DOCUMENTO:»** (la revisión, que también contiene el texto
    del documento y, desde R2b, la transcripción) y solo después «Redacta un resumen» u otras marcas (como en `:859`):
    para la revisión devuelve `RESUMEN_MODELO` si el texto tras «DOCUMENTO:» contiene «## Resumen», y si no la minuta
    que toque.
*   `_prohibir_red(monkeypatch)` hace fallar cualquier `httpx.get` o `httpx.post`.
*   `_simular_catalogo(monkeypatch, respuesta)` y `_catalogo_con_limite(modelo, limite)` (`:1670-1685`) simulan `GET
    /models` y cuentan las consultas. `_Respuesta({}, 401)` simula el 401.
*   `_minuta(tareas, acuerdos, frase)` (`:195`) construye minutas con responsable «Ana» en todas las filas.
*   `_simular_auto` (`:444-450`) se amplía en R3 con un parámetro opcional `limites: Optional[dict] = None`: si se
    pasa, cada modelo del catálogo lleva `"capabilities": {"limits": {"max_prompt_tokens": limites[id]}}`. Sin él, el
    catálogo es el de hoy y ningún test existente cambia.
*   Para no generar cientos de miles de caracteres, los tests de límite parchean `asistente_ia.UMBRAL_COMPROBAR_LIMITE`
    con `monkeypatch.setattr`.
*   Texto de dos partes de los tests (`TEXTO2`): `"\n".join(f"Segmento {i:03d} con algo de contenido." for i in
    range(40))`, 1 439 caracteres, con `max_caracteres_bloque=900` da 2 partes (720 y 719). Con notas simuladas «- Nota
    de una parte» y `MINUTA_MODELO` como redacción, a 2,3 caracteres por token: redacción ≈ 1 021 tokens; revisión
    con la transcripción ≈ 1 585 con el prompt de hoy (≈ 1 700 con el de R4); revisión con las notas ≈ 995. Los tests
    calculan el valor con `estimar_tokens` en vez de fijarlo, y usan límites con margen: **100 000** (cabe) y
    **1 300** (la redacción cabe, la revisión con la transcripción no).

### Historia R1 — Una revisión descartada no cuenta como revisada

**Criterios:**

1.  *Dado* `revision_fidelidad=True`, un resumen de una parte y una revisión que pierde una sección, *cuando* lo
    genero, *entonces* el resumen empieza por el redactado y contiene, tras «\n---\n\n», «> Nota de la aplicación: la
    revisión de fidelidad se descartó porque quitaba secciones obligatorias; este documento no está revisado.».
2.  *Dado* una minuta de 2 partes (`TEXTO2`) cuya revisión pierde «## Próximos pasos», *cuando* la genero, *entonces*
    lleva esa nota antes que la de las partes, y la de las partes no contiene «La revisión de fidelidad».
3.  *Dado* una revisión de minuta de una parte que pierde una sección **y** una tarea, *cuando* la genero, *entonces*
    el motivo es «quitaba secciones obligatorias»; *dada* una que solo pierde una tarea, el motivo es «quitaba tareas o
    acuerdos» (provisional: R4 lo sustituye); *dada* una revisión aceptada, no hay nota de revisión descartada.

**Tests** (`tests/test_asistente_ia.py`):

*   Rojos: `test_revision_que_pierde_secciones_lo_dice_y_no_cuenta_como_revisada`,
    `test_revision_descartada_con_varias_partes_no_dice_que_se_reviso`,
    `test_revision_que_pierde_secciones_y_tareas_da_el_motivo_de_secciones`,
    `test_revision_descartada_por_tareas_lo_dice` (provisional: R4 lo sustituye).
*   Guarda: `test_revision_aceptada_no_lleva_nota_de_descartada`, `test_revision_de_fidelidad_reemplaza_documento`,
    `test_revision_de_minuta_que_conserva_tareas_y_acuerdos_se_acepta`, `test_nota_de_notas_*` (`:751-763`).
*   Se ajusta: `test_revision_que_pierde_secciones_se_descarta` (`:187`) compara hoy con `==`; pasa a
    `resumen.startswith(completo)` y la nota con `in`.

**Archivos (lista cerrada):** `src/asistente_ia.py` (`_Documento.revision_descartada`, `_generar`,
`notas_de_la_aplicacion` con `revision_descartada`, `_con_nota`), `tests/test_asistente_ia.py`.

**Documentación que cambia (`/cerrar`):** `docs/specs/documentos-ia.md` «Notas de la aplicación juntas» (157-166:
añadir «revisión descartada» junto a «revisión no completada») y «Revisión de fidelidad contra las notas» (210-217:
la descartada no dice que se revisó); `src/EGM.md:297-302`; pendiente aceptado de la historia 06 → cerrado.

### Historia R4 — La revisión quita tareas y acuerdos; la app los repone marcados

**Criterios:**

1.  *Dado* una minuta de una parte con tareas «Enviar las cifras de octubre» y «Revisar el plan» y la frase «la
    entrega está sujeta a validación», y una revisión que devuelve solo «Revisar el plan» y la frase «la entrega llega
    si me llegan los datos», *cuando* la genero, *entonces* la minuta contiene la frase corregida, la línea «| Revisar
    el plan | Ana | Sin fecha |» seguida de «| Enviar las cifras de octubre [comprobar] | Ana | Sin fecha |», la nota
    de lo repuesto con la lista «Enviar las cifras de octubre (Ana)» entre «», y ninguna nota de revisión descartada.
2.  *Dado* una revisión que conserva el número de filas pero reescribe la primera celda de una, *entonces* no hay
    «[comprobar]» ni nota; *dado* una que reescribe «Enviar el informe» como «Enviar el informe final» y quita
    «Revisar el contrato» (de 3 filas a 2), *entonces* solo «Revisar el contrato» vuelve marcada. *Dado* acuerdos «-
    Se aprueba el presupuesto» y «- Se contrata a Ana» y una revisión con solo «* Se aprueba el presupuesto.»,
    *entonces* vuelve «- Se contrata a Ana [comprobar]». *Dado* una revisión que cambia la única tarea por «Sin
    tareas», la tarea vuelve marcada y la fila «Sin tareas» desaparece.
3.  *Dado* `notas_de_la_aplicacion([], 1, True, repuestas=…)` con 1, 2 y 6 elementos y uno de 200 caracteres,
    *entonces* las listas son «A»; «A» y «B»; «A», «B», «C», «D», «E» y 1 más; el largo acaba en los 120 primeros
    caracteres + «…» (un punto final se conserva); con `repuestas=[]` el resultado es `""`. *Dada* una revisión que
    pierde una sección y una tarea, se descarta (nota de R1) y no hay «[comprobar]». `PROMPT_REVISION` es el del
    punto 5 y nada de lo repuesto ni de la nota llega a ninguna petición.

**Tests** (`tests/test_asistente_ia.py`):

*   Rojos: `test_revision_que_quita_una_tarea_se_aplica_y_la_repone_marcada`,
    `test_tarea_reescrita_y_otra_quitada_solo_repone_la_quitada`, `test_acuerdo_quitado_se_repone_marcado`,
    `test_tarea_cambiada_por_sin_tareas_se_repone`, `test_nota_de_lo_repuesto_formato_y_tope`,
    `test_prompt_de_revision_permite_quitar_solo_lo_no_respaldado` (contiene «no elimines secciones.» y «un acuerdo
    con responsable también es una tarea»; no contiene «ni tareas»), `test_reponer_lo_quitado_sin_bajar_no_cambia_nada`
    (función pura, mismo número de filas).
*   Guarda: `test_revision_que_pierde_secciones_y_tareas_da_el_motivo_de_secciones` (de R1),
    `test_revision_de_resumen_no_aplica_la_regla_de_tareas`, `test_las_notas_nuevas_no_se_envian_a_copilot`,
    `test_lo_repuesto_no_se_envia_a_copilot` (nuevo, guarda desde que existe).
*   Se sustituye: `test_revision_descartada_por_tareas_lo_dice` (de R1) se borra; el motivo «quitaba tareas o
    acuerdos» deja de existir en `_generar`.
*   Se renombran y amplían: `test_revision_de_minuta_que_borra_una_tarea_se_descarta` →
    `..._se_repone_marcada` (comprueba también «Revisar el contrato [comprobar]»);
    `test_revision_de_minuta_que_borra_un_acuerdo_se_descarta` → `..._se_repone_marcado` (comprueba «- Se contrata a
    Ana [comprobar]»).

**Archivos (lista cerrada):** `src/asistente_ia.py` (`PROMPT_REVISION`, `MARCA_REPUESTA`, `reponer_lo_quitado` y sus
auxiliares privadas, `_Documento.repuestas`, `_generar`, `notas_de_la_aplicacion` con `repuestas`, `_con_nota`),
`tests/test_asistente_ia.py`.

**Documentación que cambia:** `docs/specs/documentos-ia.md` «Revisión de fidelidad que borra tareas o acuerdos»
(219-223: se aplica y repone marcado; decisión D4 sustituye a la del punto #24 para tareas y acuerdos) y «Notas de la
aplicación juntas» (157-166); `src/EGM.md:297-302`.

### Historia R6 — Estimar tokens con la relación medida

**Criterios:**

1.  *Dado* `CARACTERES_POR_TOKEN`, *entonces* vale 2.3, `estimar_tokens("x" * 230)` es 100 (no 101: sin error de
    coma flotante) y `estimar_tokens("x" * 231)` es 101.
2.  *Dado* `TEXTO_TRES_PARTES_LARGO` con 3 notas de 60 000 caracteres y un catálogo con 64 000 para `gpt-4.1`,
    *cuando* genero la minuta, *entonces* no se envía la redacción y el error dice unos T tokens con 78 000 ≤ T ≤
    81 000 (hoy, con 4, se enviaba).
3.  *Dado* 3 notas de 100 000, *entonces* el error de hoy da 129 000 ≤ T ≤ 134 000; *dado* 3 notas de 40 000 y el
    límite 64 000, se consulta el catálogo una vez y se redacta (unos 53 000 tokens).

**Tests:** rojos `test_estimar_tokens_usa_la_relacion_medida`,
`test_notas_que_cabian_con_cuatro_caracteres_por_token_ya_no_se_envian`. Se ajustan:
`test_notas_que_superan_el_limite_no_envian_la_redaccion` (`:1705`, rango 74 000-78 000 → 129 000-134 000) y
`test_notas_que_caben_consultan_el_catalogo_una_vez_y_redactan` (`:1743`, `_relleno(60_000)` → `_relleno(40_000)` y
comentario «unos 53 000 tokens»). Guarda: el resto de `:1687-1797`.

**Archivos (lista cerrada):** `src/asistente_ia.py` (`CARACTERES_POR_TOKEN`, `estimar_tokens`,
`_comprobar_limite_de_entrada`), `tests/test_asistente_ia.py`.

**Documentación que cambia:** `docs/specs/documentos-ia.md` «Notas que no caben en el modelo» (195-208);
`src/EGM.md:297-302` («caracteres / 4» → «caracteres / 2,3»).

### Historia R2a — Una consulta al catálogo por generación (refactor)

**Criterios:**

1.  *Dado* un catálogo caído y una `_ConsultaDeLimite()`, *cuando* llamo dos veces a
    `asistente._limite_del_modelo(consulta, None)`, *entonces* el catálogo se consulta una vez, las dos devuelven
    `("gpt-4.1", None)` y `consulta.error` contiene el motivo; con una consulta nueva se vuelve a consultar.
2.  *Dado* un catálogo con 64 000 para `gpt-4.1`, *entonces* devuelve `("gpt-4.1", 64000)` y una segunda llamada,
    con otra consulta, no consulta el catálogo (`self._limites` en memoria).
3.  Todos los tests de límite de hoy pasan sin cambios, y el texto del registro de la redacción es el mismo.

**Tests:** rojos `test_limite_del_modelo_no_repite_un_catalogo_caido_en_la_misma_generacion`,
`test_limite_del_modelo_guarda_el_catalogo_entre_generaciones`. Guarda: `:1687-1797` (ya ajustados en R6).

**Archivos (lista cerrada):** `src/asistente_ia.py` (`_ConsultaDeLimite`, `_limite_del_modelo`,
`_comprobar_limite_de_entrada`, `_generar` crea la consulta), `tests/test_asistente_ia.py`.

**Documentación que cambia:** ninguna (sin cambio de comportamiento).

### Historia R2b — Revisar contra la transcripción completa cuando cabe

**Criterios:**

1.  *Dado* `revision_fidelidad=True`, `TEXTO2` (2 partes), `_prohibir_red`, *cuando* genero la minuta, *entonces* el
    progreso incluye «Revisando fidelidad con la transcripción completa…», el cuerpo de la revisión (el que contiene
    «DOCUMENTO:») contiene cada línea de `TEXTO2` y no «Notas de la parte», y la minuta termina (`endswith`) con BASE
    (2 partes) + « La revisión de fidelidad lo contrastó después con la transcripción completa, pero es automática: no
    sustituye a esa comprobación.». Lo mismo con el resumen que reutiliza las notas.
2.  *Dado* `UMBRAL_COMPROBAR_LIMITE` parcheado a 500 y `gpt-4.1`: con límite 100 000, el catálogo se consulta una
    vez y la revisión lleva la transcripción; con límite 1 300, la revisión lleva las notas («Notas de la parte 1»,
    ninguna línea de `TEXTO2`), el progreso dice «Revisando fidelidad con las notas de las 2 partes…» y la nota
    termina con la frase de hoy («…se hizo contra esas notas, no contra la transcripción.»); con un catálogo que falla
    por conexión, se consulta **una** vez en la generación, la revisión lleva la transcripción, el registro contiene
    «para la revisión (» y «se revisa con la transcripción completa», y la generación siguiente vuelve a consultar
    (2 en total); con un catálogo sin el modelo (`_catalogo_con_limite("otro-modelo", 64000)`), una consulta, revisión
    con la transcripción y el registro dice «el catálogo no lo informa; se revisa con la transcripción completa».
3.  *Dado* un catálogo que responde 401 y el umbral parcheado a 1 200 (la redacción, ≈ 1 021, no consulta; la
    revisión sí), *cuando* genero la minuta, *entonces* sale `ErrorSinSesionCopilot` y no se envía la revisión (3
    cuerpos: 2 notas y la redacción); con el umbral a 500, la misma excepción sale **antes** de la redacción (2
    cuerpos). Con una sola parte nada cambia.

**Tests** (`tests/test_asistente_ia.py`, salvo el último):

*   Rojos: `test_revision_con_varias_partes_usa_la_transcripcion_completa` (sustituye a
    `test_revision_con_varias_partes_dice_que_revisa_contra_las_notas`, `:873`, cuyo escenario pasa a revisar con la
    transcripción), `test_resumen_con_notas_reutilizadas_revisa_contra_la_transcripcion`,
    `test_revision_que_cabe_consulta_el_catalogo_una_sola_vez`, `test_revision_que_no_cabe_vuelve_a_las_notas`,
    `test_catalogo_caido_se_consulta_una_vez_y_se_revisa_con_la_transcripcion`,
    `test_catalogo_sin_el_modelo_revisa_con_la_transcripcion`,
    `test_401_del_catalogo_en_la_revision_es_falta_de_sesion_y_no_envia_la_revision`,
    `test_401_del_catalogo_en_la_redaccion_es_falta_de_sesion`, y en `tests/test_copilot.py`
    `test_catalogo_con_401_es_error_de_sesion` (`limites_de_entrada` lanza `ErrorSesionCopilot`, que sigue siendo
    `ErrorCopilot`).
*   Se ajusta: `test_sin_limite_conocido_se_redacta_como_hoy` (`:1756`) pierde el parámetro `"401"` (ahora es falta de
    sesión).
*   Guarda: `test_una_sola_parte_no_lleva_nota_y_revisa_contra_la_transcripcion`, `test_nota_de_notas_*`,
    `test_401_durante_la_revision_no_entrega_documento`, `test_auto_con_catalogo_caido_tambien_salta_las_familias_excluidas`
    y los de `tests/test_copilot.py` que capturan `ErrorCopilot`.

**Archivos (lista cerrada):** `src/asistente_ia.py` (`FuenteRevision`, `_fuente_de_revision`, `_limite_del_modelo`
con el 401, `_generar`, `_Documento.fuente_revision`, `_cita_de_partes`, `nota_de_notas`, `notas_de_la_aplicacion`
con `fuente_revision`, `_con_nota`), `src/copilot.py` (`_catalogo`: 401 → `ErrorSesionCopilot`),
`tests/test_asistente_ia.py`, `tests/test_copilot.py`.

**Documentación que cambia:** `docs/specs/documentos-ia.md` «Revisión de fidelidad contra las notas» (210-217, pasa a
«Revisión de fidelidad con varias partes»), «Notas que no caben en el modelo» (204-206: el 401 ya no «redacta como
hoy») y «Sesión rechazada por Copilot» (225-230: también al consultar el catálogo); `src/EGM.md:297-302` y la entrada
de `copilot.py` (`_catalogo` lanza `ErrorSesionCopilot` ante un 401).

**Verificación manual (con red, la hace el usuario tras R2b):** con una transcripción **sintética** de al menos 160 000
caracteres (3 partes) en la que una nota de parte no puede saber un dato (una fecha que solo aparece en una línea),
generar la minuta con `claude-haiku-5.5` y la revisión activa; comprobar en el registro que la revisión envió unos
165 000 caracteres y anotó `tokens: entrada N` (pregunta abierta 1), y si la minuta corrige el dato (pregunta 2).

### Historia R3 — Decir por qué la revisión fue contra las notas

**Criterios:**

1.  *Dado* el escenario «no cabe» de R2b (umbral 500, `gpt-4.1`, límite 1 300), *cuando* genero la minuta, *entonces*
    el progreso dice «Revisando fidelidad con las notas de las 2 partes (la transcripción completa no cabe en
    «gpt-4.1»)…» y la minuta termina con BASE + « La revisión de fidelidad se hizo contra esas notas y no contra la
    transcripción completa, que suma unos {T} tokens y supera los 1300 que admite «gpt-4.1».», con T > 1300 sin
    separador de miles.
2.  *Dado* ese escenario y una revisión contra las notas que falla (500 en sus 4 intentos) o se descarta (pierde una
    sección), *entonces* la nota de las partes es BASE sola: ni dice que se revisó ni da el motivo del límite.
3.  *Dado* el modo `auto` con una sesión que elige `gpt-4.1` (misma forma de sesión que
    `test_auto_envia_todas_las_peticiones_al_modelo_autorizado`) y `_simular_auto(..., limites={"gpt-4.1": 1300})`,
    *entonces* el progreso y la nota nombran «gpt-4.1», no «auto».

`FuenteRevision.motivo` lo rellena `_fuente_de_revision` en la rama «no cabe» desde R2b; R3 lo copia a
`_Documento.motivo_notas` en `_generar` y `_con_nota` lo pasa a `notas_de_la_aplicacion` solo si `revisado`.

**Tests:** rojos `test_revision_contra_las_notas_dice_el_motivo_del_limite`,
`test_revision_contra_las_notas_fallida_o_descartada_no_da_motivo_ni_dice_revisada`,
`test_revision_contra_las_notas_en_auto_nombra_el_modelo_de_la_sesion`, `test_nota_de_notas_con_motivo` (función
pública con `motivo_notas=(70000, 64000, "gpt-4.1")`). Se ajusta: `test_revision_que_no_cabe_vuelve_a_las_notas` (de
R2b): su progreso y su `endswith` pasan a los textos de R3. Guarda: `test_nota_de_notas_*` (`:751-763`) y los
`test_auto_*` existentes (sin `limites`).

**Archivos (lista cerrada):** `src/asistente_ia.py` (`_generar`, `_Documento.motivo_notas`, `_cita_de_partes`,
`notas_de_la_aplicacion` con `motivo_notas`, `_con_nota`), `tests/test_asistente_ia.py` (incluido `_simular_auto`).

**Documentación que cambia:** `docs/specs/documentos-ia.md` «Revisión de fidelidad con varias partes» (la de R2b);
`src/EGM.md:297-302`.

### Verificación común

*   `./venv/bin/python -m pytest -q` en verde tras cada historia.
*   Ningún test hace red: `httpx.stream` simulado siempre; `httpx.get`/`post` simulados o prohibidos.
*   Tras R4, revisar a mano una minuta con una fila repuesta en un visor de Markdown: la tabla sigue siendo una tabla,
    «[comprobar]» se ve como texto y la cola de notas sigue bajo una sola línea horizontal.

## Requisitos no funcionales

*   **Privacidad.** No sale ningún texto que no saliera ya: la transcripción completa ya se envía (en partes) para
    extraer las notas; el audio nunca (regla 2). Las notas de la aplicación y las marcas «[comprobar]» nunca entran en
    un prompt (se añaden después de la última pasada).
*   **Cumplimiento.** Solo Copilot (regla 1) y solo `/chat/completions` (regla 10). La revisión pasa por `_completar`,
    que comprueba `familia_excluida` antes de cada envío, también al renovar la sesión `auto` (regla 7);
    `_limite_del_modelo` resuelve el modelo con `_modelo_para_peticion`, que también la comprueba.
*   **Fidelidad (regla 4).** La revisión solo quita lo que nada respalda y la app lo repone marcado: el usuario decide.
    Las marcas y la nota las pone la app, no el modelo.
*   **Coste.** Mismo número de peticiones; +52 % a +61 % de tokens de entrada por minuta con la revisión activa (tabla
    «Coste», en el supuesto caro de facturación por token).
*   **Latencia.** La revisión con la transcripción entera procesa más entrada; la comprobación real (70 000 tokens,
    respuesta corta) tardó 3,9 s. Sin paralelismo que perder.
*   **Hilos.** Sin cambios: todo ocurre en el hilo de la generación (regla 9).
*   **Vuelta atrás.** Cada historia es un commit con la suite en verde. Volver a revisar siempre contra las notas es
    revertir R2b. Los documentos ya guardados no cambian.

### Riesgos

1.  **Exceso de confianza.** «Contrastado con la transcripción completa» puede leerse como garantía. Mitigación: la
    nota dice que es automática y no sustituye a la comprobación.
2.  **Estimación corta.** 2,3 sale de una sola medición con texto sintético. Si una reunión real tokeniza peor,
    Copilot rechaza la revisión con 400 y el documento sale sin revisar, con nota (sin reintento, punto 3).
    Mitigación: pregunta abierta 1.
3.  **Contexto largo.** Un modelo puede pasar por alto un dato inventado en el centro de 160 000 caracteres; la
    comprobación real solo prueba que lo lee. Verificación manual de R2b.
4.  **Avisos que no se leen.** Cada nota compite por atención. Mitigación: la de lo repuesto lista como mucho 5 y la
    marca está en la propia fila.
5.  **La revisión quita algo real.** Con D4 no se pierde: vuelve marcado. Si la revisión quita mucho real, el usuario
    verá muchas «[comprobar]»; con datos se puede endurecer el prompt.
6.  **Emparejamiento erróneo.** Si la revisión reescribe mucho una fila y quita otra parecida, la similitud puede
    reponer la equivocada. La fila repuesta es la original completa y marcada: el usuario ve las dos.
7.  **Reintentos caros.** `_completar` reintenta hasta 4 veces ante 429, 5xx o fallo de conexión, cada vez con toda
    la petición (hallazgo 9). Un 429 o un 5xx no procesan la petición; un corte de conexión a mitad de respuesta sí
    pudo procesarla. No se limita en esta ronda porque cambiaría el contrato de `_completar` para todas las pasadas;
    queda en «Mejoras futuras».

### Mejoras futuras

*   Alternativa B (verificación por fragmentos) si los modelos de contexto pequeño y las reuniones largas resultan ser
    un caso real.
*   Alternativa C (verificación sin IA), tras medir sus falsos positivos en el historial local (D5).
*   Alternativa G (citas literales en las notas), a medir con transcripciones sintéticas.
*   Alternativa D: medir si una redacción en una sola pasada pierde tareas; si no, añadir la comprobación de límite a
    la ruta de una parte y reabrir `max_caracteres_bloque`.
*   Un parámetro de intentos en `_completar` para que la revisión grande reintente una sola vez.
*   Reintento contra las notas ante un 400 por longitud, si los registros muestran que ocurre.

### Recursos

*   `audit_report.md` (A-05) y `goldfish_review_report.md` (fila 10).
*   `docs/historias/hechas/2026-11-22-06-revision-de-fidelidad.md` (cálculos de partida, alternativa F, pendientes
    aceptados).
*   `docs/specs/documentos-ia.md` («Revisión de fidelidad contra las notas», «Revisión de fidelidad que borra tareas o
    acuerdos», «Notas que no caben en el modelo», «Notas de la aplicación juntas», «Sesión rechazada por Copilot»).
*   `docs/integracion-copilot.md` («Comprobado con peticiones reales (2026-11-22)»: límites del catálogo y
    `finish_reason: "length"`; `x-initiator`).
*   `src/asistente_ia.py` (`_generar`, `_comprobar_limite_de_entrada`, `_con_nota`, `notas_de_la_aplicacion`,
    `PROMPT_REVISION`, `PROMPT_MINUTA`), `src/copilot.py` (`_catalogo`, `limites_de_entrada`, `precio_entrada`,
    `PRECIO_MAX_ECONOMICO`), `src/flujo_documentos.py` (`argumentos_asistente`), `src/configuracion.py` (claves `ia.*`).

## Revisión (2026-11-22)

Revisión ligera con dos revisores (diseño: «aprobar con cambios»; preparación: «no listo») y decisiones del usuario
D1-D6. Hallazgo → cambio.

### Revisor de diseño

| # | Hallazgo | Cambio |
|---|---|---|
| 1 | (alta) Cuota: el repo ya modela precio por token | «Coste» reescrito en tokens por modelo con los precios de `copilot.py:373-399`; quitado «0 peticiones premium» como hecho |
| 2 | (alta) R2 sin R4 diría «contrastó» con la tarea inventada dentro | R4 va antes que R2b (orden 2 y 5); con D4 la tarea queda marcada antes de que la nota diga «contrastó» |
| 3 | (alta) D4(b) chocaba con `PROMPT_MINUTA` | Con D4 = reponer marcado, nada se pierde; el prompt nuevo pide quitar solo lo que nada respalda y no lo derivado (acuerdo con responsable, fecha estimada) |
| 4 | (media) Supuestos como hechos; verificación con ≥160 000 | «cubre cualquier reunión real» → «según el catálogo»; verificación manual de R2b con ≥160 000 caracteres; comprobación real hecha con 163 771 |
| 5 | (media) Alternativa D con otro rasero; la ruta de una parte no comprueba el límite | D valorada en tokens igual que A (es más barata); sigue descartada por calidad sin medir y por la falta de comprobación de límite en una parte, que se dice |
| 6 | (media) Falta caer a las notas ante un 400 | Decidido: sin reintento, con motivo (plan técnico, punto 3); mejora futura |
| 7 | (media) Falta «notas con cita literal» | Alternativa G valorada; mejora futura |
| 8 | (media) «Quería quitar» por primera celda da falsos avisos | Solo se repone cuando baja el número de filas, y se identifica la quitada por similitud con emparejamiento uno a uno |
| 9 | (media) Reintentos reenvían 160 000 caracteres hasta 4 veces | No se aplica en esta ronda: cambiaría `_completar` para todas las pasadas; riesgo 7 y mejora futura |
| 10 | (media) «Nunca dar por revisado…» no es regla del repo | Se cita el pendiente aceptado de la historia 06 |
| 11 | (baja) Umbral con 3 frente a 4 caracteres/token | Una sola relación medida, 2,3, para redacción y revisión (R6) |
| 12 | (baja) 401 en el catálogo | D3: el 401 es falta de sesión (CUJ 6, R2b criterio 3) |
| 13 | (baja) El aviso cubre tareas/acuerdos, no secciones | Dicho en «Fuera de alcance» y en D4 |
| 14 | (baja) Fuera de alcance: tareas omitidas | Añadido a «Fuera de alcance» |

### Revisor de preparación

| Hallazgo | Cambio |
|---|---|
| Cerrar decisiones | «Decisiones del usuario (cerradas)» |
| Tests rojos frente a guardas por historia | Cada historia separa rojos, guardas y tests que se ajustan o sustituyen |
| Nombres de parámetros nuevos y campos de `_Documento` | Fijados en «Plan técnico», punto 7: solo por palabra clave y con valor por defecto |
| Secciones de spec y `src/EGM.md` que cambian | Lista «Documentación que cambia» en cada historia |
| R1: `test_revision_que_pierde_secciones_se_descarta` (`==`) | Se ajusta a `startswith` + `in` |
| R1: plantilla, precedencia, orden, `in` | Plantilla literal, secciones gana, orden en el punto 4; tests con `in` y uno de precedencia que sobrevive a R4 |
| R2: dividir en R2a y R2b | R2a refactor (`_ConsultaDeLimite`, `_limite_del_modelo`) y R2b decisión y notas |
| R2: estado compartido, no un bool local | `_ConsultaDeLimite` creada en `_generar` y pasada a las dos pasadas |
| R2: notas literales «cabe», «no cabe», «desactivada» | Tabla del punto 4 con los textos completos |
| R2: firma de `_cita_de_partes` y `nota_de_notas` | Punto 7 |
| R2: números concretos | `TEXTO2`, umbral 500 o 1 200, límites 100 000 y 1 300, estimaciones calculadas con `estimar_tokens` |
| R2: dos escenarios del catálogo caído | Conexión caída y modelo ausente, con sus registros literales; el 401 aparte |
| R2: el doble decide por «DOCUMENTO:» primero | Dicho en «Dobles de test» |
| R2: texto del registro cuando el catálogo falla | Literal en el punto 3 |
| R3: ampliar `_simular_auto` | Parámetro opcional `limites` |
| R3: test de R2 cuyo texto cambia | `test_revision_que_no_cabe_vuelve_a_las_notas` |
| R3: escenario con números; dónde se rellena `motivo` | Umbral 500, límite 1 300; `_fuente_de_revision` en R2b, copiado a `_Documento` en R3 |
| R4: prompt completo, resumen, «no elimines secciones» | Prompt literal en el punto 5; el resumen lo comparte y no tiene guarda de tareas |
| R4: formato con 1, 2, 6 y vacío; cuándo; viñetas; recorte sin `_motivo`; tope | Punto 5 y criterios de R4 |
| R5 | Fuera (D5) |

### Del orquestador

*   Comprobación real hecha (2,35 caracteres por token): sección «Comprobación real», tablas recalculadas a 2,3, y la
    estimación de la redacción (4) se corrige en una historia propia, **R6**, y no en R2a, para que R2a siga siendo un
    refactor sin cambio de comportamiento y el cambio de R6 (que ajusta dos tests de límite y hace que más
    redacciones consulten el catálogo) tenga su propio commit y su propia vuelta atrás.

--------------------------------------------------------------------------------

*Redactado con EGM (Tándem `/diseno`)*
