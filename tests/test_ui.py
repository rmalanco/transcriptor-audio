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


def test_campos_de_transcripcion_y_salida():
    """C1, criterio 1: la vista tiene las siete claves de Transcripción y Salida, con sus grupos y sus opciones."""
    from src import configuracion
    from src.configuracion import DISPOSITIVOS, FORMATOS, MODELOS_WHISPER, TIPOS_COMPUTO
    from src.ui_configuracion import CAMPOS

    assert [(c.seccion, c.clave) for c in CAMPOS] == [
        ("modelo", "nombre"), ("transcripcion", "idioma"), ("modelo", "dispositivo"), ("modelo", "compute_type"),
        ("salida", "formato"), ("salida", "incluir_timestamps"), ("salida", "palabra_por_palabra"),
    ]
    assert all(not c.avanzado for c in CAMPOS)
    assert [c.grupo for c in CAMPOS] == ["Transcripción"] * 4 + ["Salida"] * 3
    tabla = configuracion._tabla()
    assert all((c.seccion, c.clave) in tabla for c in CAMPOS)
    opciones = {c.clave: c.opciones for c in CAMPOS}
    assert opciones["nombre"] == MODELOS_WHISPER
    assert opciones["dispositivo"] == DISPOSITIVOS
    assert opciones["compute_type"] == TIPOS_COMPUTO
    assert opciones["formato"] == FORMATOS


def test_motivo_para_no_guardar_durante_un_proceso():
    """C1, criterio 3: con una transcripción o una generación en curso no se guarda, y se dice por qué."""
    from src.ui_configuracion import motivo_para_no_guardar

    espera = "Espera a que termine el proceso en curso."
    assert motivo_para_no_guardar(False, False) is None
    assert motivo_para_no_guardar(True, False) == espera
    assert motivo_para_no_guardar(False, True) == espera
    assert motivo_para_no_guardar(True, True) == espera


def test_guardar_configuracion_durante_un_proceso_no_escribe(monkeypatch):
    """C1, criterio 3: con un proceso en curso, `guardar_configuracion` avisa con el diálogo, no escribe nada y
    devuelve el motivo para el pie de la vista."""
    from types import SimpleNamespace

    from src import configuracion, ui

    avisos = []
    monkeypatch.setattr(ui, "messagebox",
                        SimpleNamespace(showwarning=lambda titulo, texto: avisos.append((titulo, texto))))

    def no_debe_llamarse(*args, **kwargs):
        raise AssertionError("no se debe guardar mientras hay un proceso en curso")

    monkeypatch.setattr(ui, "guardar_formulario", no_debe_llamarse)
    app = SimpleNamespace(_transcribiendo=lambda: True, _generando_ia=lambda: False)

    resultado = AppTranscriptor.guardar_configuracion(app, {("salida", "formato"): "srt"})

    espera = "Espera a que termine el proceso en curso."
    assert resultado.efectiva is None
    assert resultado.mensaje == espera
    assert avisos == [("Configuración", espera)]
    assert not configuracion.RUTA_PREFERENCIAS.exists()


def test_aplicar_guardado_solo_toca_las_claves_cambiadas():
    """C1, criterios 1 y 2: aplicar un guardado sustituye la configuración (sin mutarla) y solo cambia en el panel
    lateral los controles de las claves que cambiaron; el selector de idioma ofrece el código nuevo al final."""
    import copy
    from types import SimpleNamespace

    from src.configuracion import ResultadoGuardado, cargar_configuracion

    class Doble:
        def __init__(self):
            self.valores = []

        def set(self, valor):
            self.valores.append(valor)

    class DobleCombo:
        def __init__(self):
            self.opciones = []

        def configure(self, values):
            self.opciones.append(values)

    anterior = cargar_configuracion()
    efectiva = copy.deepcopy(anterior)
    efectiva["transcripcion"]["idioma"] = "nl"
    efectiva["salida"]["formato"] = "srt"
    resultado = ResultadoGuardado({}, efectiva, None, [], {("transcripcion", "idioma"), ("salida", "formato")},
                                  "Configuración guardada")
    app = SimpleNamespace(
        configuracion=anterior, avisos_preferencias=[], var_modelo=Doble(), var_idioma=Doble(),
        var_formato=Doble(), var_dispositivo=Doble(), var_compute=Doble(), var_timestamps=Doble(),
        combo_idioma=DobleCombo(),
    )

    AppTranscriptor.aplicar_guardado(app, resultado)

    assert app.configuracion is efectiva
    assert app.var_idioma.valores == ["nl"]
    assert app.var_formato.valores == ["srt"]
    assert app.combo_idioma.opciones[-1][-1] == "nl"
    for sin_cambios in (app.var_modelo, app.var_dispositivo, app.var_compute, app.var_timestamps):
        assert sin_cambios.valores == []
