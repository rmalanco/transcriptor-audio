"""Documentos fuera de la ventana: texto que se envía a la IA, ruta junto al audio y fecha de la reunión.

No importa tkinter, customtkinter, faster_whisper, httpx ni src.asistente_ia. No toca widgets: quien llama desde un
hilo de fondo es responsable de llevar los resultados al hilo principal.
"""

import os
import time
from pathlib import Path
from typing import Optional

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
