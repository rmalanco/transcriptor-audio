"""Generación de resúmenes y minutas a partir de una transcripción usando los modelos de GitHub Copilot."""

import hashlib
import json
import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import httpx

from src import copilot
from src.registro import latido

log = logging.getLogger("transcriptor.ia")


NOMBRE_PROVEEDOR = "GitHub Copilot"
MODELO_POR_DEFECTO = "gpt-4.1"

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
- Datos que no aparecen en la transcripción (nombres, fechas, cifras, tareas).
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


def secciones_faltantes(documento: str, secciones: list[str]) -> list[str]:
    lineas = [linea.strip().lower() for linea in documento.splitlines()]
    return [s for s in secciones if not any(linea.startswith(s.lower()) for linea in lineas)]


class ErrorAsistenteIA(Exception):
    pass


class ErrorSinSesionCopilot(ErrorAsistenteIA):
    """No hay sesión de GitHub Copilot o fue rechazada: hay que iniciar sesión."""


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
        self.url = copilot.url_api(enterprise_url) + "/chat/completions"
        self.enterprise_url = enterprise_url
        self.modelo = modelo
        self.temperatura = temperatura
        self.max_caracteres_bloque = max_caracteres_bloque
        self.timeout = timeout
        self.revision_fidelidad = revision_fidelidad
        self.peticiones_paralelas = max(1, peticiones_paralelas)
        self._cache_notas: dict[str, str] = {}
        # Solo la primera petición de cada documento la inicia el usuario; las demás (partes,
        # reintentos, revisión) son pasos automáticos ("agent"), como hace opencode
        self._pendiente_iniciador_usuario = True
        self._cerrojo_iniciador = threading.Lock()
        # Modelo "auto": sesión compartida por las peticiones en paralelo, renovada antes de caducar
        self.es_auto = modelo == copilot.MODELO_AUTO
        self._sesion_auto: Optional[copilot.SesionAuto] = None
        self._cerrojo_auto = threading.Lock()

    @property
    def modelo_usado(self) -> str:
        """Nombre para mostrar y guardar en el historial: en modo auto, también el modelo que eligió Copilot."""
        if self.es_auto and self._sesion_auto:
            return f"auto → {self._sesion_auto.modelo}"
        return self.modelo

    def _resolver_auto(self) -> copilot.SesionAuto:
        with self._cerrojo_auto:
            if self._sesion_auto is None or not self._sesion_auto.vigente():
                try:
                    self._sesion_auto = copilot.abrir_sesion_auto(copilot.Sesion(self.api_key, self.enterprise_url))
                except copilot.ErrorCopilot as e:
                    raise ErrorAsistenteIA(str(e)) from e
            return self._sesion_auto

    def _cabeceras(self) -> dict:
        with self._cerrojo_iniciador:
            iniciador = "user" if self._pendiente_iniciador_usuario else "agent"
            self._pendiente_iniciador_usuario = False
        return copilot.cabeceras(self.api_key, iniciador)

    def _modelo_y_cabeceras(self) -> tuple[str, dict]:
        cabeceras = self._cabeceras()
        if not self.es_auto:
            return self.modelo, cabeceras
        sesion_auto = self._resolver_auto()
        return sesion_auto.modelo, cabeceras | {"Copilot-Session-Token": sesion_auto.session_token}

    def _completar(self, prompt, cancelar: Optional[threading.Event] = None) -> str:
        """`prompt` es el texto del usuario o una lista de mensajes adicionales (para reintentos)."""
        mensajes = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt
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
                        partes, fin, uso = self._leer_stream(respuesta, recibido, cancelar)
            except httpx.HTTPError as e:
                log.warning("Fallo de conexión con %s tras %.1f s (%s): %r", self.nombre_proveedor,
                            time.monotonic() - inicio, estado(), e)
                if intento == 3:
                    raise ErrorAsistenteIA(f"No se pudo conectar con {self.nombre_proveedor}: {e}") from e
                time.sleep(2 ** intento)
                continue
            segundos = time.monotonic() - inicio

            # Límite de peticiones o error temporal del servidor: reintentar con espera creciente
            if respuesta.status_code == 429 or respuesta.status_code >= 500:
                log.warning("%s respondió %d en %.1f s; reintentando en %d s: %s", self.nombre_proveedor,
                            respuesta.status_code, segundos, 2 ** (intento + 1), respuesta.text[:200])
                if intento == 3:
                    raise ErrorAsistenteIA(f"{self.nombre_proveedor} respondió {respuesta.status_code}: {respuesta.text[:300]}")
                time.sleep(2 ** (intento + 1))
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
                copilot.invalidar_token(self.api_key)
                raise ErrorSinSesionCopilot("La sesión de GitHub Copilot caducó o fue revocada (401). "
                                            "Vuelve a iniciar sesión.")
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
            if fin == "length":
                log.warning("%s cortó la respuesta por límite de longitud; el documento puede estar incompleto",
                            self.nombre_proveedor)
            if not contenido.strip():
                raise ErrorAsistenteIA(f"{self.nombre_proveedor} devolvió una respuesta vacía")
            return limpiar_respuesta(contenido)

        raise ErrorAsistenteIA(f"{self.nombre_proveedor} no respondió tras varios intentos")

    @staticmethod
    def _leer_stream(respuesta, recibido: dict, cancelar: Optional[threading.Event]):
        """Lee los eventos SSE (`data: {...}`) y devuelve (partes del contenido, finish_reason, usage)."""
        partes, fin, uso = [], None, {}
        for linea in respuesta.iter_lines():
            if cancelar and cancelar.is_set():
                raise InterruptedError
            if not linea.startswith("data:"):
                continue
            dato = linea[5:].strip()
            if dato == "[DONE]":
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
        return partes, fin, uso

    def _notas_por_bloque(self, bloques: list[str], on_progreso, cancelar) -> str:
        """Extrae notas de cada bloque en paralelo. Se guardan en memoria: el resumen y la minuta de una
        misma transcripción parten de las mismas notas, así que la segunda no repite este paso."""
        clave = hashlib.sha256("\x00".join(bloques).encode()).hexdigest()
        if clave in self._cache_notas:
            log.info("Reutilizando las notas de %d partes ya analizadas", len(bloques))
            return self._cache_notas[clave]

        total = len(bloques)
        listas = 0
        cerrojo = threading.Lock()
        if on_progreso:
            on_progreso(f"Analizando {total} partes en paralelo…")

        def analizar(i: int, bloque: str) -> str:
            nonlocal listas
            notas = self._completar(PROMPT_NOTAS_BLOQUE.format(n=i, total=total, texto=bloque), cancelar)
            with cerrojo:
                listas += 1
                if on_progreso:
                    on_progreso(f"Analizadas {listas} de {total} partes…")
            return notas

        hilos = min(self.peticiones_paralelas, total)
        with ThreadPoolExecutor(max_workers=hilos, thread_name_prefix="ia-parte") as ejecutor:
            futuros = [ejecutor.submit(analizar, i, b) for i, b in enumerate(bloques, 1)]
            try:
                notas = [f.result() for f in futuros]
            except BaseException:
                for f in futuros:
                    f.cancel()  # las partes que aún no empezaron ya no se envían
                raise

        resultado = "\n\n".join(f"Notas de la parte {i}:\n{n}" for i, n in enumerate(notas, 1))
        if len(self._cache_notas) >= 8:  # solo interesan las transcripciones recientes
            self._cache_notas.pop(next(iter(self._cache_notas)))
        self._cache_notas[clave] = resultado
        return resultado

    def _generar(
        self,
        plantilla: str,
        texto: str,
        on_progreso: Optional[Callable[[str], None]] = None,
        cancelar: Optional[threading.Event] = None,
        secciones: Optional[list[str]] = None,
    ) -> str:
        texto = texto.strip()
        if not texto:
            raise ErrorAsistenteIA("La transcripción está vacía")
        with self._cerrojo_iniciador:
            self._pendiente_iniciador_usuario = True

        bloques = dividir_texto(texto, self.max_caracteres_bloque)
        log.info("Generando documento: %d caracteres de transcripción en %d bloque(s) de %s caracteres",
                 len(texto), len(bloques), ", ".join(str(len(b)) for b in bloques))
        if len(bloques) > 1:
            # Transcripciones muy largas: primero notas por bloque, luego el documento final sobre las notas
            texto = self._notas_por_bloque(bloques, on_progreso, cancelar)

        if on_progreso:
            on_progreso("Redactando documento…")
        prompt = plantilla.format(texto=texto)
        documento = self._completar(prompt, cancelar)

        faltan = secciones_faltantes(documento, secciones or [])
        if faltan:
            log.warning("Al documento le faltan secciones %s; se pide completarlo", faltan)
            # Un reintento indicando qué falta; si aun así falla, se devuelve lo obtenido
            if on_progreso:
                on_progreso("Completando secciones faltantes…")
            reintento = self._completar([
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": documento},
                {"role": "user", "content": "Faltan estas secciones obligatorias: " + ", ".join(faltan)
                 + ". Devuelve el documento completo con todas las secciones, aplicando las mismas reglas."},
            ], cancelar)
            if len(secciones_faltantes(reintento, secciones)) < len(faltan):
                documento = reintento

        if self.revision_fidelidad:
            # Segunda pasada: contrasta el documento con la fuente para corregir reformulaciones
            if on_progreso:
                on_progreso("Revisando fidelidad con la transcripción…")
            revisado = self._completar(PROMPT_REVISION.format(texto=texto, documento=documento), cancelar)
            # Solo se acepta si conserva todas las secciones que tenía
            if len(secciones_faltantes(revisado, secciones or [])) <= len(secciones_faltantes(documento, secciones or [])):
                documento = revisado
        return documento

    def generar_resumen(self, texto: str, on_progreso=None, cancelar=None) -> str:
        return self._generar(PROMPT_RESUMEN, texto, on_progreso, cancelar, SECCIONES_RESUMEN)

    def generar_minuta(self, texto: str, on_progreso=None, cancelar=None, fecha: Optional[str] = None) -> str:
        # La fecha la aporta la app (el modelo tiende a confundirla con fechas límite de tareas)
        plantilla = PROMPT_MINUTA.replace("{fecha}", fecha or "No especificada")
        minuta = self._generar(plantilla, texto, on_progreso, cancelar, SECCIONES_MINUTA)
        minuta = normalizar_tabla_tareas(minuta)
        return re.sub(r"^\*\*Fecha:\*\*.*$", f"**Fecha:** {fecha or 'No especificada'}", minuta, count=1, flags=re.M)

