"""Carga y validación de la configuración (historia 05, módulo `src/configuracion.py`)."""

import pytest
import yaml

from src.configuracion import RUTA_POR_DEFECTO, cargar_configuracion


def test_sin_ruta_usa_la_configuracion_del_proyecto_desde_otra_carpeta(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.yaml").write_text("transcripcion:\n  beam_size: 77\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    esperado = yaml.safe_load(RUTA_POR_DEFECTO.read_text(encoding="utf-8"))["transcripcion"]["beam_size"]

    assert cargar_configuracion()["transcripcion"]["beam_size"] == esperado
    assert esperado != 77


def test_ruta_relativa_se_interpreta_desde_la_carpeta_de_trabajo(tmp_path, monkeypatch):
    (tmp_path / "otro.yaml").write_text("transcripcion:\n  beam_size: 3\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert cargar_configuracion("otro.yaml")["transcripcion"]["beam_size"] == 3


def test_archivo_inexistente_da_error_con_la_ruta(tmp_path):
    from src.configuracion import ErrorConfiguracion

    ruta = tmp_path / "no_existe.yaml"

    try:
        cargar_configuracion(str(ruta))
    except ErrorConfiguracion as e:
        assert str(e) == f"No se encontró la configuración {ruta}."
    else:
        raise AssertionError("debía lanzar ErrorConfiguracion")


def test_yaml_mal_formado_da_error_con_linea_y_columna(tmp_path):
    from src.configuracion import ErrorConfiguracion

    ruta = tmp_path / "mal.yaml"
    ruta.write_text('modelo:\n  nombre: "small"\n   dispositivo: "cpu"\n', encoding="utf-8")

    with pytest.raises(ErrorConfiguracion) as error:
        cargar_configuracion(str(ruta))

    assert str(error.value) == f"La configuración {ruta} no es un YAML válido (línea 3, columna 4)."


def test_archivo_vacio_usa_todos_los_valores_por_defecto(tmp_path):
    ruta = tmp_path / "vacio.yaml"
    ruta.write_text("", encoding="utf-8")

    config = cargar_configuracion(str(ruta))

    assert config["modelo"] == {"nombre": "large-v3-turbo", "dispositivo": "cpu", "compute_type": "int8"}
    assert config["transcripcion"] == {
        "idioma": "es", "beam_size": 5, "best_of": 5, "temperature": 0.0,
        "condition_on_previous_text": False, "compression_ratio_threshold": 2.4,
        "logprob_threshold": -1.0, "no_speech_threshold": 0.6,
    }
    assert config["salida"] == {"formato": "txt", "incluir_timestamps": True, "palabra_por_palabra": False}
    assert config["ia"] == {
        "modelo": "gpt-4.1", "copilot_enterprise_url": "", "temperatura": 0.2,
        "max_caracteres_bloque": 60000, "peticiones_paralelas": 3, "revision_fidelidad": False,
    }
    assert config["historial"] == {"ruta": "data/historial.db"}


def test_seccion_ia_vacia_usa_sus_valores_por_defecto(tmp_path):
    ruta = tmp_path / "ia_vacia.yaml"
    ruta.write_text("ia:\n", encoding="utf-8")

    config = cargar_configuracion(str(ruta))

    assert config["ia"] == {
        "modelo": "gpt-4.1", "copilot_enterprise_url": "", "temperatura": 0.2,
        "max_caracteres_bloque": 60000, "peticiones_paralelas": 3, "revision_fidelidad": False,
    }


def test_clave_ausente_toma_su_valor_por_defecto_y_conserva_las_demas(tmp_path):
    ruta = tmp_path / "parcial.yaml"
    ruta.write_text("transcripcion:\n  beam_size: 7\n", encoding="utf-8")

    transcripcion = cargar_configuracion(str(ruta))["transcripcion"]

    assert transcripcion["beam_size"] == 7
    assert transcripcion["best_of"] == 5
    assert transcripcion["idioma"] == "es"


def test_valor_de_tipo_invalido_nombra_la_clave_lo_esperado_y_el_valor(tmp_path):
    from src.configuracion import ErrorConfiguracion

    ruta = tmp_path / "tipo.yaml"
    ruta.write_text('transcripcion:\n  beam_size: "cinco"\n', encoding="utf-8")

    with pytest.raises(ErrorConfiguracion) as error:
        cargar_configuracion(str(ruta))

    assert str(error.value) == (f"En la configuración {ruta}, `transcripcion.beam_size` debe ser "
                                "un número entero mayor que 0 (vale «cinco»).")


def test_valor_no_permitido_lista_los_permitidos(tmp_path):
    from src.configuracion import ErrorConfiguracion

    ruta = tmp_path / "formato.yaml"
    ruta.write_text('salida:\n  formato: "pdf"\n', encoding="utf-8")

    with pytest.raises(ErrorConfiguracion) as error:
        cargar_configuracion(str(ruta))

    assert str(error.value) == (f"En la configuración {ruta}, `salida.formato` debe ser "
                                "uno de txt, srt, vtt, json (vale «pdf»).")


def test_booleano_no_vale_como_entero(tmp_path):
    from src.configuracion import ErrorConfiguracion

    ruta = tmp_path / "bool.yaml"
    ruta.write_text("transcripcion:\n  beam_size: true\n", encoding="utf-8")

    with pytest.raises(ErrorConfiguracion, match="debe ser un número entero mayor que 0"):
        cargar_configuracion(str(ruta))


def test_max_caracteres_bloque_cero_es_un_error(tmp_path):
    from src.configuracion import ErrorConfiguracion

    ruta = tmp_path / "bloque.yaml"
    ruta.write_text("ia:\n  max_caracteres_bloque: 0\n", encoding="utf-8")

    with pytest.raises(ErrorConfiguracion) as error:
        cargar_configuracion(str(ruta))

    assert str(error.value) == (f"En la configuración {ruta}, `ia.max_caracteres_bloque` debe ser "
                                "un número entero mayor que 0 (vale «0»).")


def test_raiz_que_no_es_un_mapa_es_un_error(tmp_path):
    from src.configuracion import ErrorConfiguracion

    ruta = tmp_path / "lista.yaml"
    ruta.write_text("- modelo\n- salida\n", encoding="utf-8")

    with pytest.raises(ErrorConfiguracion, match="no es un mapa de secciones"):
        cargar_configuracion(str(ruta))


def test_claves_desconocidas_se_ignoran_sin_error(tmp_path):
    ruta = tmp_path / "antigua.yaml"
    ruta.write_text("audio:\n  sample_rate: 16000\n"
                    "transcripcion:\n  task: \"transcribe\"\n  idoma: \"fr\"\n", encoding="utf-8")

    config = cargar_configuracion(str(ruta))

    assert config["audio"] == {"sample_rate": 16000}
    assert config["transcripcion"]["task"] == "transcribe"
    assert config["transcripcion"]["idoma"] == "fr"
    assert config["transcripcion"]["idioma"] == "es"


def test_el_yaml_del_proyecto_es_valido_y_no_tiene_claves_muertas():
    config = cargar_configuracion()
    crudo = yaml.safe_load(RUTA_POR_DEFECTO.read_text(encoding="utf-8"))

    assert config["modelo"]["nombre"] == crudo["modelo"]["nombre"]
    assert "audio" not in crudo
    assert "task" not in crudo["transcripcion"]


def test_modelo_nombre_fuera_de_la_lista_de_whisper_es_un_error(tmp_path):
    from src.configuracion import MODELOS_WHISPER, ErrorConfiguracion

    ruta = tmp_path / "modelo.yaml"
    ruta.write_text('modelo:\n  nombre: "gigante"\n', encoding="utf-8")

    with pytest.raises(ErrorConfiguracion) as error:
        cargar_configuracion(str(ruta))

    assert str(error.value) == (f"En la configuración {ruta}, `modelo.nombre` debe ser "
                                f"uno de {', '.join(MODELOS_WHISPER)} (vale «gigante»).")


@pytest.mark.parametrize("yaml_texto, mensaje", [
    ('modelo:\n  dispositivo: "gpu"\n', "`modelo.dispositivo` debe ser uno de cpu, cuda, auto (vale «gpu»)."),
    ('modelo:\n  compute_type: "int4"\n',
     "`modelo.compute_type` debe ser uno de int8, int16, float16, float32 (vale «int4»)."),
    ("transcripcion:\n  best_of: 0\n", "`transcripcion.best_of` debe ser un número entero mayor que 0 (vale «0»)."),
    ("transcripcion:\n  temperature: -1\n",
     "`transcripcion.temperature` debe ser un número mayor o igual que 0 (vale «-1»)."),
    ('transcripcion:\n  logprob_threshold: "bajo"\n',
     "`transcripcion.logprob_threshold` debe ser un número (vale «bajo»)."),
    ('transcripcion:\n  condition_on_previous_text: "si"\n',
     "`transcripcion.condition_on_previous_text` debe ser true o false (vale «si»)."),
    ("transcripcion:\n  idioma: 5\n", "`transcripcion.idioma` debe ser un texto no vacío (vale «5»)."),
    ("salida:\n  incluir_timestamps: 1\n", "`salida.incluir_timestamps` debe ser true o false (vale «1»)."),
    ("ia:\n  temperatura: -0.1\n", "`ia.temperatura` debe ser un número mayor o igual que 0 (vale «-0.1»)."),
    ("ia:\n  peticiones_paralelas: 2.5\n",
     "`ia.peticiones_paralelas` debe ser un número entero mayor que 0 (vale «2.5»)."),
    ('ia:\n  revision_fidelidad: "no"\n', "`ia.revision_fidelidad` debe ser true o false (vale «no»)."),
    ("ia:\n  modelo: 5\n", "`ia.modelo` debe ser un texto (vale «5»)."),
    ('historial:\n  ruta: ""\n', "`historial.ruta` debe ser un texto no vacío (vale «»)."),
    ("ia: 5\n", "`ia` debe ser una sección con claves (vale «5»)."),
])
def test_tipos_y_valores_de_las_demas_claves_se_comprueban(tmp_path, yaml_texto, mensaje):
    from src.configuracion import ErrorConfiguracion

    ruta = tmp_path / "config.yaml"
    ruta.write_text(yaml_texto, encoding="utf-8")

    with pytest.raises(ErrorConfiguracion) as error:
        cargar_configuracion(str(ruta))

    assert str(error.value) == f"En la configuración {ruta}, {mensaje}"


def test_sin_preferencias_no_hay_modelo_preferido(tmp_path, monkeypatch):
    from src import configuracion

    monkeypatch.setattr(configuracion, "RUTA_PREFERENCIAS", tmp_path / "no_existe.json")

    assert configuracion.leer_modelo_preferido() is None


def test_guardar_y_leer_el_modelo_preferido(tmp_path, monkeypatch):
    from src import configuracion

    monkeypatch.setattr(configuracion, "RUTA_PREFERENCIAS", tmp_path / "preferencias.json")

    configuracion.guardar_modelo_preferido("claude-sonnet-5.5")

    assert configuracion.leer_modelo_preferido() == "claude-sonnet-5.5"


@pytest.mark.parametrize("contenido", [
    "esto no es json",
    "[]",
    '{"modelo_ia": 5}',
    '{"modelo_ia": ""}',
])
def test_preferencias_corruptas_no_lanzan(tmp_path, monkeypatch, contenido):
    from src import configuracion

    ruta = tmp_path / "preferencias.json"
    ruta.write_text(contenido, encoding="utf-8")
    monkeypatch.setattr(configuracion, "RUTA_PREFERENCIAS", ruta)

    assert configuracion.leer_modelo_preferido() is None


def test_guardar_el_modelo_conserva_otras_preferencias(tmp_path, monkeypatch):
    import json

    from src import configuracion

    ruta = tmp_path / "preferencias.json"
    ruta.write_text(json.dumps({"otra_clave": "valor"}), encoding="utf-8")
    monkeypatch.setattr(configuracion, "RUTA_PREFERENCIAS", ruta)

    configuracion.guardar_modelo_preferido("claude-haiku-5.5")

    assert json.loads(ruta.read_text(encoding="utf-8")) == {"otra_clave": "valor", "modelo_ia": "claude-haiku-5.5"}


def test_guardar_el_modelo_crea_la_carpeta(tmp_path, monkeypatch):
    from src import configuracion

    ruta = tmp_path / "carpeta_nueva" / "preferencias.json"
    monkeypatch.setattr(configuracion, "RUTA_PREFERENCIAS", ruta)

    configuracion.guardar_modelo_preferido("gpt-4.1")

    assert ruta.is_file()


def test_el_modelo_preferido_gana_al_del_yaml():
    from src.configuracion import modelo_ia_efectivo

    assert modelo_ia_efectivo({"ia": {"modelo": "gpt-4.1"}}, "claude-sonnet-5.5") == "claude-sonnet-5.5"


def test_sin_preferido_se_usa_el_del_yaml():
    from src.configuracion import modelo_ia_efectivo

    assert modelo_ia_efectivo({"ia": {"modelo": "gpt-4.1"}}, None) == "gpt-4.1"


def test_los_valores_por_defecto_de_la_ia_coinciden_con_el_yaml_del_proyecto(tmp_path):
    vacio = tmp_path / "vacio.yaml"
    vacio.write_text("", encoding="utf-8")

    por_defecto = cargar_configuracion(str(vacio))["ia"]
    del_proyecto = cargar_configuracion()["ia"]

    assert por_defecto["temperatura"] == del_proyecto["temperatura"]
    assert por_defecto["revision_fidelidad"] == del_proyecto["revision_fidelidad"]
