"""Tests de la integración con GitHub Copilot (sin llamadas reales a GitHub)."""

import json
import os
import stat
import threading

import pytest

from src import asistente_ia, copilot
from src.asistente_ia import AsistenteIA, ErrorSinSesionCopilot


@pytest.fixture(autouse=True)
def rutas_aisladas(monkeypatch, tmp_path):
    monkeypatch.setattr(copilot, "RUTA_TOKEN", tmp_path / "app" / "copilot.json")
    monkeypatch.setattr(copilot, "RUTA_AUTH_OPENCODE", tmp_path / "opencode" / "auth.json")
    monkeypatch.delenv(copilot.VARIABLE_ENTORNO, raising=False)


class _Respuesta:
    def __init__(self, datos, status_code=200):
        self.datos, self.status_code, self.text = datos, status_code, json.dumps(datos)

    def json(self):
        return self.datos


def test_url_api_segun_dominio():
    assert copilot.url_api() == "https://api.githubcopilot.com"
    assert copilot.url_api("github.com") == "https://api.githubcopilot.com"
    assert copilot.url_api("https://empresa.ghe.com/") == "https://copilot-api.empresa.ghe.com"


def test_guardar_y_leer_token_con_permisos_600():
    copilot.guardar_token("gho_abc")
    if os.name != "nt":  # Windows no aplica permisos POSIX (chmod solo cambia "solo lectura")
        assert stat.S_IMODE(os.stat(copilot.RUTA_TOKEN).st_mode) == 0o600
    sesion = copilot.leer_token()
    assert sesion.token == "gho_abc" and sesion.enterprise_url is None
    assert copilot.cerrar_sesion() and copilot.leer_token() is None


def test_reutiliza_sesion_de_opencode():
    copilot.RUTA_AUTH_OPENCODE.parent.mkdir(parents=True)
    copilot.RUTA_AUTH_OPENCODE.write_text(json.dumps(
        {"github-copilot": {"type": "oauth", "refresh": "gho_oc", "access": "gho_oc", "expires": 0}}))
    assert copilot.leer_token().token == "gho_oc"
    assert copilot.leer_token("empresa.ghe.com") is None  # token de github.com no sirve para Enterprise


def test_token_propio_tiene_prioridad_y_variable_de_entorno_sobre_todo(monkeypatch):
    copilot.RUTA_AUTH_OPENCODE.parent.mkdir(parents=True)
    copilot.RUTA_AUTH_OPENCODE.write_text(json.dumps({"github-copilot": {"refresh": "gho_oc"}}))
    copilot.guardar_token("gho_app")
    assert copilot.leer_token().token == "gho_app"
    monkeypatch.setenv(copilot.VARIABLE_ENTORNO, "gho_env")
    assert copilot.leer_token().token == "gho_env"


def test_el_origen_del_token_se_informa(monkeypatch):
    copilot.RUTA_AUTH_OPENCODE.parent.mkdir(parents=True)
    copilot.RUTA_AUTH_OPENCODE.write_text(json.dumps({"github-copilot": {"refresh": "gho_oc"}}))
    assert copilot.leer_token().origen == str(copilot.RUTA_AUTH_OPENCODE)  # solo sesión de opencode
    copilot.guardar_token("gho_app")
    assert copilot.leer_token().origen == str(copilot.RUTA_TOKEN)  # el archivo propio gana a opencode
    monkeypatch.setenv(copilot.VARIABLE_ENTORNO, "gho_env")
    assert copilot.leer_token().origen == copilot.VARIABLE_ENTORNO  # la variable gana a todo


def _solo_opencode(_monkeypatch):
    copilot.RUTA_AUTH_OPENCODE.parent.mkdir(parents=True)
    copilot.RUTA_AUTH_OPENCODE.write_text(json.dumps({"github-copilot": {"refresh": "gho_oc"}}))


def _app_y_opencode(monkeypatch):
    _solo_opencode(monkeypatch)
    copilot.guardar_token("gho_app")


def _variable_y_app(monkeypatch):
    copilot.guardar_token("gho_app")
    monkeypatch.setenv(copilot.VARIABLE_ENTORNO, "gho_env")


def _json_invalido(_monkeypatch):
    copilot.RUTA_TOKEN.parent.mkdir(parents=True)
    copilot.RUTA_TOKEN.write_text("{no es json")


def _app_de_otro_dominio(_monkeypatch):
    copilot.guardar_token("gho_ghe", "empresa.ghe.com")


def _instantanea(raiz):
    """Rutas de `raiz` con su contenido y su fecha de modificación, para ver si algo se crea o cambia."""
    return {ruta: (ruta.read_bytes() if ruta.is_file() else None, ruta.stat().st_mtime_ns)
            for ruta in raiz.rglob("*")}


@pytest.mark.parametrize("preparar, origen, hay_token_propio", [
    (None, None, False),
    (_solo_opencode, "opencode", False),
    (_app_y_opencode, "app", True),
    (_variable_y_app, "variable", True),
    (_json_invalido, None, False),
    (_app_de_otro_dominio, None, True),
])
def test_estado_sesion_segun_el_origen_sin_red_ni_escritura(monkeypatch, tmp_path, preparar, origen, hay_token_propio):
    def sin_red(*args, **kwargs):
        raise AssertionError("no debe haber peticiones de red")
    monkeypatch.setattr(copilot.httpx, "get", sin_red)
    monkeypatch.setattr(copilot.httpx, "post", sin_red)
    if preparar:
        preparar(monkeypatch)
    antes = _instantanea(tmp_path)

    estado = copilot.estado_sesion(None)

    assert estado == copilot.EstadoSesion(origen, hay_token_propio)
    assert _instantanea(tmp_path) == antes
    if preparar is None:
        assert not (tmp_path / "app").exists() and not (tmp_path / "opencode").exists()


@pytest.mark.parametrize("token_guardado", [5, ["gho_x"]])
def test_archivo_propio_con_token_que_no_es_texto_no_lanza(token_guardado):
    copilot.RUTA_TOKEN.parent.mkdir(parents=True)
    copilot.RUTA_TOKEN.write_text(json.dumps({"token": token_guardado}))
    assert copilot.leer_token() is None
    assert copilot.estado_sesion(None) == copilot.EstadoSesion(None, False)
    # Igual que un JSON inválido: si hay sesión de opencode, se usa esa
    copilot.RUTA_AUTH_OPENCODE.parent.mkdir(parents=True)
    copilot.RUTA_AUTH_OPENCODE.write_text(json.dumps({"github-copilot": {"refresh": "gho_oc"}}))
    assert copilot.estado_sesion(None) == copilot.EstadoSesion("opencode", False)


@pytest.mark.parametrize("contenido", [b"\xff\xfe\x00", json.dumps({"token": "gho_x", "enterprise_url": 5}).encode()],
                         ids=["no_utf8", "dominio_no_texto"])
def test_archivo_propio_mal_formado_no_lanza(contenido):
    """Un archivo propio que no es UTF-8 o con un dominio que no es texto cuenta como «sin sesión», igual que un JSON
    inválido: ni leer_token ni estado_sesion lanzan."""
    copilot.RUTA_TOKEN.parent.mkdir(parents=True)
    copilot.RUTA_TOKEN.write_bytes(contenido)
    assert copilot.leer_token() is None
    assert copilot.estado_sesion(None).origen is None


@pytest.mark.parametrize("origen, hay_token_propio, texto, puede_iniciar, texto_iniciar, puede_cerrar", [
    (None, False, "No has iniciado sesión en GitHub Copilot.", True, "Iniciar sesión", False),
    (None, True, "No has iniciado sesión en GitHub Copilot. Hay una sesión guardada por la app para otro dominio de "
                 "GitHub.", True, "Iniciar sesión", True),
    ("app", True, "Sesión iniciada con la app. La sesión se comprueba al usarla.", False, None, True),
    ("opencode", False, "Se usa la sesión de opencode. La app no la cierra: ciérrala desde opencode. La sesión se "
                        "comprueba al usarla.", True, "Iniciar sesión con la app", False),
    ("opencode", True, "Se usa la sesión de opencode. La app no la cierra: ciérrala desde opencode. Hay una sesión "
                       "guardada por la app para otro dominio de GitHub. La sesión se comprueba al usarla.",
     True, "Iniciar sesión con la app", True),
    ("variable", False, "Se usa el token de la variable de entorno COPILOT_GITHUB_TOKEN. La app no puede cerrarlo: quita "
                        "la variable para usar otra sesión. La sesión se comprueba al usarla.", False, None, False),
    ("variable", True, "Se usa el token de la variable de entorno COPILOT_GITHUB_TOKEN. La app no puede cerrarlo: quita "
                       "la variable para usar otra sesión. Hay además una sesión guardada por la app que ahora no se "
                       "usa. La sesión se comprueba al usarla.", False, None, True),
])
def test_describir_sesion_texto_y_botones(origen, hay_token_propio, texto, puede_iniciar, texto_iniciar, puede_cerrar):
    descripcion = copilot.describir_sesion(copilot.EstadoSesion(origen, hay_token_propio))
    assert descripcion.texto == texto
    assert descripcion.puede_iniciar is puede_iniciar
    if puede_iniciar:  # el texto del botón solo importa cuando el botón existe
        assert descripcion.texto_iniciar == texto_iniciar
    assert descripcion.puede_cerrar is puede_cerrar


@pytest.mark.parametrize("por_variable", [False, True])
def test_el_token_no_aparece_en_repr_ni_en_los_textos(monkeypatch, por_variable):
    if por_variable:
        monkeypatch.setenv(copilot.VARIABLE_ENTORNO, "gho_secreto")
    else:
        copilot.guardar_token("gho_secreto")
    sesion = copilot.leer_token()
    estado = copilot.estado_sesion(None)
    descripcion = copilot.describir_sesion(estado)
    assert sesion.token == "gho_secreto"  # quien lo pide por su nombre sigue teniéndolo
    for texto in (repr(sesion), repr(estado), descripcion.texto, descripcion.texto_iniciar):
        assert "gho_secreto" not in texto


class _RespuestaSinJSON:
    """Respuesta 200 que no es JSON (p. ej. una página de un portal cautivo)."""
    status_code = 200
    text = "<html>Inicia sesión en la red</html>"

    def json(self):
        raise json.JSONDecodeError("Expecting value", self.text, 0)


def test_codigo_de_dispositivo_con_respuesta_que_no_es_json_da_error_copilot(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _RespuestaSinJSON())
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.iniciar_login()
    assert str(error.value) == "GitHub devolvió una respuesta inesperada al pedir el código de dispositivo."


def test_codigo_de_dispositivo_sin_las_claves_esperadas_da_error_copilot(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta({"user_code": "ABCD-1234"}))
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.iniciar_login()
    assert str(error.value) == "GitHub devolvió una respuesta inesperada al pedir el código de dispositivo."


def test_sondeo_del_token_con_respuesta_inesperada_da_error_copilot(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta({"foo": 1}))  # ni token ni error
    codigo = copilot.CodigoDispositivo("dc", "X", "https://github.com/login/device", 5, 900)
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.esperar_login(codigo, dormir=lambda s: pytest.fail("no debe reintentar ante una respuesta inesperada"))
    assert str(error.value) == "GitHub devolvió una respuesta inesperada al consultar la autorización."


def test_intervalo_de_sondeo_que_no_es_un_numero_usa_el_valor_por_defecto(monkeypatch):
    # Como cuando falta el campo: 5 s al pedir el código y el intervalo actual + 5 s con slow_down
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(
        {"device_code": "dc", "user_code": "ABCD", "verification_uri": "https://github.com/login/device",
         "interval": "rapido"}))
    assert copilot.iniciar_login().interval == 5
    respuestas = iter([_Respuesta({"error": "slow_down", "interval": "lento"}), _Respuesta({"access_token": "gho_ok"})])
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: next(respuestas))
    esperas = []
    codigo = copilot.CodigoDispositivo("dc", "ABCD", "https://github.com/login/device", 5, 900)
    assert copilot.esperar_login(codigo, dormir=esperas.append) == "gho_ok"
    assert esperas == [5 + 5 + copilot.ESPERA_EXTRA]


def test_device_flow_espera_autorizacion_y_guarda_token(monkeypatch):
    respuestas = iter([
        _Respuesta({"device_code": "dc", "user_code": "ABCD-1234", "verification_uri": "https://github.com/login/device",
                    "interval": 5, "expires_in": 900}),
        _Respuesta({"error": "authorization_pending"}),
        _Respuesta({"error": "slow_down", "interval": 10}),
        _Respuesta({"access_token": "gho_nuevo", "token_type": "bearer"}),
    ])
    peticiones = []
    monkeypatch.setattr(copilot.httpx, "post",
                        lambda url, json, headers, timeout: peticiones.append((url, json)) or next(respuestas))
    esperas = []

    codigo = copilot.iniciar_login()
    assert codigo.user_code == "ABCD-1234"
    assert peticiones[0] == ("https://github.com/login/device/code",
                             {"client_id": copilot.CLIENT_ID, "scope": "read:user"})
    assert copilot.esperar_login(codigo, dormir=esperas.append) == "gho_nuevo"
    assert peticiones[-1][0] == "https://github.com/login/oauth/access_token"
    assert esperas == [5 + copilot.ESPERA_EXTRA, 10 + copilot.ESPERA_EXTRA]  # respeta slow_down
    assert copilot.leer_token().token == "gho_nuevo"


def test_device_flow_denegado(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta({"error": "access_denied"}))
    codigo = copilot.CodigoDispositivo("dc", "X", "https://github.com/login/device", 5, 900)
    with pytest.raises(copilot.ErrorCopilot):
        copilot.esperar_login(codigo, dormir=lambda s: None)


def test_device_flow_cancelable(monkeypatch):
    cancelar = threading.Event()
    cancelar.set()
    codigo = copilot.CodigoDispositivo("dc", "X", "https://github.com/login/device", 5, 900)
    with pytest.raises(InterruptedError):
        copilot.esperar_login(codigo, cancelar, dormir=lambda s: None)


def test_listar_modelos_filtra_los_de_chat_habilitados(monkeypatch):
    # Como responde la API real: model_picker_enabled en False para todos; lo que cuenta es policy.state
    habilitado = {"model_picker_enabled": False, "policy": {"state": "enabled"}}
    datos = {"data": [
        {"id": "gpt-4.1", **habilitado, "capabilities": {"type": "chat"}},
        {"id": "gpt-6-luna", **habilitado, "supported_endpoints": ["/responses", "ws:/responses"]},
        {"id": "text-embedding-3-small", **habilitado, "capabilities": {"type": "embeddings"}},
        {"id": "claude-opus-5", "model_picker_enabled": False, "policy": {"state": "disabled"}},
        {"id": "gpt-4o", "model_picker_enabled": False},  # sin política: modelo antiguo o interno
        {"id": "claude-haiku-4.5", **habilitado, "supported_endpoints": ["/chat/completions", "/v1/messages"]},
    ]}
    monkeypatch.setattr(copilot.httpx, "get", lambda url, headers, timeout: _Respuesta(datos))
    ids = [m["id"] for m in copilot.listar_modelos(copilot.Sesion("gho_x"))]
    assert ids == ["claude-haiku-4.5", "gpt-4.1"]


def test_listar_modelos_con_respuesta_inesperada_da_error_copilot(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "get", lambda url, headers, timeout: _Respuesta({"foo": 1}))  # sin "data"
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.listar_modelos(copilot.Sesion("gho_x"))
    assert str(error.value) == "GitHub devolvió una respuesta inesperada al pedir la lista de modelos."


def test_limites_de_entrada_del_catalogo(monkeypatch):
    datos = {"data": [
        {"id": "gpt-4.1", "policy": {"state": "enabled"}, "capabilities": {"limits": {"max_prompt_tokens": 64000}}},
        # Sin filtro de habilitados: el modelo con el que se generó puede no estar en el selector
        {"id": "claude-haiku-5.5", "model_picker_enabled": False,
         "capabilities": {"limits": {"max_prompt_tokens": 936000}}},
        {"id": "sin-max-prompt", "capabilities": {"limits": {"max_output_tokens": 16384}}},
        {"id": "sin-capacidades"},
        {"id": "capacidades-de-texto", "capabilities": "chat"},
        {"id": "limite-de-texto", "capabilities": {"limits": {"max_prompt_tokens": "64000"}}},
        {"id": "limite-cero", "capabilities": {"limits": {"max_prompt_tokens": 0}}},
        {"id": "limite-negativo", "capabilities": {"limits": {"max_prompt_tokens": -1}}},
        {"id": "limite-decimal", "capabilities": {"limits": {"max_prompt_tokens": 64000.0}}},
        {"id": "limite-booleano", "capabilities": {"limits": {"max_prompt_tokens": True}}},
    ]}
    monkeypatch.setattr(copilot.httpx, "get", lambda url, headers, timeout: _Respuesta(datos))
    assert copilot.limites_de_entrada(copilot.Sesion("gho_x")) == {"gpt-4.1": 64000, "claude-haiku-5.5": 936000}


def test_sin_sesion_lanza_error_especifico():
    with pytest.raises(ErrorSinSesionCopilot):
        AsistenteIA()


class _Stream:
    def __init__(self, status_code=200, texto="", contenido="OK"):
        self.status_code, self.text, self.contenido = status_code, texto, contenido
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def read(self):
        pass
    def iter_lines(self):
        yield "data: " + json.dumps({"choices": [{"delta": {"content": self.contenido}, "finish_reason": "stop"}]})
        yield "data: [DONE]"


def test_peticion_a_copilot_con_cabeceras_de_opencode(monkeypatch):
    copilot.guardar_token("gho_abc")
    enviado = []
    monkeypatch.setattr(asistente_ia.httpx, "stream",
                        lambda metodo, url, json, headers, timeout: enviado.append((url, headers)) or _Stream())
    asistente = AsistenteIA(modelo="gpt-4.1")
    assert asistente._completar("hola") == "OK"
    url, cabeceras = enviado[0]
    assert url == "https://api.githubcopilot.com/chat/completions"
    assert cabeceras["Authorization"] == "Bearer gho_abc"
    assert cabeceras["X-GitHub-Api-Version"] == copilot.API_VERSION
    assert cabeceras["Openai-Intent"] == "conversation-edits"


def test_solo_la_primera_peticion_de_cada_documento_es_del_usuario(monkeypatch):
    iniciadores = []
    documento = "## Resumen\nt\n### Puntos clave\n- a\n### Conclusiones\n- b"
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        iniciadores.append(headers["x-initiator"]) or _Stream(contenido=documento))
    asistente = AsistenteIA(api_key="gho_x", revision_fidelidad=True)
    asistente.generar_resumen("texto")  # documento + revisión de fidelidad
    asistente.generar_resumen("otro texto")
    assert iniciadores == ["user", "agent", "user", "agent"]


def test_reintenta_sin_temperatura_si_el_modelo_no_la_admite(monkeypatch):
    cuerpos = []
    respuestas = iter([_Stream(400, '{"error":{"message":"Unsupported value: \'temperature\'"}}'), _Stream()])
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        cuerpos.append(dict(json)) or next(respuestas))
    AsistenteIA(api_key="gho_x", modelo="gpt-5-mini")._completar("hola")
    assert "temperature" in cuerpos[0] and "temperature" not in cuerpos[1]


def test_401_invalida_el_token_propio(monkeypatch):
    copilot.guardar_token("gho_revocado")
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: _Stream(401, "unauthorized"))
    with pytest.raises(ErrorSinSesionCopilot):
        AsistenteIA()._completar("hola")
    assert copilot.leer_token() is None  # la próxima vez se pide iniciar sesión


def _catalogo(*modelos):
    return _Respuesta({"data": [{"id": i, "supported_endpoints": e} for i, e in modelos]})


def test_familia_excluida_reconoce_kimi_y_mistral_sin_distinguir_mayusculas():
    assert copilot.familia_excluida("Mistral-Large-3") == "mistral"
    assert copilot.familia_excluida("kimi-k3-mini") == "kimi"
    assert copilot.familia_excluida("gpt-5.4") is None
    assert copilot.familia_excluida("claude-haiku-5.5") is None


@pytest.mark.parametrize("modelo, excluido", [
    ("codestral-2501", True), ("Devstral-Medium", True), ("ministral-8b", True), ("pixtral-large", True),
    ("magistral-medium", True), ("gpt-5.4", False), ("claude-haiku-5.5", False),
])
def test_familia_excluida_reconoce_todos_los_modelos_de_mistral_ai(modelo, excluido):
    assert (copilot.familia_excluida(modelo) is not None) == excluido


def test_familia_excluida_tolera_valores_que_no_son_cadena():
    assert copilot.familia_excluida(None) is None
    assert copilot.familia_excluida("") is None
    assert copilot.familia_excluida(5) is None


def test_modelos_economicos_excluye_caros_sin_precio_prohibidos_y_duplicados(monkeypatch):
    def modelo(id_modelo, precio, nombre=None):
        datos = {"id": id_modelo, "name": nombre or id_modelo, "policy": {"state": "enabled"}}
        if precio is not None:
            datos["billing"] = {"token_prices": {"default": {"input_price": precio, "output_price": precio * 5}}}
        return datos
    datos = {"data": [
        modelo("claude-sonnet-5.5", 200),
        modelo("claude-haiku-5.5", 10),
        modelo("gpt-4.1", 0, "GPT-4.1"),
        modelo("gpt-4.1-2025-04-14", 0, "GPT-4.1"),
        modelo("gemini-3.8-flash", 75),
        modelo("kimi-k3-mini", 5),
        modelo("modelo-sin-precio", None),
    ]}
    monkeypatch.setattr(copilot.httpx, "get", lambda url, headers, timeout: _Respuesta(datos))
    assert copilot.modelos_economicos(copilot.Sesion("gho_x")) == ["gpt-4.1", "claude-haiku-5.5"]


def test_sesion_auto_con_respuesta_inesperada_da_error_copilot(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta({"selected_model": "gpt-5.4"}))  # sin claves
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.abrir_sesion_auto(copilot.Sesion("gho_x"))
    assert str(error.value) == "GitHub devolvió una respuesta inesperada al abrir la sesión de modo auto."


def test_sesion_auto_con_caducidad_que_no_es_un_numero_da_error_copilot(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(
        {"available_models": ["gpt-5.4"], "selected_model": "gpt-5.4", "session_token": "st", "expires_at": "pronto"}))
    monkeypatch.setattr(copilot.httpx, "get", lambda *a, **kw: _catalogo(("gpt-5.4", ["/chat/completions"])))
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.abrir_sesion_auto(copilot.Sesion("gho_x"))
    assert str(error.value) == "GitHub devolvió una respuesta inesperada al abrir la sesión de modo auto."


def test_sesion_auto_con_modelos_que_no_son_texto_da_error_copilot(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(
        {"available_models": [{"id": "gpt-5.4"}], "selected_model": "gpt-5.4", "session_token": "st",
         "expires_at": 9999999999}))
    monkeypatch.setattr(copilot.httpx, "get", lambda *a, **kw: pytest.fail("no debe consultarse el catálogo"))
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.abrir_sesion_auto(copilot.Sesion("gho_x"))
    assert str(error.value) == "GitHub devolvió una respuesta inesperada al abrir la sesión de modo auto."


def test_auto_salta_modelos_que_solo_admiten_responses(monkeypatch):
    enviado = {}
    sesion = {"available_models": ["gpt-5.3-codex", "gpt-5.4-mini", "claude-haiku-4.5", "gpt-5.4"],
              "selected_model": "gpt-5.3-codex", "session_token": "st", "expires_at": 9999999999,
              "discounted_costs": {"gpt-5.4": 0.1}}
    monkeypatch.setattr(copilot.httpx, "post", lambda url, headers, json, timeout:
                        enviado.update(url=url, cuerpo=json) or _Respuesta(sesion))
    monkeypatch.setattr(copilot.httpx, "get", lambda url, headers, timeout: _catalogo(
        ("gpt-5.3-codex", ["/responses"]), ("gpt-5.4-mini", ["/responses"]),
        ("claude-haiku-4.5", ["/chat/completions", "/v1/messages"]), ("gpt-5.4", ["/responses", "/chat/completions"])))
    auto = copilot.abrir_sesion_auto(copilot.Sesion("gho_x"))
    assert enviado["url"] == "https://api.githubcopilot.com/models/session"
    assert enviado["cuerpo"] == {"auto_mode": {"model_hints": ["auto"]}}
    assert auto.modelo == "claude-haiku-4.5" and auto.session_token == "st" and auto.vigente()


def test_auto_salta_modelos_de_familias_excluidas(monkeypatch):
    sesion = {"available_models": ["kimi-k3", "mistral-medium-3", "gpt-5.4"], "selected_model": "kimi-k3",
              "session_token": "st", "expires_at": 9999999999}
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(sesion))
    monkeypatch.setattr(copilot.httpx, "get", lambda *a, **kw: _catalogo(
        ("kimi-k3", ["/chat/completions"]), ("mistral-medium-3", ["/chat/completions"]),
        ("gpt-5.4", ["/chat/completions"])))
    assert copilot.abrir_sesion_auto(copilot.Sesion("gho_x")).modelo == "gpt-5.4"


def test_auto_sin_modelo_autorizado_y_compatible_lanza_error(monkeypatch):
    sesion = {"available_models": ["mistral-medium-3", "gpt-5.3-codex"], "selected_model": "mistral-medium-3",
              "session_token": "st", "expires_at": 9999999999}
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(sesion))
    monkeypatch.setattr(copilot.httpx, "get", lambda *a, **kw: _catalogo(
        ("mistral-medium-3", ["/chat/completions"]), ("gpt-5.3-codex", ["/responses"])))
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.abrir_sesion_auto(copilot.Sesion("gho_x"))
    assert "mistral-medium-3" in str(error.value) and "gpt-5.3-codex" in str(error.value)
    assert "autorizado" in str(error.value)


def test_auto_sin_modelos_compatibles(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(
        {"available_models": ["gpt-5.3-codex"], "session_token": "st", "expires_at": 9999999999}))
    monkeypatch.setattr(copilot.httpx, "get", lambda *a, **kw: _catalogo(("gpt-5.3-codex", ["/responses"])))
    with pytest.raises(copilot.ErrorCopilot):
        copilot.abrir_sesion_auto(copilot.Sesion("gho_x"))


def test_asistente_en_modo_auto_envia_session_token_y_reutiliza_la_sesion(monkeypatch):
    import time as _time
    aperturas, enviado = [], []
    def abrir(sesion):
        aperturas.append(sesion.token)
        return copilot.SesionAuto("gpt-5.4", f"st{len(aperturas)}", _time.time() + 3600, ["gpt-5.4"], {})
    monkeypatch.setattr(copilot, "abrir_sesion_auto", abrir)
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviado.append((json["model"], headers.get("Copilot-Session-Token"))) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo="auto")
    asistente._completar("uno")
    asistente._completar("dos")
    assert enviado == [("gpt-5.4", "st1"), ("gpt-5.4", "st1")]
    assert len(aperturas) == 1  # la sesión se reutiliza mientras esté vigente
    assert asistente.modelo_usado == "auto → gpt-5.4"


def test_auto_renueva_la_sesion_cerca_de_caducar(monkeypatch):
    import time as _time
    caducidades = iter([_time.time() + 60, _time.time() + 3600])  # la primera vence en 1 min (< margen de 5)
    aperturas = []
    monkeypatch.setattr(copilot, "abrir_sesion_auto", lambda s: aperturas.append(1) or
                        copilot.SesionAuto("gpt-5.4", "st", next(caducidades), ["gpt-5.4"], {}))
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo="auto")
    asistente._completar("uno")
    asistente._completar("dos")
    assert len(aperturas) == 2


def test_auto_401_abre_nueva_sesion_sin_borrar_el_token(monkeypatch):
    import time as _time
    copilot.guardar_token("gho_valido")
    tokens = iter(["st_caducado", "st_nuevo"])
    monkeypatch.setattr(copilot, "abrir_sesion_auto", lambda s:
                        copilot.SesionAuto("gpt-5.4", next(tokens), _time.time() + 3600, ["gpt-5.4"], {}))
    respuestas = iter([_Stream(401, "session expired"), _Stream()])
    usados = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        usados.append(headers["Copilot-Session-Token"]) or next(respuestas))
    assert AsistenteIA(modelo="auto")._completar("hola") == "OK"
    assert usados == ["st_caducado", "st_nuevo"]
    assert copilot.leer_token().token == "gho_valido"


def test_opciones_de_modelo_incluyen_el_configurado_si_esta_autorizado():
    opciones = copilot.opciones_de_modelo(["auto", "claude-haiku-5.5"], "gpt-5.4")
    assert opciones == ["auto", "claude-haiku-5.5", "gpt-5.4"]


def test_opciones_de_modelo_no_incluyen_un_configurado_de_familia_excluida():
    opciones = copilot.opciones_de_modelo(["auto", "claude-haiku-5.5"], "kimi-k3")
    assert opciones == ["auto", "claude-haiku-5.5"]


def test_codigo_de_dispositivo_con_caducidad_que_no_es_un_numero_no_revienta(monkeypatch):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(
        {"device_code": "dc", "user_code": "ABCD-1234", "verification_uri": "https://github.com/login/device",
         "expires_in": "pronto"}))
    codigo = copilot.iniciar_login()
    assert codigo.expires_in == 900  # el mismo valor por defecto que cuando falta el campo


@pytest.mark.parametrize("disponibles", [None, "gpt-5.4", {"a": 1}])
def test_sesion_auto_con_modelos_nulos_da_error_copilot(monkeypatch, disponibles):
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(
        {"available_models": disponibles, "selected_model": "gpt-5.4", "session_token": "st",
         "expires_at": 9999999999}))
    monkeypatch.setattr(copilot.httpx, "get", lambda *a, **kw: pytest.fail("no debe consultarse el catálogo"))
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.abrir_sesion_auto(copilot.Sesion("gho_x"))
    assert str(error.value) == "GitHub devolvió una respuesta inesperada al abrir la sesión de modo auto."


@pytest.mark.parametrize("data", [None, 5, ["x"]])
def test_listar_modelos_con_data_inesperado_da_error_copilot(monkeypatch, data):
    monkeypatch.setattr(copilot.httpx, "get", lambda url, headers, timeout: _Respuesta({"data": data}))
    with pytest.raises(copilot.ErrorCopilot) as error:
        copilot.listar_modelos(copilot.Sesion("gho_x"))
    assert str(error.value) == "GitHub devolvió una respuesta inesperada al pedir la lista de modelos."


@pytest.mark.parametrize("data", [None, 5, ["x"], [{"id": ["lista"]}], [{"id": None}]])
def test_sesion_auto_con_catalogo_de_formato_inesperado_sigue_sin_endpoints(monkeypatch, data):
    sesion = {"available_models": ["mistral-medium-3", "gpt-5.4"], "selected_model": "mistral-medium-3",
              "session_token": "st", "expires_at": 9999999999}
    monkeypatch.setattr(copilot.httpx, "post", lambda *a, **kw: _Respuesta(sesion))
    monkeypatch.setattr(copilot.httpx, "get", lambda *a, **kw: _Respuesta({"data": data}))
    assert copilot.abrir_sesion_auto(copilot.Sesion("gho_x")).modelo == "gpt-5.4"


def test_cargar_opciones_hace_una_sola_consulta_y_no_abre_sesion_auto(monkeypatch):
    gets, posts = [], []
    datos = {"data": [{"id": "claude-haiku-5.5", "policy": {"state": "enabled"},
                       "billing": {"token_prices": {"default": {"input_price": 10}}}}]}

    def get(url, headers, timeout):
        gets.append(url)
        return _Respuesta(datos)

    monkeypatch.setattr(copilot.httpx, "get", get)
    monkeypatch.setattr(copilot.httpx, "post", lambda url, **kw: posts.append(url) or _Respuesta({}))

    copilot.cargar_opciones_de_modelo(copilot.Sesion("gho_x"), "claude-haiku-5.5")

    assert len(gets) == 1 and gets[0].endswith("/models")
    assert posts == []


def test_cargar_opciones_incluye_auto_y_el_modelo_actual(monkeypatch):
    datos = {"data": [
        {"id": "claude-haiku-5.5", "policy": {"state": "enabled"},
         "billing": {"token_prices": {"default": {"input_price": 10}}}},
        {"id": "claude-sonnet-5.5", "policy": {"state": "enabled"},
         "billing": {"token_prices": {"default": {"input_price": 200}}}},
    ]}
    monkeypatch.setattr(copilot.httpx, "get", lambda url, headers, timeout: _Respuesta(datos))

    opciones = copilot.cargar_opciones_de_modelo(copilot.Sesion("gho_x"), "gpt-4.1")

    assert opciones == ["auto", "claude-haiku-5.5", "gpt-4.1"]


def test_cargar_opciones_no_incluye_familias_excluidas(monkeypatch):
    datos = {"data": [
        {"id": "claude-haiku-5.5", "policy": {"state": "enabled"},
         "billing": {"token_prices": {"default": {"input_price": 10}}}},
        {"id": "kimi-k3-mini", "policy": {"state": "enabled"},
         "billing": {"token_prices": {"default": {"input_price": 5}}}},
    ]}
    monkeypatch.setattr(copilot.httpx, "get", lambda url, headers, timeout: _Respuesta(datos))

    opciones = copilot.cargar_opciones_de_modelo(copilot.Sesion("gho_x"), "mistral-medium-3")

    assert opciones == ["auto", "claude-haiku-5.5"]


def test_opciones_de_modelo_nunca_incluyen_familias_excluidas_aunque_lleguen_en_la_lista():
    opciones = copilot.opciones_de_modelo(["auto", "gpt-5.4", "kimi-k3-mini", "Mistral-Large-3"], "claude-haiku-5.5")
    assert opciones == ["auto", "gpt-5.4", "claude-haiku-5.5"]


def test_cerrar_sesion_propia_no_toca_opencode(monkeypatch):
    copilot.guardar_token("gho_app")
    copilot.RUTA_AUTH_OPENCODE.parent.mkdir(parents=True)
    copilot.RUTA_AUTH_OPENCODE.write_text('{"github-copilot": {"refresh": "gho_oc"}}', encoding="utf-8")
    antes = (copilot.RUTA_AUTH_OPENCODE.read_bytes(), copilot.RUTA_AUTH_OPENCODE.stat().st_mtime_ns)

    def sin_red(*args, **kwargs):
        raise AssertionError("cerrar_sesion_propia no debe hacer peticiones de red")

    monkeypatch.setattr(copilot.httpx, "get", sin_red)
    monkeypatch.setattr(copilot.httpx, "post", sin_red)

    estado = copilot.cerrar_sesion_propia(None)

    assert estado == copilot.EstadoSesion(copilot.ORIGEN_OPENCODE, False)
    assert not copilot.RUTA_TOKEN.exists()
    assert (copilot.RUTA_AUTH_OPENCODE.read_bytes(), copilot.RUTA_AUTH_OPENCODE.stat().st_mtime_ns) == antes
    assert copilot.cerrar_sesion_propia(None) == estado


def test_cerrar_sesion_propia_con_la_variable_sigue_en_la_variable(monkeypatch):
    monkeypatch.setenv(copilot.VARIABLE_ENTORNO, "gho_variable")
    copilot.guardar_token("gho_app")

    estado = copilot.cerrar_sesion_propia(None)

    assert estado == copilot.EstadoSesion(copilot.ORIGEN_VARIABLE, False)
    assert os.environ[copilot.VARIABLE_ENTORNO] == "gho_variable"
    assert not copilot.RUTA_TOKEN.exists()


def test_cerrar_sesion_propia_propaga_oserror(monkeypatch):
    copilot.guardar_token("gho_app")

    def sin_permiso(self, *args, **kwargs):
        raise PermissionError("permiso denegado")

    monkeypatch.setattr(type(copilot.RUTA_TOKEN), "unlink", sin_permiso)

    with pytest.raises(OSError):
        copilot.cerrar_sesion_propia(None)

    assert copilot.RUTA_TOKEN.exists()
    assert copilot.leer_token().token == "gho_app"
