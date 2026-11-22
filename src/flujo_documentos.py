"""Documentos fuera de la ventana: texto que se envía a la IA, ruta junto al audio y fecha de la reunión.

No importa tkinter, customtkinter ni faster_whisper. No toca widgets: quien llama desde un hilo de fondo es responsable
de llevar los resultados al hilo principal.
"""

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.asistente_ia import AsistenteIA
from src.transcriber import ResultadoTranscripcion
from src.utils import ruta_junto_al_audio

# Sufijo de cada documento que la app escribe junto al audio (punto #18: se conserva la extensión del audio).
SUFIJOS_DOCUMENTO = {"resumen": "_resumen.md", "minuta": "_minuta.md"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def texto_para_ia(resultado: ResultadoTranscripcion) -> str:
    """Texto que se envía a la IA: una línea por segmento, para que los bloques se dividan por frases."""
    return "\n".join(seg.texto for seg in resultado.segmentos)


def ruta_documento(audio: str, clave: str) -> Optional[str]:
    """Ruta del documento junto al audio, o None si el audio no existe (el documento solo se guarda en el historial)."""
    if not Path(audio).exists():
        return None
    return ruta_junto_al_audio(audio, SUFIJOS_DOCUMENTO[clave])


def fecha_de_la_reunion(audio: str, fecha_historial: Optional[str]) -> str:
    """Fecha de la minuta: la de modificación del audio, o la de creación de la entrada del historial si el audio ya
    no existe. Un error al leerla (disco o formato) no impide generar la minuta: devuelve «No especificada»."""
    try:
        if os.path.exists(audio):
            t = time.localtime(os.path.getmtime(audio))
            origen = "fecha del archivo"
        elif fecha_historial:
            t = time.strptime(fecha_historial[:10], "%Y-%m-%d")
            origen = "fecha de transcripción"
        else:
            return "No especificada"
    except (OSError, ValueError):
        return "No especificada"
    return f"{t.tm_mday} de {MESES[t.tm_mon - 1]} de {t.tm_year} ({origen})"


@dataclass(eq=False)  # se compara por identidad: dos generaciones con los mismos datos son distintas
class Generacion:
    """Una generación de resumen o minuta en curso. Su señal de cancelación es propia: cancelar una no afecta a otra."""
    clave: str                          # "resumen" | "minuta"
    asistente: AsistenteIA
    texto: str
    fecha: Optional[str]                # solo minuta; la calcula quien llama, en el hilo principal
    ruta_salida: Optional[str]          # None si el audio ya no existe: solo se guarda en el historial
    id_historial: Optional[int]         # el vigente al pulsar el botón
    cancelar: threading.Event = field(default_factory=threading.Event)


@dataclass
class DocumentoGenerado:
    contenido: str
    modelo_usado: str                   # leído del asistente después de generar
    segundos: float                     # medido con time.monotonic() dentro de generar_documento


def generar_documento(generacion: Generacion, on_progreso=None) -> DocumentoGenerado:
    """Llama al asistente según el tipo de la generación. No toca historial, archivos ni widgets; las excepciones
    salen tal cual (incluida InterruptedError)."""
    inicio = time.monotonic()
    if generacion.clave == "resumen":
        contenido = generacion.asistente.generar_resumen(
            generacion.texto, on_progreso=on_progreso, cancelar=generacion.cancelar)
    else:
        contenido = generacion.asistente.generar_minuta(
            generacion.texto, on_progreso=on_progreso, cancelar=generacion.cancelar, fecha=generacion.fecha)
    return DocumentoGenerado(contenido, generacion.asistente.modelo_usado, time.monotonic() - inicio)


def procesar_generacion(generacion: Generacion, on_progreso, entregar) -> None:
    """Destino del hilo de fondo: genera y entrega el resultado exactamente una vez, con (generacion, documento, None)
    o con (generacion, None, error). `on_progreso` se llama desde el hilo que ejecuta esta función y también desde los
    hilos «ia-parte» de AsistenteIA._notas_por_bloque (notas en paralelo); `entregar` se llama desde el hilo que ejecuta
    esta función. Ninguno de los dos puede tocar widgets: la ventana los envuelve en _en_ui. Si `entregar` lanza, la
    excepción sale de aquí (la registra threading.excepthook) y no se reintenta."""
    try:
        documento, error = generar_documento(generacion, on_progreso), None
    except Exception as e:  # incluye InterruptedError (cancelada) y ErrorSinSesionCopilot
        documento, error = None, e
    entregar(generacion, documento, error)
