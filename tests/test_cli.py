"""Transcripción por la CLI (`src.main`) dentro del proceso, con un modelo de Whisper falso y una configuración propia."""

import sys

import pytest

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


def test_cli_srt_sin_salida_falla_antes_de_transcribir(tmp_path, monkeypatch, capsys, modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")])

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "-f", "srt"])

    assert codigo == 1
    assert doble.llamadas == []
    assert capsys.readouterr().err == (
        "Error: el formato srt necesita un archivo de salida: añade -o <archivo>.\n"
    )


def test_cli_formato_srt_de_la_configuracion_sin_salida_tambien_falla_antes(tmp_path, monkeypatch, capsys,
                                                                           modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "srt.yaml"
    config.write_text('salida:\n  formato: "srt"\n', encoding="utf-8")
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")])

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "--config", str(config)])

    assert codigo == 1
    assert doble.llamadas == []
    assert capsys.readouterr().err == (
        "Error: el formato srt necesita un archivo de salida: añade -o <archivo>.\n"
    )


def test_cli_txt_por_stdout_es_igual_que_el_archivo(tmp_path, monkeypatch, capsys, modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "config_test.yaml"
    config.write_text(CONFIGURACION, encoding="utf-8")
    modelo_whisper_falso([(0.0, 2.0, "Hola equipo."), (3.0, 5.0, "Cerramos el punto.")])

    assert _ejecutar(monkeypatch, ["reunion.m4a", "-o", "salida.txt", "--config", str(config)]) in (None, 0)
    capsys.readouterr()
    assert _ejecutar(monkeypatch, ["reunion.m4a", "--config", str(config)]) in (None, 0)

    esperado = ("[00:00:00,000 --> 00:00:02,000] Hola equipo.\n"
                "[00:00:03,000 --> 00:00:05,000] Cerramos el punto.\n")
    assert (tmp_path / "salida.txt").read_text(encoding="utf-8") == esperado
    assert capsys.readouterr().out == esperado


def test_cli_json_por_stdout_es_igual_que_el_archivo(tmp_path, monkeypatch, capsys, modelo_whisper_falso):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "config_test.yaml"
    config.write_text(CONFIGURACION, encoding="utf-8")
    modelo_whisper_falso([(0.0, 2.0, "Hola equipo."), (3.0, 5.0, "Cerramos el punto.")])

    assert _ejecutar(monkeypatch, ["reunion.m4a", "-o", "salida.json", "-f", "json", "--config", str(config)]) in (None, 0)
    capsys.readouterr()
    assert _ejecutar(monkeypatch, ["reunion.m4a", "-f", "json", "--config", str(config)]) in (None, 0)

    assert (tmp_path / "salida.json").read_text(encoding="utf-8") != ""
    assert capsys.readouterr().out == (tmp_path / "salida.json").read_text(encoding="utf-8")


def test_cli_json_con_palabras_por_stdout_conserva_las_palabras(tmp_path, monkeypatch, capsys, modelo_whisper_falso):
    import json

    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "config_test.yaml"
    config.write_text(CONFIGURACION, encoding="utf-8")
    modelo_whisper_falso([(0.0, 2.0, "Hola equipo.", [(0.0, 0.5, " Hola"), (0.5, 2.0, " equipo.")])])

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "-f", "json", "--word-timestamps", "--config", str(config)])

    assert codigo in (None, 0)
    datos = json.loads(capsys.readouterr().out)
    assert datos["segmentos"][0]["palabras"] == [
        {"inicio": 0.0, "fin": 0.5, "palabra": " Hola"},
        {"inicio": 0.5, "fin": 2.0, "palabra": " equipo."},
    ]


@pytest.fixture(autouse=True)
def rutas_aisladas_y_sin_red(monkeypatch, tmp_path):
    """Como `rutas_aisladas` de test_copilot: el token no toca el equipo real y ninguna prueba sale a la red."""
    from src import copilot

    monkeypatch.setattr(copilot, "RUTA_TOKEN", tmp_path / "app" / "copilot.json")
    monkeypatch.setattr(copilot, "RUTA_AUTH_OPENCODE", tmp_path / "opencode" / "auth.json")
    monkeypatch.delenv(copilot.VARIABLE_ENTORNO, raising=False)

    def red_prohibida(*args, **kwargs):
        raise AssertionError("el test intentó llamar a la red")

    monkeypatch.setattr(copilot.httpx, "get", red_prohibida)
    monkeypatch.setattr(copilot.httpx, "post", red_prohibida)


def _prohibir_cargar_whisper(monkeypatch):
    """Si la CLI llega a crear el transcriptor, el test falla: el rechazo debe ocurrir antes."""
    def no_debe_crearse(*args, **kwargs):
        raise AssertionError("la CLI cargó Whisper antes de rechazar la entrada")

    monkeypatch.setattr("src.main.TranscriptorAudio", no_debe_crearse)


def test_cli_archivo_inexistente_sale_con_codigo_1_sin_cargar_whisper(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _prohibir_cargar_whisper(monkeypatch)

    codigo = _ejecutar(monkeypatch, ["no_existe.m4a", "-o", "salida.txt"])

    assert codigo == 1
    assert capsys.readouterr().err == "Error: Archivo no encontrado: no_existe.m4a\n"
    assert not (tmp_path / "salida.txt").exists()


def test_cli_extension_no_admitida_sale_con_codigo_1_sin_cargar_whisper(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "notas.txt").touch()
    _prohibir_cargar_whisper(monkeypatch)

    codigo = _ejecutar(monkeypatch, ["notas.txt", "-o", "salida.txt"])

    assert codigo == 1
    assert capsys.readouterr().err.startswith("Error: Formato no soportado: .txt.")
    assert not (tmp_path / "salida.txt").exists()


def test_cli_fallo_durante_la_transcripcion_sale_con_codigo_1_y_no_deja_archivo(tmp_path, monkeypatch, capsys):
    from src.transcriber import TranscriptorAudio

    monkeypatch.chdir(tmp_path)
    (tmp_path / "reunion.m4a").touch()
    config = tmp_path / "config_test.yaml"
    config.write_text(CONFIGURACION, encoding="utf-8")

    class ModeloRoto:
        def transcribe(self, audio, **kwargs):
            raise RuntimeError("memoria de GPU agotada")

    monkeypatch.setattr(TranscriptorAudio, "modelo", property(lambda self: ModeloRoto()))

    codigo = _ejecutar(monkeypatch, ["reunion.m4a", "-o", "salida.txt", "--config", str(config)])

    assert codigo == 1
    assert not (tmp_path / "salida.txt").exists()
    assert "Error durante la transcripción: memoria de GPU agotada" in capsys.readouterr().err


def test_cli_copilot_logout_con_token_propio_lo_borra_y_no_toca_la_sesion_de_opencode(tmp_path, monkeypatch, capsys):
    from src import copilot

    copilot.guardar_token("gho_app")
    copilot.RUTA_AUTH_OPENCODE.parent.mkdir(parents=True)
    datos_opencode = '{"github-copilot": {"refresh": "gho_oc"}}'
    copilot.RUTA_AUTH_OPENCODE.write_text(datos_opencode, encoding="utf-8")
    config = tmp_path / "ia.yaml"
    config.write_text("ia:\n", encoding="utf-8")

    codigo = _ejecutar(monkeypatch, ["--copilot-logout", "--config", str(config)])

    assert codigo == 0
    assert capsys.readouterr().out == "Sesión cerrada\n"
    assert not copilot.RUTA_TOKEN.exists()
    assert copilot.RUTA_AUTH_OPENCODE.read_text(encoding="utf-8") == datos_opencode
    assert copilot.leer_token().token == "gho_oc"


def test_cli_copilot_logout_sin_token_propio_lo_dice_y_sale_con_codigo_0(tmp_path, monkeypatch, capsys):
    from src import copilot

    config = tmp_path / "ia.yaml"
    config.write_text("ia:\n", encoding="utf-8")

    codigo = _ejecutar(monkeypatch, ["--copilot-logout", "--config", str(config)])

    assert codigo == 0
    assert capsys.readouterr().out == "No había sesión guardada por esta app\n"
    assert not copilot.RUTA_TOKEN.exists()


def test_cli_copilot_modelos_no_lista_las_familias_excluidas(tmp_path, monkeypatch, capsys):
    from src import copilot

    monkeypatch.setenv(copilot.VARIABLE_ENTORNO, "gho_prueba")
    catalogo = [
        {"id": "gpt-5.4", "policy": {"state": "enabled"}, "supported_endpoints": ["/chat/completions"],
         "capabilities": {"type": "chat"}},
        {"id": "kimi-k3", "policy": {"state": "enabled"}, "supported_endpoints": ["/chat/completions"],
         "capabilities": {"type": "chat"}},
        {"id": "mistral-medium-3", "policy": {"state": "enabled"}, "supported_endpoints": ["/chat/completions"],
         "capabilities": {"type": "chat"}},
    ]

    class _Respuesta:
        status_code = 200

        def __init__(self, datos):
            self.datos, self.text = datos, ""

        def json(self):
            return self.datos

    sesion_auto = {"selected_model": "gpt-5.4", "available_models": ["gpt-5.4", "kimi-k3", "mistral-medium-3"],
                   "session_token": "st", "expires_at": 9999999999}
    monkeypatch.setattr(copilot.httpx, "get", lambda *a, **kw: _Respuesta({"data": catalogo}))
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(sesion_auto))
    config = tmp_path / "ia.yaml"
    config.write_text("ia:\n", encoding="utf-8")

    codigo = _ejecutar(monkeypatch, ["--copilot-modelos", "--config", str(config)])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "gpt-5.4" in salida
    assert "kimi" not in salida and "mistral" not in salida
    assert "Se omiten 2 modelos de familias no autorizadas por la empresa." in salida
