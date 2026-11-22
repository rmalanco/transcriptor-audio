"""Flujo transcribir → guardar en el historial → exportar, con un modelo de Whisper falso (sin red ni audio real)."""

from pathlib import Path

from src.historial import Historial
from src.persistencia import persistir_transcripcion
from src.transcriber import TranscriptorAudio


def test_flujo_transcribir_guardar_historial_descarta_alucinacion_y_exporta(tmp_path, modelo_whisper_falso):
    modelo_whisper_falso([
        (0.0, 2.0, "Hola equipo."),
        (2.0, 3.0, "¡Suscríbete!"),          # alucinación conocida: no debe llegar al historial
        (3.0, 5.0, "Cerramos el punto."),
    ], duracion=5.0, idioma="es")
    audio = tmp_path / "reunion.m4a"
    audio.touch()
    historial = Historial(str(tmp_path / "historial.db"))

    # Mismo orden que la interfaz: transcribir y después persistir (historial primero, luego el archivo)
    resultado = TranscriptorAudio(modelo_nombre="small").transcribir(str(audio), idioma="es")
    ruta = str(tmp_path / "reunion_transcripcion.txt")
    persistencia = persistir_transcripcion(historial, str(audio), resultado, "small", ruta, "txt", True)

    assert persistencia.motivo_historial is None
    assert persistencia.motivo_exportacion is None
    assert persistencia.ruta_exportada == ruta

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

    assert Path(ruta).read_text(encoding="utf-8") == (
        "[00:00:00,000 --> 00:00:02,000] Hola equipo.\n"
        "[00:00:03,000 --> 00:00:05,000] Cerramos el punto.\n"
    )
