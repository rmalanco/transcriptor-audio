"""Documentos fuera de la ventana (historia 10): texto que se envía, ruta junto al audio y fecha de la reunión.
Sin ventana, sin red y sin modelo real."""

import os
import time

import pytest

from src import flujo_documentos as fd
from src.transcriber import ResultadoTranscripcion, SegmentoTranscripcion


def test_texto_para_ia_une_segmentos_con_salto_de_linea():
    resultado = ResultadoTranscripcion(
        texto_completo="otra cosa",
        segmentos=[SegmentoTranscripcion(0.0, 1.0, "Hola equipo."), SegmentoTranscripcion(1.0, 2.0, "Cerramos el punto.")],
        idioma_detectado="es",
        probabilidad_idioma=1.0,
        duracion_total=2.0,
    )

    assert fd.texto_para_ia(resultado) == "Hola equipo.\nCerramos el punto."


def test_ruta_documento_conserva_la_extension_y_es_none_sin_audio(tmp_path):
    audio = tmp_path / "reunion.m4a"
    audio.touch()

    assert fd.ruta_documento(str(audio), "minuta") == str(tmp_path / "reunion.m4a_minuta.md")
    assert fd.ruta_documento(str(audio), "resumen") == str(tmp_path / "reunion.m4a_resumen.md")
    sin_audio = str(tmp_path / "no-existe.m4a")
    assert fd.ruta_documento(sin_audio, "minuta") is None
    assert fd.ruta_documento(sin_audio, "resumen") is None


# Mediodía local: la zona horaria del equipo no cambia el día.
MARZO_5 = time.mktime((2026, 3, 5, 12, 0, 0, 0, 0, -1))


@pytest.mark.parametrize("con_audio, fecha_historial, fallo_de_disco, esperado", [
    (True, None, False, "5 de marzo de 2026 (fecha del archivo)"),
    (False, "2026-04-07T10:00:00", False, "7 de abril de 2026 (fecha de transcripción)"),
    (False, None, False, "No especificada"),
    (False, "ayer", False, "No especificada"),
    (True, None, True, "No especificada"),
])
def test_fecha_de_la_reunion_desde_archivo_historial_o_ninguna(
        tmp_path, monkeypatch, con_audio, fecha_historial, fallo_de_disco, esperado):
    audio = tmp_path / "reunion.m4a"
    if con_audio:
        audio.touch()
        os.utime(audio, (MARZO_5, MARZO_5))
    if fallo_de_disco:
        def getmtime_roto(ruta):
            raise OSError("el disco ya no responde")
        monkeypatch.setattr(os.path, "getmtime", getmtime_roto)

    assert fd.fecha_de_la_reunion(str(audio), fecha_historial) == esperado
