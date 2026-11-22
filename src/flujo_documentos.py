"""Documentos fuera de la ventana: texto que se envía a la IA, ruta junto al audio y fecha de la reunión.

No importa tkinter, customtkinter ni faster_whisper. No toca widgets: quien llama desde un hilo de fondo es responsable
de llevar los resultados al hilo principal.
"""

import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from src.asistente_ia import AsistenteIA, ErrorSinSesionCopilot
from src.persistencia import Persistencia, persistir_documento
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


@dataclass
class Recepcion:
    """Lo que el gestor decidió con el resultado de una generación; la ventana solo pinta según `estado`."""
    estado: str                         # "descartada" | "lista" | "error" | "sin_sesion"
    generacion: Generacion
    documento: Optional[DocumentoGenerado] = None
    persistencia: Optional[Persistencia] = None
    mensaje: Optional[str] = None


class GestorDocumentos:
    """Lleva la generación vigente y el asistente que se reutiliza entre generaciones. Sin interfaz ni red. Solo se
    usa desde el hilo en que se creó (el principal): cada método que cambia estado lo comprueba."""

    def __init__(self, historial, crear_asistente: Callable[[], AsistenteIA]):
        self._historial = historial
        self._crear_asistente = crear_asistente
        self._hilo = threading.get_ident()
        self._vigente: Optional[Generacion] = None
        self._asistente: Optional[AsistenteIA] = None

    @property
    def vigente(self) -> Optional[Generacion]:
        return self._vigente

    def _comprobar_hilo(self):
        if threading.get_ident() != self._hilo:
            raise RuntimeError("GestorDocumentos solo se usa desde el hilo principal")

    def asistente(self) -> AsistenteIA:
        self._comprobar_hilo()
        if self._asistente is None:
            self._asistente = self._crear_asistente()
        return self._asistente

    def iniciar(self, clave: str, resultado: ResultadoTranscripcion, archivo: str, id_historial: Optional[int],
                fecha_historial: Optional[str]) -> Generacion:
        self._comprobar_hilo()
        if self._vigente is not None:
            raise ValueError("ya hay una generación en curso")
        asistente = self.asistente()
        fecha = fecha_de_la_reunion(archivo, fecha_historial) if clave == "minuta" else None
        generacion = Generacion(clave=clave, asistente=asistente, texto=texto_para_ia(resultado), fecha=fecha,
                                ruta_salida=ruta_documento(archivo, clave), id_historial=id_historial)
        self._vigente = generacion
        return generacion

    def terminar(self, generacion: Generacion) -> bool:
        self._comprobar_hilo()
        if generacion is None or generacion is not self._vigente:
            return False
        self._vigente = None
        return True

    def cancelar(self) -> Optional[Generacion]:
        self._comprobar_hilo()
        cancelada = self._vigente
        if cancelada is None:
            return None
        cancelada.cancelar.set()
        self._vigente = None
        self._asistente = None
        return cancelada

    def olvidar_asistente(self):
        self._comprobar_hilo()
        self._asistente = None

    def recibir(self, generacion: Generacion, documento: Optional[DocumentoGenerado],
                error: Optional[Exception]) -> Recepcion:
        self._comprobar_hilo()
        if not self.terminar(generacion):
            return Recepcion("descartada", generacion)
        if isinstance(error, ErrorSinSesionCopilot):
            self.olvidar_asistente()  # se recrea con el token nuevo tras iniciar sesión
            return Recepcion("sin_sesion", generacion, mensaje=str(error) or type(error).__name__)
        if error is not None:
            return Recepcion("error", generacion, mensaje=str(error) or type(error).__name__)
        persistencia = persistir_documento(self._historial, generacion.id_historial, generacion.clave,
                                           documento.contenido, documento.modelo_usado, generacion.ruta_salida)
        return Recepcion("lista", generacion, documento=documento, persistencia=persistencia)
