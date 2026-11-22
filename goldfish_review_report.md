# Goldfish Annotated Review Report

Status: resolved (2026-11-22)

**Target:** `audit_report.md` (`full file`)

> En una auditoría, **PROPOSE FIX** significa «convertirlo en trabajo del backlog», no editar el código ahora.
> La descripción y el escenario de cada hallazgo están en `audit_report.md`, bajo el mismo id.
> Decisiones del usuario (2026-11-22): aceptar los 25 propuestos en el orden sugerido, con A-18 pospuesto;
> A-12 es un requisito real de la empresa; A-14 se acepta como riesgo y se mantiene la regla «Solo GitHub Copilot».

## Hallazgos que necesitan tu conocimiento (ESCALATE)

### [A-12] [`tandem-design`, `tandem-zoom-out`] - Severity: Major
*   **Affected Scope:** `src/copilot.py:237-238`, `:316-321`; `src/ui.py:888-893`
*   **Discrepancy Description:** la política de familias excluidas y precio máximo solo filtra el desplegable; el modo `auto` y un modelo escrito a mano la saltan.
*   ***AI Suggestion:*** ESCALATE
*   ***Justification:*** el código dice «no autorizadas por la empresa», pero ningún archivo del repo recoge esa política. Si es un requisito real, debe aplicarse al enviar (trabajo de backlog); si es una preferencia personal, sobra en un repo publicado. Solo tú sabes cuál de las dos.
*   ***Proposed Edit:*** ninguna hasta tu respuesta.
*   ***Decisión del usuario:*** requisito real. Entra al backlog: aplicar la política también en modo `auto` y con modelo manual.

### [A-14] [`tandem-design`, `tandem-zoom-out`] - Severity: Major
*   **Affected Scope:** `src/copilot.py:27-28`, `:71-81`
*   **Discrepancy Description:** dependencia de una API no documentada y del `client_id` de opencode, sin alternativa.
*   ***AI Suggestion:*** ESCALATE
*   ***Justification:*** el riesgo es real y el README ya lo admite. Pero la mitigación que propone el revisor (admitir otros proveedores) choca con la regla «Solo GitHub Copilot como IA» de `CLAUDE.md`, que el revisor no tenía en su contexto. Aceptar el riesgo tal cual o reabrir esa regla es decisión tuya.
*   ***Proposed Edit:*** si lo aceptas como riesgo, se registra en `AGENTS.md` como riesgo conocido, sin historia.
*   ***Decisión del usuario:*** riesgo aceptado; se mantiene la regla «Solo GitHub Copilot».

## Prioritized Findings & AI Suggestions

Ningún hallazgo se impugna (CONTEST): los dos que comprobé contra el código (A-01 y A-02) son correctos.

| Orden | Id | Severidad | Hallazgo | Sugerencia | Justificación | Decisión |
|---|---|---|---|---|---|---|
| 1 | A-01 | 🔴 Blocker | La transcripción o el documento se pierden si falla la exportación | PROPOSE FIX | Pérdida de datos en el camino principal; comprobado en el código | Aceptado |
| 2 | A-16 | 🟡 Major | Tests no ejecutables y caminos críticos sin cubrir | PROPOSE FIX | Sin `pytest` declarado no se puede verificar ningún otro arreglo | Aceptado |
| 3 | A-02 | 🟡 Major | Cargar otro archivo no invalida el resultado anterior | PROPOSE FIX | Escribe la minuta de una reunión con el nombre y la fecha de otra | Aceptado |
| 4 | A-03 | 🟡 Major | `.gitignore` no cubre resúmenes, minutas ni varias extensiones | PROPOSE FIX | Riesgo de publicar el contenido de una reunión; arreglo de minutos | Aceptado |
| 5 | A-15 | 🟡 Major | La orquestación vive dentro de la clase Tk | PROPOSE FIX | Desbloquea los tests de A-01 y A-02; conviene hacerlo junto con ellos | Aceptado |
| 6 | A-08 | 🟡 Major | Configuración relativa al directorio de trabajo y sin validar | PROPOSE FIX | Fallo al arrancar desde un acceso directo | Aceptado |
| 7 | A-06 | 🟡 Major | En modo `auto`, un token revocado no abre el login | PROPOSE FIX | Deja la IA inutilizable hasta reiniciar | Aceptado |
| 8 | A-07 | 🟡 Major | Bucle de login con `COPILOT_GITHUB_TOKEN` inválido | PROPOSE FIX | Mismo componente que A-06; se resuelven juntos | Aceptado |
| 9 | A-04 | 🟡 Major | La generación con IA no se puede cancelar | PROPOSE FIX | `AsistenteIA` ya acepta `cancelar`; falta conectarlo | Aceptado |
| 10 | A-05 | 🟡 Major | La revisión de fidelidad compara contra notas | PROPOSE FIX | Afecta a la regla de fidelidad de la minuta | Aceptado |
| 11 | A-11 | 🟡 Major | Sin resultados parciales ni aviso de truncado | PROPOSE FIX | Parte «posible»: confirmar con una respuesta real antes de planificar | Aceptado |
| 12 | A-10 | 🟡 Major | La CLI valida `srt`/`vtt` después de transcribir | PROPOSE FIX | El ejemplo de la propia ayuda falla | Aceptado |
| 13 | A-09 | 🟡 Major | La CLI ignora valores del YAML; claves muertas | PROPOSE FIX | Se resuelve con el módulo de configuración de A-08 | Aceptado |
| 14 | A-13 | 🟡 Major | Llamadas a Copilot en cada arranque | PROPOSE FIX | Ya figura como pendiente en `CLAUDE.md` | Aceptado |
| 15 | A-19 | 🟡 Major | La app reescribe `settings.yaml`, que está versionado | PROPOSE FIX | Ensucia git y acopla un test al archivo real | Aceptado |
| 16 | A-20 | 🟡 Major | Código y dependencias muertas; `ffprobe` obligatorio | PROPOSE FIX | Borrado de bajo riesgo | Aceptado |
| 17 | A-21 | 🟡 Major | Listas y formateadores duplicados | PROPOSE FIX | Ya divergen (`.ts`, `.mts`) | Aceptado |
| 18 | A-22 | 🟡 Major | `00-actual.md` omite riesgos y límites | PROPOSE FIX | Documentación; incluye las correcciones del informe de deriva y A-32 | Aceptado |
| 19 | A-17 | 🟡 Major (posible) | El login se cuelga ante respuestas inesperadas | PROPOSE FIX | Arreglo pequeño aunque no esté confirmado | Aceptado |
| 20 | A-18 | 🟡 Major (posible) | Búsqueda del historial en el hilo de la interfaz | PROPOSE FIX (posponer) | Sin medición; no merece trabajo hasta que haya cientos de entradas | Pospuesto: medir antes |
| — | A-12 | 🟡 Major | Política de modelos no aplicada en `auto` | ESCALATE | Ver arriba | Aceptado: requisito real; aplicar la política al enviar |
| — | A-14 | 🟡 Major | Dependencia de una API no documentada | ESCALATE | Ver arriba | Riesgo aceptado; sin historia |
| 21 | A-25 | 🟢 Nit | Colisión de nombres en el guardado automático | PROPOSE FIX | Sobrescribe sin aviso; se resuelve con A-01 | Aceptado |
| 22 | A-26 | 🟢 Nit | «Transcribir» se habilita sin audio | PROPOSE FIX | Una línea | Aceptado |
| 23 | A-27 | 🟢 Nit | Errores de «Guardar como…» invisibles | PROPOSE FIX | El usuario cree que guardó | Aceptado |
| 24 | A-30 | 🟢 Nit | README lista `large`; patrones muertos en `.gitignore` | PROPOSE FIX | Se hace junto con A-03 | Aceptado |
| 25 | A-29 | 🟢 Nit | Dependencias sin fijar | PROPOSE FIX | Se hace junto con A-16 | Aceptado |
| — | A-23 | 🟢 Nit | `user_version` sin migraciones; columnas sin leer | DECLINE | Sin efecto hasta el primer cambio de esquema | Descartado |
| — | A-24 | 🟢 Nit (posible) | Permisos del token si el archivo ya existía | DECLINE | Sin escenario confirmado | Descartado |
| — | A-28 | 🟢 Nit | `--ui` pierde `--log` y `--config` | DECLINE | Hay otras dos formas de lanzar la interfaz | Descartado |
| — | A-31 | 🟢 Nit | Un hilo de latido por operación | DECLINE | El propio revisor lo da por aceptable | Descartado |
| — | A-32 | 🟢 Nit | Supuestos de los tests sin documentar | DECLINE | Absorbido por A-22 | Descartado |

## Recuento

- PROPOSE FIX: 25 (1 Blocker, 19 Major, 5 Nit)
- ESCALATE: 2
- CONTEST: 0
- DECLINE: 5

## Resultado

- Aceptados para el backlog: 25 (24 propuestos más A-12)
- Pospuestos: 1 (A-18)
- Riesgo aceptado sin historia: 1 (A-14)
- Descartados: 5 (A-23, A-24, A-28, A-31, A-32)
- Impugnados: 0 · Sin atender: 0
