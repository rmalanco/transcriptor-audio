"""Utilidades para el transcriptor."""

import os
import ffmpeg
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class InfoArchivo:
    ruta: str
    nombre: str
    extension: str
    tamaño_bytes: int
    duracion_segundos: Optional[float]
    codec_audio: Optional[str]
    sample_rate: Optional[int]
    canales: Optional[int]
    es_video: bool


EXTENSIONES_AUDIO = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.opus', '.wma'}
EXTENSIONES_VIDEO = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v', '.ts', '.mts'}


def validar_archivo(ruta: str) -> bool:
    path = Path(ruta)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta}")
    if not path.is_file():
        raise ValueError(f"No es un archivo: {ruta}")
    extension = path.suffix.lower()
    if extension not in EXTENSIONES_AUDIO and extension not in EXTENSIONES_VIDEO:
        raise ValueError(f"Formato no soportado: {extension}. Soportados: {EXTENSIONES_AUDIO | EXTENSIONES_VIDEO}")
    return True


def obtener_info_archivo(ruta: str) -> InfoArchivo:
    validar_archivo(ruta)
    path = Path(ruta)
    
    try:
        probe = ffmpeg.probe(ruta)
        formato = probe.get('format', {})
        streams = probe.get('streams', [])
        
        audio_stream = next((s for s in streams if s.get('codec_type') == 'audio'), None)
        video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
        
        return InfoArchivo(
            ruta=str(path.absolute()),
            nombre=path.stem,
            extension=path.suffix.lower(),
            tamaño_bytes=path.stat().st_size,
            duracion_segundos=float(formato.get('duration', 0)) if formato.get('duration') else None,
            codec_audio=audio_stream.get('codec_name') if audio_stream else None,
            sample_rate=int(audio_stream.get('sample_rate', 0)) if audio_stream and audio_stream.get('sample_rate') else None,
            canales=audio_stream.get('channels') if audio_stream else None,
            es_video=video_stream is not None
        )
    except ffmpeg.Error:
        return InfoArchivo(
            ruta=str(path.absolute()),
            nombre=path.stem,
            extension=path.suffix.lower(),
            tamaño_bytes=path.stat().st_size,
            duracion_segundos=None,
            codec_audio=None,
            sample_rate=None,
            canales=None,
            es_video=path.suffix.lower() in EXTENSIONES_VIDEO
        )


def formatear_tiempo(segundos: float) -> str:
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    miliseg = int((segundos % 1) * 1000)
    return f"{horas:02d}:{minutos:02d}:{segs:02d},{miliseg:03d}"


def _partes_tiempo(segundos: float) -> tuple[int, int, int, int]:
    # Se redondea a milisegundos enteros antes de dividir para evitar salidas como "00:00:60,000"
    total_ms = round(max(segundos, 0) * 1000)
    horas, resto = divmod(total_ms, 3_600_000)
    minutos, resto = divmod(resto, 60_000)
    segs, miliseg = divmod(resto, 1000)
    return horas, minutos, segs, miliseg


def formatear_tiempo_srt(segundos: float) -> str:
    """Formato SRT: HH:MM:SS,mmm (coma decimal)."""
    horas, minutos, segs, miliseg = _partes_tiempo(segundos)
    return f"{horas:02d}:{minutos:02d}:{segs:02d},{miliseg:03d}"


def formatear_tiempo_vtt(segundos: float) -> str:
    """Formato WebVTT: HH:MM:SS.mmm (punto decimal)."""
    horas, minutos, segs, miliseg = _partes_tiempo(segundos)
    return f"{horas:02d}:{minutos:02d}:{segs:02d}.{miliseg:03d}"


def guardar_transcripcion(
    resultado,
    ruta_salida: str,
    formato: str = "txt",
    incluir_timestamps: bool = True
) -> None:
    path = Path(ruta_salida)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    if formato == "txt":
        with open(path, 'w', encoding='utf-8') as f:
            if incluir_timestamps:
                for seg in resultado.segmentos:
                    f.write(f"[{formatear_tiempo(seg.inicio)} --> {formatear_tiempo(seg.fin)}] {seg.texto}\n")
            else:
                f.write(resultado.texto_completo)
    
    elif formato == "srt":
        with open(path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(resultado.segmentos, 1):
                f.write(f"{i}\n")
                f.write(f"{formatear_tiempo_srt(seg.inicio)} --> {formatear_tiempo_srt(seg.fin)}\n")
                f.write(f"{seg.texto}\n\n")
    
    elif formato == "vtt":
        with open(path, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            for seg in resultado.segmentos:
                f.write(f"{formatear_tiempo_vtt(seg.inicio)} --> {formatear_tiempo_vtt(seg.fin)}\n")
                f.write(f"{seg.texto}\n\n")
    
    elif formato == "json":
        import json
        data = {
            "texto": resultado.texto_completo,
            "idioma": resultado.idioma_detectado,
            "probabilidad_idioma": resultado.probabilidad_idioma,
            "duracion": resultado.duracion_total,
            "segmentos": [
                {
                    "inicio": s.inicio,
                    "fin": s.fin,
                    "texto": s.texto,
                    "palabras": s.palabras
                }
                for s in resultado.segmentos
            ]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    else:
        raise ValueError(f"Formato no soportado: {formato}")