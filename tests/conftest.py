"""Fixtures compartidas de los tests. Ningún fixture carga faster-whisper ni lee audio."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Optional

import pytest

from src import configuracion
from src.transcriber import TranscriptorAudio


@dataclass
class SegmentoFalso:
    """Segmento tal como lo devuelve faster-whisper (atributos `start`, `end`, `text`, `words`)."""
    start: float
    end: float
    text: str
    words: Optional[list] = None


def _segmento_falso(inicio, fin, texto, palabras=None):
    words = [SimpleNamespace(start=a, end=b, word=p) for a, b, p in palabras] if palabras else None
    return SegmentoFalso(inicio, fin, texto, words)


class ModeloWhisperFalso:
    """Doble de `WhisperModel` con segmentos fijos: no lee el audio ni necesita el modelo en caché."""

    def __init__(self, segmentos, duracion=5.0, idioma="es", probabilidad=0.98):
        self.segmentos = list(segmentos)
        self.info = SimpleNamespace(duration=duracion, language=idioma, language_probability=probabilidad)
        self.llamadas = []

    def transcribe(self, audio, **kwargs):
        self.llamadas.append((audio, kwargs))
        return iter(self.segmentos), self.info


@pytest.fixture
def modelo_whisper_falso(monkeypatch):
    """Coloca un doble de Whisper en `TranscriptorAudio.modelo` (la propiedad pública por la que se obtiene el modelo).

    Uso: `doble = modelo_whisper_falso([(0.0, 2.0, "Hola.")], duracion=5.0)`. Vale también para los
    `TranscriptorAudio` que crea la CLI, porque se parchea la clase y no una instancia.
    """
    def colocar(segmentos, duracion=5.0, idioma="es", probabilidad=0.98):
        """`segmentos` es una lista de tuplas (inicio, fin, texto) o (inicio, fin, texto, palabras), donde
        `palabras` es una lista de tuplas (inicio, fin, palabra) como las que daría Whisper con word_timestamps."""
        fabricados = [_segmento_falso(*tupla) for tupla in segmentos]
        doble = ModeloWhisperFalso(fabricados, duracion=duracion, idioma=idioma, probabilidad=probabilidad)
        monkeypatch.setattr(TranscriptorAudio, "modelo", property(lambda self: doble))
        return doble
    return colocar


@pytest.fixture(autouse=True)
def preferencias_aisladas(monkeypatch, tmp_path_factory):
    """Ningún test lee ni escribe las preferencias reales del usuario: apuntan a una carpeta temporal."""
    carpeta = tmp_path_factory.mktemp("preferencias")
    monkeypatch.setattr(configuracion, "RUTA_PREFERENCIAS", carpeta / "preferencias.json")
