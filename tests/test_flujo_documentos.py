"""Documentos fuera de la ventana (historia 10): texto que se envía, ruta junto al audio y fecha de la reunión.
Sin ventana, sin red y sin modelo real."""

import os
import threading
import time

import pytest

from src import flujo_documentos as fd
from src.asistente_ia import ErrorAsistenteIA, ErrorModeloIA, ErrorSinSesionCopilot
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


# ---- GestorDocumentos (historia 13)

class FabricaAsistentes:
    """Hace de `crear_asistente`: cuenta sus llamadas, devuelve un AsistenteFalso nuevo o lanza lo que se le diga."""

    def __init__(self, lanza=None):
        self.lanza = lanza
        self.llamadas = 0

    def __call__(self):
        self.llamadas += 1
        if self.lanza is not None:
            raise self.lanza
        return AsistenteFalso()


def _resultado_reunion():
    return ResultadoTranscripcion(
        texto_completo="Hola equipo. Cerramos el punto.",
        segmentos=[SegmentoTranscripcion(0.0, 1.0, "Hola equipo."), SegmentoTranscripcion(1.0, 2.0, "Cerramos el punto.")],
        idioma_detectado="es",
        probabilidad_idioma=1.0,
        duracion_total=2.0,
    )


def _audio(tmp_path):
    audio = tmp_path / "reunion.m4a"
    audio.touch()
    os.utime(audio, (MARZO_5, MARZO_5))
    return str(audio)


def test_gestor_reutiliza_el_asistente_entre_generaciones(tmp_path):
    fabrica = FabricaAsistentes()
    gestor = fd.GestorDocumentos(None, fabrica)
    audio = _audio(tmp_path)

    minuta = gestor.iniciar("minuta", _resultado_reunion(), audio, 7, None)
    assert gestor.terminar(minuta) is True
    assert gestor.vigente is None
    resumen = gestor.iniciar("resumen", _resultado_reunion(), audio, 7, None)

    assert minuta.asistente is resumen.asistente
    assert fabrica.llamadas == 1
    assert minuta.clave == "minuta" and resumen.clave == "resumen"
    assert minuta.texto == resumen.texto == "Hola equipo.\nCerramos el punto."
    assert minuta.ruta_salida == str(tmp_path / "reunion.m4a_minuta.md")
    assert resumen.ruta_salida == str(tmp_path / "reunion.m4a_resumen.md")
    assert minuta.id_historial == resumen.id_historial == 7
    assert minuta.fecha == "5 de marzo de 2026 (fecha del archivo)"
    assert resumen.fecha is None


@pytest.mark.parametrize("via", ["cancelar", "olvidar"])
def test_gestor_recrea_el_asistente_tras_cancelar_u_olvidar(tmp_path, via):
    fabrica = FabricaAsistentes()
    gestor = fd.GestorDocumentos(None, fabrica)
    audio = _audio(tmp_path)
    primera = gestor.iniciar("minuta", _resultado_reunion(), audio, None, None)
    asistente_anterior = primera.asistente

    if via == "cancelar":
        gestor.cancelar()
    else:
        gestor.terminar(primera)
        gestor.olvidar_asistente()
    segunda = gestor.iniciar("resumen", _resultado_reunion(), audio, None, None)

    assert segunda.asistente is not asistente_anterior
    assert fabrica.llamadas == 2


@pytest.mark.parametrize("error", [ErrorSinSesionCopilot("sin sesión de Copilot"), ErrorModeloIA("modelo no válido")])
def test_iniciar_sin_asistente_no_deja_vigente(tmp_path, error):
    fabrica = FabricaAsistentes(lanza=error)
    gestor = fd.GestorDocumentos(None, fabrica)
    audio = _audio(tmp_path)

    with pytest.raises(type(error)) as info:
        gestor.iniciar("minuta", _resultado_reunion(), audio, None, None)
    assert info.value is error
    assert gestor.vigente is None

    fabrica.lanza = None
    gestor.iniciar("minuta", _resultado_reunion(), audio, None, None)
    assert fabrica.llamadas == 2


def test_iniciar_con_otra_vigente_lanza_value_error(tmp_path):
    fabrica = FabricaAsistentes()
    gestor = fd.GestorDocumentos(None, fabrica)
    audio = _audio(tmp_path)
    primera = gestor.iniciar("minuta", _resultado_reunion(), audio, None, None)

    with pytest.raises(ValueError):
        gestor.iniciar("resumen", _resultado_reunion(), audio, None, None)

    assert gestor.vigente is primera
    assert fabrica.llamadas == 1


def test_cancelar_devuelve_la_cancelada_y_libera(tmp_path):
    fabrica = FabricaAsistentes()
    gestor = fd.GestorDocumentos(None, fabrica)
    audio = _audio(tmp_path)

    assert gestor.cancelar() is None
    assert fabrica.llamadas == 0

    primera = gestor.iniciar("minuta", _resultado_reunion(), audio, None, None)
    assert gestor.cancelar() is primera
    assert primera.cancelar.is_set()
    assert gestor.vigente is None

    segunda = gestor.iniciar("resumen", _resultado_reunion(), audio, None, None)
    assert gestor.terminar(primera) is False
    assert gestor.vigente is segunda
    assert gestor.asistente() is segunda.asistente
    assert fabrica.llamadas == 2


def test_gestor_desde_otro_hilo_lanza_runtime_error(tmp_path):
    fabrica = FabricaAsistentes()
    gestor = fd.GestorDocumentos(None, fabrica)
    audio = _audio(tmp_path)
    vigente = gestor.iniciar("minuta", _resultado_reunion(), audio, None, None)
    llamadas_iniciales = fabrica.llamadas
    metodos = {
        "cancelar": gestor.cancelar,
        "iniciar": lambda: gestor.iniciar("resumen", _resultado_reunion(), audio, None, None),
        "terminar": lambda: gestor.terminar(vigente),
        "asistente": gestor.asistente,
        "olvidar_asistente": gestor.olvidar_asistente,
    }
    errores = {}

    def llamar_todos():
        for nombre, metodo in metodos.items():
            try:
                metodo()
            except Exception as e:
                errores[nombre] = e

    hilo = threading.Thread(target=llamar_todos)
    hilo.start()
    hilo.join()

    assert set(errores) == set(metodos)
    assert all(isinstance(e, RuntimeError) for e in errores.values())
    assert gestor.vigente is vigente
    assert vigente.cancelar.is_set() is False
    assert fabrica.llamadas == llamadas_iniciales


def test_terminar_sin_generacion_no_da_por_terminada_ninguna():
    gestor = fd.GestorDocumentos(None, lambda: object())
    assert gestor.terminar(None) is False
