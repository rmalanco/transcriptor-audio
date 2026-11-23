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

    basicos = [c for c in CAMPOS if not c.avanzado and c.grupo in ("Transcripción", "Salida")]
    assert [(c.seccion, c.clave) for c in basicos] == [
        ("modelo", "nombre"), ("transcripcion", "idioma"), ("modelo", "dispositivo"), ("modelo", "compute_type"),
        ("salida", "formato"), ("salida", "incluir_timestamps"), ("salida", "palabra_por_palabra"),
    ]
    assert [c.grupo for c in basicos] == ["Transcripción"] * 4 + ["Salida"] * 3
    tabla = configuracion._tabla()
    assert all((c.seccion, c.clave) in tabla for c in CAMPOS)
    opciones = {c.clave: c.opciones for c in basicos}
    assert opciones["nombre"] == MODELOS_WHISPER
    assert opciones["dispositivo"] == DISPOSITIVOS
    assert opciones["compute_type"] == TIPOS_COMPUTO
    assert opciones["formato"] == FORMATOS


def test_campos_avanzados_e_historial():
    """C2, criterios 1 y 2: las 15 claves fuera de «ia», en su orden; las siete de decodificación plegadas dentro de
    Transcripción, y `historial.ruta` con su nota."""
    from src import configuracion
    from src.ui_configuracion import CAMPOS as TODOS

    CAMPOS = [c for c in TODOS if c.seccion != "ia"]  # las claves de «ia» tienen su propio test (D1)
    assert [(c.seccion, c.clave) for c in CAMPOS] == [
        ("modelo", "nombre"), ("transcripcion", "idioma"), ("modelo", "dispositivo"), ("modelo", "compute_type"),
        ("transcripcion", "beam_size"), ("transcripcion", "best_of"), ("transcripcion", "temperature"),
        ("transcripcion", "condition_on_previous_text"), ("transcripcion", "compression_ratio_threshold"),
        ("transcripcion", "logprob_threshold"), ("transcripcion", "no_speech_threshold"),
        ("salida", "formato"), ("salida", "incluir_timestamps"), ("salida", "palabra_por_palabra"),
        ("historial", "ruta"),
    ]
    fuera_de_ia = {clave for clave in configuracion._tabla() if clave[0] != "ia"}
    assert {(c.seccion, c.clave) for c in CAMPOS} == fuera_de_ia
    assert [c.avanzado for c in CAMPOS] == [False] * 4 + [True] * 7 + [False] * 4

    decodificacion = CAMPOS[4:11]
    assert all(c.grupo == "Transcripción" for c in decodificacion)
    assert decodificacion[3].control == "interruptor"
    assert all(c.control == "texto" for i, c in enumerate(decodificacion) if i != 3)

    historial = CAMPOS[-1]
    assert (historial.grupo, historial.control, historial.avanzado) == ("Historial", "texto", False)
    assert historial.nota == "Se aplica al reiniciar la app."
    assert all(c.nota == "" for c in CAMPOS[:-1])


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
        configuracion=anterior, avisos_preferencias=[], _modelo_preferido=None, var_modelo=Doble(), var_idioma=Doble(),
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


@pytest.mark.parametrize("transcribiendo", [True, False])
def test_restablecer_configuracion_rechazado_o_cancelado_no_escribe(monkeypatch, transcribiendo):
    """C2, criterio 3: con un proceso en curso se avisa y no se pregunta; si se responde «No», no se restablece nada."""
    from types import SimpleNamespace

    from src import configuracion, ui

    avisos, preguntas = [], []
    monkeypatch.setattr(ui, "messagebox", SimpleNamespace(
        showwarning=lambda titulo, texto: avisos.append((titulo, texto)),
        showerror=lambda titulo, texto: avisos.append((titulo, texto)),
        askyesno=lambda titulo, texto: preguntas.append((titulo, texto)) or False,
    ))

    def no_debe_llamarse(*args, **kwargs):
        raise AssertionError("no se debe restablecer")

    monkeypatch.setattr(ui, "restablecer_formulario", no_debe_llamarse)
    app = SimpleNamespace(_transcribiendo=lambda: transcribiendo, _generando_ia=lambda: False)

    resultado = AppTranscriptor.restablecer_configuracion(app)

    assert not configuracion.RUTA_PREFERENCIAS.exists()
    if transcribiendo:
        espera = "Espera a que termine el proceso en curso."
        assert resultado.efectiva is None
        assert resultado.mensaje == espera
        assert avisos == [("Configuración", espera)]
        assert preguntas == []
    else:
        assert resultado is None
        assert avisos == []
        assert preguntas == [("Restablecer configuración",
                              "¿Volver a los valores de config/settings.yaml? Se borrarán los cambios guardados en "
                              "este panel y el modelo de IA elegido.")]


def test_aplicar_guardado_repone_el_modelo_de_ia_y_olvida_el_asistente():
    """C2, criterio 3: si el modelo de IA efectivo cambió, el selector, la línea de estado de las pestañas que lo
    mostraban y el asistente se reponen; si no cambió, nada de eso se toca."""
    import copy
    from types import SimpleNamespace

    from src.configuracion import ResultadoGuardado, cargar_configuracion

    class Valor:
        def __init__(self, valor):
            self.valor = valor

        def set(self, valor):
            self.valor = valor

    class Combo:
        def __init__(self, valores):
            self.valores = list(valores)

        def cget(self, atributo):
            assert atributo == "values"
            return list(self.valores)

        def configure(self, values):
            self.valores = list(values)

    class Etiqueta:
        def __init__(self, texto):
            self.texto = texto

        def cget(self, atributo):
            return self.texto

        def configure(self, text):
            self.texto = text

    class Documentos:
        def __init__(self):
            self.olvidados = 0

        def olvidar_asistente(self):
            self.olvidados += 1

    def app_con_sonnet_preferido():
        return SimpleNamespace(
            configuracion=cargar_configuracion(), _modelo_preferido="claude-sonnet-5.5", avisos_preferencias=["aviso"],
            var_modelo_ia=Valor("claude-sonnet-5.5"), combo_modelo_ia=Combo(["auto", "claude-sonnet-5.5"]),
            tabs_ia={"resumen": {"estado": Etiqueta("Modelo: GitHub Copilot · claude-sonnet-5.5")},
                     "minuta": {"estado": Etiqueta("Listo en 12 s con …")}},
            _documentos=Documentos(),
        )

    proyecto = cargar_configuracion()
    app = app_con_sonnet_preferido()
    resultado = ResultadoGuardado({}, copy.deepcopy(proyecto), None, [], {("ia", "modelo")},
                                  "Se restablecieron los valores de config/settings.yaml")

    AppTranscriptor.aplicar_guardado(app, resultado)

    assert app._modelo_preferido is None
    assert app.var_modelo_ia.valor == "claude-haiku-5.5"
    assert "claude-haiku-5.5" in app.combo_modelo_ia.valores
    assert app.tabs_ia["resumen"]["estado"].texto == "Modelo: GitHub Copilot · claude-haiku-5.5"
    assert app.tabs_ia["minuta"]["estado"].texto == "Listo en 12 s con …"
    assert app._documentos.olvidados == 1

    app = app_con_sonnet_preferido()
    sin_modelo = ResultadoGuardado({}, copy.deepcopy(proyecto), "claude-sonnet-5.5", [], set(), "Configuración guardada")

    AppTranscriptor.aplicar_guardado(app, sin_modelo)

    assert app.var_modelo_ia.valor == "claude-sonnet-5.5"
    assert app.combo_modelo_ia.valores == ["auto", "claude-sonnet-5.5"]
    assert app.tabs_ia["resumen"]["estado"].texto == "Modelo: GitHub Copilot · claude-sonnet-5.5"
    assert app._documentos.olvidados == 0


def test_campos_de_ia_sin_modelo():
    """D1, criterio 1: `CAMPOS` tiene las cinco claves `ia.*` salvo `ia.modelo`, seguidas y en el grupo «IA», entre
    la última de «Salida» y `historial.ruta`; dominio y revisión sin plegar, el resto plegado; sin nota; con sus
    etiquetas."""
    from src.ui_configuracion import CAMPOS

    indices = [i for i, c in enumerate(CAMPOS) if c.seccion == "ia"]
    ia = [CAMPOS[i] for i in indices]
    assert [c.clave for c in ia] == [
        "copilot_enterprise_url", "revision_fidelidad", "temperatura", "max_caracteres_bloque", "peticiones_paralelas",
    ]
    assert indices == list(range(indices[0], indices[0] + 5))
    assert all(c.grupo == "IA" for c in ia)
    assert CAMPOS[indices[0] - 1].grupo == "Salida"
    assert (CAMPOS[indices[-1] + 1].seccion, CAMPOS[indices[-1] + 1].clave) == ("historial", "ruta")
    assert [(c.control, c.avanzado) for c in ia] == [
        ("texto", False), ("interruptor", False), ("texto", True), ("texto", True), ("texto", True),
    ]
    assert [c.etiqueta for c in ia] == [
        "Dominio de GitHub Enterprise (vacío = github.com)", "Revisión de fidelidad", "Temperatura de la IA",
        "Caracteres por parte", "Partes a la vez",
    ]
    assert all(c.nota == "" for c in ia)


class Doble:
    """Registra cada llamada a cualquier método (`configure`, `set`, `cget`…) y devuelve lo que se le indique."""

    def __init__(self, devuelve=None):
        self.llamadas = []
        self.devuelve = devuelve

    def __getattr__(self, nombre):
        def registrar(*args, **kwargs):
            self.llamadas.append((nombre, args, kwargs))
            return self.devuelve
        return registrar


@pytest.fixture
def asistentes_anotados(monkeypatch):
    """Sustituye `ui.AsistenteIA` por un doble que anota los argumentos con que se crea y no lee el token."""
    from src import ui

    creados = []

    class AsistenteAnotador:
        def __init__(self, **kwargs):
            creados.append(kwargs)
            self.kwargs = kwargs
            self.modelo = kwargs["modelo"]
            self.modelo_usado = kwargs["modelo"]
            self.nombre_proveedor = "GitHub Copilot"

    monkeypatch.setattr(ui, "AsistenteIA", AsistenteAnotador)
    return creados


def test_crear_asistente_usa_los_valores_de_la_ventana(monkeypatch, asistentes_anotados):
    """D1, criterio 2: `_crear_asistente` crea el asistente con `argumentos_asistente` de la configuración y el modelo
    efectivo de ese momento."""
    from types import SimpleNamespace

    from src import ui
    from src.configuracion import cargar_configuracion

    cfg = cargar_configuracion()
    espiados = []
    esperado = {"modelo": "claude-sonnet-5.5", "temperatura": 0.5, "max_caracteres_bloque": 30000,
                "revision_fidelidad": True, "peticiones_paralelas": 2, "enterprise_url": "empresa.ghe.com"}

    def espia(configuracion, modelo):
        espiados.append((configuracion, modelo))
        return esperado

    monkeypatch.setattr(ui, "argumentos_asistente", espia)
    app = SimpleNamespace(configuracion=cfg, _modelo_ia_configurado=lambda: "claude-sonnet-5.5")

    AppTranscriptor._crear_asistente(app)

    assert espiados == [(cfg, "claude-sonnet-5.5")]
    assert asistentes_anotados == [esperado]


@pytest.mark.parametrize("seccion,clave,valor,argumento", [
    ("ia", "temperatura", 0.5, "temperatura"),
    ("ia", "revision_fidelidad", True, "revision_fidelidad"),
    ("ia", "copilot_enterprise_url", "empresa.ghe.com", "enterprise_url"),
    ("ia", "peticiones_paralelas", 2, "peticiones_paralelas"),
    ("ia", "max_caracteres_bloque", 30000, "max_caracteres_bloque"),
    ("salida", "formato", "srt", None),  # lo que no es de IA no rehace el asistente: sus notas se conservan
])
def test_guardar_ia_rehace_el_asistente_solo_en_la_siguiente_generacion(
        tmp_path, asistentes_anotados, seccion, clave, valor, argumento):
    """D1, criterio 2: guardar una clave de IA hace que la generación siguiente use los valores nuevos; la generación
    en curso sigue con su asistente. Guardar otra clave no rehace el asistente."""
    import copy
    from types import SimpleNamespace

    from src.configuracion import ResultadoGuardado, cargar_configuracion
    from src.flujo_documentos import GestorDocumentos
    from src.transcriber import ResultadoTranscripcion, SegmentoTranscripcion

    anterior = cargar_configuracion()
    app = SimpleNamespace(configuracion=anterior, _modelo_preferido=None, avisos_preferencias=[], _epoca_ia=0,
                          combo_modelo_ia=Doble(), var_modelo_ia=Doble(), var_formato=Doble(), tabs_ia={})
    app._modelo_ia_configurado = lambda: "claude-haiku-5.5"
    app._documentos = GestorDocumentos(None, lambda: AppTranscriptor._crear_asistente(app))
    resultado = ResultadoTranscripcion(
        texto_completo="Hola.", segmentos=[SegmentoTranscripcion(0.0, 1.0, "Hola.")],
        idioma_detectado="es", probabilidad_idioma=1.0, duracion_total=1.0)
    archivo = str(tmp_path / "reunion.m4a")

    en_curso = app._documentos.iniciar("resumen", resultado, archivo, None, None)
    antes = dict(en_curso.asistente.kwargs)

    efectiva = copy.deepcopy(anterior)
    efectiva[seccion][clave] = valor
    AppTranscriptor.aplicar_guardado(app, ResultadoGuardado({}, efectiva, None, [], {(seccion, clave)},
                                                            "Configuración guardada"))
    assert en_curso.asistente.kwargs == antes  # la generación en curso no cambia

    app._documentos.terminar(en_curso)
    app._documentos.iniciar("resumen", resultado, archivo, None, None)

    assert len(asistentes_anotados) == (1 if argumento is None else 2)
    if argumento is not None:
        assert asistentes_anotados[-1][argumento] == valor


def test_guardar_el_dominio_avanza_la_epoca_y_reinicia_el_selector(monkeypatch):
    """D1, criterio 3: al cambiar `ia.copilot_enterprise_url`, la época de la IA sube y el selector del lateral vuelve
    a ofrecer solo `auto` y el modelo configurado; con otra clave de IA, ni la época ni el selector cambian."""
    import copy
    from types import SimpleNamespace

    from src.configuracion import ResultadoGuardado, cargar_configuracion

    anterior = cargar_configuracion()
    app = SimpleNamespace(configuracion=anterior, _modelo_preferido=None, avisos_preferencias=[], _epoca_ia=0,
                          combo_modelo_ia=Doble(), var_modelo_ia=Doble(), var_formato=Doble(), tabs_ia={},
                          _documentos=Doble())
    app._modelo_ia_configurado = lambda: "claude-haiku-5.5"

    efectiva = copy.deepcopy(anterior)
    efectiva["ia"]["copilot_enterprise_url"] = "empresa.ghe.com"
    AppTranscriptor.aplicar_guardado(app, ResultadoGuardado({}, efectiva, None, [], {("ia", "copilot_enterprise_url")},
                                                            "Configuración guardada"))

    assert app._epoca_ia == 1
    assert app.combo_modelo_ia.llamadas == [("configure", (), {"values": ["auto", "claude-haiku-5.5"]})]

    otra = copy.deepcopy(efectiva)
    otra["ia"]["temperatura"] = 0.5
    app.combo_modelo_ia.llamadas.clear()
    AppTranscriptor.aplicar_guardado(app, ResultadoGuardado({}, otra, None, [], {("ia", "temperatura")},
                                                            "Configuración guardada"))

    assert app._epoca_ia == 1
    assert app.combo_modelo_ia.llamadas == []


def _ventana_para_modelos(epoca_actual, proceso=False):
    """Doble de la ventana con lo que usan las respuestas de «↻»; registra lo que hacen sin tocar Tk ni la red."""
    from types import SimpleNamespace

    app = SimpleNamespace(_epoca_ia=epoca_actual, _consultando_modelos=True, combo_modelo_ia=Doble(),
                          btn_cargar_modelos_ia=Doble(), label_estado=Doble(), registro=[], login=[])
    app._log = app.registro.append
    app._iniciar_sesion_copilot = app.login.append
    app._modelo_ia_configurado = lambda: "claude-haiku-5.5"
    app._cargar_modelos_ia = lambda: None
    app._transcribiendo = lambda: proceso == "transcripcion"
    app._generando_ia = lambda: proceso == "generacion"
    return app


RESPUESTAS_DE_MODELOS = {
    "mostrar": lambda app, epoca: AppTranscriptor._mostrar_modelos_ia(app, ["auto", "gpt-4.1"], epoca),
    "fallo": lambda app, epoca: AppTranscriptor._fallo_cargar_modelos_ia(app, "sin red", epoca),
    "sin_sesion": lambda app, epoca: AppTranscriptor._sin_sesion_para_modelos(app, epoca),
}
DESCARTE = "Se descarta una lista de modelos de una sesión o un dominio anteriores"


@pytest.mark.parametrize("proceso", ["transcripcion", "generacion"])
def test_lista_de_otra_epoca_no_pisa_la_barra_de_un_proceso_en_curso(proceso):
    """Si al descartar la lista vieja hay una transcripción o una generación en curso, la barra de estado es suya: no
    se cambia a «Listo»."""
    app = _ventana_para_modelos(epoca_actual=1, proceso=proceso)

    AppTranscriptor._mostrar_modelos_ia(app, ["auto", "gpt-4.1"], 0)

    assert app.registro == [DESCARTE]
    assert app.label_estado.llamadas == []


@pytest.mark.parametrize("nombre", list(RESPUESTAS_DE_MODELOS))
def test_lista_de_modelos_de_otra_epoca_se_descarta(nombre):
    """D1, criterio 3: una respuesta de «↻» lanzada con otra época no pinta la lista ni abre el inicio de sesión;
    rehabilita «↻», anota en Registro y devuelve la barra de estado a «Listo». Con la misma época, hace lo de hoy."""
    app = _ventana_para_modelos(epoca_actual=1)

    RESPUESTAS_DE_MODELOS[nombre](app, 0)

    assert app.combo_modelo_ia.llamadas == []
    assert app.login == []
    assert app.btn_cargar_modelos_ia.llamadas == [("configure", (), {"state": "normal"})]
    assert app._consultando_modelos is False
    assert app.registro == [DESCARTE]
    assert app.label_estado.llamadas[-1] == ("configure", (), {"text": "Listo"})

    app = _ventana_para_modelos(epoca_actual=0)

    RESPUESTAS_DE_MODELOS[nombre](app, 0)

    assert app.btn_cargar_modelos_ia.llamadas == [("configure", (), {"state": "normal"})]
    assert app._consultando_modelos is False
    assert DESCARTE not in app.registro
    if nombre == "mostrar":
        assert app.combo_modelo_ia.llamadas == [("configure", (), {"values": ["auto", "gpt-4.1"]})]
        assert app.label_estado.llamadas[-1] == ("configure", (), {"text": "Modelos de IA cargados"})
    elif nombre == "fallo":
        assert app.label_estado.llamadas[-1] == ("configure", (), {"text": "No se pudieron cargar los modelos de IA"})
    else:
        assert app.login == [app._cargar_modelos_ia]


@pytest.mark.parametrize("cambia_la_epoca", [True, False])
def test_cargar_modelos_ia_descarta_si_cambia_la_epoca_durante_la_consulta(monkeypatch, cambia_la_epoca):
    """D1, criterio 3: la época se captura al lanzar «↻», no al recibir la respuesta. Si el dominio cambia mientras se
    consulta, la lista no se pinta; si no cambia, sí. El dominio que recibe `leer_token` es el de la configuración."""
    from types import SimpleNamespace

    from src import copilot, ui
    from src.configuracion import cargar_configuracion

    cfg = cargar_configuracion()
    cfg["ia"]["copilot_enterprise_url"] = "empresa.ghe.com"
    app = _ventana_para_modelos(epoca_actual=0)
    app.configuracion = cfg
    app._en_ui = lambda funcion, *args: funcion(*args)
    app._mostrar_modelos_ia = lambda opciones, epoca: AppTranscriptor._mostrar_modelos_ia(app, opciones, epoca)
    dominios = []

    def leer_token(enterprise_url=None):
        dominios.append(enterprise_url)
        return object()

    def cargar_opciones(sesion, actual):
        if cambia_la_epoca:
            app._epoca_ia += 1  # un guardado del dominio mientras se consulta
        return ["auto", "gpt-4.1"]

    class HiloSincrono:
        def __init__(self, target, daemon):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr(copilot, "leer_token", leer_token)
    monkeypatch.setattr(copilot, "cargar_opciones_de_modelo", cargar_opciones)
    monkeypatch.setattr(ui, "threading", SimpleNamespace(Thread=HiloSincrono))

    AppTranscriptor._cargar_modelos_ia(app)

    assert dominios == ["empresa.ghe.com"]
    if cambia_la_epoca:
        assert app.combo_modelo_ia.llamadas == []
        assert app.registro == [DESCARTE]
    else:
        assert app.combo_modelo_ia.llamadas == [("configure", (), {"values": ["auto", "gpt-4.1"]})]
