"""Generación de resúmenes y minutas a partir de una transcripción usando los modelos de GitHub Copilot."""

import hashlib
import json
import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Callable, Optional

import httpx

from src import copilot
from src.registro import latido

log = logging.getLogger("transcriptor.ia")


NOMBRE_PROVEEDOR = "GitHub Copilot"
MODELO_POR_DEFECTO = "gpt-4.1"
LIMITE_NOTAS_EN_CACHE = 64  # partes; equivale a unas 8 transcripciones de 8 partes
# Límite de entrada: solo se consulta el catálogo si la redacción estimada supera este umbral (historia 16)
UMBRAL_COMPROBAR_LIMITE = 32_000  # tokens estimados
# Relación medida (diseño 07, «Comprobación real», 2026-11-22): 164 993 caracteres = 70 318 tokens en claude-haiku-5.5, ≈ 2,35
CARACTERES_POR_TOKEN = 2.3

PROMPT_SISTEMA = """Eres un asistente experto en redactar documentos en español a partir de transcripciones \
automáticas de audio. Las transcripciones pueden contener errores de reconocimiento, muletillas y \
repeticiones: interprétalas con criterio.

Reglas de fidelidad (obligatorias):
1. No inventes datos: nombres, fechas, cifras, acuerdos ni tareas que no aparezcan en el texto.
2. Conserva el sentido exacto de lo dicho. Las condiciones y matices se mantienen con las mismas palabras \
del hablante, sin reformularlas: por ejemplo, "si llueve lo cancelamos" se escribe "se cancelará si llueve", \
nunca "sujeto a condiciones climáticas".
3. No agregues calificativos ni valoraciones que nadie expresó (por ejemplo "prioritario", "urgente", \
"crítico", "importante", "exitoso").
4. Escribe las fechas tal como se mencionan: no agregues el año ni las conviertas a formato numérico.
5. No deduzcas motivos, intenciones ni consecuencias que no se digan explícitamente.

Responde únicamente con el documento en Markdown, sin envolverlo en bloques de código."""

PROMPT_RESUMEN = """Redacta un resumen de la siguiente transcripción. Usa exactamente esta estructura; \
las tres secciones son obligatorias y deben aparecer en este orden:

## Resumen
Un párrafo de 3 a 6 oraciones con la idea general.

### Puntos clave
- Lista con las ideas más importantes, en orden de aparición.

### Conclusiones
- Decisiones, acuerdos o ideas con las que cierra la conversación, sin repetir literalmente los puntos clave. \
Si no hay, escribe "- Sin conclusiones explícitas".

Transcripción:
\"\"\"
{texto}
\"\"\""""

PROMPT_MINUTA = """Redacta la minuta de la reunión a partir de la siguiente transcripción. Usa exactamente \
esta estructura; todas las secciones son obligatorias:

# Minuta: <título breve deducido del contenido>

**Fecha:** {fecha}
**Participantes:** <solo personas mencionadas o que hablan; si no se identifican, "No identificados">

## Objetivo
Propósito de la reunión en 1 o 2 oraciones.

## Temas tratados
1. **<Tema>:** síntesis de lo que se discutió.

## Acuerdos
- Decisiones tomadas. Si no hay, "Sin acuerdos explícitos".

## Tareas y pendientes
| Tarea | Responsable | Fecha límite |
|-------|-------------|--------------|
Incluye todas las tareas, encargos y entregables comprometidos (también los que tienen fecha de entrega). \
Todo acuerdo que tenga una persona responsable también es una tarea y debe aparecer en esta tabla, igual que \
las fechas de entrega que alguien estima para su propio trabajo (con esa persona como responsable). \
Cada celda contiene solo el dato, sin comentarios ni paréntesis añadidos. Usa exactamente "No asignado" o \
"Sin fecha" cuando no se mencione. Si no hay tareas, escribe una fila indicando "Sin tareas".

## Próximos pasos
- Siguientes acciones o próxima reunión, si se mencionan.

Transcripción:
\"\"\"
{texto}
\"\"\""""

PROMPT_REVISION = """Revisa el DOCUMENTO comparándolo frase por frase con la TRANSCRIPCIÓN y corrige únicamente:
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
\"\"\"
{texto}
\"\"\"

DOCUMENTO:
\"\"\"
{documento}
\"\"\""""

# El resumen no tiene reposición: no se le pide quitar nada, solo corregir (regla 4)
PROMPT_REVISION_RESUMEN = """Revisa el DOCUMENTO comparándolo frase por frase con la TRANSCRIPCIÓN y corrige únicamente:
- Condiciones, matices o compromisos reformulados con otro sentido: reescríbelos con las palabras de la \
transcripción (por ejemplo, si se dijo "lo entrego el lunes si me llegan los datos", no puede quedar \
"entrega sujeta a validación de datos").
- Datos que no aparecen en la transcripción (nombres, fechas, cifras).
- Calificativos o valoraciones que nadie expresó.

No cambies la estructura, los títulos, el orden ni el estilo; no elimines secciones ni tareas. Si no hay nada \
que corregir, devuelve el documento igual. Responde solo con el documento completo.

TRANSCRIPCIÓN:
\"\"\"
{texto}
\"\"\"

DOCUMENTO:
\"\"\"
{documento}
\"\"\""""

PROMPT_NOTAS_BLOQUE = """Esta es la parte {n} de {total} de una transcripción larga. Extrae notas detalladas \
en viñetas: temas, argumentos, nombres, fechas, cifras, decisiones y tareas con su responsable. \
Conserva las condiciones y matices tal como se dijeron. No redactes conclusiones generales ni añadas \
valoraciones, solo notas fieles al texto.

Fragmento:
\"\"\"
{texto}
\"\"\""""


SECCIONES_RESUMEN = ["## Resumen", "### Puntos clave", "### Conclusiones"]
SECCIONES_MINUTA = ["# Minuta", "## Objetivo", "## Temas tratados", "## Acuerdos",
                    "## Tareas y pendientes", "## Próximos pasos"]


def estimar_tokens(texto: str) -> int:
    """Tokens estimados de un texto: caracteres entre CARACTERES_POR_TOKEN, redondeado hacia arriba. La división es
    entera para que no haya error de coma flotante (230 caracteres son 100 tokens y 231, 101)."""
    return -(-len(texto) * 10 // round(CARACTERES_POR_TOKEN * 10))


def secciones_faltantes(documento: str, secciones: list[str]) -> list[str]:
    lineas = [linea.strip().lower() for linea in documento.splitlines()]
    return [s for s in secciones if not any(linea.startswith(s.lower()) for linea in lineas)]


def _lineas_de_seccion(documento: str, titulo: str) -> list[str]:
    """Líneas de la sección que empieza por `titulo`, sin el encabezado, hasta el siguiente encabezado de nivel 1 o 2."""
    lineas, dentro = [], False
    for linea in documento.splitlines():
        if linea.strip().lower().startswith(titulo.lower()):
            dentro = True
        elif dentro and re.match(r"#{1,2} ", linea.strip()):
            break
        elif dentro:
            lineas.append(linea)
    return lineas


def contar_filas_tareas(minuta: str) -> int:
    """Filas de datos de la tabla de tareas: sin la cabecera ni el separador |---|."""
    filas = [l.strip() for l in _lineas_de_seccion(minuta, "## Tareas y pendientes") if l.strip().startswith("|")]
    filas = [f for f in filas if not set(f.replace("|", "").strip()) <= set("-: ")]  # quita el separador
    return max(0, len(filas) - 1)  # quita la cabecera


def contar_vinetas_acuerdos(minuta: str) -> int:
    """Viñetas de la sección de acuerdos."""
    return sum(1 for l in _lineas_de_seccion(minuta, "## Acuerdos") if re.match(r"\s*[-*] ", l))


MARCA_REPUESTA = "[comprobar]"  # en las filas y viñetas que la app repone cuando la revisión las quitó
TITULO_TAREAS = "## Tareas y pendientes"
TITULO_ACUERDOS = "## Acuerdos"
CABECERA_TAREAS = "| Tarea | Responsable | Fecha límite |"
SEPARADOR_TAREAS = "|-------|-------------|--------------|"


def _seccion(lineas: list[str], titulo: str) -> Optional[tuple[int, int]]:
    """Índices (inicio, fin) de la sección que empieza por `titulo`, con su encabezado; `fin` no se incluye.
    None si la sección no está."""
    inicio = next((i for i, l in enumerate(lineas) if l.strip().lower().startswith(titulo.lower())), None)
    if inicio is None:
        return None
    fin = next((i for i in range(inicio + 1, len(lineas)) if re.match(r"#{1,2} ", lineas[i].strip())), len(lineas))
    return inicio, fin


def _es_separador(linea: str) -> bool:
    return set(linea.replace("|", "").strip()) <= set("-: ")


def _celdas(linea: str) -> list[str]:
    """Celdas de una fila; un «\\|» dentro de una celda no separa."""
    return [c.strip() for c in re.split(r"(?<!\\)\|", linea.strip().strip("|"))]


def _clave(texto: str) -> str:
    """Forma comparable de una fila o viñeta: minúsculas, espacios colapsados y sin punto final."""
    return " ".join(texto.lower().split()).rstrip(".")


def _clave_fila(linea: str) -> str:
    return _clave(" | ".join(_celdas(linea)))


def _filas_tareas(lineas: list[str]) -> list[int]:
    """Índices de las filas de datos de la tabla de tareas: sin cabecera, separador ni la fila «Sin tareas». La primera
    fila es cabecera solo si la sigue el separador; una tabla sin cabecera (la revisión a veces la quita) da todas."""
    rango = _seccion(lineas, TITULO_TAREAS)
    if rango is None:
        return []
    inicio, fin = rango
    filas = [i for i in range(inicio + 1, fin) if lineas[i].strip().startswith("|") and not _es_separador(lineas[i])]
    con_cabecera = bool(filas) and filas[0] + 1 < len(lineas) and lineas[filas[0] + 1].strip().startswith("|") \
        and _es_separador(lineas[filas[0] + 1])
    datos = filas[1:] if con_cabecera else filas
    return [i for i in datos if not _es_relleno_tarea(lineas[i])]


def _es_relleno_tarea(linea: str) -> bool:
    """La fila «Sin tareas» (de una o de varias columnas), que la app no cuenta como tarea."""
    return _celdas(linea)[0].lower().rstrip(".") == "sin tareas"


def _pendientes(antes: list[str], despues: list[str], clave) -> list[str]:
    """Filas de `antes` sin pareja en `despues`. Si `despues` no tiene menos, no falta ninguna. Las parejas se eligen de
    mayor a menor similitud (a igualdad, el orden original de antes y de después), una a una. Las iguales (similitud 1)
    se emparejan primero, en orden, sin comparar nada; solo lo que sobra se compara, así que una revisión que quita filas
    sin reescribir las demás cuesta casi nada."""
    if len(despues) >= len(antes):
        return []
    libres: dict[str, list[int]] = {}
    for j, b in enumerate(despues):
        libres.setdefault(clave(b), []).append(j)
    usadas_antes, usadas_despues = set(), set()
    for i, a in enumerate(antes):
        candidatas = libres.get(clave(a))
        if candidatas:
            usadas_antes.add(i)
            usadas_despues.add(candidatas.pop(0))
    sobrantes_antes = [i for i in range(len(antes)) if i not in usadas_antes]
    sobrantes_despues = [j for j in range(len(despues)) if j not in usadas_despues]
    pares = sorted((-SequenceMatcher(None, clave(antes[i]), clave(despues[j])).ratio(), i, j)
                   for i in sobrantes_antes for j in sobrantes_despues)
    for _, i, j in pares:
        if i not in usadas_antes and j not in usadas_despues:
            usadas_antes.add(i)
            usadas_despues.add(j)
    return [a for i, a in enumerate(antes) if i not in usadas_antes]


def _tareas_quitadas(antes: str, despues: str) -> list[str]:
    la, ld = antes.splitlines(), despues.splitlines()
    return _pendientes([la[i] for i in _filas_tareas(la)], [ld[i] for i in _filas_tareas(ld)], _clave_fila)


def _marcar_fila(linea: str) -> str:
    celdas = _celdas(linea)
    celdas[0] += f" {MARCA_REPUESTA}"
    return "| " + " | ".join(celdas) + " |"


def _elemento_de_tarea(linea: str) -> str:
    """Cómo se nombra una tarea en la nota: «tarea (responsable)», o solo la tarea sin responsable conocido."""
    tarea, responsable = (_celdas(linea) + ["", ""])[:2]
    if not responsable or responsable.lower() == "no asignado":
        return tarea
    return f"{tarea} ({responsable})"


def _reponer_tareas(lineas: list[str], quitadas: list[str]) -> list[str]:
    """Añade al final de la tabla de tareas las filas quitadas, marcadas; si no hay tabla, bajo el título. Quita la fila
    de relleno «Sin tareas», que ya no hace falta."""
    inicio, fin = _seccion(lineas, TITULO_TAREAS)
    lineas = [l for i, l in enumerate(lineas)
              if not (inicio < i < fin and l.strip().startswith("|") and _es_relleno_tarea(l))]
    inicio, fin = _seccion(lineas, TITULO_TAREAS)
    filas = [i for i in range(inicio + 1, fin) if lineas[i].strip().startswith("|")]
    marcadas = [_marcar_fila(l) for l in quitadas]
    if filas:
        pos = filas[-1] + 1
        return lineas[:pos] + marcadas + lineas[pos:]
    return lineas[:inicio + 1] + [CABECERA_TAREAS, SEPARADOR_TAREAS] + marcadas + lineas[inicio + 1:]


def _es_vineta(linea: str) -> bool:
    return re.match(r"\s*[-*] ", linea) is not None


def _texto_de_vineta(linea: str) -> str:
    return re.sub(r"^\s*[-*] ", "", linea).strip()


def _es_relleno_acuerdo(linea: str) -> bool:
    return _clave(_texto_de_vineta(linea)) == "sin acuerdos explícitos"


def _vinetas_acuerdos(lineas: list[str]) -> list[int]:
    """Índices de las viñetas de «## Acuerdos», sin la viñeta «Sin acuerdos explícitos»."""
    rango = _seccion(lineas, TITULO_ACUERDOS)
    if rango is None:
        return []
    inicio, fin = rango
    return [i for i in range(inicio + 1, fin) if _es_vineta(lineas[i]) and not _es_relleno_acuerdo(lineas[i])]


def _acuerdos_quitados(antes: str, despues: str) -> list[str]:
    la, ld = antes.splitlines(), despues.splitlines()
    return _pendientes([la[i] for i in _vinetas_acuerdos(la)], [ld[i] for i in _vinetas_acuerdos(ld)],
                       lambda linea: _clave(_texto_de_vineta(linea)))


def _reponer_acuerdos(lineas: list[str], quitados: list[str]) -> list[str]:
    """Añade tras la última viñeta de Acuerdos las quitadas, marcadas. Si se repone algo, sale la viñeta «Sin acuerdos
    explícitos»."""
    inicio, fin = _seccion(lineas, TITULO_ACUERDOS)
    lineas = [l for i, l in enumerate(lineas) if not (inicio < i < fin and _es_relleno_acuerdo(l))]
    inicio, fin = _seccion(lineas, TITULO_ACUERDOS)
    vinetas = [i for i in range(inicio + 1, fin) if _es_vineta(lineas[i])]
    marcadas = [f"- {_texto_de_vineta(l)} {MARCA_REPUESTA}" for l in quitados]
    pos = vinetas[-1] + 1 if vinetas else inicio + 1
    return lineas[:pos] + marcadas + lineas[pos:]


def _sin_donde_reponer(despues: str, quitadas: list[str], quitados: list[str]) -> bool:
    """Hay tareas o acuerdos que reponer y `despues` ya no tiene el título de su sección, donde irían."""
    dl = despues.splitlines()
    return (bool(quitadas) and _seccion(dl, TITULO_TAREAS) is None
            or bool(quitados) and _seccion(dl, TITULO_ACUERDOS) is None)


def reponer_lo_quitado(antes: str, despues: str, quitadas: Optional[list[str]] = None,
                       quitados: Optional[list[str]] = None) -> tuple[str, list[str]]:
    """Devuelve `despues` con lo que la revisión quitó de las tareas y de los acuerdos, repuesto y marcado, y la lista de
    lo repuesto para la nota. Solo repone donde `despues` tiene menos filas o viñetas que `antes`. `quitadas` y `quitados`
    son lo que ya calculó `_tareas_quitadas` y `_acuerdos_quitados`; si no se pasan, se calculan."""
    if quitadas is None:
        quitadas = _tareas_quitadas(antes, despues)
    if quitados is None:
        quitados = _acuerdos_quitados(antes, despues)
    if not quitadas and not quitados:
        return despues, []
    lineas = despues.splitlines()
    if quitadas:
        lineas = _reponer_tareas(lineas, quitadas)
    if quitados:
        lineas = _reponer_acuerdos(lineas, quitados)
    elementos = [_elemento_de_tarea(l) for l in quitadas] + [_texto_de_vineta(l) for l in quitados]
    return "\n".join(lineas), elementos


class ErrorAsistenteIA(Exception):
    pass


class _TextoDeCopilot(str):
    """Texto de una respuesta de Copilot. `corte` es el motivo por el que Copilot la cortó (None si terminó bien).
    Va en el propio resultado y no en el asistente: las partes se piden en paralelo y no deben compartir estado."""
    corte: Optional[str] = None


def _corte(texto) -> Optional[str]:
    """Motivo del corte de una respuesta; None si no se cortó (o si es un texto sin esa información)."""
    return getattr(texto, "corte", None)


def _sin_cortar(texto: str) -> str:
    """Una pasada posterior a la redacción no puede mejorar el documento con una respuesta incompleta: si Copilot la
    cortó, falla como cualquier error recuperable de esa pasada (y su motivo va en la nota)."""
    motivo = _corte(texto)
    if motivo:
        raise ErrorAsistenteIA(f"Copilot cortó la respuesta: {motivo}")
    return texto


class ErrorSinSesionCopilot(ErrorAsistenteIA):
    """No hay sesión de GitHub Copilot o fue rechazada: hay que iniciar sesión."""


class ErrorModeloIA(ErrorAsistenteIA):
    """El modelo no se puede usar (vacío, de una familia no autorizada o sin ninguno válido en auto): no se envía nada,
    así que tampoco hay documento que entregar."""


@dataclass
class _Documento:
    """Resultado de `_generar`: el texto y lo necesario para sus notas de la aplicación."""
    texto: str
    partes: int
    faltan: list[str]
    error_secciones: Optional[str] = None  # motivo si no se pudieron pedir de nuevo las secciones que faltaban
    error_revision: Optional[str] = None  # motivo si la revisión de fidelidad no se pudo completar
    corte: Optional[str] = None  # motivo si Copilot cortó la respuesta que quedó en el documento
    cortes_partes: dict = field(default_factory=dict)  # parte -> motivo, de las notas que Copilot cortó
    revision_descartada: Optional[str] = None  # motivo si la revisión se descartó y se conservó el documento anterior
    repuestas: list[str] = field(default_factory=list)  # tareas que la revisión quitó y que la app repuso marcadas
    fuente_revision: str = "notas"  # con qué se revisó: "transcripcion" o "notas"
    motivo_notas: Optional[tuple[int, int, str]] = None  # (estimado, límite, modelo) si la transcripción no cupo


@dataclass
class _ConsultaDeLimite:
    """Estado de la consulta al catálogo en una generación: si falló, no se repite en esa generación."""
    error: Optional[str] = None  # motivo del fallo; None si no se consultó o salió bien


@dataclass
class FuenteRevision:
    """Lo que la revisión de fidelidad recibe como fuente: la transcripción completa o las notas de las partes."""
    tipo: str  # "transcripcion" o "notas"
    texto: str  # lo que va en {texto} de PROMPT_REVISION
    motivo: Optional[tuple[int, int, str]] = None  # (estimado, límite, modelo) si la transcripción no cupo


def _fallo_recuperable(error: ErrorAsistenteIA) -> bool:
    """Si una pasada posterior a la redacción falla con esto, se entrega lo ya redactado con una nota. No lo es la falta
    de sesión (hay que iniciar sesión) ni un modelo no autorizado o vacío (no se envía nada a ningún modelo)."""
    return not isinstance(error, (ErrorSinSesionCopilot, ErrorModeloIA))


MOTIVOS_DE_CORTE = {"length": "límite de longitud del modelo",  # finish_reason de Copilot -> motivo para el usuario
                   "content_filter": "filtro de contenido de Copilot"}


def _motivo_de_corte(fin: Optional[str], cerrado: bool) -> Optional[str]:
    """Por qué Copilot cortó la respuesta, o None si terminó bien. Sin `finish_reason` y sin [DONE] el stream se cortó;
    con `stop` (con o sin [DONE]) o con [DONE] sin `finish_reason` terminó, aunque no conste el motivo."""
    if fin in MOTIVOS_DE_CORTE:
        return MOTIVOS_DE_CORTE[fin]
    if fin is None and not cerrado:
        return "la respuesta terminó sin la marca de cierre"
    return None


MAX_MOTIVO_NOTA = 120  # caracteres: el motivo se incrusta en una nota que se guarda y se exporta


def _motivo(error: Exception) -> str:
    """Motivo de una nota de la aplicación: de una sola línea (el cuerpo de una respuesta puede traer saltos que
    romperían la cita Markdown) y recortado si es largo."""
    texto = " ".join(str(error).split()).rstrip(".")
    return texto if len(texto) <= MAX_MOTIVO_NOTA else texto[:MAX_MOTIVO_NOTA] + "…"


def dividir_texto(texto: str, max_caracteres: int) -> list[str]:
    """Divide el texto en bloques parejos de hasta `max_caracteres`, cortando por líneas u oraciones.

    Los bloques se equilibran: 61 000 caracteres con límite 60 000 dan dos de ~30 500, no uno de 60 000
    y otro diminuto (el bloque grande es el que más tarda y los bloques se procesan en paralelo).
    """
    if len(texto) <= max_caracteres:
        return [texto]

    objetivo = math.ceil(len(texto) / math.ceil(len(texto) / max_caracteres))
    bloques, actual = [], ""
    unidades = texto.splitlines(keepends=True) if "\n" in texto else texto.replace(". ", ".\n").splitlines(keepends=True)
    for unidad in unidades:
        while len(unidad) > max_caracteres:  # unidad demasiado larga: corte duro
            if actual:
                bloques.append(actual)
                actual = ""
            bloques.append(unidad[:max_caracteres])
            unidad = unidad[max_caracteres:]
        if actual and len(actual) + len(unidad) > max_caracteres:
            bloques.append(actual)
            actual = ""
        actual += unidad
        if len(actual) >= objetivo:  # bloque completo: se cierra en el primer corte de línea tras el objetivo
            bloques.append(actual)
            actual = ""
    if actual.strip():
        bloques.append(actual)
    return bloques


def limpiar_respuesta(texto: str) -> str:
    """Quita el bloque ```markdown ... ``` con el que a veces el modelo envuelve la respuesta."""
    texto = texto.strip()
    if texto.startswith("```") and texto.endswith("```"):
        texto = texto.split("\n", 1)[1] if "\n" in texto else ""
        texto = texto[:-3]
    return texto.strip()


def normalizar_tabla_tareas(minuta: str) -> str:
    """En la columna de fecha límite, el modelo a veces escribe "No asignado" en vez de "Sin fecha"; y a veces
    añade la fila "Sin tareas" aunque la tabla sí tenga tareas."""
    lineas = []
    for linea in minuta.splitlines():
        celdas = linea.split("|")
        # | Tarea | Responsable | Fecha | -> ['', tarea, responsable, fecha, '']
        if len(celdas) == 5 and celdas[3].strip().lower() == "no asignado":
            celdas[3] = " Sin fecha "
            linea = "|".join(celdas)
        lineas.append(linea)

    def es_fila_sin_tareas(linea: str) -> bool:
        celdas = linea.split("|")
        return len(celdas) == 5 and celdas[1].strip().lower().rstrip(".") == "sin tareas"

    filas_tarea = [l for l in lineas if len(l.split("|")) == 5 and not set(l.replace("|", "").strip()) <= set("-: ")]
    if len(filas_tarea) > 2 and any(es_fila_sin_tareas(l) for l in filas_tarea):  # encabezado + tareas reales
        lineas = [l for l in lineas if not es_fila_sin_tareas(l)]
    return "\n".join(lineas)


def _cita_de_partes(partes: int, revisado: bool, *, fuente_revision: str = "notas",
                    motivo_notas: Optional[tuple[int, int, str]] = None) -> str:
    cita = (f"> Nota de la aplicación: la transcripción se procesó en {partes} partes y este documento se "
            "redactó a partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, "
            "fechas, cifras y condiciones con la transcripción antes de darlo por bueno.")
    if revisado and fuente_revision == "transcripcion":
        cita += (" La revisión de fidelidad lo contrastó después con la transcripción completa, pero es automática: no "
                 "sustituye a esa comprobación.")
    elif revisado and motivo_notas:
        estimado, limite, modelo = motivo_notas
        cita += (" La revisión de fidelidad se hizo contra esas notas y no contra la transcripción completa, que suma "
                 f"unos {estimado} tokens y supera los {limite} que admite «{modelo}».")
    elif revisado:
        cita += " La revisión de fidelidad se hizo contra esas notas, no contra la transcripción."
    return cita


def _nota_de_corte(motivo: str) -> str:
    return (f"> Nota de la aplicación: Copilot cortó su respuesta antes de terminarla ({motivo}); este documento puede "
            "estar incompleto. No lo des por completo: vuelve a generarlo o "
            "complétalo con la transcripción.")


def _nota_de_cortes_de_partes(cortes: dict, total: int) -> str:
    ordenadas = sorted(cortes.items())
    if len(ordenadas) == 1:
        parte, motivo = ordenadas[0]
        return (f"> Nota de la aplicación: Copilot cortó antes de terminarlas las notas de la parte {parte} de {total} "
                f"({motivo}); lo que se dijo en esa parte puede faltar en este documento.")
    detalle = [f"{parte} ({motivo})" for parte, motivo in ordenadas]
    lista = ", ".join(detalle[:-1]) + " y " + detalle[-1]
    return (f"> Nota de la aplicación: Copilot cortó antes de terminarlas las notas de las partes {lista} de {total}; "
            "lo que se dijo en esas partes puede faltar en este documento.")


def _recortado(texto: str) -> str:
    """Una línea y, si pasa de MAX_MOTIVO_NOTA caracteres, sus primeros caracteres y «…» (sin quitar el punto final)."""
    texto = " ".join(texto.split())
    return texto if len(texto) <= MAX_MOTIVO_NOTA else texto[:MAX_MOTIVO_NOTA] + "…"


def _lista_entre_comillas(elementos: list[str]) -> str:
    citados = [f"«{e}»" for e in elementos[:5]]
    if len(elementos) > 5:
        return ", ".join(citados) + f" y {len(elementos) - 5} más"
    if len(citados) == 1:
        return citados[0]
    return ", ".join(citados[:-1]) + " y " + citados[-1]


def _cita_de_lo_repuesto(repuestas: list[str]) -> str:
    return ("> Nota de la aplicación: la revisión de fidelidad quiso quitar de la minuta lo siguiente por no encontrarlo "
            "en la transcripción; la app lo ha repuesto marcado con «[comprobar]»: "
            f"{_lista_entre_comillas([_recortado(r) for r in repuestas])}. "
            "Compruébalo con la transcripción y bórralo si no se dijo.")


def notas_de_la_aplicacion(faltan: list[str], partes: int, revisado: bool,
                           error_secciones: Optional[str] = None, error_revision: Optional[str] = None,
                           corte: Optional[str] = None, cortes_partes: Optional[dict] = None, *,
                           revision_descartada: Optional[str] = None,
                           repuestas: Optional[list[str]] = None,
                           fuente_revision: str = "notas",
                           motivo_notas: Optional[tuple[int, int, str]] = None) -> str:
    """Bloque final que la app añade a un documento: una sola línea horizontal y, debajo, las notas que apliquen
    (primero las de secciones, después la de la revisión y la de las partes). Vacío si no hay nada que avisar.
    `error_secciones` y `error_revision`: motivo por el que no se pudo completar esa pasada."""
    citas = []
    if corte:
        citas.append(_nota_de_corte(corte))
    if cortes_partes:
        citas.append(_nota_de_cortes_de_partes(cortes_partes, partes))
    if error_secciones:
        citas.append(f"> Nota de la aplicación: no se pudieron pedir de nuevo a Copilot las secciones que faltaban "
                     f"({error_secciones}).")
    if faltan:
        nombres = ", ".join(s.lstrip("# ") for s in faltan)
        if error_secciones:  # ya no se pidieron: no se puede decir que Copilot no las devolvió
            citas.append("> Nota de la aplicación: a este documento le faltan secciones obligatorias: " + nombres + ". "
                         "No lo des por completo: vuelve a generarlo o complétalo con la transcripción.")
        else:
            citas.append("> Nota de la aplicación: a este documento le faltan secciones obligatorias que Copilot no "
                         "devolvió ni al pedírselas de nuevo: " + nombres + ". No lo des por completo: vuelve a generarlo "
                         "o complétalo con la transcripción.")
    if error_revision:
        citas.append(f"> Nota de la aplicación: la revisión de fidelidad no se pudo completar ({error_revision}); "
                     "este documento no está revisado.")
    if revision_descartada:
        citas.append(f"> Nota de la aplicación: la revisión de fidelidad se descartó porque {revision_descartada}; "
                     "este documento no está revisado.")
    if repuestas:
        citas.append(_cita_de_lo_repuesto(repuestas))
    if partes >= 2:
        citas.append(_cita_de_partes(partes, revisado, fuente_revision=fuente_revision, motivo_notas=motivo_notas))
    if not citas:
        return ""
    return "\n---\n\n" + "\n\n".join(citas)


def nota_de_notas(partes: int, revisado: bool, *, fuente_revision: str = "notas",
                  motivo_notas: Optional[tuple[int, int, str]] = None) -> str:
    """Bloque que la app añade al final de un documento redactado a partir de notas (2 o más partes).
    Lo añade la app, no el modelo: ningún prompt lo contiene y el post-proceso no lo toca."""
    return notas_de_la_aplicacion([], partes, revisado, fuente_revision=fuente_revision, motivo_notas=motivo_notas)


def _frase_de_partes_conservadas(n: int) -> str:
    if n == 0:
        return "No se conserva ninguna nota: al volver a generar se pedirán todas las partes."
    if n == 1:
        return "Se conserva la nota de la parte que terminó; al volver a generar solo se pedirán las que faltan."
    return f"Se conservan las notas de las {n} partes que terminaron; al volver a generar solo se pedirán las que faltan."


TOPE_RETRY_AFTER = 60  # segundos: un Retry-After mayor no se espera, la generación falla con el aviso


def _retry_after(respuesta) -> Optional[float]:
    """Segundos que pide la cabecera Retry-After (solo se entiende el número de segundos, no una fecha).
    None si falta, no es un número o es negativo: entonces se usa la espera fija."""
    try:
        segundos = float(respuesta.headers.get("Retry-After"))
    except (TypeError, ValueError):
        return None
    return segundos if math.isfinite(segundos) and segundos >= 0 else None


def _esperar(segundos: float, cancelar: Optional[threading.Event]) -> None:
    """Espera entre reintentos. Con `cancelar`, la espera se corta en cuanto se activa la señal."""
    if cancelar:
        cancelar.wait(segundos)
    else:
        time.sleep(segundos)


class AsistenteIA:
    def __init__(
        self,
        api_key: Optional[str] = None,
        modelo: str = MODELO_POR_DEFECTO,
        temperatura: float = 0.3,
        max_caracteres_bloque: int = 60000,
        timeout: float = 180.0,  # segundos máximos SIN recibir datos (no la duración total)
        revision_fidelidad: bool = True,
        peticiones_paralelas: int = 3,
        enterprise_url: Optional[str] = None,  # dominio de GitHub Enterprise, si se usa
    ):
        """`api_key`: token de GitHub; si se omite, se usa la sesión guardada (ver copilot.leer_token)."""
        self.nombre_proveedor = NOMBRE_PROVEEDOR
        sesion = copilot.leer_token(enterprise_url) if not api_key else None
        self.api_key = api_key or (sesion.token if sesion else None)
        if not self.api_key:
            raise ErrorSinSesionCopilot("No has iniciado sesión en GitHub Copilot.")
        if sesion:
            log.info("Usando la sesión de GitHub Copilot de %s", sesion.origen)
        self._origen_token = sesion.origen if sesion else ""
        self.url = copilot.url_api(enterprise_url) + "/chat/completions"
        self.enterprise_url = enterprise_url
        self.modelo = modelo
        self.temperatura = temperatura
        self.max_caracteres_bloque = max_caracteres_bloque
        self.timeout = timeout
        self.revision_fidelidad = revision_fidelidad
        self.peticiones_paralelas = max(1, peticiones_paralelas)
        # Notas por parte (clave de `_clave_nota` → notas); el cerrojo las protege: las partes van en paralelo
        self._cache_notas: dict[str, str] = {}
        self._cerrojo_cache = threading.Lock()
        # Solo la primera petición de cada documento la inicia el usuario; las demás (partes,
        # reintentos, revisión) son pasos automáticos ("agent"), como hace opencode
        self._pendiente_iniciador_usuario = True
        self._cerrojo_iniciador = threading.Lock()
        # Modelo "auto": sesión compartida por las peticiones en paralelo, renovada antes de caducar
        self.es_auto = modelo == copilot.MODELO_AUTO
        self._sesion_auto: Optional[copilot.SesionAuto] = None
        self._cerrojo_auto = threading.Lock()
        # Límites de entrada del catálogo (id -> tokens), leídos una vez por asistente cuando hacen falta
        self._limites: Optional[dict[str, int]] = None
        self._cerrojo_limites = threading.Lock()

    @property
    def modelo_usado(self) -> str:
        """Nombre para mostrar y guardar en el historial: en modo auto, también el modelo que eligió Copilot."""
        if self.es_auto and self._sesion_auto:
            return f"auto → {self._sesion_auto.modelo}"
        return self.modelo

    def _error_de_token_rechazado(self) -> ErrorAsistenteIA:
        """Copilot rechazó el token (401). Si viene de la variable de entorno, iniciar sesión no lo arregla (la variable
        sigue ganando al leerlo): se dice así y el archivo propio no se toca. Si no, se invalida el token guardado y se
        pide iniciar sesión."""
        if self._origen_token == copilot.VARIABLE_ENTORNO:
            return ErrorAsistenteIA("GitHub Copilot rechazó el token de la variable de entorno COPILOT_GITHUB_TOKEN. "
                                    "Corrígela o quítala para usar la sesión guardada con el inicio de sesión de la app.")
        copilot.invalidar_token(self.api_key)
        return ErrorSinSesionCopilot("La sesión de GitHub Copilot caducó o fue revocada (401). Vuelve a iniciar sesión.")

    def _resolver_auto(self) -> copilot.SesionAuto:
        with self._cerrojo_auto:
            if self._sesion_auto is None or not self._sesion_auto.vigente():
                try:
                    self._sesion_auto = copilot.abrir_sesion_auto(copilot.Sesion(self.api_key, self.enterprise_url))
                except copilot.ErrorSesionCopilot as e:  # el token rechazado: igual que el 401 de /chat/completions
                    raise self._error_de_token_rechazado() from e
                except copilot.ErrorModeloCopilot as e:
                    raise ErrorModeloIA(str(e)) from e
                except copilot.ErrorCopilot as e:
                    raise ErrorAsistenteIA(str(e)) from e
            return self._sesion_auto

    def _cabeceras(self) -> dict:
        with self._cerrojo_iniciador:
            iniciador = "user" if self._pendiente_iniciador_usuario else "agent"
            self._pendiente_iniciador_usuario = False
        return copilot.cabeceras(self.api_key, iniciador)

    def _modelo_para_peticion(self) -> tuple[str, Optional[copilot.SesionAuto]]:
        """Resuelve y valida el modelo de la próxima petición. En modo auto abre (o reutiliza) la sesión.
        Sus errores salen tal cual: no se ha enviado nada todavía."""
        sesion_auto = self._resolver_auto() if self.es_auto else None
        modelo = sesion_auto.modelo if sesion_auto else self.modelo
        if not isinstance(modelo, str) or not modelo.strip():
            raise ErrorModeloIA("No hay ningún modelo de IA configurado. Elige uno en el selector o en "
                                "`ia.modelo` de config/settings.yaml.")
        familia = copilot.familia_excluida(modelo)
        if familia:  # antes de enviar nada: ni la transcripción ni ninguna parte sale hacia ese modelo
            raise ErrorModeloIA(f"El modelo «{modelo}» es de la familia «{familia}», que no está autorizada por la "
                                "empresa. Elige otro modelo en el selector o en `ia.modelo` de config/settings.yaml.")
        return modelo, sesion_auto

    def _modelo_y_cabeceras(self) -> tuple[str, dict]:
        cabeceras = self._cabeceras()
        modelo, sesion_auto = self._modelo_para_peticion()
        if sesion_auto:
            cabeceras = cabeceras | {"Copilot-Session-Token": sesion_auto.session_token}
        return modelo, cabeceras

    def _completar(self, prompt, cancelar: Optional[threading.Event] = None) -> str:
        """`prompt` es el texto del usuario o una lista de mensajes adicionales (para reintentos)."""
        mensajes = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt
        if cancelar and cancelar.is_set():
            raise InterruptedError  # antes de resolver el modelo: en modo auto eso puede abrir una sesión nueva
        modelo, cabeceras = self._modelo_y_cabeceras()
        cuerpo = {
            "model": modelo,
            "messages": [{"role": "system", "content": PROMPT_SISTEMA}, *mensajes],
            # En streaming el timeout cuenta el tiempo SIN recibir datos, no el total: los modelos con
            # razonamiento pueden tardar varios minutos con transcripciones largas, pero envían tokens sin parar.
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": self.temperatura,
        }
        timeout = httpx.Timeout(30.0, read=self.timeout)

        caracteres = sum(len(m["content"]) for m in cuerpo["messages"])
        for intento in range(4):
            if cancelar and cancelar.is_set():
                raise InterruptedError
            log.info("Petición a %s (%s): %d caracteres, intento %d/4", self.nombre_proveedor, self.modelo_usado,
                     caracteres, intento + 1)
            inicio = time.monotonic()
            recibido = {"razonamiento": 0, "contenido": 0}
            estado = lambda: (f"recibiendo de {self.nombre_proveedor}: razonamiento {recibido['razonamiento']} car., "
                              f"respuesta {recibido['contenido']} car.")
            try:
                with latido(estado, cada=30), \
                        httpx.stream("POST", self.url, json=cuerpo, headers=cabeceras,
                                     timeout=timeout) as respuesta:
                    if respuesta.status_code >= 400:
                        respuesta.read()
                    else:
                        partes, fin, uso, cerrado = self._leer_stream(respuesta, recibido, cancelar)
            except httpx.HTTPError as e:
                log.warning("Fallo de conexión con %s tras %.1f s (%s): %r", self.nombre_proveedor,
                            time.monotonic() - inicio, estado(), e)
                if intento == 3:
                    raise ErrorAsistenteIA(f"No se pudo conectar con {self.nombre_proveedor}: {e}") from e
                _esperar(2 ** intento, cancelar)
                continue
            segundos = time.monotonic() - inicio

            # Límite de peticiones o error temporal del servidor: reintentar con espera creciente
            if respuesta.status_code == 429 or respuesta.status_code >= 500:
                espera = _retry_after(respuesta)
                if espera is not None and espera > TOPE_RETRY_AFTER:  # esperar tanto bloquearía la generación
                    raise ErrorAsistenteIA(f"{self.nombre_proveedor} respondió {respuesta.status_code}: "
                                           f"{respuesta.text[:300].rstrip('.')}. Copilot pide esperar {espera:g} s "
                                           "antes de reintentar.")
                if espera is None:
                    espera = 2 ** (intento + 1)
                log.warning("%s respondió %d en %.1f s; reintentando en %d s: %s", self.nombre_proveedor,
                            respuesta.status_code, segundos, espera, respuesta.text[:200])
                if intento == 3:
                    raise ErrorAsistenteIA(f"{self.nombre_proveedor} respondió {respuesta.status_code}: {respuesta.text[:300]}")
                _esperar(espera, cancelar)
                continue
            if respuesta.status_code >= 400:
                log.error("%s respondió %d en %.1f s: %s", self.nombre_proveedor, respuesta.status_code,
                          segundos, respuesta.text[:300])
            if respuesta.status_code == 400 and "temperature" in cuerpo and "temperature" in respuesta.text.lower():
                # Algunos modelos (p. ej. los de razonamiento) solo admiten la temperatura por defecto
                log.warning("%s no admite temperatura en %s; se reintenta sin ella", self.modelo, self.nombre_proveedor)
                del cuerpo["temperature"]
                continue
            if respuesta.status_code == 401 and self.es_auto and intento < 3:
                # Puede haber caducado la sesión auto y no el token de GitHub: se abre otra y se reintenta
                log.warning("Copilot rechazó la sesión auto (401); se abre una nueva")
                with self._cerrojo_auto:
                    self._sesion_auto = None
                modelo, cabeceras = self._modelo_y_cabeceras()
                cuerpo["model"] = modelo
                continue
            if respuesta.status_code == 401:
                raise self._error_de_token_rechazado()
            if respuesta.status_code == 400 and "model_not_supported" in respuesta.text:
                raise ErrorAsistenteIA(f"Tu plan de GitHub Copilot no permite usar el modelo «{self.modelo}». Elige otro "
                                       "en `ia.modelo` de config/settings.yaml (gpt-4.1 está en todos los planes).")
            if respuesta.status_code == 403:
                raise ErrorAsistenteIA("GitHub Copilot rechazó la petición (403): la cuenta no tiene Copilot activo "
                                       f"o la organización no permite este modelo. Detalle: {respuesta.text[:300]}")
            if respuesta.status_code >= 400:
                raise ErrorAsistenteIA(f"{self.nombre_proveedor} respondió {respuesta.status_code}: {respuesta.text[:300]}")

            contenido = "".join(partes)
            log.info("Respuesta de %s en %.1f s: %d caracteres (tokens: entrada %s, salida %s, razonamiento %s, fin=%s)",
                     self.nombre_proveedor, segundos, len(contenido), uso.get("prompt_tokens", "?"),
                     uso.get("completion_tokens", "?"),
                     (uso.get("completion_tokens_details") or {}).get("reasoning_tokens", "?"), fin)
            motivo = _motivo_de_corte(fin, cerrado)
            if motivo:
                log.warning("%s cortó la respuesta (%s); el documento puede estar incompleto",
                            self.nombre_proveedor, motivo)
            if not contenido.strip():
                raise ErrorAsistenteIA(f"{self.nombre_proveedor} devolvió una respuesta vacía")
            resultado = _TextoDeCopilot(limpiar_respuesta(contenido))
            resultado.corte = motivo
            return resultado

        raise ErrorAsistenteIA(f"{self.nombre_proveedor} no respondió tras varios intentos")

    @staticmethod
    def _leer_stream(respuesta, recibido: dict, cancelar: Optional[threading.Event]):
        """Lee los eventos SSE (`data: {...}`) y devuelve (partes del contenido, finish_reason, usage, si llegó [DONE])."""
        partes, fin, uso, cerrado = [], None, {}, False
        for linea in respuesta.iter_lines():
            if cancelar and cancelar.is_set():
                raise InterruptedError
            if not linea.startswith("data:"):
                continue
            dato = linea[5:].strip()
            if dato == "[DONE]":
                cerrado = True
                break
            evento = json.loads(dato)
            uso = evento.get("usage") or uso
            for opcion in evento.get("choices") or []:
                delta = opcion.get("delta") or {}
                # Los modelos con razonamiento envían aparte `reasoning_content`/`reasoning_text`; solo interesa `content`
                recibido["razonamiento"] += len(delta.get("reasoning_content") or delta.get("reasoning_text") or "")
                if delta.get("content"):
                    partes.append(delta["content"])
                    recibido["contenido"] += len(delta["content"])
                fin = opcion.get("finish_reason") or fin
                uso = opcion.get("usage") or uso
        return partes, fin, uso, cerrado

    def _clave_nota(self, n: int, total: int, bloque: str) -> str:
        """Identifica las notas de una parte: el modelo, su posición y el total (el prompt los nombra) y su texto."""
        return hashlib.sha256("\x00".join([str(self.modelo), str(n), str(total), bloque]).encode()).hexdigest()

    def _notas_por_bloque(self, bloques: list[str], on_progreso, cancelar) -> tuple[str, dict[int, str]]:
        """Extrae las notas de cada parte en paralelo. Cada parte guarda sus notas en cuanto termina: si una falla,
        las que terminaron se conservan y, al volver a generar, solo se piden las que faltan. Devuelve también las
        partes cuya respuesta cortó Copilot (parte -> motivo). Esas notas se usan en el documento, pero no se conservan."""
        total = len(bloques)
        claves = [self._clave_nota(n, total, b) for n, b in enumerate(bloques, 1)]
        notas: dict[int, str] = {}
        with self._cerrojo_cache:
            for n, clave in enumerate(claves, 1):
                if clave in self._cache_notas:
                    notas[n] = self._cache_notas[clave]
        pendientes = [n for n in range(1, total + 1) if n not in notas]
        if not pendientes:
            log.info("Reutilizando las notas de %d partes ya analizadas", total)
        elif notas:
            log.info("Reutilizando las notas de %d de %d partes", len(notas), total)
        if pendientes and on_progreso:
            on_progreso(f"Analizando {len(pendientes)} partes en paralelo…")

        if pendientes:  # el modelo se valida una vez, antes de lanzar ninguna parte: sus errores no llevan partes
            if cancelar and cancelar.is_set():
                raise InterruptedError  # una generación cancelada no abre una sesión auto
            self._modelo_para_peticion()

        abortar = threading.Event()  # si una parte falla, las que aún no empezaron no se envían
        claves_en_curso = set(claves)

        def analizar(n: int) -> Optional[str]:
            if abortar.is_set():
                return None
            try:
                texto = self._completar(PROMPT_NOTAS_BLOQUE.format(n=n, total=total, texto=bloques[n - 1]), cancelar)
            except BaseException:
                abortar.set()
                raise
            with self._cerrojo_cache:
                if not _corte(texto):  # unas notas cortadas no se conservan: al volver a generar se piden otra vez
                    # Al menos una generación entera cabe en la caché, y nunca se expulsan notas de la generación en curso
                    limite = max(LIMITE_NOTAS_EN_CACHE, total)
                    while len(self._cache_notas) >= limite:
                        expulsable = next((k for k in self._cache_notas if k not in claves_en_curso), None)
                        if expulsable is None:
                            break
                        del self._cache_notas[expulsable]
                    self._cache_notas[claves[n - 1]] = texto
                notas[n] = texto
                if on_progreso:
                    on_progreso(f"Analizadas {len(notas)} de {total} partes…")
            return texto

        fallo = None
        cortes: dict[int, str] = {}
        if pendientes:
            with ThreadPoolExecutor(max_workers=min(self.peticiones_paralelas, len(pendientes)),
                                    thread_name_prefix="ia-parte") as ejecutor:
                futuros = {n: ejecutor.submit(analizar, n) for n in pendientes}
                for n in pendientes:
                    try:
                        texto = futuros[n].result()
                    except BaseException as e:
                        for f in futuros.values():
                            f.cancel()  # las partes que aún no empezaron ya no se envían
                        if isinstance(e, ErrorAsistenteIA) and not isinstance(e, (ErrorSinSesionCopilot, ErrorModeloIA)):
                            fallo = (n, e)
                            break
                        raise
                    if _corte(texto):
                        cortes[n] = _corte(texto)
        if fallo:  # el bloque anterior ya ha esperado a las partes en curso: todas las que terminaron están contadas
            n, e = fallo
            raise ErrorAsistenteIA(f"falló la parte {n} de {total}: {str(e).rstrip('.')}. "
                                   f"{_frase_de_partes_conservadas(len(notas))}") from e
        return "\n\n".join(f"Notas de la parte {n}:\n{notas[n]}" for n in range(1, total + 1)), cortes

    def _generar(
        self,
        plantilla: str,
        texto: str,
        on_progreso: Optional[Callable[[str], None]] = None,
        cancelar: Optional[threading.Event] = None,
        secciones: Optional[list[str]] = None,
        postproceso: Optional[Callable[[str], str]] = None,
        conservar_tareas_y_acuerdos: bool = False,
    ) -> _Documento:
        """Devuelve el documento (ya post-procesado), el número de partes en que se dividió la transcripción, las
        secciones obligatorias que siguen faltando y los fallos de las pasadas posteriores a la redacción."""
        texto = texto.strip()
        if not texto:
            raise ErrorAsistenteIA("La transcripción está vacía")
        original = texto  # la transcripción completa; `texto` pasa a ser las notas si hay varias partes
        with self._cerrojo_iniciador:
            self._pendiente_iniciador_usuario = True

        consulta = _ConsultaDeLimite()  # del catálogo de límites, de esta generación
        bloques = dividir_texto(texto, self.max_caracteres_bloque)
        log.info("Generando documento: %d caracteres de transcripción en %d bloque(s) de %s caracteres",
                 len(texto), len(bloques), ", ".join(str(len(b)) for b in bloques))
        cortes_partes: dict[int, str] = {}
        if len(bloques) > 1:
            # Transcripciones muy largas: primero notas por bloque, luego el documento final sobre las notas
            texto, cortes_partes = self._notas_por_bloque(bloques, on_progreso, cancelar)

        if on_progreso:
            on_progreso("Redactando documento…")
        prompt = plantilla.format(texto=texto)
        if len(bloques) > 1:
            self._comprobar_limite_de_entrada(prompt, len(bloques), cancelar, consulta)
        documento = self._completar(prompt, cancelar)

        corte = _corte(documento)
        error_secciones = None
        faltan = secciones_faltantes(documento, secciones or [])
        if faltan:
            log.warning("Al documento le faltan secciones %s; se pide completarlo", faltan)
            # Un reintento indicando qué falta; si aun así falla, se entrega lo obtenido, con una nota
            if on_progreso:
                on_progreso("Completando secciones faltantes…")
            try:
                reintento = _sin_cortar(self._completar([
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": documento},
                    {"role": "user", "content": "Faltan estas secciones obligatorias: " + ", ".join(faltan)
                     + ". Devuelve el documento completo con todas las secciones, aplicando las mismas reglas."},
                ], cancelar))
            except ErrorAsistenteIA as e:
                if cancelar and cancelar.is_set():
                    raise InterruptedError from e  # cancelada: el borrador no se entrega
                if not _fallo_recuperable(e):
                    raise
                log.warning("No se pudieron pedir de nuevo las secciones que faltaban; se entrega el borrador: %s", e)
                error_secciones = _motivo(e)
            else:
                if len(secciones_faltantes(reintento, secciones)) < len(faltan):
                    documento = reintento
                    corte = _corte(reintento)  # el motivo es el de la respuesta que quedó

        error_revision = None
        revision_descartada = None
        repuestas: list[str] = []
        fuente_revision = "notas"
        motivo_notas = None
        if self.revision_fidelidad:
            # Segunda pasada: contrasta el documento con la fuente para corregir reformulaciones. Solo la minuta puede
            # quitar tareas y acuerdos (y se repone lo quitado); el resumen no tiene reposición y no los quita
            plantilla_revision = PROMPT_REVISION if conservar_tareas_y_acuerdos else PROMPT_REVISION_RESUMEN
            try:
                fuente = self._fuente_de_revision(original, texto, documento, len(bloques), consulta, cancelar,
                                                  plantilla_revision)
                fuente_revision = fuente.tipo
                motivo_notas = fuente.motivo
                if on_progreso:
                    quien = ("la transcripción" if len(bloques) == 1 else "la transcripción completa"
                             if fuente.tipo == "transcripcion" else f"las notas de las {len(bloques)} partes")
                    if fuente.motivo:
                        quien += f" (la transcripción completa no cabe en «{fuente.motivo[2]}»)"
                    on_progreso(f"Revisando fidelidad con {quien}…")
                revisado = _sin_cortar(self._completar(
                    plantilla_revision.format(texto=fuente.texto, documento=documento), cancelar))
            except ErrorAsistenteIA as e:
                if cancelar and cancelar.is_set():
                    raise InterruptedError from e  # cancelada: el documento sin revisar no se entrega
                if not _fallo_recuperable(e):
                    raise
                log.warning("No se pudo completar la revisión de fidelidad; se entrega sin revisar: %s", e)
                error_revision = _motivo(e)
            else:
                # Solo se acepta si conserva todas las secciones que tenía. En la minuta, lo que la revisión quitó de las
                # tareas se repone marcado (D4). Lo quitado se calcula una sola vez: decide y repone
                conserva_secciones = (len(secciones_faltantes(revisado, secciones or []))
                                      <= len(secciones_faltantes(documento, secciones or [])))
                quitadas = _tareas_quitadas(documento, revisado) if conservar_tareas_y_acuerdos else []
                quitados = _acuerdos_quitados(documento, revisado) if conservar_tareas_y_acuerdos else []
                # Si hay que reponer algo y la revisión ya no tiene el título de su sección, no hay dónde: se descarta
                if not conserva_secciones or _sin_donde_reponer(revisado, quitadas, quitados):
                    revision_descartada = "quitaba secciones obligatorias"
                else:
                    motivo_corte = _corte(revisado)  # el motivo es el de la respuesta que quedó
                    if conservar_tareas_y_acuerdos:
                        revisado, repuestas = reponer_lo_quitado(documento, revisado, quitadas, quitados)
                    documento, corte = revisado, motivo_corte
        if postproceso:
            documento = postproceso(documento)
        faltan_al_final = secciones_faltantes(documento, secciones or [])
        # Si la revisión devolvió las que faltaban, no hay nada que decir del fallo al pedirlas
        return _Documento(documento, len(bloques), faltan_al_final,
                          error_secciones if faltan_al_final else None, error_revision, corte, cortes_partes,
                          revision_descartada=revision_descartada, repuestas=repuestas,
                          fuente_revision=fuente_revision, motivo_notas=motivo_notas)

    def _limite_del_modelo(self, consulta: _ConsultaDeLimite,
                           cancelar: Optional[threading.Event]) -> tuple[str, Optional[int]]:
        """Modelo de la próxima petición (`_modelo_para_peticion`: regla 7 y sesión auto) y su límite de entrada, o None
        si el catálogo falló en esta generación o no lo trae. El límite se guarda en el asistente; el fallo, solo en
        `consulta`, así que la siguiente generación vuelve a consultar el catálogo."""
        if cancelar and cancelar.is_set():
            raise InterruptedError
        modelo, _ = self._modelo_para_peticion()
        with self._cerrojo_limites:
            if self._limites is None and consulta.error is None:
                try:
                    self._limites = copilot.limites_de_entrada(copilot.Sesion(self.api_key, self.enterprise_url))
                except copilot.ErrorSesionCopilot as e:  # el token rechazado: no es un fallo más del catálogo
                    raise self._error_de_token_rechazado() from e
                except copilot.ErrorCopilot as e:
                    consulta.error = str(e)
        if self._limites is None:
            return modelo, None
        return modelo, self._limites.get(modelo)

    def _comprobar_limite_de_entrada(self, prompt: str, partes: int, cancelar: Optional[threading.Event],
                                     consulta: Optional[_ConsultaDeLimite] = None) -> None:
        """Antes de redactar a partir de notas: si la petición entera supera el límite de entrada del modelo que se
        usará, no se envía (Copilot la rechazaría con un error poco claro). Solo se consulta el catálogo si la
        estimación supera el umbral."""
        estimado = estimar_tokens(PROMPT_SISTEMA + prompt)
        if estimado <= UMBRAL_COMPROBAR_LIMITE:
            return
        if consulta is None:
            consulta = _ConsultaDeLimite()
        modelo, limite = self._limite_del_modelo(consulta, cancelar)
        if limite is None and consulta.error is not None:
            log.warning("No se pudo comprobar el límite de entrada de «%s» (%s); se envía la redacción como hoy.",
                        modelo, consulta.error)
        elif limite is None:
            log.warning("No se pudo comprobar el límite de entrada de «%s»: el catálogo no lo informa; se envía la "
                        "redacción como hoy.", modelo)
        elif estimado > limite:
            raise ErrorAsistenteIA(
                f"las notas de las {partes} partes suman unos {estimado} tokens y el modelo «{modelo}» admite como "
                f"máximo {limite} tokens de entrada, así que no se envió la redacción. Elige en el selector un modelo "
                "con más contexto y vuelve a generar; con otro modelo se pedirán de nuevo las notas de todas las "
                "partes.")

    def _fuente_de_revision(self, original: str, notas: str, documento: str, partes: int,
                            consulta: _ConsultaDeLimite, cancelar: Optional[threading.Event],
                            plantilla_revision: str = PROMPT_REVISION) -> FuenteRevision:
        """Qué recibe la revisión: la transcripción completa si cabe en el modelo, y las notas si no. Con varias partes
        se estima la petición con la transcripción y solo se consulta el límite si pasa del umbral (con la misma
        consulta de la redacción). Sin dato del límite se revisa con la transcripción, y el registro lo dice."""
        if partes == 1:
            return FuenteRevision("transcripcion", original)
        estimado = estimar_tokens(PROMPT_SISTEMA + plantilla_revision.format(texto=original, documento=documento))
        if estimado <= UMBRAL_COMPROBAR_LIMITE:
            return FuenteRevision("transcripcion", original)
        modelo, limite = self._limite_del_modelo(consulta, cancelar)
        if limite is None:
            if consulta.error is not None:
                log.warning("No se pudo comprobar el límite de entrada de «%s» para la revisión (%s); se revisa con la "
                            "transcripción completa.", modelo, consulta.error)
            else:
                log.warning("No se pudo comprobar el límite de entrada de «%s» para la revisión: el catálogo no lo "
                            "informa; se revisa con la transcripción completa.", modelo)
            return FuenteRevision("transcripcion", original)
        if estimado <= limite:
            return FuenteRevision("transcripcion", original)
        log.info("La revisión con la transcripción completa suma unos %d tokens y «%s» admite %d; se revisa con las "
                 "notas de las %d partes.", estimado, modelo, limite, partes)
        return FuenteRevision("notas", notas, (estimado, limite, modelo))

    def _con_nota(self, d: _Documento) -> str:
        """Añade al final las notas de la aplicación que apliquen. Va después de todas las pasadas del modelo y del
        post-proceso, así ningún prompt la contiene y el post-proceso no la toca."""
        # sin revisión, o con una revisión que no se completó o se descartó, no se dice que se revisó
        revisado = self.revision_fidelidad and not d.error_revision and not d.revision_descartada
        nota = notas_de_la_aplicacion(d.faltan, d.partes, revisado, d.error_secciones, d.error_revision, d.corte,
                                      d.cortes_partes, revision_descartada=d.revision_descartada,
                                      repuestas=d.repuestas, fuente_revision=d.fuente_revision,
                                      motivo_notas=d.motivo_notas)
        return d.texto.rstrip() + "\n" + nota if nota else d.texto

    def generar_resumen(self, texto: str, on_progreso=None, cancelar=None) -> str:
        return self._con_nota(self._generar(PROMPT_RESUMEN, texto, on_progreso, cancelar, SECCIONES_RESUMEN))

    def generar_minuta(self, texto: str, on_progreso=None, cancelar=None, fecha: Optional[str] = None) -> str:
        # La fecha la aporta la app (el modelo tiende a confundirla con fechas límite de tareas)
        plantilla = PROMPT_MINUTA.replace("{fecha}", fecha or "No especificada")

        def postproceso(minuta: str) -> str:
            minuta = normalizar_tabla_tareas(minuta)
            return re.sub(r"^\*\*Fecha:\*\*.*$", f"**Fecha:** {fecha or 'No especificada'}", minuta, count=1, flags=re.M)

        return self._con_nota(self._generar(plantilla, texto, on_progreso, cancelar, SECCIONES_MINUTA, postproceso,
                                            conservar_tareas_y_acuerdos=True))

