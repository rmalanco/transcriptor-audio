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


def test_sin_preferencias_la_efectiva_es_la_del_yaml_sin_avisos(tmp_path):
    from src.configuracion import cargar_configuracion, combinar, leer_ajustes

    ruta = tmp_path / "settings.yaml"
    ruta.write_text('salida:\n  formato: "vtt"\n', encoding="utf-8")
    proyecto = cargar_configuracion(str(ruta))

    ajustes = leer_ajustes()
    efectiva, avisos = combinar(proyecto, ajustes)

    assert efectiva == cargar_configuracion(str(ruta))
    assert avisos == []
    assert ajustes.ilegible is False


def test_un_ajuste_guardado_gana_al_yaml_sin_tocarlo(tmp_path):
    import json

    from src import configuracion
    from src.configuracion import cargar_configuracion, combinar, leer_ajustes

    ruta = tmp_path / "settings.yaml"
    ruta.write_text('salida:\n  formato: "txt"\ntranscripcion:\n  beam_size: 5\n', encoding="utf-8")
    contenido = ruta.read_text(encoding="utf-8")
    mtime = ruta.stat().st_mtime_ns
    configuracion.RUTA_PREFERENCIAS.write_text(
        json.dumps({"configuracion": {"salida": {"formato": "srt"}}}), encoding="utf-8")

    efectiva, avisos = combinar(cargar_configuracion(str(ruta)), leer_ajustes())

    assert efectiva["salida"]["formato"] == "srt"
    assert efectiva["transcripcion"]["beam_size"] == 5
    assert avisos == []
    assert ruta.read_text(encoding="utf-8") == contenido
    assert ruta.stat().st_mtime_ns == mtime


def test_ajustes_invalidos_desconocidos_no_finitos_e_ia_modelo_se_ignoran_con_aviso(tmp_path):
    from src import configuracion
    from src.configuracion import cargar_configuracion, combinar, leer_ajustes

    ruta = tmp_path / "settings.yaml"
    ruta.write_text('transcripcion:\n  beam_size: 7\n  temperature: 0.5\nsalida:\n  formato: "vtt"\n',
                    encoding="utf-8")
    configuracion.RUTA_PREFERENCIAS.write_text(
        '{"configuracion": {"transcripcion": {"beam_size": "cinco", "temperature": NaN},'
        ' "audio": {"sample_rate": 16000}, "ia": {"modelo": "x"}, "salida": 3}}', encoding="utf-8")
    proyecto = cargar_configuracion(str(ruta))
    ruta_pref = configuracion.RUTA_PREFERENCIAS

    efectiva, avisos = combinar(proyecto, leer_ajustes())

    assert efectiva == proyecto
    assert len(avisos) == 5
    assert (f"En {ruta_pref}, `transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «cinco»); "
            "se usa el valor de config/settings.yaml.") in avisos
    assert f"En {ruta_pref}, `audio.sample_rate` no es una clave de la configuración; se ignora." in avisos
    assert (f"En {ruta_pref}, `ia.modelo` no se guarda en «configuracion» (el modelo elegido va en «modelo_ia»); "
            "se ignora.") in avisos
    assert f"En {ruta_pref}, la sección `salida` no es un objeto; se ignora." in avisos
    assert any("`transcripcion.temperature`" in aviso and "(vale «nan»)" in aviso for aviso in avisos)


def test_ajuste_infinito_en_clave_sin_tope_se_ignora(tmp_path):
    from src import configuracion
    from src.configuracion import cargar_configuracion, combinar, leer_ajustes

    ruta = tmp_path / "settings.yaml"
    ruta.write_text("transcripcion:\n  compression_ratio_threshold: 2.0\n", encoding="utf-8")
    configuracion.RUTA_PREFERENCIAS.write_text(
        '{"configuracion": {"transcripcion": {"compression_ratio_threshold": Infinity}}}', encoding="utf-8")
    proyecto = cargar_configuracion(str(ruta))

    efectiva, avisos = combinar(proyecto, leer_ajustes())

    assert efectiva["transcripcion"]["compression_ratio_threshold"] == 2.0
    assert avisos == [
        f"En {configuracion.RUTA_PREFERENCIAS}, `transcripcion.compression_ratio_threshold` debe ser un número "
        "(vale «inf»); se usa el valor de config/settings.yaml.",
    ]


@pytest.mark.parametrize("contenido", ["{", "[]", '{"configuracion": 3}', "carpeta"])
def test_preferencias_ilegibles_dan_aviso_y_valores_del_yaml(tmp_path, contenido):
    from src import configuracion
    from src.configuracion import cargar_configuracion, combinar, leer_ajustes

    ruta_yaml = tmp_path / "settings.yaml"
    ruta_yaml.write_text("transcripcion:\n  beam_size: 7\n", encoding="utf-8")
    proyecto = cargar_configuracion(str(ruta_yaml))
    ruta = configuracion.RUTA_PREFERENCIAS
    if contenido == "carpeta":
        ruta.mkdir()  # leer un directorio da OSError
    else:
        ruta.write_text(contenido, encoding="utf-8")

    ajustes = leer_ajustes()
    efectiva, avisos = combinar(proyecto, ajustes)

    assert efectiva == proyecto
    assert len(avisos) == 1
    if contenido == "carpeta":
        assert avisos[0].startswith(f"Las preferencias {ruta} no se pudieron leer (")
        assert avisos[0].endswith("); se usan los valores de config/settings.yaml.")
        assert ajustes.ilegible is False
    elif contenido == '{"configuracion": 3}':
        assert avisos[0] == f"En {ruta}, «configuracion» no es un objeto; se ignora."
        assert ajustes.ilegible is False
    else:
        assert avisos[0] == (f"Las preferencias {ruta} no son un JSON válido; se usan los valores de "
                             "config/settings.yaml. Al guardar se reemplazará el archivo.")
        assert ajustes.ilegible is True


def test_preferencias_con_anidamiento_extremo_no_impiden_abrir(tmp_path, monkeypatch):
    from src import configuracion
    ruta = tmp_path / "preferencias.json"
    ruta.write_text("[" * 200_000, encoding="utf-8")
    monkeypatch.setattr(configuracion, "RUTA_PREFERENCIAS", ruta)
    ajustes = configuracion.leer_ajustes()
    assert ajustes.valores == {} and ajustes.ilegible


@pytest.mark.parametrize("seccion, clave, valor, esperado", [
    ("transcripcion", "beam_size", "3", 3),
    ("transcripcion", "no_speech_threshold", " 0,6 ", 0.6),
    ("transcripcion", "logprob_threshold", "-1", -1.0),
    ("ia", "copilot_enterprise_url", "", ""),
    ("ia", "copilot_enterprise_url", "empresa.ghe.com", "empresa.ghe.com"),
    ("salida", "incluir_timestamps", True, True),
])
def test_valor_desde_formulario_convierte(seccion, clave, valor, esperado):
    from src.configuracion import valor_desde_formulario

    convertido = valor_desde_formulario(seccion, clave, valor)

    assert convertido == esperado
    assert type(convertido) is type(esperado)


@pytest.mark.parametrize("seccion, clave, valor, mensaje", [
    ("transcripcion", "beam_size", "cinco",
     "`transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «cinco»)."),
    ("transcripcion", "beam_size", "3.0",
     "`transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «3.0»)."),
    ("transcripcion", "beam_size", "50",
     "`transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «50»)."),
    ("transcripcion", "temperature", "nan",
     "`transcripcion.temperature` debe ser un número entre 0 y 2 (vale «nan»)."),
    ("transcripcion", "temperature", "1e999",
     "`transcripcion.temperature` debe ser un número entre 0 y 2 (vale «1e999»)."),
    ("ia", "max_caracteres_bloque", "4000",
     "`ia.max_caracteres_bloque` debe ser un número entero entre 5000 y 500000 (vale «4000»)."),
    ("transcripcion", "compression_ratio_threshold", "",
     "`transcripcion.compression_ratio_threshold` debe ser un número (vale «»)."),
    ("transcripcion", "compression_ratio_threshold", "inf",
     "`transcripcion.compression_ratio_threshold` debe ser un número (vale «inf»)."),
])
def test_valor_desde_formulario_rechaza_con_topes_y_no_finitos(seccion, clave, valor, mensaje):
    from src.configuracion import ErrorConfiguracion, valor_desde_formulario

    with pytest.raises(ErrorConfiguracion) as error:
        valor_desde_formulario(seccion, clave, valor)

    assert str(error.value) == mensaje


def test_dominio_enterprise_debe_ser_un_nombre_de_host():
    from src.configuracion import ErrorConfiguracion, valor_desde_formulario

    for valor in ("https://empresa.ghe.com/", "empresa.ghe.com/", "empresa ghe.com"):
        with pytest.raises(ErrorConfiguracion) as error:
            valor_desde_formulario("ia", "copilot_enterprise_url", valor)
        assert str(error.value) == ("`ia.copilot_enterprise_url` debe ser un nombre de dominio sin https:// ni "
                                    f"barras, como empresa.ghe.com, o estar vacío (vale «{valor}»).")

    assert valor_desde_formulario("ia", "copilot_enterprise_url", "empresa.ghe.com") == "empresa.ghe.com"
    assert valor_desde_formulario("ia", "copilot_enterprise_url", "") == ""


def test_historial_ruta_fuera_del_repo_salvo_data_y_escribible(tmp_path, monkeypatch):
    from src import configuracion
    from src.configuracion import ErrorConfiguracion, valor_desde_formulario

    proyecto = tmp_path / "proyecto"
    proyecto.mkdir()
    monkeypatch.setattr(configuracion, "RAIZ_PROYECTO", proyecto)

    for valor in ("src/historial.db", "data/../src/historial.db"):
        with pytest.raises(ErrorConfiguracion) as error:
            valor_desde_formulario("historial", "ruta", valor)
        assert str(error.value) == ("`historial.ruta` no puede estar dentro de la carpeta del proyecto salvo en data/ "
                                    f"(vale «{valor}»).")

    archivo = tmp_path / "archivo"
    archivo.write_text("contenido", encoding="utf-8")
    bajo_archivo = str(archivo / "sub" / "historial.db")
    with pytest.raises(ErrorConfiguracion) as error:
        valor_desde_formulario("historial", "ruta", bajo_archivo)
    assert str(error.value) == ("`historial.ruta` está en una carpeta que no se puede crear ni escribir "
                                f"(vale «{bajo_archivo}»).")

    nueva = str(tmp_path / "nueva" / "historial.db")
    assert valor_desde_formulario("historial", "ruta", "data/sub/otro.db") == "data/sub/otro.db"
    assert valor_desde_formulario("historial", "ruta", nueva) == nueva

    assert not (proyecto / "data").exists()
    assert not (tmp_path / "nueva").exists()


def test_preferencias_aplican_los_topes_del_panel_y_las_reglas_de_ruta_y_dominio(tmp_path, monkeypatch):
    import json

    from src import configuracion
    from src.configuracion import cargar_configuracion, combinar, leer_ajustes

    monkeypatch.setattr(configuracion, "RAIZ_PROYECTO", tmp_path / "proyecto")
    (tmp_path / "proyecto").mkdir()
    ruta_yaml = tmp_path / "settings.yaml"
    ruta_yaml.write_text('transcripcion:\n  beam_size: 7\n  best_of: 4\nhistorial:\n  ruta: "data/otra.db"\n'
                         'ia:\n  copilot_enterprise_url: "empresa.ghe.com"\n', encoding="utf-8")
    proyecto = cargar_configuracion(str(ruta_yaml))
    ruta_pref = configuracion.RUTA_PREFERENCIAS
    configuracion.RUTA_PREFERENCIAS.write_text(json.dumps({"configuracion": {
        "transcripcion": {"beam_size": 50, "best_of": "cinco"},
        "historial": {"ruta": "src/historial.db"},
        "ia": {"copilot_enterprise_url": "https://empresa.ghe.com/"},
    }}), encoding="utf-8")

    efectiva, avisos = combinar(proyecto, leer_ajustes())

    assert efectiva == proyecto
    assert avisos == [
        f"En {ruta_pref}, `transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «50»); "
        "se usa el valor de config/settings.yaml.",
        f"En {ruta_pref}, `transcripcion.best_of` debe ser un número entero entre 1 y 20 (vale «cinco»); "
        "se usa el valor de config/settings.yaml.",
        f"En {ruta_pref}, `historial.ruta` no puede estar dentro de la carpeta del proyecto salvo en data/ "
        "(vale «src/historial.db»); se usa el valor de config/settings.yaml.",
        f"En {ruta_pref}, `ia.copilot_enterprise_url` debe ser un nombre de dominio sin https:// ni barras, como "
        "empresa.ghe.com, o estar vacío (vale «https://empresa.ghe.com/»); se usa el valor de config/settings.yaml.",
    ]

    ruta_fuera = tmp_path / "archivo"
    ruta_fuera.write_text("contenido", encoding="utf-8")
    ruta_bajo_archivo = str(ruta_fuera / "sub" / "historial.db")
    configuracion.RUTA_PREFERENCIAS.write_text(json.dumps(
        {"configuracion": {"historial": {"ruta": ruta_bajo_archivo}}}), encoding="utf-8")

    efectiva, avisos = combinar(proyecto, leer_ajustes())

    assert efectiva["historial"]["ruta"] == ruta_bajo_archivo
    assert avisos == []
    assert not (ruta_fuera / "sub").exists()


def test_yaml_con_beam_size_alto_se_carga_sin_tope(tmp_path):
    ruta = tmp_path / "alto.yaml"
    ruta.write_text("transcripcion:\n  beam_size: 50\n", encoding="utf-8")

    assert cargar_configuracion(str(ruta))["transcripcion"]["beam_size"] == 50


def test_validar_formulario_subconjunto_errores_en_orden_y_regla_7():
    from src.configuracion import validar_formulario

    convertidos, errores = validar_formulario({
        ("transcripcion", "beam_size"): "cinco",
        ("salida", "formato"): "srt",
        ("transcripcion", "best_of"): "x",
    }, modelo_ia="Mistral-Large-3")

    assert convertidos == {("salida", "formato"): "srt"}
    assert list(errores) == [("transcripcion", "beam_size"), ("transcripcion", "best_of"), ("ia", "modelo")]
    assert errores[("transcripcion", "beam_size")] == (
        "`transcripcion.beam_size` debe ser un número entero entre 1 y 20 (vale «cinco»).")
    assert errores[("transcripcion", "best_of")] == (
        "`transcripcion.best_of` debe ser un número entero entre 1 y 20 (vale «x»).")
    assert errores[("ia", "modelo")] == ("El modelo «Mistral-Large-3» es de la familia «mistral», que no está "
                                         "autorizada por la empresa. Elige otro modelo.")

    _, errores = validar_formulario({("salida", "formato"): "srt"}, modelo_ia="claude-sonnet-5.5")
    assert errores == {}
    _, errores = validar_formulario({("salida", "formato"): "srt"})
    assert errores == {}


def test_validar_formulario_no_acepta_ia_modelo_entre_los_valores():
    from src.configuracion import validar_formulario

    with pytest.raises(ValueError):
        validar_formulario({("ia", "modelo"): "gpt-4.1"})


def test_resumen_errores_singular_y_plural():
    from src.configuracion import resumen_errores

    assert resumen_errores(1) == "No se guardó nada: corrige 1 valor."
    assert resumen_errores(3) == "No se guardó nada: corrige 3 valores."


# --- Historia 19: guardar y restablecer las preferencias en una escritura atómica ---

YAML_PROYECTO_19 = """\
salida:
  formato: "txt"
transcripcion:
  beam_size: 5
  best_of: 5
ia:
  modelo: "gpt-4.1"
"""


def _proyecto_19(tmp_path):
    from src.configuracion import cargar_configuracion

    ruta = tmp_path / "settings.yaml"
    ruta.write_text(YAML_PROYECTO_19, encoding="utf-8")
    return cargar_configuracion(ruta)


def _ruta_preferencias_19(monkeypatch, tmp_path, contenido=None):
    from src import configuracion

    ruta = tmp_path / "preferencias.json"
    if contenido is not None:
        ruta.write_text(contenido, encoding="utf-8")
    monkeypatch.setattr(configuracion, "RUTA_PREFERENCIAS", ruta)
    return ruta


def _contar_replace_19(monkeypatch):
    """Envuelve os.replace: anota cada llamada y llama al original."""
    import os

    from src import configuracion

    llamadas = []
    original = os.replace

    def contar(origen, destino):
        llamadas.append((origen, destino))
        return original(origen, destino)

    monkeypatch.setattr(configuracion.os, "replace", contar)
    return llamadas


def test_guardar_ajustes_solo_diferencias_y_descarta_lo_que_no_sirve(tmp_path, monkeypatch):
    import json

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, json.dumps({
        "modelo_ia": "gpt-4.1", "x": 1,
        "configuracion": {"transcripcion": {"best_of": 3, "beam_size": "x"}, "audio": {"a": 1}},
    }))

    avisos = configuracion.guardar_ajustes(_proyecto_19(tmp_path), {("salida", "formato"): "srt",
                                                                    ("transcripcion", "beam_size"): 5})

    assert json.loads(ruta.read_text(encoding="utf-8")) == {
        "modelo_ia": "gpt-4.1", "x": 1,
        "configuracion": {"transcripcion": {"best_of": 3}, "salida": {"formato": "srt"}},
    }
    assert avisos == [f"Se descartaron de {ruta} claves que no sirven: `transcripcion.beam_size`, `audio.a`."]
    assert not ruta.with_name("preferencias.json.tmp").exists()


def test_guardar_ajustes_quita_configuracion_vacia(tmp_path, monkeypatch):
    import json

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, json.dumps({
        "modelo_ia": "gpt-4.1", "x": 1,
        "configuracion": {"transcripcion": {"best_of": 3}, "salida": {"formato": "srt"}},
    }))

    configuracion.guardar_ajustes(_proyecto_19(tmp_path), {("salida", "formato"): "txt",
                                                           ("transcripcion", "best_of"): 5})

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert "configuracion" not in datos
    assert datos["x"] == 1
    assert datos["modelo_ia"] == "gpt-4.1"


def test_guardar_ajustes_con_modelo_en_una_sola_escritura(tmp_path, monkeypatch):
    import json

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, json.dumps({"x": 1}))
    llamadas = _contar_replace_19(monkeypatch)

    configuracion.guardar_ajustes(_proyecto_19(tmp_path), {("salida", "formato"): "srt"},
                                  modelo_ia="claude-sonnet-5.5")

    assert len(llamadas) == 1
    assert json.loads(ruta.read_text(encoding="utf-8")) == {
        "x": 1, "modelo_ia": "claude-sonnet-5.5", "configuracion": {"salida": {"formato": "srt"}},
    }


def test_guardar_el_modelo_del_yaml_quita_modelo_ia(tmp_path, monkeypatch):
    import json

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, json.dumps({"modelo_ia": "claude-sonnet-5.5", "x": 1}))

    configuracion.guardar_ajustes(_proyecto_19(tmp_path), {}, modelo_ia="gpt-4.1")

    assert json.loads(ruta.read_text(encoding="utf-8")) == {"x": 1}


def test_guardar_ajustes_rechaza_modelo_excluido_sin_escribir(tmp_path, monkeypatch):
    import json

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, json.dumps({"x": 1}))
    antes = ruta.read_bytes()
    llamadas = _contar_replace_19(monkeypatch)

    with pytest.raises(ValueError):
        configuracion.guardar_ajustes(_proyecto_19(tmp_path), {("salida", "formato"): "srt"},
                                      modelo_ia="Mistral-Large-3")

    assert ruta.read_bytes() == antes
    assert llamadas == []


def test_restablecer_borra_ajustes_y_modelo_y_conserva_lo_demas(tmp_path, monkeypatch):
    import json

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, json.dumps({
        "modelo_ia": "claude-sonnet-5.5", "x": 1, "configuracion": {"salida": {"formato": "srt"}},
    }))
    llamadas = _contar_replace_19(monkeypatch)

    configuracion.restablecer_ajustes()

    assert json.loads(ruta.read_text(encoding="utf-8")) == {"x": 1}
    assert len(llamadas) == 1


CONTENIDO_19 = '{"modelo_ia": "gpt-4.1", "x": 1, "configuracion": {"salida": {"formato": "txt"}}}'


def _llamar_19(operacion, proyecto):
    from src import configuracion

    if operacion == "guardar_ajustes":
        return configuracion.guardar_ajustes(proyecto, {("salida", "formato"): "srt"})
    if operacion == "restablecer_ajustes":
        return configuracion.restablecer_ajustes()
    return configuracion.guardar_modelo_preferido("claude-haiku-5.5")


@pytest.mark.parametrize("operacion", ["guardar_ajustes", "restablecer_ajustes", "guardar_modelo_preferido"])
def test_fallo_de_lectura_no_borra_las_preferencias(tmp_path, monkeypatch, operacion):
    import errno
    from pathlib import Path

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, CONTENIDO_19)
    antes = ruta.read_bytes()
    original = Path.read_text

    def leer_denegado(self, *args, **kwargs):
        if self == configuracion.RUTA_PREFERENCIAS:
            raise PermissionError(errno.EACCES, "Permiso denegado", str(self))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", leer_denegado)
    llamadas = _contar_replace_19(monkeypatch)

    with pytest.raises(OSError):
        _llamar_19(operacion, _proyecto_19(tmp_path))

    assert ruta.read_bytes() == antes
    assert llamadas == []
    assert not ruta.with_name("preferencias.json.tmp").exists()


@pytest.mark.parametrize("fallo", ["temporal_a_medias", "renombrado"])
@pytest.mark.parametrize("operacion", ["guardar_ajustes", "restablecer_ajustes", "guardar_modelo_preferido"])
def test_fallo_al_escribir_no_toca_el_archivo_ni_deja_temporal(tmp_path, monkeypatch, operacion, fallo):
    import errno
    from pathlib import Path

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, CONTENIDO_19)
    antes = ruta.read_bytes()
    original_escribir = Path.write_text

    if fallo == "temporal_a_medias":
        def escribir_lleno(self, texto, *args, **kwargs):
            if self.name == "preferencias.json.tmp":
                original_escribir(self, texto[:len(texto) // 2], *args, **kwargs)
                raise OSError(errno.ENOSPC, "No queda espacio en el disco")
            return original_escribir(self, texto, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", escribir_lleno)
    else:
        def renombrar_fallido(origen, destino):
            raise OSError(errno.EIO, "Error de entrada/salida")

        monkeypatch.setattr(configuracion.os, "replace", renombrar_fallido)

    with pytest.raises(OSError):
        _llamar_19(operacion, _proyecto_19(tmp_path))

    assert ruta.read_bytes() == antes
    assert not ruta.with_name("preferencias.json.tmp").exists()


@pytest.mark.parametrize("contenido", ["{", "[]"])
def test_json_invalido_se_reemplaza_al_guardar(tmp_path, monkeypatch, contenido):
    import json

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, contenido)

    avisos = configuracion.guardar_ajustes(_proyecto_19(tmp_path), {("salida", "formato"): "srt"})

    assert json.loads(ruta.read_text(encoding="utf-8")) == {"configuracion": {"salida": {"formato": "srt"}}}
    assert avisos == []


def test_guardar_modelo_preferido_no_reescribe_si_no_puede_leer(tmp_path, monkeypatch):
    import errno
    from pathlib import Path

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, '{"x": 1, "configuracion": {"salida": {"formato": "srt"}}}')
    antes = ruta.read_bytes()
    original = Path.read_text

    def leer_denegado(self, *args, **kwargs):
        if self == configuracion.RUTA_PREFERENCIAS:
            raise PermissionError(errno.EACCES, "Permiso denegado", str(self))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", leer_denegado)

    with pytest.raises(OSError):
        configuracion.guardar_modelo_preferido("claude-haiku-5.5")

    assert ruta.read_bytes() == antes
    assert not ruta.with_name("preferencias.json.tmp").exists()


@pytest.mark.parametrize("configuracion_guardada, descartadas", [
    ({"ia": {"modelo": "gpt-4.1", "temperatura": 0.5}}, "`ia.modelo`"),
    ({"salida": 3, "transcripcion": {"best_of": 3}}, "`salida`"),
    (3, "`configuracion`"),
])
def test_guardar_ajustes_descarta_entradas_mal_formadas_sin_fallar(tmp_path, monkeypatch, configuracion_guardada,
                                                                    descartadas):
    import json

    from src import configuracion

    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, json.dumps({"x": 1, "configuracion": configuracion_guardada}))

    avisos = configuracion.guardar_ajustes(_proyecto_19(tmp_path), {("salida", "formato"): "srt"})

    guardado = json.loads(ruta.read_text(encoding="utf-8"))
    assert guardado["x"] == 1
    assert guardado["configuracion"]["salida"] == {"formato": "srt"}
    assert "modelo" not in guardado["configuracion"].get("ia", {})
    assert avisos == [f"Se descartaron de {ruta} claves que no sirven: {descartadas}."]


# --- Historia 20: componer el guardado y los valores laterales sin ventana ---

def test_claves_cambiadas_solo_las_de_la_tabla(tmp_path):
    import copy

    from src.configuracion import cargar_configuracion, claves_cambiadas

    ruta = tmp_path / "settings.yaml"
    ruta.write_text('salida:\n  formato: "txt"\n', encoding="utf-8")
    anterior = cargar_configuracion(ruta)
    nueva = copy.deepcopy(anterior)
    nueva["salida"]["formato"] = "srt"
    nueva["salida"]["extra"] = 1
    nueva["audio"] = {"a": 1}

    assert claves_cambiadas(anterior, nueva) == {("salida", "formato")}
    assert claves_cambiadas(anterior, copy.deepcopy(anterior)) == set()


def test_valores_laterales_solo_de_las_claves_cambiadas(tmp_path):
    import copy

    from src.configuracion import cargar_configuracion, valores_laterales

    ruta = tmp_path / "settings.yaml"
    ruta.write_text(
        'modelo:\n  nombre: "small"\n  dispositivo: "cuda"\n  compute_type: "float16"\n'
        'transcripcion:\n  idioma: "nl"\n  beam_size: 3\n'
        'salida:\n  formato: "srt"\n  incluir_timestamps: false\n',
        encoding="utf-8")
    configuracion = cargar_configuracion(ruta)
    idioma_nl = {("transcripcion", "idioma"), ("salida", "formato"), ("transcripcion", "beam_size")}

    assert valores_laterales(idioma_nl, configuracion) == {
        "var_idioma": "nl",
        "opciones_idioma": ["Auto-detectar", "Español", "Inglés", "Francés", "Alemán", "Italiano", "Portugués",
                            "Catalán", "Ruso", "Chino", "Japonés", "Coreano", "nl"],
        "var_formato": "srt",
    }

    directos = {("modelo", "nombre"), ("modelo", "dispositivo"), ("modelo", "compute_type"),
                ("salida", "formato"), ("salida", "incluir_timestamps")}
    assert valores_laterales(directos, configuracion) == {
        "var_modelo": "small", "var_dispositivo": "cuda", "var_compute": "float16", "var_formato": "srt",
        "var_timestamps": False,
    }

    es = copy.deepcopy(configuracion)
    es["transcripcion"]["idioma"] = "es"
    laterales_es = valores_laterales({("transcripcion", "idioma")}, es)
    assert laterales_es["var_idioma"] == "Español"
    assert "es" not in laterales_es["opciones_idioma"]


def test_guardar_formulario_con_errores_no_escribe(tmp_path, monkeypatch):
    from src.configuracion import combinar, guardar_formulario, leer_ajustes

    proyecto = _proyecto_19(tmp_path)
    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, '{"x": 1}')
    antes = ruta.read_bytes()
    anterior = combinar(proyecto, leer_ajustes())[0]

    resultado = guardar_formulario(proyecto, anterior, {
        ("transcripcion", "beam_size"): "cinco",
        ("salida", "formato"): "srt",
    })

    assert resultado.errores == {
        ("transcripcion", "beam_size"): "`transcripcion.beam_size` debe ser un número entero entre 1 y 20 "
                                        "(vale «cinco»).",
    }
    assert resultado.efectiva is None
    assert resultado.modelo_preferido is None
    assert resultado.avisos == []
    assert resultado.cambiadas == set()
    assert resultado.mensaje == "No se guardó nada: corrige 1 valor."
    assert ruta.read_bytes() == antes


def test_guardar_formulario_con_fallo_de_escritura_no_devuelve_efectiva(tmp_path, monkeypatch):
    import errno

    from src import configuracion
    from src.configuracion import combinar, guardar_formulario, leer_ajustes

    proyecto = _proyecto_19(tmp_path)
    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, '{"x": 1}')
    antes = ruta.read_bytes()
    anterior = combinar(proyecto, leer_ajustes())[0]

    def fallar(*args, **kwargs):
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(configuracion, "guardar_ajustes", fallar)

    resultado = guardar_formulario(proyecto, anterior, {("salida", "formato"): "srt"})

    assert resultado.errores == {}
    assert resultado.efectiva is None
    assert resultado.modelo_preferido is None
    assert resultado.cambiadas == set()
    assert resultado.mensaje == "No se pudo guardar la configuración: Permission denied."
    assert ruta.read_bytes() == antes


def test_guardar_formulario_devuelve_cambiadas_avisos_y_mensaje(tmp_path, monkeypatch):
    from src.configuracion import combinar, guardar_formulario, leer_ajustes

    proyecto = _proyecto_19(tmp_path)
    yaml = tmp_path / "settings.yaml"
    antes_yaml = (yaml.read_bytes(), yaml.stat().st_mtime_ns)
    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, "{")  # archivo ilegible: al abrir dio aviso
    historial = tmp_path / "historial.db"
    anterior = combinar(proyecto, leer_ajustes())[0]

    cambio_formato_y_ruta = guardar_formulario(proyecto, anterior, {
        ("salida", "formato"): "srt",
        ("historial", "ruta"): str(historial),
    })

    assert cambio_formato_y_ruta.efectiva["salida"]["formato"] == "srt"
    assert cambio_formato_y_ruta.efectiva["historial"]["ruta"] == str(historial)
    assert cambio_formato_y_ruta.cambiadas == {("salida", "formato"), ("historial", "ruta")}
    assert cambio_formato_y_ruta.avisos == []
    assert cambio_formato_y_ruta.modelo_preferido is None
    assert cambio_formato_y_ruta.mensaje == (
        "Configuración guardada · el historial nuevo se abrirá al reiniciar la app")

    solo_formato = guardar_formulario(proyecto, cambio_formato_y_ruta.efectiva, {
        ("salida", "formato"): "vtt",
        ("historial", "ruta"): str(historial),
    })

    assert solo_formato.cambiadas == {("salida", "formato")}
    assert solo_formato.mensaje == "Configuración guardada"

    con_modelo = guardar_formulario(proyecto, solo_formato.efectiva, {
        ("salida", "formato"): "vtt",
        ("historial", "ruta"): str(historial),
    }, modelo_ia="claude-sonnet-5.5", preferido_anterior=None)

    assert con_modelo.modelo_preferido == "claude-sonnet-5.5"
    assert con_modelo.cambiadas == {("ia", "modelo")}

    repetido = guardar_formulario(proyecto, con_modelo.efectiva, {
        ("salida", "formato"): "vtt",
        ("historial", "ruta"): str(historial),
    }, modelo_ia="claude-sonnet-5.5", preferido_anterior="claude-sonnet-5.5")

    assert repetido.cambiadas == set()
    assert (yaml.read_bytes(), yaml.stat().st_mtime_ns) == antes_yaml


# --- Historia 22 (C2): restablecer desde la vista, sin ventana ---

YAML_RESTABLECER_C2 = """\
salida:
  formato: "txt"
transcripcion:
  beam_size: 5
  no_speech_threshold: 0.6
ia:
  modelo: "claude-haiku-5.5"
historial:
  ruta: "data/historial.db"
"""


def test_restablecer_formulario_devuelve_el_yaml_y_sin_modelo(tmp_path, monkeypatch):
    """C2, criterio 3: restablecer borra «configuracion» y «modelo_ia», devuelve lo del YAML con su mensaje y deja el
    YAML intacto; con `historial.ruta` guardado el mensaje añade la nota de reinicio; sin nada guardado no cambia nada."""
    import json

    from src.configuracion import cargar_configuracion, combinar, leer_ajustes, restablecer_formulario

    yaml_ = tmp_path / "settings.yaml"
    yaml_.write_text(YAML_RESTABLECER_C2, encoding="utf-8")
    proyecto = cargar_configuracion(yaml_)
    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, json.dumps({
        "x": 1, "modelo_ia": "claude-sonnet-5.5",
        "configuracion": {"salida": {"formato": "srt"}, "transcripcion": {"beam_size": 50}},
    }))
    anterior, _ = combinar(proyecto, leer_ajustes())
    antes_yaml = (yaml_.read_bytes(), yaml_.stat().st_mtime_ns)

    resultado = restablecer_formulario(proyecto, anterior, "claude-sonnet-5.5")

    assert resultado.errores == {}
    assert resultado.efectiva == proyecto
    assert resultado.modelo_preferido is None
    assert resultado.avisos == []
    assert resultado.cambiadas == {("salida", "formato"), ("ia", "modelo")}
    assert resultado.mensaje == "Se restablecieron los valores de config/settings.yaml"
    assert json.loads(ruta.read_text(encoding="utf-8")) == {"x": 1}
    assert (yaml_.read_bytes(), yaml_.stat().st_mtime_ns) == antes_yaml

    ruta.write_text(json.dumps({"configuracion": {"historial": {"ruta": str(tmp_path / "otro.db")}}}),
                    encoding="utf-8")
    con_ruta, _ = combinar(proyecto, leer_ajustes())
    resultado = restablecer_formulario(proyecto, con_ruta, None)

    assert ("historial", "ruta") in resultado.cambiadas
    assert resultado.mensaje == ("Se restablecieron los valores de config/settings.yaml · el historial nuevo "
                                 "se abrirá al reiniciar la app")

    ruta.write_text("{}", encoding="utf-8")
    resultado = restablecer_formulario(proyecto, proyecto, None)

    assert resultado.cambiadas == set()


def test_restablecer_formulario_con_fallo_no_devuelve_efectiva(tmp_path, monkeypatch):
    """C2, criterio 3: si no se puede escribir, no hay configuración efectiva que aplicar; el archivo no cambia."""
    import errno
    import json

    from src import configuracion
    from src.configuracion import cargar_configuracion, restablecer_formulario

    yaml_ = tmp_path / "settings.yaml"
    yaml_.write_text(YAML_RESTABLECER_C2, encoding="utf-8")
    proyecto = cargar_configuracion(yaml_)
    ruta = _ruta_preferencias_19(monkeypatch, tmp_path, json.dumps({"modelo_ia": "claude-sonnet-5.5"}))
    antes = ruta.read_bytes()

    def fallar():
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(configuracion, "restablecer_ajustes", fallar)

    resultado = restablecer_formulario(proyecto, proyecto, "claude-sonnet-5.5")

    assert resultado.efectiva is None
    assert resultado.modelo_preferido is None
    assert resultado.cambiadas == set()
    assert resultado.mensaje == "No se pudo restablecer la configuración: Permission denied."
    assert ruta.read_bytes() == antes
