"""Documentos fuera de la ventana (historia 10): texto que se envía, ruta junto al audio y fecha de la reunión.
Sin ventana, sin red y sin modelo real."""

import os
import time

import pytest

from src import flujo_documentos as fd
from src.asistente_ia import ErrorAsistenteIA
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


class AsistenteFalso:
    """Doble del asistente: anota cada llamada, devuelve un documento o lanza lo que se le diga, y cambia su
    `modelo_usado` al generar, como hace el real en modo auto."""

    def __init__(self, devuelve="# Documento", lanza=None, modelo_tras_generar="auto → gpt-5.4"):
        self.modelo_usado = "auto"
        self.devuelve = devuelve
        self.lanza = lanza
        self.modelo_tras_generar = modelo_tras_generar
        self.llamadas = []

    def _generar(self, metodo, args, kwargs):
        self.llamadas.append((metodo, args, kwargs))
        if self.lanza is not None:
            raise self.lanza
        self.modelo_usado = self.modelo_tras_generar
        return self.devuelve

    def generar_resumen(self, texto, on_progreso=None, cancelar=None):
        return self._generar("generar_resumen", (texto,), {"on_progreso": on_progreso, "cancelar": cancelar})

    def generar_minuta(self, texto, on_progreso=None, cancelar=None, fecha=None):
        return self._generar("generar_minuta", (texto,),
                             {"on_progreso": on_progreso, "cancelar": cancelar, "fecha": fecha})


def test_generar_documento_minuta_pasa_fecha_senal_y_progreso():
    falso = AsistenteFalso(devuelve="# Minuta")
    generacion = fd.Generacion(clave="minuta", asistente=falso, texto="Hola equipo.\nCerramos el punto.",
                               fecha="5 de marzo de 2026 (fecha del archivo)", ruta_salida=None, id_historial=None)

    def progreso(mensaje):
        pass

    assert falso.modelo_usado == "auto"  # antes de generar
    documento = fd.generar_documento(generacion, progreso)

    assert len(falso.llamadas) == 1
    metodo, args, kwargs = falso.llamadas[0]
    assert metodo == "generar_minuta"
    assert args == ("Hola equipo.\nCerramos el punto.",)
    assert kwargs["fecha"] == "5 de marzo de 2026 (fecha del archivo)"
    assert kwargs["on_progreso"] is progreso
    assert kwargs["cancelar"] is generacion.cancelar
    assert documento.contenido == "# Minuta"
    assert documento.modelo_usado == "auto → gpt-5.4"
    assert documento.segundos >= 0


def test_generar_documento_resumen_sin_fecha():
    falso = AsistenteFalso(devuelve="# Resumen")
    generacion = fd.Generacion(clave="resumen", asistente=falso, texto="Hola equipo.", fecha=None,
                               ruta_salida=None, id_historial=None)

    documento = fd.generar_documento(generacion)

    assert len(falso.llamadas) == 1
    metodo, args, kwargs = falso.llamadas[0]
    assert metodo == "generar_resumen"
    assert args == ("Hola equipo.",)
    assert "fecha" not in kwargs
    assert documento.contenido == "# Resumen"


@pytest.mark.parametrize("lanza", [None, ErrorAsistenteIA("sin cuota"), InterruptedError(), ValueError("mal formato")])
def test_procesar_generacion_entrega_una_vez(lanza):
    falso = AsistenteFalso(devuelve="# Resumen", lanza=lanza)
    generacion = fd.Generacion(clave="resumen", asistente=falso, texto="Hola.", fecha=None,
                               ruta_salida=None, id_historial=None)
    entregas = []

    def entregar(g, documento, error):
        entregas.append((g, documento, error))

    fd.procesar_generacion(generacion, lambda mensaje: None, entregar)

    assert len(entregas) == 1
    g, documento, error = entregas[0]
    assert g is generacion
    if lanza is None:
        assert documento.contenido == "# Resumen"
        assert error is None
    else:
        assert documento is None
        assert error is lanza


@pytest.mark.parametrize("lanza", [None, ErrorAsistenteIA("sin cuota")])
def test_procesar_generacion_entregar_que_lanza_no_reentrega(lanza):
    falso = AsistenteFalso(devuelve="# Resumen", lanza=lanza)
    generacion = fd.Generacion(clave="resumen", asistente=falso, texto="Hola.", fecha=None,
                               ruta_salida=None, id_historial=None)
    entregas = []

    def entregar(g, documento, error):
        entregas.append((g, documento, error))
        raise RuntimeError("la ventana ya no existe")

    with pytest.raises(RuntimeError):
        fd.procesar_generacion(generacion, lambda mensaje: None, entregar)

    assert len(entregas) == 1


def test_cada_generacion_tiene_su_propia_senal():
    falso = AsistenteFalso()
    datos = dict(clave="minuta", asistente=falso, texto="Hola equipo.\nCerramos el punto.",
                 fecha="5 de marzo de 2026 (fecha del archivo)", ruta_salida=None, id_historial=None)
    primera = fd.Generacion(**datos)
    segunda = fd.Generacion(**datos)

    primera.cancelar.set()

    assert segunda.cancelar.is_set() is False
    assert primera is not segunda
