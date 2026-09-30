"""Transcriptor de audio/video a texto usando faster-whisper."""

from .transcriber import TranscriptorAudio
from .utils import validar_archivo, obtener_info_archivo

__all__ = ["TranscriptorAudio", "validar_archivo", "obtener_info_archivo"]
__version__ = "0.1.0"