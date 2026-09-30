"""Log por consola: qué está haciendo la app y en qué paso se queda esperando."""

import logging
import os
import sys
import threading
import time
from contextlib import contextmanager
from typing import Callable, Optional, Union

FORMATO = "%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s"
FORMATO_FECHA = "%H:%M:%S"
VARIABLE_NIVEL = "TRANSCRIPTOR_LOG"  # DEBUG, INFO, WARNING…

log = logging.getLogger("transcriptor")


def configurar_logging(nivel: Optional[str] = None) -> None:
    """Envía los logs a la consola (stderr). El nivel sale de `nivel`, de $TRANSCRIPTOR_LOG o es INFO."""
    nivel = (nivel or os.environ.get(VARIABLE_NIVEL) or "INFO").upper()
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter(FORMATO, FORMATO_FECHA))
    raiz = logging.getLogger()
    raiz.handlers[:] = [manejador]
    raiz.setLevel(logging.WARNING)  # librerías de terceros: solo avisos y errores

    log.setLevel(nivel)
    # faster-whisper informa la duración del audio y cuánto silencio quitó el VAD
    logging.getLogger("faster_whisper").setLevel(nivel)
    if nivel == "DEBUG":
        logging.getLogger("httpx").setLevel("INFO")  # una línea por petición HTTP

    # Excepciones no capturadas en hilos secundarios
    def _excepcion_hilo(args):
        log.critical("Error no capturado en el hilo %s", args.thread.name if args.thread else "?",
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    threading.excepthook = _excepcion_hilo


@contextmanager
def latido(descripcion: Union[str, Callable[[], str]], cada: float = 15.0, logger: logging.Logger = log):
    """Mientras dura el bloque, registra cada `cada` segundos que la operación sigue en curso.

    Sirve para ver en qué paso está esperando la app (descarga del modelo, respuesta de la API…).
    `descripcion` puede ser una función para mostrar información actualizada.
    """
    fin = threading.Event()
    inicio = time.monotonic()

    def _latir():
        while not fin.wait(cada):
            texto = descripcion() if callable(descripcion) else descripcion
            logger.info("… %s (lleva %.0f s)", texto, time.monotonic() - inicio)

    hilo = threading.Thread(target=_latir, name="latido", daemon=True)
    hilo.start()
    try:
        yield
    finally:
        fin.set()
