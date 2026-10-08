"""Tests básicos para el transcriptor."""

import pytest
from src.utils import formatear_tiempo, formatear_tiempo_srt, formatear_tiempo_vtt
from src.transcriber import TranscriptorAudio, cargar_configuracion


def test_formatear_tiempo():
    assert formatear_tiempo(0) == "00:00:00,000"
    assert formatear_tiempo(1.5) == "00:00:01,500"
    assert formatear_tiempo(61) == "00:01:01,000"
    assert formatear_tiempo(3661.123) == "01:01:01,123"


def test_formatear_tiempo_srt():
    assert formatear_tiempo_srt(0) == "00:00:00,000"
    assert formatear_tiempo_srt(1.5) == "00:00:01,500"
    assert formatear_tiempo_srt(3661.123) == "01:01:01,123"
    assert formatear_tiempo_srt(59.9999) == "00:01:00,000"


def test_formatear_tiempo_vtt():
    assert formatear_tiempo_vtt(0) == "00:00:00.000"
    assert formatear_tiempo_vtt(1.5) == "00:00:01.500"
    assert formatear_tiempo_vtt(3661.123) == "01:01:01.123"
    assert formatear_tiempo_vtt(59.9999) == "00:01:00.000"


def test_guardar_vtt_usa_punto(tmp_path):
    from src.utils import guardar_transcripcion
    from src.transcriber import SegmentoTranscripcion, ResultadoTranscripcion
    resultado = ResultadoTranscripcion(
        "Hola mundo", [SegmentoTranscripcion(0.0, 2.5, "Hola mundo")], "es", 0.99, 2.5
    )
    ruta = tmp_path / "salida.vtt"
    guardar_transcripcion(resultado, str(ruta), formato="vtt")
    assert ruta.read_text(encoding="utf-8") == "WEBVTT\n\n00:00:00.000 --> 00:00:02.500\nHola mundo\n\n"


def test_cargar_configuracion():
    config = cargar_configuracion("config/settings.yaml")
    assert "modelo" in config
    assert "transcripcion" in config
    from src.main import MODELOS_DISPONIBLES
    assert config["modelo"]["nombre"] in MODELOS_DISPONIBLES


def test_transcriptor_inicializacion():
    transcriptor = TranscriptorAudio(modelo_nombre="tiny", dispositivo="cpu")
    assert transcriptor.modelo_nombre == "tiny"
    assert transcriptor.dispositivo == "cpu"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

def test_transcribir_usa_parametros_validos_de_faster_whisper():
    """Los argumentos enviados a WhisperModel.transcribe deben existir en su firma."""
    import inspect
    from types import SimpleNamespace
    from faster_whisper import WhisperModel
    from src.transcriber import TranscriptorAudio

    validos = set(inspect.signature(WhisperModel.transcribe).parameters)

    class ModeloFalso:
        def transcribe(self, audio, **kwargs):
            desconocidos = set(kwargs) - validos
            assert not desconocidos, f"Parámetros inexistentes en faster-whisper: {desconocidos}"
            return iter([]), SimpleNamespace(duration=10.0, language="es", language_probability=0.99)

    t = TranscriptorAudio()
    t._modelo = ModeloFalso()
    resultado = t.transcribir("audio.wav")
    assert resultado.segmentos == []


def test_alucinaciones_conocidas_solo_segmento_completo():
    from src.transcriber import es_alucinacion_conocida
    assert es_alucinacion_conocida("¡Suscríbete!")
    assert es_alucinacion_conocida(" Subtítulos realizados por la comunidad de Amara.org")
    assert not es_alucinacion_conocida("Gracias.")  # en una reunión es real
    assert not es_alucinacion_conocida("gracias por ver el video del proyecto, Ricardo")
