"""Tests básicos para el módulo de UI."""

import pytest
from src.configuracion import MODELOS_WHISPER
from src.ui import (
    IDIOMAS_DISPONIBLES,
    FORMATOS_DISPONIBLES,
    AppTranscriptor,
    TKDND_DISPONIBLE
)


def test_modelos_disponibles():
    assert "tiny" in MODELOS_WHISPER
    assert "base" in MODELOS_WHISPER
    assert "large-v3" in MODELOS_WHISPER


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

def test_idioma_configurado_fuera_del_selector_se_ofrece_y_se_usa_tal_cual():
    from src.ui import codigo_de_idioma, opciones_de_idioma

    assert "nl" in opciones_de_idioma("nl")
    assert codigo_de_idioma("nl") == "nl"


def test_idioma_del_selector_se_muestra_con_su_nombre():
    from src.ui import codigo_de_idioma, opciones_de_idioma

    assert "Español" in opciones_de_idioma("es")
    assert "es" not in opciones_de_idioma("es")
    assert codigo_de_idioma("Español") == "es"


def test_auto_sigue_siendo_autodetectar():
    from src.ui import codigo_de_idioma, opciones_de_idioma

    assert "Auto-detectar" in opciones_de_idioma("auto")
    assert codigo_de_idioma("Auto-detectar") == "auto"


def test_el_hilo_de_transcripcion_no_lee_la_configuracion():
    """Guardia (C0): el hilo de fondo recibe sus parámetros y no lee `self.configuracion`."""
    import inspect
    codigo = inspect.getsource(AppTranscriptor._procesar_transcripcion)
    assert "self.configuracion" not in codigo
    parametros = inspect.signature(AppTranscriptor._procesar_transcripcion).parameters
    assert list(parametros)[1:] == ["opciones", "parametros"]


def test_los_parametros_se_capturan_en_el_hilo_principal():
    """C0: `_iniciar_transcripcion` captura `self.configuracion["transcripcion"]` y lanza el hilo con esos parámetros."""
    import inspect
    codigo = inspect.getsource(AppTranscriptor._iniciar_transcripcion)
    assert 'self.configuracion["transcripcion"]' in codigo
    assert "args=(opciones, parametros)" in codigo
