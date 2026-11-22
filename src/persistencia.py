"""Persistencia de transcripciones y documentos: primero el historial, después el archivo junto al audio.

Sin interfaz: no importa customtkinter. Las funciones devuelven lo guardado y los avisos en vez de lanzar errores.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.utils import guardar_transcripcion

if TYPE_CHECKING:
    from src.historial import Historial
    from src.transcriber import ResultadoTranscripcion


def _motivo(error: Exception) -> str:
    """Texto del fallo; si la excepción no trae mensaje, su tipo (para que el aviso no quede vacío)."""
    return str(error) or type(error).__name__


@dataclass
class Persistencia:
    id_historial: Optional[int] = None
    ruta_exportada: Optional[str] = None
    motivo_historial: Optional[str] = None
    motivo_exportacion: Optional[str] = None


def persistir_transcripcion(
    historial: Optional["Historial"],
    archivo: str,
    resultado: "ResultadoTranscripcion",
    modelo_whisper: Optional[str],
    ruta_salida: str,
    formato: str,
    incluir_timestamps: bool,
) -> Persistencia:
    id_historial, motivo_historial = None, None
    if historial is None:
        motivo_historial = "Historial no disponible"
    else:
        try:
            id_historial = historial.crear(archivo, resultado, modelo_whisper=modelo_whisper)
        except Exception as e:
            motivo_historial = _motivo(e)
    try:
        guardar_transcripcion(resultado, ruta_salida, formato=formato, incluir_timestamps=incluir_timestamps)
    except Exception as e:
        return Persistencia(id_historial=id_historial, motivo_historial=motivo_historial,
                            motivo_exportacion=f"{Path(ruta_salida).name}: {_motivo(e)}")
    return Persistencia(id_historial=id_historial, motivo_historial=motivo_historial, ruta_exportada=ruta_salida)


def persistir_documento(
    historial: Optional["Historial"],
    id_historial: Optional[int],
    clave: str,
    contenido: str,
    modelo: Optional[str],
    ruta_salida: Optional[str],
) -> Persistencia:
    guardado_id, motivo_historial = None, None
    if historial is None:
        motivo_historial = "Historial no disponible"
    elif id_historial is None:
        motivo_historial = "La transcripción no está en el historial"
    else:
        try:
            historial.guardar_documento(id_historial, clave, contenido, modelo=modelo)
            guardado_id = id_historial
        except Exception as e:
            motivo_historial = _motivo(e)
    if ruta_salida is None:
        return Persistencia(id_historial=guardado_id, motivo_historial=motivo_historial)
    try:
        Path(ruta_salida).write_text(contenido + "\n", encoding="utf-8")
    except Exception as e:
        return Persistencia(id_historial=guardado_id, motivo_historial=motivo_historial,
                            motivo_exportacion=f"{Path(ruta_salida).name}: {_motivo(e)}")
    return Persistencia(id_historial=guardado_id, motivo_historial=motivo_historial, ruta_exportada=ruta_salida)


def texto_sin_guardado(persistencia: Persistencia) -> Optional[str]:
    """Aviso para cuando no quedó nada guardado (ni en el historial ni como archivo)."""
    if persistencia.id_historial is None and persistencia.ruta_exportada is None:
        return "El resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para conservarlo."
    return None


def texto_destino_documento(persistencia: Persistencia) -> str:
    """Texto de estado de un documento: dónde quedó (archivo y/o historial) y, si no quedó nada, el aviso."""
    partes = []
    if persistencia.ruta_exportada:
        partes.append(f"guardado como {Path(persistencia.ruta_exportada).name}")
    elif persistencia.motivo_exportacion:
        partes.append(f"no se pudo exportar {persistencia.motivo_exportacion}")
    if persistencia.id_historial is not None:
        partes.append("guardado en el historial")
    elif persistencia.motivo_historial:
        partes.append(f"no se guardó en el historial: {persistencia.motivo_historial}")
    destino = "; ".join(partes)
    aviso_sin_guardar = texto_sin_guardado(persistencia)
    if aviso_sin_guardar:
        destino += ". " + aviso_sin_guardar
    return destino
