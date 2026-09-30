"""Tests básicos para el módulo de UI."""

import pytest
from src.ui import (
    MODELOS_DISPONIBLES,
    IDIOMAS_DISPONIBLES,
    FORMATOS_DISPONIBLES,
    AppTranscriptor,
    TKDND_DISPONIBLE
)


def test_modelos_disponibles():
    assert "tiny" in MODELOS_DISPONIBLES
    assert "base" in MODELOS_DISPONIBLES
    assert "large-v3" in MODELOS_DISPONIBLES


def test_idiomas_disponibles():
    assert "es" in IDIOMAS_DISPONIBLES
    assert "en" in IDIOMAS_DISPONIBLES
    assert IDIOMAS_DISPONIBLES["es"] == "Español"


def test_formatos_disponibles():
    assert "txt" in FORMATOS_DISPONIBLES
    assert "srt" in FORMATOS_DISPONIBLES
    assert "json" in FORMATOS_DISPONIBLES


def test_ui_importa_correctamente():
    assert AppTranscriptor is not None
    assert isinstance(TKDND_DISPONIBLE, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])