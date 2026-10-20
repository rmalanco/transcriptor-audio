"""Módulo principal de transcripción usando faster-whisper."""

import logging
import os
import re
from pathlib import Path
import threading
import time
from typing import Callable, Optional, Generator
from dataclasses import dataclass
from faster_whisper import WhisperModel
import yaml

from src.registro import latido

log = logging.getLogger("transcriptor.whisper")

# Frases que Whisper inventa sobre silencio o ruido (vienen de subtítulos de YouTube con los que se entrenó).
# Solo se descartan si son el segmento completo. "Gracias" o "adiós" no se incluyen: en una reunión son reales.
ALUCINACIONES_CONOCIDAS = {
    "subtítulos realizados por la comunidad de amara.org",
    "subtítulos por la comunidad de amara.org",
    "gracias por ver el video", "gracias por ver el vídeo",
    "suscríbete", "suscríbete al canal", "no olvides suscribirte",
    "thanks for watching", "thank you for watching",
}


def es_alucinacion_conocida(texto: str) -> bool:
    return texto.lower().strip(".,!¡?¿ \t") in ALUCINACIONES_CONOCIDAS


@dataclass
class SegmentoTranscripcion:
    inicio: float
    fin: float
    texto: str
    palabras: Optional[list] = None


@dataclass
class ResultadoTranscripcion:
    texto_completo: str
    segmentos: list[SegmentoTranscripcion]
    idioma_detectado: str
    probabilidad_idioma: float
    duracion_total: float


class TranscriptorAudio:
    def __init__(
        self,
        modelo_nombre: str = "base",
        dispositivo: str = "cpu",
        compute_type: str = "int8",
        cache_dir: Optional[str] = None
    ):
        self.modelo_nombre = modelo_nombre
        self.dispositivo = dispositivo
        self.compute_type = compute_type
        self.cache_dir = cache_dir or os.path.expanduser("~/.cache/faster-whisper")
        self._modelo: Optional[WhisperModel] = None

    @property
    def modelo(self) -> WhisperModel:
        if self._modelo is None:
            log.info("Cargando modelo Whisper '%s' (%s, %s) desde %s; si no está en caché se descarga",
                     self.modelo_nombre, self.dispositivo, self.compute_type, self.cache_dir)
            inicio = time.monotonic()
            with latido(f"cargando/descargando el modelo '{self.modelo_nombre}'"):
                self._modelo = WhisperModel(
                    self.modelo_nombre,
                    device=self.dispositivo,
                    compute_type=self.compute_type,
                    download_root=self.cache_dir
                )
            log.info("Modelo '%s' listo en %.1f s", self.modelo_nombre, time.monotonic() - inicio)
        return self._modelo

    def transcribir(
        self,
        archivo: str,
        idioma: str = "es",
        task: str = "transcribe",
        beam_size: int = 5,
        best_of: int = 5,
        temperature: float = 0.0,
        condition_on_previous_text: bool = True,
        compression_ratio_threshold: float = 2.4,
        logprob_threshold: float = -1.0,
        no_speech_threshold: float = 0.6,
        word_timestamps: bool = False,
        on_segmento: Optional[Callable[[SegmentoTranscripcion, float], None]] = None,
        cancelar: Optional[threading.Event] = None,
    ) -> ResultadoTranscripcion:
        """Transcribe un archivo.

        on_segmento(segmento, duracion_total) se llama por cada segmento nuevo.
        Si `cancelar` se activa, se detiene y devuelve lo transcrito hasta ese momento.
        """
        log.info("Transcribiendo %s (idioma=%s, beam_size=%s)", archivo, idioma, beam_size)
        inicio = time.monotonic()
        # Decodifica el audio completo y aplica el VAD antes de devolver el primer segmento
        modelo = self.modelo
        with latido("leyendo el audio, filtrando silencios (VAD) y detectando idioma"):
            segmentos, info = modelo.transcribe(
                archivo,
                language=idioma if idioma != "auto" else None,
                task=task,
                beam_size=beam_size,
                best_of=best_of,
                temperature=temperature,
                condition_on_previous_text=condition_on_previous_text,
                compression_ratio_threshold=compression_ratio_threshold,
                log_prob_threshold=logprob_threshold,
                no_speech_threshold=no_speech_threshold,
                word_timestamps=word_timestamps,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )

        log.info("Audio de %s; idioma %s (%.0f%%); preparación en %.1f s",
                 _mmss(info.duration), info.language, info.language_probability * 100, time.monotonic() - inicio)

        segmentos_lista = []
        texto_completo = []
        siguiente_aviso = 0.1  # se informa el avance cada 10 %

        def _estado() -> str:
            posicion = segmentos_lista[-1].fin if segmentos_lista else 0.0
            return (f"transcribiendo, {len(segmentos_lista)} segmentos hasta {_mmss(posicion)} "
                    f"de {_mmss(info.duration)}")

        with latido(_estado, cada=30):
            for seg in segmentos:
                if es_alucinacion_conocida(seg.text):
                    log.info("Descartada alucinación conocida en %s: %r", _mmss(seg.start), seg.text.strip())
                    continue
                segmento = SegmentoTranscripcion(
                    inicio=seg.start,
                    fin=seg.end,
                    texto=seg.text.strip(),
                    palabras=[{"inicio": w.start, "fin": w.end, "palabra": w.word} for w in seg.words] if seg.words and word_timestamps else None
                )
                segmentos_lista.append(segmento)
                texto_completo.append(seg.text.strip())
                if on_segmento:
                    on_segmento(segmento, info.duration)
                log.debug("[%s → %s] %s", _mmss(seg.start), _mmss(seg.end), segmento.texto)
                if info.duration and seg.end / info.duration >= siguiente_aviso:
                    transcurrido = time.monotonic() - inicio
                    log.info("Avance %3.0f%% · %s de %s · %d segmentos · %.1fx tiempo real",
                             seg.end / info.duration * 100, _mmss(seg.end), _mmss(info.duration),
                             len(segmentos_lista), seg.end / transcurrido if transcurrido else 0)
                    siguiente_aviso = int(seg.end / info.duration * 10) / 10 + 0.1
                if cancelar and cancelar.is_set():
                    log.info("Cancelado en %s", _mmss(seg.end))
                    break

        total = time.monotonic() - inicio
        log.info("Transcripción terminada: %d segmentos en %s (%.1fx tiempo real)",
                 len(segmentos_lista), _mmss(total), info.duration / total if total else 0)
        return ResultadoTranscripcion(
            texto_completo=" ".join(texto_completo),
            segmentos=segmentos_lista,
            idioma_detectado=info.language,
            probabilidad_idioma=info.language_probability,
            duracion_total=info.duration
        )

    def transcribir_archivo_largo(
        self,
        archivo: str,
        chunk_duration: int = 30,
        **kwargs
    ) -> Generator[ResultadoTranscripcion, None, None]:
        """Transcribe archivos largos dividiéndolos en chunks."""
        import ffmpeg
        
        probe = ffmpeg.probe(archivo)
        duracion = float(probe['format']['duration'])
        
        for inicio in range(0, int(duracion), chunk_duration):
            fin = min(inicio + chunk_duration, duracion)
            
            chunk_path = f"/tmp/chunk_{Path(archivo).stem}_{inicio}_{fin}.wav"
            (
                ffmpeg
                .input(archivo, ss=inicio, t=fin-inicio)
                .output(chunk_path, acodec='pcm_s16le', ar=16000, ac=1)
                .overwrite_output()
                .run(quiet=True)
            )
            
            yield self.transcribir(chunk_path, **kwargs)
            
            os.remove(chunk_path)


def _mmss(segundos: float) -> str:
    minutos, segs = divmod(int(segundos), 60)
    return f"{minutos:02d}:{segs:02d}" if minutos < 60 else f"{minutos // 60}:{minutos % 60:02d}:{segs:02d}"


def cargar_configuracion(ruta: str = "config/settings.yaml") -> dict:
    with open(ruta, 'r') as f:
        return yaml.safe_load(f)


def guardar_modelo_ia(modelo: str, ruta: str = "config/settings.yaml") -> bool:
    """Cambia `ia.modelo` en el archivo editando solo esa línea, para no perder los comentarios del YAML.
    Devuelve False si no encuentra la clave."""
    lineas = Path(ruta).read_text(encoding="utf-8").splitlines(keepends=True)
    en_ia = False
    for i, linea in enumerate(lineas):
        if linea.strip() and not linea[0].isspace():
            en_ia = linea.startswith("ia:")
            continue
        if en_ia:
            nueva, cambios = re.subn(r'^(\s+modelo:\s*)("[^"]*"|[^\s#]+)', lambda m: f'{m[1]}"{modelo}"', linea)
            if cambios:
                lineas[i] = nueva
                Path(ruta).write_text("".join(lineas), encoding="utf-8")
                return True
    return False