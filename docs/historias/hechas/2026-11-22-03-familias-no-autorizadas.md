# 03 · Ningún texto a un modelo de una familia no autorizada

> Origen: `BACKLOG.md`, «Backlog» #2 — hallazgo A-12 — carril M. Regla de oro 7 de `AGENTS.md` (con las reglas 1, 3
> y 10). Decisión del usuario en `goldfish_review_report.md`: requisito real de la empresa, «aplicar la política al
> enviar». Refinada con `/story` el 2026-11-22.

## Historia

Como usuario con una cuenta de empresa, quiero que mi transcripción nunca se envíe a un modelo de una familia no
autorizada, tampoco en modo `auto` ni con un modelo escrito a mano, para cumplir la política de mi empresa.

## Criterios de aceptación

- [ ] [MODIFICA: sin spec] Dado `ia.modelo: "Mistral-Large-3"` escrito a mano en `config/settings.yaml` (o
  `"kimi-k3-mini"`), una sesión de Copilot válida y una transcripción tan larga que se procesaría en varias partes,
  cuando se pide la minuta o el resumen, entonces no sale ninguna petición a `/chat/completions` (ni la de ninguna
  parte), aparece el error de «Asistente IA» con un mensaje que nombra el modelo, dice que su familia (`mistral` o
  `kimi`) no está autorizada por la empresa y pide elegir otro en el selector o en `ia.modelo`, y la pestaña no
  muestra ningún documento nuevo. El resultado es el mismo si el catálogo de modelos de Copilot no se puede
  consultar o si el modelo no aparece en él. (antes: el modelo de `ia.modelo` se enviaba tal cual en cada petición,
  sin comprobar su familia; la exclusión solo quitaba esos modelos de la lista de económicos del selector, y el
  selector añadía el modelo configurado aunque no estuviera en esa lista)
- [ ] [MODIFICA: sin spec] Dado `ia.modelo: "auto"` y una sesión `auto` en la que Copilot propone primero
  `kimi-k3` y ofrece `kimi-k3`, `mistral-medium-3` y `gpt-5.4`, los tres compatibles con `/chat/completions`,
  cuando se genera la minuta, entonces todas las peticiones con texto de la transcripción van a `gpt-5.4`, y la
  línea de estado de la pestaña y la entrada del historial muestran «auto → gpt-5.4». Lo mismo vale cuando la
  sesión `auto` se renueva a mitad de la generación (por caducidad o tras un 401): el modelo de la sesión nueva
  tampoco puede ser de una familia excluida. (antes: el modo `auto` usaba el primer modelo ofrecido compatible con
  `/chat/completions` sin mirar su familia, en este caso `kimi-k3`, para todas las peticiones del documento)
- [ ] [MODIFICA: sin spec] Dado `ia.modelo: "auto"` y una sesión `auto` que solo ofrece `mistral-medium-3`
  (compatible con `/chat/completions`) y `gpt-5.3-codex` (solo `/responses`), cuando se pide la minuta, entonces no
  sale ninguna petición a `/chat/completions` y aparece el error de «Asistente IA» diciendo que el modo `auto` no
  ofrece ningún modelo autorizado y compatible, con los modelos ofrecidos, y que se elija un modelo concreto.
  (antes: el error «El modo auto solo ofrece modelos que no admiten /chat/completions…» solo saltaba cuando ningún
  modelo admitía `/chat/completions`; aquí se habría enviado la transcripción a `mistral-medium-3`)

Cómo se verifican:

- **Con tests sin red** (regla 3: `httpx` simulado con `monkeypatch` y el fixture `rutas_aisladas`), contando las
  llamadas simuladas a `/chat/completions` y el campo `model` de cada cuerpo:
  - Criterio 1: cero llamadas con un id en mayúsculas y otro en minúsculas, con una transcripción que se divide en
    varias partes, y con el catálogo simulado devolviendo error de conexión o sin el modelo. El error lleva el
    nombre del modelo y la familia.
  - Criterio 2: con la sesión `auto` y el catálogo simulados, todas las llamadas llevan `model: "gpt-5.4"` y el
    modelo usado es «auto → gpt-5.4». Una segunda variante simula un 401 en la primera petición y una sesión
    renovada que vuelve a proponer primero un modelo excluido: la petición que se reintenta tampoco va a él.
  - Criterio 3: cero llamadas y el error con los modelos ofrecidos.
- **Verificación manual:** que el diálogo de error de «Asistente IA» se ve en la ventana con el mensaje del
  criterio 1, poniendo a mano un modelo excluido en `ia.modelo` (sin necesidad de sesión real: el rechazo ocurre
  antes de la primera petición de chat).

## Plan

- Una sola regla para saber si un modelo es de una familia excluida, la que ya usa la lista de modelos económicos
  (el id del modelo contiene el nombre de la familia, sin distinguir mayúsculas), usada desde ahora en todos los
  sitios que deciden a qué modelo se envía.
- Modo `auto`: al elegir el modelo de la sesión, saltar los de familias excluidas igual que hoy se saltan los que
  solo admiten `/responses`; si no queda ninguno, un error que lo diga. La renovación de la sesión pasa por la misma
  elección y queda cubierta.
- Comprobar la regla en el punto donde cada petición fija su modelo, justo antes de enviarla, para el modelo fijo y
  para el que eligió `auto`. Así vale para cada parte de una transcripción larga, cada reintento y cada renovación,
  y el rechazo sale por el camino de error de la generación que ya existe en la ventana.
- Tests sin red de los tres criterios, junto a los del modo `auto` que ya existen.

## Fuera de alcance

- El precio máximo (`PRECIO_MAX_ECONOMICO`). A-12 lo cita junto a las familias, pero la regla 7, el backlog y la
  decisión del usuario solo hablan de familias, y `AGENTS.md` recomienda fijar a mano `claude-sonnet-5.5` (precio
  200, por encima del límite de 50) para minutas de calidad. El precio sigue filtrando solo el selector.
- Que `--copilot-modelos` y el selector dejen de ofrecer modelos excluidos: es lo que se ve, no lo que se envía. Se
  propone como historia derivada.
- Cambiar la lista de familias o permitir desactivarla: la exclusión es un requisito de la empresa
  (`.context/transcriptor-facts.md`).
- Reconocer la familia por otros datos del catálogo (proveedor, nombre comercial): ver el supuesto 2.
- Los documentos ya guardados en el historial que se generaron con un modelo excluido antes de este cambio.
- Soporte de `/responses`; consultar el catálogo una sola vez (Salud #10); guardar el modelo fuera del repo
  (Salud #11); el módulo de configuración (Salud #6); el panel de configuración (Backlog #5); el 401 del modo `auto`
  (Salud #7).
- La CLI: no genera resumen ni minuta, así que no envía texto a Copilot.

## Sugerencias

- Hoy la regla de familia está escrita en un solo sitio y esta historia la necesita en otros dos (la elección de
  `auto` y el envío). Conviene que los tres usen la misma función en vez de repetir la comparación, para que no
  diverjan si un día cambia la forma de reconocer una familia (supuesto 2).
- Al poner el rechazo del modelo fijo en el punto de envío, el error sale en el hilo de fondo y llega a la ventana
  por el camino de error de la generación (pestaña «No se pudo generar» y diálogo). Si se prefiere que el usuario lo
  vea antes de que la pestaña pase a «Generando…», se puede comprobar además al crear el asistente; no es necesario
  para cumplir los criterios.

## Supuestos

Decididos por el agente, sin usuario al otro lado; el orquestador debe validarlos.

1. **El caso que más duele** es que el modo `auto` envíe la transcripción a un modelo excluido sin que el usuario lo
   haya elegido: solo se entera después, por el «auto → kimi-…» del historial. Lo cubren los criterios 2 y 3. Que
   Copilot ofrezca de verdad modelos de esas familias en `auto` no está comprobado (A-12 lo marca como posible); los
   tests lo simulan.
2. **Cómo se reconoce la familia — PARA VALIDAR (decisión de política).** Se mantiene la regla de hoy: un modelo es
   de una familia excluida si su id contiene `kimi` o `mistral`, sin distinguir mayúsculas. La regla solo depende
   del id, que siempre se conoce, así que el veredicto no cambia si el catálogo no se puede consultar ni si el
   modelo no aparece en él: no hay un caso «desconocido» que dejar pasar. Exigir además que el catálogo confirme el
   modelo (fallar cerrado) no añadiría protección con esta regla, porque el catálogo no aporta otro dato de familia
   comprobado en el repo; solo bloquearía la generación cuando el catálogo falla.
   **Hueco que solo el usuario puede cerrar:** hay modelos de Mistral AI cuyo id no contiene «mistral» (Codestral,
   Devstral, Ministral, Pixtral, Magistral, según sus nombres comerciales). Con esta regla pasarían. Si la política
   de la empresa excluye todo modelo de Mistral AI, la opción más restrictiva es añadir esos nombres a la lista de
   familias excluidas (un cambio de una línea con su test) o reconocer al proveedor por los metadatos del catálogo,
   que primero hay que comprobar con una respuesta real. Esta historia no lo hace sin esa confirmación.
3. **`auto` salta el modelo excluido en vez de rechazar todo el modo `auto`** cuando queda uno autorizado: es lo que
   ya hace con los modelos solo `/responses`, y la historia pide que no se envíe nada a un modelo excluido, no que se
   desactive `auto`.
4. **Lo que ve el usuario al rechazarse** es el error de «Asistente IA» que la ventana ya muestra cuando falla una
   generación. El texto exacto es libre si nombra el modelo, la familia y cómo cambiarlo (criterio 1), o los modelos
   ofrecidos (criterio 3).
5. **Efectos secundarios aceptados, sin criterio propio:** como la ventana comprueba al arrancar si `auto` funciona
   con la misma elección, `auto` deja de aparecer en el selector si Copilot solo ofrece modelos excluidos; y
   `--copilot-modelos` mostrará en «auto (ahora: …)» el modelo ya filtrado.
6. **Al cerrar con `/cerrar`**, los comportamientos van a `docs/specs/documentos-ia.md`, el dominio que ya trata la
   generación de resumen y minuta.

## Historias derivadas (para el backlog)

- Como usuario con una cuenta de empresa, quiero que `--copilot-modelos` y el selector de modelo de la ventana no me
  ofrezcan modelos de familias no autorizadas (ni me sugieran ponerlos en `ia.modelo`), para no elegir uno que la
  app va a rechazar. — hallazgo A-12, complemento de la historia 03 — carril S. Hoy `--copilot-modelos` lista todos
  los modelos habilitados, incluidos los excluidos, y termina con «Para usar uno, pon su id en `ia.modelo`»; el
  selector añade el modelo configurado aunque sea de una familia excluida.

## Cierre

Cerrada con `/cerrar` el 2026-11-22. Tests: `./venv/bin/python -m pytest -q`, 108 pasan. Code review con contexto
limpio: «listo para commit», sin ningún camino por el que el texto salga hacia `kimi` o `mistral`; sus hallazgos menores
(modelo vacío o no cadena; tests de caducidad y de catálogo caído; aislamiento de red y de rutas de token en los tests)
se arreglaron y se verificaron.

| # | Marca | Criterio | Evidencia con test y `ruta:línea` | Estado |
|---|---|---|---|---|
| 1 | [MODIFICA: sin spec] | `ia.modelo` escrito a mano con `Mistral-Large-3` o `kimi-k3-mini`: ninguna petición, error con modelo y familia, sin documento nuevo; igual si el catálogo no se consulta | Tests: `tests/test_asistente_ia.py:253` (`test_modelo_excluido_escrito_a_mano_no_envia_nada`), `:267` (`test_modelo_excluido_no_depende_del_catalogo`). Código: `src/asistente_ia.py:273` (comprobación antes de enviar, en `_modelo_y_cabeceras`, `:263`), `src/copilot.py:241` (`familia_excluida`) | cumple (tests y verificación visual del 2026-11-22) |
| 2 | [MODIFICA: sin spec] | `auto` con Copilot que propone `kimi-k3` y ofrece `mistral-medium-3` y `gpt-5.4`: todas las peticiones a `gpt-5.4`, «auto → gpt-5.4»; también tras renovar la sesión (caducidad o 401) | Tests: `tests/test_asistente_ia.py:293` (`test_auto_envia_todas_las_peticiones_al_modelo_autorizado`), `:309` (`test_auto_tras_401_tampoco_usa_un_modelo_excluido`), `:353` (`test_auto_tras_caducar_la_sesion_tampoco_usa_un_modelo_excluido`), `:370` (`test_auto_con_catalogo_caido_tambien_salta_las_familias_excluidas`); `tests/test_copilot.py:228` (`test_auto_salta_modelos_de_familias_excluidas`). Código: `src/copilot.py:322` (filtro en `abrir_sesion_auto`, `:293`) | cumple (tests y verificación visual del 2026-11-22) |
| 3 | [MODIFICA: sin spec] | `auto` sin ningún modelo autorizado y compatible: ninguna petición y error con los modelos ofrecidos | Tests: `tests/test_asistente_ia.py:324` (`test_auto_sin_modelo_autorizado_no_envia_nada`); `tests/test_copilot.py:238` (`test_auto_sin_modelo_autorizado_y_compatible_lanza_error`). Código: `src/copilot.py:322-326` | cumple (tests y verificación visual del 2026-11-22) |

Comprobación añadida fuera de los criterios (modelo vacío, `ia.modelo` sin valor): `tests/test_asistente_ia.py:340`
(`test_modelo_vacio_no_envia_nada_y_explica_el_motivo`). Código: `src/asistente_ia.py:271`. Pasa a la spec como
«Modelo sin configurar».

Helpers de tests que `ruta:línea` citan: `tests/test_copilot.py:180` y `:187` (`familia_excluida`: mayúsculas, valores
que no son cadena).

**Pendientes aceptados:**

- DECISIÓN DEL USUARIO PENDIENTE (supuesto 2): los modelos de Mistral AI cuyo nombre no contiene «mistral» (Codestral,
  Devstral, Ministral, Pixtral, Magistral) no se reconocen como excluidos. Si la política de la empresa los excluye,
  hay que añadirlos a la lista de familias. Pasa al punto 21 de «Salud del código» de `BACKLOG.md`.
- No está comprobado con una respuesta real que Copilot ofrezca modelos `kimi` o `mistral` en modo `auto`; los tests lo
  simulan.
- Efecto aceptado: si `auto` solo ofrece modelos excluidos, `auto` deja de aparecer en el selector de la ventana.
  Pasa, junto con `--copilot-modelos`, al punto 20 de «Salud del código» de `BACKLOG.md`.

### Verificación visual (2026-11-22)

Hecha por el orquestador sobre la ventana real, con el asistente real y la red interceptada. Con `ia.modelo` =
`Mistral-Large-3`, `kimi-k3-mini` y vacío aparece el diálogo «Asistente IA» con el mensaje esperado; la pestaña dice
«No se pudo generar: …» sin documento; no se escribe ningún archivo y hubo cero llamadas de red.
