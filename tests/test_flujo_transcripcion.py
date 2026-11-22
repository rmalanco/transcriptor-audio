"""Flujo de la transcripción sin interfaz (historia 09). Sin ventana, sin red y sin modelo real."""

import threading
from pathlib import Path

import pytest

from src.configuracion import cargar_configuracion
from src.flujo_transcripcion import (FASE_CARGANDO_MODELO, FASE_TRANSCRIBIENDO, OpcionesTranscripcion,
                                     ruta_transcripcion, transcribir, transcribir_y_persistir, transcriptor_para)
from src.historial import Historial
from src.persistencia import texto_sin_guardado
from src.transcriber import TranscriptorAudio


@pytest.fixture
def historial(tmp_path):
    return Historial(str(tmp_path / "historial.db"))


def _configuracion(tmp_path):
    ruta = tmp_path / "settings.yaml"
    ruta.write_text("", encoding="utf-8")
    return cargar_configuracion(str(ruta))


def _opciones(config, audio, formato="txt"):
    return OpcionesTranscripcion.desde_configuracion(
        config, str(audio), modelo="small", idioma="es", formato=formato, incluir_timestamps=True)


def test_ruta_transcripcion_conserva_la_extension():
    assert ruta_transcripcion(str(Path("/carpeta") / "reunion.m4a"), "srt") == str(
        Path("/carpeta") / "reunion.m4a_transcripcion.srt"
    )


def _prohibido_cargar_modelo(self):
    raise AssertionError("transcriptor_para no debe cargar el modelo de Whisper")


def test_transcriptor_para_reutiliza_o_recrea(monkeypatch):
    monkeypatch.setattr(TranscriptorAudio, "modelo", property(_prohibido_cargar_modelo))

    actual = transcriptor_para(None, "small", "cpu", "int8")

    assert isinstance(actual, TranscriptorAudio)
    assert (actual.modelo_nombre, actual.dispositivo, actual.compute_type) == ("small", "cpu", "int8")
    assert transcriptor_para(actual, "small", "cpu", "int8") is actual
    for modelo, dispositivo, compute in [("base", "cpu", "int8"), ("small", "cuda", "int8"), ("small", "cpu", "float32")]:
        nuevo = transcriptor_para(actual, modelo, dispositivo, compute)
        assert nuevo is not actual
        assert (nuevo.modelo_nombre, nuevo.dispositivo, nuevo.compute_type) == (modelo, dispositivo, compute)


def test_opciones_y_parametros_llegan_a_whisper(tmp_path, modelo_whisper_falso):
    ruta = tmp_path / "settings.yaml"
    ruta.write_text(
        "transcripcion:\n  idioma: auto\n  beam_size: 3\n  logprob_threshold: -0.8\n"
        "salida:\n  palabra_por_palabra: true\n",
        encoding="utf-8",
    )
    config = cargar_configuracion(str(ruta))
    cfg = config["transcripcion"]
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola.")])
    opciones = OpcionesTranscripcion.desde_configuracion(config, "reunion.m4a", modelo="small")
    transcriptor = transcriptor_para(None, opciones.modelo, opciones.dispositivo, opciones.compute_type)

    transcribir(transcriptor, opciones, cfg)

    audio, kwargs = doble.llamadas[0]
    assert audio == "reunion.m4a"
    assert kwargs["language"] is None
    assert kwargs["task"] == "transcribe"
    assert kwargs["beam_size"] == 3
    assert kwargs["log_prob_threshold"] == -0.8
    assert kwargs["word_timestamps"] is True
    assert kwargs["best_of"] == cfg["best_of"]
    assert kwargs["temperature"] == cfg["temperature"]
    assert kwargs["condition_on_previous_text"] == cfg["condition_on_previous_text"]
    assert kwargs["compression_ratio_threshold"] == cfg["compression_ratio_threshold"]
    assert kwargs["no_speech_threshold"] == cfg["no_speech_threshold"]
    assert opciones.modelo == "small"
    assert (opciones.dispositivo, opciones.compute_type, opciones.formato, opciones.incluir_timestamps) == (
        "cpu", "int8", "txt", True)


def test_desde_configuracion_rechaza_un_campo_desconocido(tmp_path):
    ruta = tmp_path / "settings.yaml"
    ruta.write_text("", encoding="utf-8")
    config = cargar_configuracion(str(ruta))

    with pytest.raises(TypeError):
        OpcionesTranscripcion.desde_configuracion(config, "reunion.m4a", timestamps=False)


def test_flujo_completo_guarda_en_historial_y_exporta(tmp_path, modelo_whisper_falso, historial):
    modelo_whisper_falso([
        (0.0, 2.0, "Hola equipo."),
        (2.0, 3.0, "¡Suscríbete!"),          # alucinación conocida: no debe llegar al historial
        (3.0, 5.0, "Cerramos el punto."),
    ], duracion=5.0, idioma="es")
    audio = tmp_path / "reunion.m4a"
    audio.touch()
    config = _configuracion(tmp_path)
    opciones = _opciones(config, audio)
    transcriptor = transcriptor_para(None, opciones.modelo, opciones.dispositivo, opciones.compute_type)
    fases, textos = [], []

    obtenido = transcribir_y_persistir(
        transcriptor, opciones, config["transcripcion"], historial,
        on_fase=fases.append,
        on_segmento=lambda segmento, duracion_total: textos.append(segmento.texto),
    )

    assert FASE_CARGANDO_MODELO == "cargando_modelo"
    assert FASE_TRANSCRIBIENDO == "transcribiendo"
    assert fases == [FASE_CARGANDO_MODELO, FASE_TRANSCRIBIENDO]
    assert textos == ["Hola equipo.", "Cerramos el punto."]
    assert obtenido.resultado.texto_completo == "Hola equipo. Cerramos el punto."

    ruta = tmp_path / "reunion.m4a_transcripcion.txt"
    persistencia = obtenido.persistencia
    assert persistencia.motivo_historial is None
    assert persistencia.motivo_exportacion is None
    assert persistencia.ruta_exportada == str(ruta)

    entrada = historial.obtener(persistencia.id_historial)
    assert entrada.titulo == "reunion"
    assert entrada.texto == "Hola equipo. Cerramos el punto."
    assert "Suscríbete" not in entrada.texto
    assert [(s["inicio"], s["fin"], s["texto"]) for s in entrada.segmentos] == [
        (0.0, 2.0, "Hola equipo."),
        (3.0, 5.0, "Cerramos el punto."),
    ]
    assert entrada.idioma == "es"
    assert entrada.duracion_segundos == 5.0
    assert entrada.modelo_whisper == "small"

    assert ruta.read_text(encoding="utf-8") == (
        "[00:00:00,000 --> 00:00:02,000] Hola equipo.\n"
        "[00:00:03,000 --> 00:00:05,000] Cerramos el punto.\n"
    )


def test_exportacion_fallida_no_lanza_y_deja_la_entrada(tmp_path, modelo_whisper_falso, historial):
    modelo_whisper_falso([
        (0.0, 2.0, "Hola equipo."),
        (2.0, 3.0, "¡Suscríbete!"),
        (3.0, 5.0, "Cerramos el punto."),
    ], duracion=5.0, idioma="es")
    (tmp_path / "bloqueo").write_text("no es una carpeta", encoding="utf-8")
    audio = tmp_path / "bloqueo" / "reunion.m4a"   # la carpeta del audio no se puede crear ni escribir
    config = _configuracion(tmp_path)
    opciones = _opciones(config, audio)
    transcriptor = transcriptor_para(None, opciones.modelo, opciones.dispositivo, opciones.compute_type)

    obtenido = transcribir_y_persistir(transcriptor, opciones, config["transcripcion"], historial)

    assert obtenido.resultado.texto_completo == "Hola equipo. Cerramos el punto."
    persistencia = obtenido.persistencia
    assert persistencia.ruta_exportada is None
    assert persistencia.motivo_exportacion.startswith("reunion.m4a_transcripcion.txt:")
    assert historial.obtener(persistencia.id_historial) is not None


def test_sin_historial_exporta_y_avisa(tmp_path, modelo_whisper_falso):
    modelo_whisper_falso([(0.0, 2.0, "Hola equipo."), (3.0, 5.0, "Cerramos el punto.")], duracion=5.0)
    audio = tmp_path / "reunion.m4a"
    audio.touch()
    config = _configuracion(tmp_path)
    opciones = _opciones(config, audio)
    transcriptor = transcriptor_para(None, opciones.modelo, opciones.dispositivo, opciones.compute_type)

    obtenido = transcribir_y_persistir(transcriptor, opciones, config["transcripcion"], None)

    persistencia = obtenido.persistencia
    assert persistencia.motivo_historial == "Historial no disponible"
    assert persistencia.id_historial is None
    assert (tmp_path / "reunion.m4a_transcripcion.txt").exists()


def test_sin_historial_ni_exportacion_no_queda_en_ningun_sitio(tmp_path, modelo_whisper_falso):
    modelo_whisper_falso([(0.0, 2.0, "Hola equipo."), (3.0, 5.0, "Cerramos el punto.")], duracion=5.0)
    (tmp_path / "bloqueo").write_text("no es una carpeta", encoding="utf-8")
    audio = tmp_path / "bloqueo" / "reunion.m4a"
    config = _configuracion(tmp_path)
    opciones = _opciones(config, audio)
    transcriptor = transcriptor_para(None, opciones.modelo, opciones.dispositivo, opciones.compute_type)

    obtenido = transcribir_y_persistir(transcriptor, opciones, config["transcripcion"], None)

    assert obtenido.resultado.texto_completo == "Hola equipo. Cerramos el punto."
    assert texto_sin_guardado(obtenido.persistencia) == (
        "El resultado no quedó guardado en ningún sitio. Usa «Guardar como…» para conservarlo.")


def test_cancelar_antes_de_transcribir_no_guarda(tmp_path, modelo_whisper_falso, historial):
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")], duracion=5.0)
    audio = tmp_path / "reunion.m4a"
    audio.touch()
    config = _configuracion(tmp_path)
    opciones = _opciones(config, audio)
    transcriptor = transcriptor_para(None, opciones.modelo, opciones.dispositivo, opciones.compute_type)
    cancelar = threading.Event()
    cancelar.set()
    fases = []

    with pytest.raises(InterruptedError):
        transcribir_y_persistir(transcriptor, opciones, config["transcripcion"], historial,
                                on_fase=fases.append, cancelar=cancelar)

    assert doble.llamadas == []
    assert fases == [FASE_CARGANDO_MODELO]
    assert historial.listar() == []
    assert not (tmp_path / "reunion.m4a_transcripcion.txt").exists()


def test_cancelar_durante_la_transcripcion_no_guarda(tmp_path, modelo_whisper_falso, historial):
    modelo_whisper_falso([(0.0, 2.0, "Hola equipo."), (3.0, 5.0, "Cerramos el punto.")], duracion=5.0)
    audio = tmp_path / "reunion.m4a"
    audio.touch()
    config = _configuracion(tmp_path)
    opciones = _opciones(config, audio)
    transcriptor = transcriptor_para(None, opciones.modelo, opciones.dispositivo, opciones.compute_type)
    cancelar = threading.Event()

    def cancelar_tras_el_primero(segmento, duracion_total):
        cancelar.set()

    with pytest.raises(InterruptedError):
        transcribir_y_persistir(transcriptor, opciones, config["transcripcion"], historial,
                                on_segmento=cancelar_tras_el_primero, cancelar=cancelar)

    assert historial.listar() == []
    assert not (tmp_path / "reunion.m4a_transcripcion.txt").exists()


def test_error_de_whisper_no_guarda(tmp_path, modelo_whisper_falso, historial):
    doble = modelo_whisper_falso([(0.0, 2.0, "Hola equipo.")], duracion=5.0)

    def transcribe_que_falla(audio, **kwargs):
        raise RuntimeError("audio ilegible")

    doble.transcribe = transcribe_que_falla
    audio = tmp_path / "reunion.m4a"
    audio.touch()
    config = _configuracion(tmp_path)
    opciones = _opciones(config, audio)
    transcriptor = transcriptor_para(None, opciones.modelo, opciones.dispositivo, opciones.compute_type)

    with pytest.raises(RuntimeError, match="audio ilegible"):
        transcribir_y_persistir(transcriptor, opciones, config["transcripcion"], historial)

    assert historial.listar() == []
    assert not (tmp_path / "reunion.m4a_transcripcion.txt").exists()
