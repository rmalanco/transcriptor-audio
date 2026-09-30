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
