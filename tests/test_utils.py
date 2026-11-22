"""Tests de `src/utils.py`: metadatos de archivo y extensiones admitidas."""

import ffmpeg
import pytest

from src import utils
from src.utils import obtener_info_archivo


@pytest.fixture
def archivo_audio(tmp_path):
    ruta = tmp_path / "reunion.m4a"
    ruta.write_bytes(b"\x00" * 1234)
    return ruta


def test_info_de_archivo_sin_ffprobe_devuelve_el_tamano_y_sin_duracion(archivo_audio, monkeypatch):
    def ffprobe_ausente(*args, **kwargs):
        # Es lo que lanza `subprocess.Popen` dentro de `ffmpeg.probe` cuando el binario no está en el PATH.
        raise FileNotFoundError(2, "No such file or directory: 'ffprobe'")

    monkeypatch.setattr(utils.ffmpeg, "probe", ffprobe_ausente)

    info = obtener_info_archivo(str(archivo_audio))

    assert info.nombre == "reunion"
    assert info.extension == ".m4a"
    assert info.tamaño_bytes == 1234
    assert info.duracion_segundos is None
    assert info.codec_audio is None
    assert info.es_video is False


def test_info_de_archivo_con_ffprobe_que_falla_no_lanza(archivo_audio, monkeypatch):
    def ffprobe_error(*args, **kwargs):
        raise ffmpeg.Error("ffprobe", b"", b"Invalid data found when processing input")

    monkeypatch.setattr(utils.ffmpeg, "probe", ffprobe_error)

    info = obtener_info_archivo(str(archivo_audio))

    assert info.duracion_segundos is None
    assert info.tamaño_bytes == 1234


def test_el_dialogo_y_la_validacion_usan_las_mismas_extensiones(tmp_path):
    from src.utils import EXTENSIONES_AUDIO, EXTENSIONES_VIDEO, filtros_seleccion_archivo, validar_archivo

    multimedia, audio, video, _todos = filtros_seleccion_archivo()

    def extensiones(filtro):
        return {patron[1:] for patron in filtro[1].split()}

    assert extensiones(multimedia) == EXTENSIONES_AUDIO | EXTENSIONES_VIDEO
    assert extensiones(audio) == EXTENSIONES_AUDIO
    assert extensiones(video) == EXTENSIONES_VIDEO
    for ext in extensiones(multimedia):
        muestra = tmp_path / f"muestra{ext}"
        muestra.write_bytes(b"x")
        assert validar_archivo(str(muestra)) is True


def test_formatear_duracion_corta_legible():
    from src.utils import formatear_duracion

    assert formatear_duracion(0) == "00:00"
    assert formatear_duracion(309) == "05:09"
    assert formatear_duracion(3909.7) == "1:05:09"
    assert formatear_duracion(-4) == "00:00"


@pytest.mark.parametrize("formato", ["txt", "srt", "vtt", "json"])
def test_serializar_y_guardar_escriben_lo_mismo(formato, tmp_path):
    from src.transcriber import ResultadoTranscripcion, SegmentoTranscripcion
    from src.utils import serializar_transcripcion

    resultado = ResultadoTranscripcion(
        texto_completo="Hola equipo. Cerramos el punto.",
        segmentos=[
            SegmentoTranscripcion(0.0, 2.0, "Hola equipo."),
            SegmentoTranscripcion(3.0, 5.0, "Cerramos el punto.",
                                  palabras=[{"inicio": 3.0, "fin": 3.5, "palabra": "Cerramos"}]),
        ],
        idioma_detectado="es",
        probabilidad_idioma=0.98,
        duracion_total=5.0,
    )
    ruta = tmp_path / f"salida.{formato}"

    utils.guardar_transcripcion(resultado, str(ruta), formato=formato, incluir_timestamps=True)

    assert ruta.read_text(encoding="utf-8") == serializar_transcripcion(resultado, formato, True)
