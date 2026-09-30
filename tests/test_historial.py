"""Tests del historial en SQLite."""

import pytest
from src.historial import Historial, titulo_desde_minuta
from src.transcriber import ResultadoTranscripcion, SegmentoTranscripcion


@pytest.fixture
def historial(tmp_path):
    return Historial(str(tmp_path / "historial.db"))


def _resultado(texto="Hola mundo. Segunda frase."):
    return ResultadoTranscripcion(
        texto_completo=texto,
        segmentos=[SegmentoTranscripcion(0.0, 2.0, "Hola mundo."), SegmentoTranscripcion(2.0, 4.5, "Segunda frase.")],
        idioma_detectado="es",
        probabilidad_idioma=0.98,
        duracion_total=4.5,
    )


def test_crear_y_obtener(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "reunion_lunes.mp3"), _resultado(), modelo_whisper="base")
    entrada = historial.obtener(id_)
    assert entrada.titulo == "reunion_lunes"            # título por defecto: nombre sin extensión
    assert entrada.archivo_nombre == "reunion_lunes.mp3"
    assert entrada.modelo_whisper == "base"
    assert not entrada.tiene_resumen and not entrada.tiene_minuta
    resultado = entrada.a_resultado()
    assert [s.texto for s in resultado.segmentos] == ["Hola mundo.", "Segunda frase."]
    assert resultado.duracion_total == 4.5


def test_guardar_resumen_y_minuta(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "a.wav"), _resultado())
    historial.guardar_documento(id_, "resumen", "## Resumen\ntexto", modelo="gpt-5.4")
    historial.guardar_documento(id_, "minuta", "# Minuta: Revisión de lanzamiento\n...", modelo="gpt-5.4")
    entrada = historial.obtener(id_)
    assert entrada.resumen.startswith("## Resumen") and entrada.resumen_modelo == "gpt-5.4"
    assert entrada.tiene_minuta
    assert entrada.titulo == "Revisión de lanzamiento"   # tomado de la minuta


def test_titulo_editado_no_se_sobrescribe_con_la_minuta(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "a.wav"), _resultado())
    historial.renombrar(id_, "Mi título")
    historial.guardar_documento(id_, "minuta", "# Minuta: Otro título\n")
    assert historial.obtener(id_).titulo == "Mi título"


def test_renombrar_vacio_falla(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "a.wav"), _resultado())
    with pytest.raises(ValueError):
        historial.renombrar(id_, "   ")


def test_listar_ordena_y_busca(historial, tmp_path):
    id1 = historial.crear(str(tmp_path / "uno.wav"), _resultado("presupuesto de servidores"))
    id2 = historial.crear(str(tmp_path / "dos.wav"), _resultado("pruebas de usabilidad"))
    historial.guardar_documento(id1, "resumen", "Se habló del 50% de avance")
    assert [e.id for e in historial.listar()] == [id2, id1]          # más reciente primero
    assert [e.id for e in historial.listar("usabilidad")] == [id2]   # busca en el texto
    assert [e.id for e in historial.listar("DOS")] == [id2]          # archivo, sin distinguir mayúsculas
    assert [e.id for e in historial.listar("50%")] == [id1]          # el % se busca literal
    assert historial.listar("100%") == []
    assert historial.listar()[1].tiene_resumen


def test_busqueda_ignora_acentos_y_mayusculas(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "a.wav"), _resultado("Reunión de planeación"))
    historial.renombrar(id_, "Revisión TÉCNICA")
    for consulta in ("reunion", "REUNIÓN", "planeacion", "revision tecnica", "técnica"):
        assert [e.id for e in historial.listar(consulta)] == [id_], consulta


def test_eliminar(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "a.wav"), _resultado())
    historial.eliminar(id_)
    assert historial.obtener(id_) is None
    assert historial.listar() == []


def test_persistencia_entre_instancias(tmp_path):
    ruta = str(tmp_path / "h.db")
    id_ = Historial(ruta).crear(str(tmp_path / "a.wav"), _resultado())
    assert Historial(ruta).obtener(id_).texto == "Hola mundo. Segunda frase."


def test_titulo_desde_minuta():
    assert titulo_desde_minuta("# Minuta: **Revisión** \n## Objetivo") == "Revisión"
    assert titulo_desde_minuta("## Resumen") is None
