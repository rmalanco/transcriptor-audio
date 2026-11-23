"""Documentos fuera de la ventana (historia 10): texto que se envía, ruta junto al audio y fecha de la reunión.
Sin ventana, sin red y sin modelo real."""

import json
import os
import re
import threading
import time

import pytest

from src import asistente_ia, copilot
from src import flujo_documentos as fd
from src.asistente_ia import (SECCIONES_MINUTA, SECCIONES_RESUMEN, AsistenteIA, ErrorAsistenteIA, ErrorModeloIA,
                             ErrorSinSesionCopilot, dividir_texto)
from src.historial import Historial
from src.persistencia import persistir_documento
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

def _prohibido(*a, **kw):
    raise AssertionError("no debe haber ninguna petición de catálogo ni de sesión")


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
        "recibir": lambda: gestor.recibir(vigente, None, None),
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


# ---- Recepcion y GestorDocumentos.recibir (historia 14)

@pytest.fixture
def historial(tmp_path):
    return Historial(str(tmp_path / "historial.db"))


def test_recibir_vigente_guarda_y_devuelve_lista(historial, tmp_path):
    audio = _audio(tmp_path)
    id_ = historial.crear(audio, _resultado_reunion())
    gestor = fd.GestorDocumentos(historial, FabricaAsistentes())
    generacion = gestor.iniciar("minuta", _resultado_reunion(), audio, id_, None)
    documento = fd.DocumentoGenerado("# Minuta: Revisión de lanzamiento\n\n## Objetivo\nRevisar.", "gpt-5.4", 1.5)

    recepcion = gestor.recibir(generacion, documento, None)

    assert recepcion.estado == "lista"
    assert recepcion.documento is documento
    assert recepcion.persistencia.motivo_historial is None
    assert recepcion.persistencia.motivo_exportacion is None
    entrada = historial.obtener(id_)
    assert entrada.minuta == documento.contenido
    assert entrada.minuta_modelo == "gpt-5.4"
    assert entrada.titulo == "Revisión de lanzamiento"
    archivo = tmp_path / "reunion.m4a_minuta.md"
    assert archivo.read_text(encoding="utf-8") == documento.contenido + "\n"
    assert recepcion.persistencia.ruta_exportada == str(archivo)
    assert recepcion.persistencia.id_historial == id_
    assert gestor.vigente is None


def test_recibir_entrada_eliminada_exporta_y_avisa(historial, tmp_path):
    audio = _audio(tmp_path)
    id_ = historial.crear(audio, _resultado_reunion())
    gestor = fd.GestorDocumentos(historial, FabricaAsistentes())
    generacion = gestor.iniciar("minuta", _resultado_reunion(), audio, id_, None)
    historial.eliminar(id_)
    documento = fd.DocumentoGenerado("# Minuta: Revisión de lanzamiento", "gpt-5.4", 1.5)

    recepcion = gestor.recibir(generacion, documento, None)

    assert recepcion.estado == "lista"
    assert recepcion.persistencia.motivo_historial == "La entrada ya no está en el historial"
    assert recepcion.persistencia.id_historial is None
    archivo = tmp_path / "reunion.m4a_minuta.md"
    assert archivo.read_text(encoding="utf-8") == documento.contenido + "\n"
    assert recepcion.persistencia.ruta_exportada == str(archivo)
    assert gestor.vigente is None


def test_recibir_sin_audio_solo_historial(historial, tmp_path):
    audio = str(tmp_path / "reunion.m4a")  # no existe: la generación no tiene ruta junto al audio
    id_ = historial.crear(audio, _resultado_reunion())
    gestor = fd.GestorDocumentos(historial, FabricaAsistentes())
    generacion = gestor.iniciar("minuta", _resultado_reunion(), audio, id_, "2026-04-07T10:00:00")
    documento = fd.DocumentoGenerado("# Minuta: Revisión de lanzamiento", "gpt-5.4", 1.5)

    recepcion = gestor.recibir(generacion, documento, None)

    assert recepcion.estado == "lista"
    assert historial.obtener(id_).minuta == documento.contenido
    assert recepcion.persistencia.ruta_exportada is None
    assert recepcion.persistencia.motivo_exportacion is None
    assert not list(tmp_path.glob("*.md"))


@pytest.mark.parametrize("documento, error", [
    (fd.DocumentoGenerado("# Minuta nueva", "gpt-5.4", 1.0), None),
    (None, ErrorAsistenteIA("sin cuota")),
    (None, ErrorSinSesionCopilot("sin sesión de Copilot")),
], ids=["documento", "error", "sin_sesion"])
def test_recibir_cancelada_descarta_sin_guardar_ni_olvidar(historial, tmp_path, documento, error):
    audio = _audio(tmp_path)
    id_ = historial.crear(audio, _resultado_reunion())
    ruta = tmp_path / "reunion.m4a_minuta.md"
    persistir_documento(historial, id_, "minuta", "# Minuta anterior", "gpt-4.1", str(ruta))
    os.utime(ruta, (MARZO_5, MARZO_5))  # una fecha pasada: si se reescribe, el mtime cambia
    antes = ruta.stat().st_mtime
    fabrica = FabricaAsistentes()
    gestor = fd.GestorDocumentos(historial, fabrica)
    cancelada = gestor.iniciar("minuta", _resultado_reunion(), audio, id_, None)
    gestor.cancelar()
    vigente = gestor.iniciar("minuta", _resultado_reunion(), audio, id_, None)

    recepcion = gestor.recibir(cancelada, documento, error)

    assert recepcion.estado == "descartada"
    assert recepcion.persistencia is None
    assert recepcion.documento is None
    entrada = historial.obtener(id_)
    assert entrada.minuta == "# Minuta anterior"
    assert entrada.minuta_modelo == "gpt-4.1"
    assert ruta.read_text(encoding="utf-8") == "# Minuta anterior\n"
    assert ruta.stat().st_mtime == antes
    assert gestor.vigente is vigente
    assert gestor.asistente() is vigente.asistente
    assert fabrica.llamadas == 2


def test_recibir_sin_sesion_vigente_olvida_el_asistente(historial, tmp_path):
    audio = _audio(tmp_path)
    fabrica = FabricaAsistentes()
    gestor = fd.GestorDocumentos(historial, fabrica)
    generacion = gestor.iniciar("minuta", _resultado_reunion(), audio, None, None)
    asistente_anterior = generacion.asistente
    error = ErrorSinSesionCopilot("sin sesión de Copilot")

    recepcion = gestor.recibir(generacion, None, error)

    assert recepcion.estado == "sin_sesion"
    assert recepcion.mensaje == str(error)
    assert gestor.vigente is None
    siguiente = gestor.iniciar("resumen", _resultado_reunion(), audio, None, None)
    assert siguiente.asistente is not asistente_anterior
    assert fabrica.llamadas == 2


@pytest.mark.parametrize("error, mensaje", [(ErrorAsistenteIA(""), "ErrorAsistenteIA"),
                                             (InterruptedError(), "InterruptedError")])
def test_recibir_error_sin_texto_usa_el_nombre_del_error(historial, tmp_path, error, mensaje):
    gestor = fd.GestorDocumentos(historial, FabricaAsistentes())
    generacion = gestor.iniciar("minuta", _resultado_reunion(), _audio(tmp_path), None, None)

    recepcion = gestor.recibir(generacion, None, error)

    assert recepcion.estado == "error"
    assert recepcion.mensaje == mensaje


# ---- Fallo de una parte con AsistenteIA real (httpx simulado, sin red)

DOCUMENTO_COMPLETO = "\n\n".join(f"{seccion}\nContenido." for seccion in SECCIONES_RESUMEN + SECCIONES_MINUTA)


@pytest.fixture(autouse=True)
def rutas_aisladas(monkeypatch, tmp_path):
    """Como el fixture homónimo de test_copilot.py: el token real del equipo nunca se lee ni se toca."""
    monkeypatch.setattr(copilot, "RUTA_TOKEN", tmp_path / "app" / "copilot.json")
    monkeypatch.setattr(copilot, "RUTA_AUTH_OPENCODE", tmp_path / "opencode" / "auth.json")
    monkeypatch.delenv(copilot.VARIABLE_ENTORNO, raising=False)


class _StreamFalso:
    """Respuesta de chat simulada: con `status_code` distinto de 200 es un error; si no, devuelve `contenido`."""
    def __init__(self, status_code=200, contenido=""):
        self.status_code, self.text, self.headers = status_code, "sin permiso" if status_code >= 400 else "", {}
        self._contenido = contenido

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        pass

    def iter_lines(self):
        yield "data: " + json.dumps({"choices": [{"delta": {"content": self._contenido}, "finish_reason": "stop"}]})
        yield "data: [DONE]"


def _numero_de_parte(cuerpo):
    """Número de parte de una petición de notas, o None si es otra petición (la redacción)."""
    coincidencia = re.search(r"Esta es la parte (\d+) de", cuerpo["messages"][-1]["content"])
    return int(coincidencia.group(1)) if coincidencia else None


def _numeros_de_nota(cuerpos):
    return [n for n in (_numero_de_parte(c) for c in cuerpos) if n is not None]


def test_fallo_de_una_parte_reutiliza_notas_y_cancelar_las_pierde(historial, tmp_path, monkeypatch):
    lineas = [f"Segmento {i:03d} con algo de contenido." for i in range(60)]
    resultado = ResultadoTranscripcion(
        texto_completo="\n".join(lineas),
        segmentos=[SegmentoTranscripcion(float(i), i + 1.0, linea) for i, linea in enumerate(lineas)],
        idioma_detectado="es", probabilidad_idioma=1.0, duracion_total=60.0)
    partes = dividir_texto("\n".join(lineas), 300)
    total = len(partes)
    assert total >= 3
    audio = _audio(tmp_path)
    id_ = historial.crear(audio, resultado)

    fallar = {"activo": True}  # la parte 2 recibe un 403 mientras esté activo
    cuerpos = []

    def stream(metodo, url, json, headers, timeout):
        cuerpos.append(json)
        contenido = json["messages"][-1]["content"]
        if _numero_de_parte(json) is None:
            return _StreamFalso(200, DOCUMENTO_COMPLETO)
        if fallar["activo"] and partes[1] in contenido:
            return _StreamFalso(403)
        return _StreamFalso(200, f"- Nota de la parte {_numero_de_parte(json)}")

    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    monkeypatch.setattr(asistente_ia.httpx, "get", _prohibido)
    monkeypatch.setattr(asistente_ia.httpx, "post", _prohibido)

    creados = []

    def crear_asistente():
        creados.append(AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=300,
                                   revision_fidelidad=False, peticiones_paralelas=1))
        return creados[-1]

    gestor = fd.GestorDocumentos(historial, crear_asistente)

    def ejecutar(generacion):
        """Como el hilo de fondo: genera y entrega en este hilo; después pasa el resultado a `recibir`."""
        entregas = []
        fd.procesar_generacion(generacion, lambda mensaje: None, lambda g, d, e: entregas.append((g, d, e)))
        (g, documento, error), = entregas
        return gestor.recibir(g, documento, error)

    # 1. La minuta falla en la parte 2: «error» con el mensaje del asistente
    recepcion = ejecutar(gestor.iniciar("minuta", resultado, audio, id_, None))
    assert recepcion.estado == "error"
    assert recepcion.mensaje.startswith(f"falló la parte 2 de {total}: ")

    # 2. El otro documento reutiliza las notas que terminaron: solo se piden las partes que faltan y la redacción
    fallar["activo"] = False
    cuerpos.clear()
    recepcion = ejecutar(gestor.iniciar("resumen", resultado, audio, id_, None))
    assert recepcion.estado == "lista"
    assert sorted(_numeros_de_nota(cuerpos)) == list(range(2, total + 1))
    assert len([c for c in cuerpos if _numero_de_parte(c) is None]) == 1

    # 3. Tras cancelar, la siguiente generación vuelve a pedir todas las partes con un asistente nuevo
    gestor.iniciar("resumen", resultado, audio, id_, None)
    gestor.cancelar()
    cuerpos.clear()
    ejecutar(gestor.iniciar("minuta", resultado, audio, id_, None))
    assert len(creados) == 2
    assert sorted(_numeros_de_nota(cuerpos)) == list(range(1, total + 1))


# ---- Argumentos del asistente desde la configuración (historia D1 de 06-panel-de-configuracion)

def _configuracion_base():
    import copy

    from src.configuracion import cargar_configuracion
    return copy.deepcopy(cargar_configuracion())


def test_argumentos_asistente_salen_de_la_configuracion():
    """D1, criterio 1: el asistente se crea con los valores de `ia`; un dominio vacío da `enterprise_url` None."""
    cfg = {"ia": {"copilot_enterprise_url": "", "revision_fidelidad": True, "temperatura": 0.5,
                  "max_caracteres_bloque": 60000, "peticiones_paralelas": 2}}

    assert fd.argumentos_asistente(cfg, "claude-haiku-5.5") == {
        "modelo": "claude-haiku-5.5", "temperatura": 0.5, "max_caracteres_bloque": 60000,
        "revision_fidelidad": True, "peticiones_paralelas": 2, "enterprise_url": None,
    }
    cfg["ia"]["copilot_enterprise_url"] = "empresa.ghe.com"
    assert fd.argumentos_asistente(cfg, "claude-haiku-5.5")["enterprise_url"] == "empresa.ghe.com"


@pytest.mark.parametrize("seccion,clave,valor,argumento", [
    ("ia", "temperatura", 0.5, "temperatura"),
    ("ia", "max_caracteres_bloque", 30000, "max_caracteres_bloque"),
    ("ia", "peticiones_paralelas", 2, "peticiones_paralelas"),
    ("ia", "revision_fidelidad", True, "revision_fidelidad"),
    ("ia", "copilot_enterprise_url", "empresa.ghe.com", "enterprise_url"),
    ("modelo", None, "claude-sonnet-5.5", "modelo"),  # el modelo no está en la configuración: llega como argumento
    ("salida", "formato", "srt", None),  # lo que no es de IA no cambia ningún argumento
    ("transcripcion", "beam_size", 3, None),
    ("historial", "ruta", "otra/historial.db", None),
])
def test_argumentos_asistente_solo_cambian_con_la_ia(seccion, clave, valor, argumento):
    """D1, criterio 2: cambiar una clave de IA (o el modelo) cambia solo su argumento; cambiar lo que no es de IA no
    cambia ninguno, y el asistente no se olvida por ello."""
    antes = _configuracion_base()
    despues = _configuracion_base()
    modelo_despues = "claude-haiku-5.5"
    if seccion == "modelo":
        modelo_despues = valor
    else:
        despues[seccion][clave] = valor

    a = fd.argumentos_asistente(antes, "claude-haiku-5.5")
    d = fd.argumentos_asistente(despues, modelo_despues)

    assert {k for k in a if a[k] != d[k]} == ({argumento} if argumento else set())
