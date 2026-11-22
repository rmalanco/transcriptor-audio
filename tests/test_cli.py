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


def _ejecutar(monkeypatch, argumentos):
    """Ejecuta la CLI dentro del proceso y devuelve su código de salida (None si termina sin error)."""
    monkeypatch.setattr(sys, "argv", ["main.py", *argumentos])
    try:
        main()
    except SystemExit as salida:
        return salida.code
    return None


def test_cli_desde_otra_carpeta_usa_la_configuracion_del_proyecto(tmp_path, monkeypatch, modelo_whisper_falso):
    import yaml
    from src.configuracion import RUTA_POR_DEFECTO

    carpeta = tmp_path / "trabajo"
    (carpeta / "config").mkdir(parents=True)
    (carpeta / "config" / "settings.yaml").write_text(CONFIGURACION.replace("beam_size: 5", "beam_size: 77"),
                                                       encoding="utf-8")
    (carpeta / "reunion.m4a").touch()
    monkeypatch.chdir(carpeta)
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")])
    esperado = yaml.safe_load(RUTA_POR_DEFECTO.read_text(encoding="utf-8"))["transcripcion"]["beam_size"]

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "-o", "salida.txt"])

    assert codigo in (None, 0)
    assert doble.llamadas[0][1]["beam_size"] == esperado


def test_cli_yaml_mal_formado_sale_con_codigo_1_sin_transcribir(tmp_path, monkeypatch, capsys, modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "mal.yaml"
    config.write_text('modelo:\n  nombre: "small"\n   dispositivo: "cpu"\n', encoding="utf-8")
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")])

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "-o", "salida.txt", "--config", str(config)])

    assert codigo == 1
    assert doble.llamadas == []
    assert capsys.readouterr().err.startswith("Error: La configuración")


def test_cli_valor_invalido_sale_con_codigo_1_sin_transcribir(tmp_path, monkeypatch, capsys, modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "formato.yaml"
    config.write_text('salida:\n  formato: "pdf"\n', encoding="utf-8")
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")])

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "-o", "salida.txt", "--config", str(config)])

    assert codigo == 1
    assert doble.llamadas == []
    assert capsys.readouterr().err.startswith(f"Error: En la configuración {config}, `salida.formato` debe ser "
                                              "uno de txt, srt, vtt, json (vale «pdf»).")


def test_cli_configuracion_incompleta_usa_los_valores_por_defecto(tmp_path, monkeypatch, modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "incompleta.yaml"
    config.write_text("transcripcion:\n  beam_size: 5\nia:\n", encoding="utf-8")
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")])

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "-o", "salida.txt", "--config", str(config)])

    assert codigo in (None, 0)
    assert doble.llamadas[0][1]["language"] == "es"
    assert (tmp_path / "salida.txt").read_text(encoding="utf-8") == "[00:00:00,000 --> 00:00:02,000] Hola equipo.\n"


def test_cli_sin_opciones_usa_idioma_y_formato_de_la_configuracion(tmp_path, monkeypatch, modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "en_srt.yaml"
    config.write_text('transcripcion:\n  idioma: "en"\nsalida:\n  formato: "srt"\n', encoding="utf-8")
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")])

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "-o", "salida.srt", "--config", str(config)])

    assert codigo in (None, 0)
    assert doble.llamadas[0][1]["language"] == "en"
    assert (tmp_path / "salida.srt").read_text(encoding="utf-8") == (
        "1\n00:00:00,000 --> 00:00:02,000\nHola equipo.\n\n"
    )


def test_cli_la_opcion_explicita_gana_a_la_configuracion(tmp_path, monkeypatch, modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "en_srt.yaml"
    config.write_text('transcripcion:\n  idioma: "en"\nsalida:\n  formato: "srt"\n', encoding="utf-8")
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")])

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "-o", "salida.vtt", "-l", "fr", "-f", "vtt",
                                     "--config", str(config)])

    assert codigo in (None, 0)
    assert doble.llamadas[0][1]["language"] == "fr"
    assert (tmp_path / "salida.vtt").read_text(encoding="utf-8") == (
        "WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHola equipo.\n\n"
    )


def test_cli_copilot_modelos_con_ia_vacio_no_revienta(tmp_path, monkeypatch, capsys):
    from src import copilot

    monkeypatch.setattr(copilot, "RUTA_TOKEN", tmp_path / "app" / "copilot.json")
    monkeypatch.setattr(copilot, "RUTA_AUTH_OPENCODE", tmp_path / "opencode" / "auth.json")
    monkeypatch.delenv(copilot.VARIABLE_ENTORNO, raising=False)
    config = tmp_path / "ia_vacia.yaml"
    config.write_text("ia:\n", encoding="utf-8")

    codigo = _ejecutar(monkeypatch, ["--copilot-modelos", "--config", str(config)])

    assert codigo == 1
    assert "No has iniciado sesión" in capsys.readouterr().err
