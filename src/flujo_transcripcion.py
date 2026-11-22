"""Flujo de la transcripción sin interfaz: opciones, elección del transcriptor, ruta del resultado y llamada a Whisper.

No importa tkinter, customtkinter ni faster_whisper. Sus funciones se llaman desde un hilo de fondo y no tocan
widgets: quien pasa callbacks (p. ej. la ventana) es responsable de llevarlos al hilo principal.
"""

from dataclasses import dataclass, replace
from typing import Optional

from src.transcriber import ResultadoTranscripcion, TranscriptorAudio
from src.utils import ruta_junto_al_audio


@dataclass(frozen=True)
class OpcionesTranscripcion:
    """Lo que eligen la ventana o la CLI para una transcripción. Los parámetros de decodificación van aparte."""
    archivo: str
    modelo: str
    dispositivo: str
    compute_type: str
    idioma: str                  # código; "auto" = detectar
    formato: str
    incluir_timestamps: bool
    palabra_por_palabra: bool
    task: str = "transcribe"

    @classmethod
    def desde_configuracion(cls, configuracion: dict, archivo: str, **cambios) -> "OpcionesTranscripcion":
        """Opciones con los valores de `configuracion`; `cambios` usa los nombres de los campos. Un nombre
        desconocido lanza TypeError."""
        base = cls(
            archivo=archivo,
            modelo=configuracion["modelo"]["nombre"],
            dispositivo=configuracion["modelo"]["dispositivo"],
            compute_type=configuracion["modelo"]["compute_type"],
            idioma=configuracion["transcripcion"]["idioma"],
            formato=configuracion["salida"]["formato"],
            incluir_timestamps=configuracion["salida"]["incluir_timestamps"],
            palabra_por_palabra=configuracion["salida"]["palabra_por_palabra"],
        )
        return replace(base, **cambios)


def ruta_transcripcion(archivo: str, formato: str) -> str:
    """Ruta de la transcripción junto al audio: `reunion.m4a` + `srt` -> `reunion.m4a_transcripcion.srt`."""
    return ruta_junto_al_audio(archivo, f"_transcripcion.{formato}")


def transcriptor_para(actual: Optional[TranscriptorAudio], modelo: str, dispositivo: str,
                      compute_type: str) -> TranscriptorAudio:
    """Devuelve `actual` si ya tiene esos tres valores; si no, un transcriptor nuevo. No carga el modelo."""
    if actual is not None and (actual.modelo_nombre, actual.dispositivo, actual.compute_type) == (
            modelo, dispositivo, compute_type):
        return actual
    return TranscriptorAudio(modelo_nombre=modelo, dispositivo=dispositivo, compute_type=compute_type)


def transcribir(transcriptor: TranscriptorAudio, opciones: OpcionesTranscripcion, parametros: dict,
                on_segmento=None, cancelar=None) -> ResultadoTranscripcion:
    """Transcribe `opciones.archivo`. `parametros` es `configuracion["transcripcion"]`; los siete parámetros de
    decodificación se pasan por nombre, porque esa sección también trae `idioma`, que elige la ventana."""
    return transcriptor.transcribir(
        opciones.archivo,
        idioma=opciones.idioma,
        task=opciones.task,
        beam_size=parametros["beam_size"],
        best_of=parametros["best_of"],
        temperature=parametros["temperature"],
        condition_on_previous_text=parametros["condition_on_previous_text"],
        compression_ratio_threshold=parametros["compression_ratio_threshold"],
        logprob_threshold=parametros["logprob_threshold"],
        no_speech_threshold=parametros["no_speech_threshold"],
        word_timestamps=opciones.palabra_por_palabra,
        on_segmento=on_segmento,
        cancelar=cancelar,
    )
