"""Flujo de la transcripción sin interfaz (historia 09). Sin ventana, sin red y sin modelo real."""

from pathlib import Path

import pytest

from src.configuracion import cargar_configuracion
from src.flujo_transcripcion import (OpcionesTranscripcion, ruta_transcripcion, transcribir,
                                     transcriptor_para)
from src.transcriber import TranscriptorAudio


def test_ruta_transcripcion_conserva_la_extension():
    assert ruta_transcripcion(str(Path("/carpeta") / "reunion.m4a"), "srt") == str(
        Path("/carpeta") / "reunion.m4a_transcripcion.srt"
    )


def _prohibido_cargar_modelo(self):
    raise AssertionError("transcriptor_para no debe cargar el modelo de Whisper")


def test_transcriptor_para_reutiliza_o_recrea(monkeypatch):
    monkeypatch.setattr(TranscriptorAudio, "modelo", property(_prohibido_cargar_modelo))

    actual = transcriptor_para(None, "small", "cpu", "int8")

    assert isinstance(actual, TranscriptorAudio)
    assert (actual.modelo_nombre, actual.dispositivo, actual.compute_type) == ("small", "cpu", "int8")
    assert transcriptor_para(actual, "small", "cpu", "int8") is actual
    for modelo, dispositivo, compute in [("base", "cpu", "int8"), ("small", "cuda", "int8"), ("small", "cpu", "float32")]:
        nuevo = transcriptor_para(actual, modelo, dispositivo, compute)
        assert nuevo is not actual
        assert (nuevo.modelo_nombre, nuevo.dispositivo, nuevo.compute_type) == (modelo, dispositivo, compute)


def test_opciones_y_parametros_llegan_a_whisper(tmp_path, modelo_whisper_falso):
    ruta = tmp_path / "settings.yaml"
    ruta.write_text(
        "transcripcion:\n  idioma: auto\n  beam_size: 3\n  logprob_threshold: -0.8\n"
        "salida:\n  palabra_por_palabra: true\n",
        encoding="utf-8",
    )
    config = cargar_configuracion(str(ruta))
    cfg = config["transcripcion"]
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola.")])
    opciones = OpcionesTranscripcion.desde_configuracion(config, "reunion.m4a", modelo="small")
    transcriptor = transcriptor_para(None, opciones.modelo, opciones.dispositivo, opciones.compute_type)

    transcribir(transcriptor, opciones, cfg)

    audio, kwargs = doble.llamadas[0]
    assert audio == "reunion.m4a"
    assert kwargs["language"] is None
    assert kwargs["task"] == "transcribe"
    assert kwargs["beam_size"] == 3
    assert kwargs["log_prob_threshold"] == -0.8
    assert kwargs["word_timestamps"] is True
    assert kwargs["best_of"] == cfg["best_of"]
    assert kwargs["temperature"] == cfg["temperature"]
    assert kwargs["condition_on_previous_text"] == cfg["condition_on_previous_text"]
    assert kwargs["compression_ratio_threshold"] == cfg["compression_ratio_threshold"]
    assert kwargs["no_speech_threshold"] == cfg["no_speech_threshold"]
    assert opciones.modelo == "small"
    assert (opciones.dispositivo, opciones.compute_type, opciones.formato, opciones.incluir_timestamps) == (
        "cpu", "int8", "txt", True)


def test_desde_configuracion_rechaza_un_campo_desconocido(tmp_path):
    ruta = tmp_path / "settings.yaml"
    ruta.write_text("", encoding="utf-8")
    config = cargar_configuracion(str(ruta))

    with pytest.raises(TypeError):
        OpcionesTranscripcion.desde_configuracion(config, "reunion.m4a", timestamps=False)
