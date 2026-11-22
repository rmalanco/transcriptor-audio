"""Generación de resúmenes y minutas a partir de una transcripción usando los modelos de GitHub Copilot."""

import hashlib
import json
import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Optional

import httpx

from src import copilot
from src.registro import latido

log = logging.getLogger("transcriptor.ia")


NOMBRE_PROVEEDOR = "GitHub Copilot"
MODELO_POR_DEFECTO = "gpt-4.1"
LIMITE_NOTAS_EN_CACHE = 64  # partes; equivale a unas 8 transcripciones de 8 partes

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


def _fallo_recuperable(error: ErrorAsistenteIA) -> bool:
    """Si una pasada posterior a la redacción falla con esto, se entrega lo ya redactado con una nota. No lo es la falta
    de sesión (hay que iniciar sesión) ni un modelo no autorizado o vacío (no se envía nada a ningún modelo)."""
    return not isinstance(error, (ErrorSinSesionCopilot, ErrorModeloIA))


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


def _cita_de_partes(partes: int, revisado: bool) -> str:
    cita = (f"> Nota de la aplicación: la transcripción se procesó en {partes} partes y este documento se "
            "redactó a partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, "
            "fechas, cifras y condiciones con la transcripción antes de darlo por bueno.")
    if revisado:
        cita += " La revisión de fidelidad se hizo contra esas notas, no contra la transcripción."
    return cita


def notas_de_la_aplicacion(faltan: list[str], partes: int, revisado: bool,
                           error_secciones: Optional[str] = None, error_revision: Optional[str] = None) -> str:
    """Bloque final que la app añade a un documento: una sola línea horizontal y, debajo, las notas que apliquen
    (primero las de secciones, después la de la revisión y la de las partes). Vacío si no hay nada que avisar.
    `error_secciones` y `error_revision`: motivo por el que no se pudo completar esa pasada."""
    citas = []
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
    if partes >= 2:
        citas.append(_cita_de_partes(partes, revisado))
    if not citas:
        return ""
    return "\n---\n\n" + "\n\n".join(citas)


def nota_de_notas(partes: int, revisado: bool) -> str:
    """Bloque que la app añade al final de un documento redactado a partir de notas (2 o más partes).
    Lo añade la app, no el modelo: ningún prompt lo contiene y el post-proceso no lo toca."""
    return notas_de_la_aplicacion([], partes, revisado)


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
                        partes, fin, uso = self._leer_stream(respuesta, recibido, cancelar)
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

    def _clave_nota(self, n: int, total: int, bloque: str) -> str:
        """Identifica las notas de una parte: el modelo, su posición y el total (el prompt los nombra) y su texto."""
        return hashlib.sha256("\x00".join([str(self.modelo), str(n), str(total), bloque]).encode()).hexdigest()

    def _notas_por_bloque(self, bloques: list[str], on_progreso, cancelar) -> str:
        """Extrae las notas de cada parte en paralelo. Cada parte guarda sus notas en cuanto termina: si una falla,
        las que terminaron se conservan y, al volver a generar, solo se piden las que faltan."""
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

        def analizar(n: int) -> None:
            if abortar.is_set():
                return
            try:
                texto = self._completar(PROMPT_NOTAS_BLOQUE.format(n=n, total=total, texto=bloques[n - 1]), cancelar)
            except BaseException:
                abortar.set()
                raise
            with self._cerrojo_cache:
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

        fallo = None
        if pendientes:
            with ThreadPoolExecutor(max_workers=min(self.peticiones_paralelas, len(pendientes)),
                                    thread_name_prefix="ia-parte") as ejecutor:
                futuros = {n: ejecutor.submit(analizar, n) for n in pendientes}
                for n in pendientes:
                    try:
                        futuros[n].result()
                    except BaseException as e:
                        for f in futuros.values():
                            f.cancel()  # las partes que aún no empezaron ya no se envían
                        if isinstance(e, ErrorAsistenteIA) and not isinstance(e, (ErrorSinSesionCopilot, ErrorModeloIA)):
                            fallo = (n, e)
                            break
                        raise
        if fallo:  # el bloque anterior ya ha esperado a las partes en curso: todas las que terminaron están contadas
            n, e = fallo
            raise ErrorAsistenteIA(f"falló la parte {n} de {total}: {str(e).rstrip('.')}. "
                                   f"{_frase_de_partes_conservadas(len(notas))}") from e
        return "\n\n".join(f"Notas de la parte {n}:\n{notas[n]}" for n in range(1, total + 1))

    def _generar(
        self,
        plantilla: str,
        texto: str,
        on_progreso: Optional[Callable[[str], None]] = None,
        cancelar: Optional[threading.Event] = None,
        secciones: Optional[list[str]] = None,
        postproceso: Optional[Callable[[str], str]] = None,
    ) -> _Documento:
        """Devuelve el documento (ya post-procesado), el número de partes en que se dividió la transcripción, las
        secciones obligatorias que siguen faltando y los fallos de las pasadas posteriores a la redacción."""
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

        error_secciones = None
        faltan = secciones_faltantes(documento, secciones or [])
        if faltan:
            log.warning("Al documento le faltan secciones %s; se pide completarlo", faltan)
            # Un reintento indicando qué falta; si aun así falla, se entrega lo obtenido, con una nota
            if on_progreso:
                on_progreso("Completando secciones faltantes…")
            try:
                reintento = self._completar([
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": documento},
                    {"role": "user", "content": "Faltan estas secciones obligatorias: " + ", ".join(faltan)
                     + ". Devuelve el documento completo con todas las secciones, aplicando las mismas reglas."},
                ], cancelar)
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

        error_revision = None
        if self.revision_fidelidad:
            # Segunda pasada: contrasta el documento con la fuente para corregir reformulaciones
            if on_progreso:
                fuente = "la transcripción" if len(bloques) == 1 else f"las notas de las {len(bloques)} partes"
                on_progreso(f"Revisando fidelidad con {fuente}…")
            try:
                revisado = self._completar(PROMPT_REVISION.format(texto=texto, documento=documento), cancelar)
            except ErrorAsistenteIA as e:
                if cancelar and cancelar.is_set():
                    raise InterruptedError from e  # cancelada: el documento sin revisar no se entrega
                if not _fallo_recuperable(e):
                    raise
                log.warning("No se pudo completar la revisión de fidelidad; se entrega sin revisar: %s", e)
                error_revision = _motivo(e)
            else:
                # Solo se acepta si conserva todas las secciones que tenía
                if len(secciones_faltantes(revisado, secciones or [])) <= len(secciones_faltantes(documento, secciones or [])):
                    documento = revisado
        if postproceso:
            documento = postproceso(documento)
        faltan_al_final = secciones_faltantes(documento, secciones or [])
        # Si la revisión devolvió las que faltaban, no hay nada que decir del fallo al pedirlas
        return _Documento(documento, len(bloques), faltan_al_final,
                          error_secciones if faltan_al_final else None, error_revision)

    def _con_nota(self, d: _Documento) -> str:
        """Añade al final las notas de la aplicación que apliquen. Va después de todas las pasadas del modelo y del
        post-proceso, así ningún prompt la contiene y el post-proceso no la toca."""
        revisado = self.revision_fidelidad and not d.error_revision  # sin revisión, no se dice que se revisó
        nota = notas_de_la_aplicacion(d.faltan, d.partes, revisado, d.error_secciones, d.error_revision)
        return d.texto.rstrip() + "\n" + nota if nota else d.texto

    def generar_resumen(self, texto: str, on_progreso=None, cancelar=None) -> str:
        return self._con_nota(self._generar(PROMPT_RESUMEN, texto, on_progreso, cancelar, SECCIONES_RESUMEN))

    def generar_minuta(self, texto: str, on_progreso=None, cancelar=None, fecha: Optional[str] = None) -> str:
        # La fecha la aporta la app (el modelo tiende a confundirla con fechas límite de tareas)
        plantilla = PROMPT_MINUTA.replace("{fecha}", fecha or "No especificada")

        def postproceso(minuta: str) -> str:
            minuta = normalizar_tabla_tareas(minuta)
            return re.sub(r"^\*\*Fecha:\*\*.*$", f"**Fecha:** {fecha or 'No especificada'}", minuta, count=1, flags=re.M)

        return self._con_nota(self._generar(plantilla, texto, on_progreso, cancelar, SECCIONES_MINUTA, postproceso))

