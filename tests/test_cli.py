"""Transcripción por la CLI (`src.main`) dentro del proceso, con un modelo de Whisper falso y una configuración propia."""

import sys

from src.main import main


CONFIGURACION = """\
modelo:
  nombre: "small"
  dispositivo: "cpu"
  compute_type: "int8"
transcripcion:
  beam_size: 5
  best_of: 5
  temperature: 0.0
  condition_on_previous_text: false
  compression_ratio_threshold: 2.4
  logprob_threshold: -1.0
  no_speech_threshold: 0.6
"""


def test_cli_transcribe_a_srt_con_configuracion_propia(tmp_path, monkeypatch, capsys, modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "config_test.yaml"
    config.write_text(CONFIGURACION, encoding="utf-8")
    modelo_whisper_falso([
        (0.0, 2.0, "Hola equipo."),
        (3.0, 5.0, "Cerramos el punto."),
    ], duracion=5.0, idioma="es")
    monkeypatch.setattr(sys, "argv", ["main.py", "reunion.m4a", "-o", "salida.srt", "-f", "srt",
                                      "--config", str(config)])

    codigo = None
    try:
        main()
    except SystemExit as salida:
        codigo = salida.code
    assert codigo in (None, 0)

    assert capsys.readouterr().out == "Transcripción guardada en: salida.srt\n"
    assert (tmp_path / "salida.srt").read_text(encoding="utf-8") == (
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "Hola equipo.\n"
        "\n"
        "2\n"
        "00:00:03,000 --> 00:00:05,000\n"
        "Cerramos el punto.\n"
        "\n"
    )
