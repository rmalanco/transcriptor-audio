"""Tests del log por consola."""

import logging
import time

from src.registro import configurar_logging, latido


def test_configurar_logging_usa_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("TRANSCRIPTOR_LOG", "debug")
    configurar_logging()
    assert logging.getLogger("transcriptor").level == logging.DEBUG
    configurar_logging("WARNING")
    assert logging.getLogger("transcriptor").level == logging.WARNING


def test_latido_avisa_mientras_dura_el_bloque(caplog):
    logger = logging.getLogger("transcriptor.prueba")
    with caplog.at_level(logging.INFO, logger="transcriptor.prueba"):
        with latido(lambda: "procesando", cada=0.05, logger=logger):
            time.sleep(0.18)
        avisos = len(caplog.records)
        time.sleep(0.12)
    assert avisos >= 2
    assert "procesando" in caplog.records[0].getMessage()
    assert len(caplog.records) == avisos  # al salir del bloque deja de avisar
