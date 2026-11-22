"""Tests del asistente de IA (sin llamadas reales a la API)."""

import pytest
from src import asistente_ia, copilot
from src.asistente_ia import AsistenteIA, ErrorAsistenteIA, dividir_texto


class _Respuesta:
    def __init__(self, datos):
        self.datos, self.status_code, self.text = datos, 200, ""

    def json(self):
        return self.datos


class _Stream:
    """Respuesta de chat simulada; con `status_code` distinto de 200 simula un error (el contenido no importa)."""
    def __init__(self, status_code=200):
        self.status_code, self.text = status_code, ""
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def read(self):
        pass
    def iter_lines(self):
        import json
        yield "data: " + json.dumps({"choices": [{"delta": {"content": "OK"}, "finish_reason": "stop"}]})
        yield "data: [DONE]"


TEXTO_LARGO = "\n".join(f"Segmento {i} con algo de contenido." for i in range(40))


@pytest.fixture(autouse=True)
def rutas_aisladas(monkeypatch, tmp_path):
    """Como el fixture homónimo de test_copilot.py: el token real del equipo nunca se lee ni se toca."""
    monkeypatch.setattr(copilot, "RUTA_TOKEN", tmp_path / "app" / "copilot.json")
    monkeypatch.setattr(copilot, "RUTA_AUTH_OPENCODE", tmp_path / "opencode" / "auth.json")
    monkeypatch.delenv(copilot.VARIABLE_ENTORNO, raising=False)


def _prohibir_red(monkeypatch):
    """Si el código consulta el catálogo o abre una sesión por GET/POST, el test falla en vez de hacer red."""
    def prohibido(*a, **kw):
        raise AssertionError("no debe haber ninguna petición de catálogo ni de sesión")
    monkeypatch.setattr(asistente_ia.httpx, "get", prohibido)
    monkeypatch.setattr(asistente_ia.httpx, "post", prohibido)


def test_dividir_texto_corto_no_divide():
    assert dividir_texto("hola\nmundo", 100) == ["hola\nmundo"]


def test_dividir_texto_respeta_limite_y_contenido():
    texto = "\n".join(f"Línea número {i} de la transcripción." for i in range(200))
    bloques = dividir_texto(texto, 500)
    assert len(bloques) > 1
    assert all(len(b) <= 500 for b in bloques)
    assert "".join(bloques) == texto


def test_dividir_texto_equilibra_bloques():
    # 61 000 caracteres con límite 60 000: dos bloques parejos, no 60 000 + 1 000
    texto = "".join(f"Segmento {i:05d} " + "x" * 84 + "\n" for i in range(610))
    bloques = dividir_texto(texto, 60000)
    assert len(bloques) == 2
    assert min(map(len, bloques)) > 0.9 * max(map(len, bloques))
    assert "".join(bloques) == texto


def test_bloques_se_analizan_en_paralelo_y_notas_se_reutilizan(monkeypatch):
    import threading, time
    from src.asistente_ia import SECCIONES_MINUTA, SECCIONES_RESUMEN
    documento = "\n".join(f"{s}\ncontenido" for s in SECCIONES_MINUTA + SECCIONES_RESUMEN)
    llamadas, simultaneas, activas, cerrojo = [], [], [0], threading.Lock()

    def completar(prompt, cancelar=None):
        with cerrojo:
            llamadas.append(prompt)
            activas[0] += 1
            simultaneas.append(activas[0])
        time.sleep(0.05)
        with cerrojo:
            activas[0] -= 1
        return documento

    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=300, revision_fidelidad=False,
                                 peticiones_paralelas=3)
    monkeypatch.setattr(asistente, "_completar", completar)
    texto = "\n".join(f"Segmento {i} con algo de contenido." for i in range(40))
    n_bloques = len(dividir_texto(texto, 300))
    assert n_bloques >= 3

    asistente.generar_resumen(texto)
    assert len(llamadas) == n_bloques + 1
    assert max(simultaneas) > 1  # hubo partes analizándose a la vez

    asistente.generar_minuta(texto)
    assert len(llamadas) == n_bloques + 2  # la minuta reutiliza las notas: solo 1 llamada más


def test_texto_largo_se_procesa_por_bloques(monkeypatch):
    llamadas = []
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=300, revision_fidelidad=False)
    from src.asistente_ia import SECCIONES_MINUTA
    completa = "\n".join(f"{s}\ncontenido" for s in SECCIONES_MINUTA)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: llamadas.append(prompt) or completa)
    texto = "\n".join(f"Segmento {i} con algo de contenido." for i in range(40))
    assert asistente.generar_minuta(texto).startswith("# Minuta")
    # N llamadas de notas por bloque + 1 para el documento final
    assert len(llamadas) == len(dividir_texto(texto, 300)) + 1
    assert "# Minuta" in llamadas[-1]


def test_limpiar_respuesta_quita_bloque_de_codigo():
    from src.asistente_ia import limpiar_respuesta
    assert limpiar_respuesta("```markdown\n# Minuta\ntexto\n```") == "# Minuta\ntexto"
    assert limpiar_respuesta("# Minuta\ntexto") == "# Minuta\ntexto"


def test_minuta_usa_fecha_de_la_app(monkeypatch):
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    monkeypatch.setattr(asistente, "_completar",
                        lambda prompt, cancelar=None: "# Minuta: X\n\n**Fecha:** Viernes 15 de noviembre\n")
    minuta = asistente.generar_minuta("texto", fecha="29 de septiembre de 2026")
    assert "**Fecha:** 29 de septiembre de 2026" in minuta
    assert "noviembre" not in minuta


def test_secciones_faltantes():
    from src.asistente_ia import secciones_faltantes, SECCIONES_RESUMEN
    doc = "## Resumen\ntexto\n\n### Puntos clave\n- a\n"
    assert secciones_faltantes(doc, SECCIONES_RESUMEN) == ["### Conclusiones"]
    assert secciones_faltantes(doc + "\n### Conclusiones\n- b\n", SECCIONES_RESUMEN) == []


def test_reintenta_si_falta_una_seccion(monkeypatch):
    respuestas = iter([
        "## Resumen\ntexto\n\n### Puntos clave\n- a",
        "## Resumen\ntexto\n\n### Puntos clave\n- a\n\n### Conclusiones\n- b",
    ])
    llamadas = []
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    monkeypatch.setattr(asistente, "_completar",
                        lambda prompt, cancelar=None: llamadas.append(prompt) or next(respuestas))
    resumen = asistente.generar_resumen("texto de prueba")
    assert "### Conclusiones" in resumen
    assert len(llamadas) == 2
    assert "### Conclusiones" in llamadas[1][-1]["content"]  # el reintento indica qué falta


def test_no_reintenta_si_esta_completo(monkeypatch):
    llamadas = []
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    completo = "## Resumen\nt\n### Puntos clave\n- a\n### Conclusiones\n- b"
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: llamadas.append(prompt) or completo)
    asistente.generar_resumen("texto")
    assert len(llamadas) == 1


def test_normalizar_tabla_tareas():
    from src.asistente_ia import normalizar_tabla_tareas
    tabla = ("| Tarea | Responsable | Fecha límite |\n"
             "| Rediseñar registro | Ana | No asignado |\n"
             "| Revisar botón | No asignado | Miércoles |")
    resultado = normalizar_tabla_tareas(tabla)
    assert "| Ana | Sin fecha |" in resultado
    assert "| No asignado | Miércoles |" in resultado  # el responsable no se toca


def test_revision_de_fidelidad_reemplaza_documento(monkeypatch):
    completo = "## Resumen\nsujeto a confirmación del proveedor\n### Puntos clave\n- a\n### Conclusiones\n- b"
    corregido = completo.replace("sujeto a confirmación del proveedor", "si no hay problemas con el proveedor")
    respuestas = iter([completo, corregido])
    llamadas = []
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar",
                        lambda prompt, cancelar=None: llamadas.append(prompt) or next(respuestas))
    resumen = asistente.generar_resumen("si no hay problemas con el proveedor")
    assert "si no hay problemas con el proveedor" in resumen
    assert "TRANSCRIPCIÓN" in llamadas[1] and "DOCUMENTO" in llamadas[1]


def test_revision_que_pierde_secciones_se_descarta(monkeypatch):
    completo = "## Resumen\nt\n### Puntos clave\n- a\n### Conclusiones\n- b"
    respuestas = iter([completo, "## Resumen\nsolo esto"])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))
    assert asistente.generar_resumen("texto") == completo


class _RespuestaFalsa:
    """Respuesta en streaming (SSE) de un modelo con razonamiento: razonamiento, contenido en trozos y uso al final."""
    status_code = 200
    eventos = [
        {"choices": [{"delta": {"role": "assistant", "content": ""}}]},
        {"choices": [{"delta": {"reasoning_content": "pensando..."}}]},
        {"choices": [{"delta": {"content": "O"}}]},
        {"choices": [{"delta": {"content": "K"}, "finish_reason": "stop",
                      "usage": {"prompt_tokens": 5, "completion_tokens": 3}}]},
    ]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_lines(self):
        import json
        for e in self.eventos:
            yield "data: " + json.dumps(e)
            yield ""
        yield "data: [DONE]"


def test_stream_ignora_razonamiento_y_une_los_trozos(monkeypatch):
    enviado = {}
    def stream(metodo, url, json, headers, timeout):
        enviado.update(url=url, cuerpo=json)
        return _RespuestaFalsa()
    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    asistente = AsistenteIA(api_key="x", modelo="gpt-5.4", temperatura=0.2)
    assert asistente._completar("hola") == "OK"
    assert enviado["url"] == "https://api.githubcopilot.com/chat/completions"
    assert enviado["cuerpo"]["temperature"] == 0.2
    assert enviado["cuerpo"]["stream"] is True


def test_timeout_es_por_inactividad_no_total(monkeypatch):
    """Con streaming, `timeout` limita el tiempo sin recibir datos: una respuesta larga no se corta."""
    enviado = {}
    monkeypatch.setattr(asistente_ia.httpx, "stream",
                        lambda metodo, url, json, headers, timeout: enviado.update(timeout=timeout) or _RespuestaFalsa())
    AsistenteIA(api_key="x", timeout=180)._completar("hola")
    assert enviado["timeout"].read == 180


def test_cancelar_durante_el_stream(monkeypatch):
    import threading
    cancelar = threading.Event()
    class RespuestaQueCancela(_RespuestaFalsa):
        def iter_lines(self):
            cancelar.set()  # el usuario cancela mientras llegan datos
            yield from super().iter_lines()
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: RespuestaQueCancela())
    with pytest.raises(InterruptedError):
        AsistenteIA(api_key="x")._completar("hola", cancelar)


FAMILIAS_EXCLUIDAS_A_MANO = [("Mistral-Large-3", "mistral"), ("kimi-k3-mini", "kimi")]


@pytest.mark.parametrize("modelo, familia", FAMILIAS_EXCLUIDAS_A_MANO)
def test_modelo_excluido_escrito_a_mano_no_envia_nada(monkeypatch, modelo, familia):
    enviados = []
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append((url, json["model"])) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo=modelo, max_caracteres_bloque=300, revision_fidelidad=False)
    assert len(dividir_texto(TEXTO_LARGO, 300)) > 1  # la transcripción se procesaría en varias partes
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(TEXTO_LARGO)
    assert enviados == []
    assert modelo in str(error.value) and familia in str(error.value) and "autorizad" in str(error.value)


@pytest.mark.parametrize("modelo, familia", FAMILIAS_EXCLUIDAS_A_MANO)
def test_modelo_excluido_no_depende_del_catalogo(monkeypatch, modelo, familia):
    enviados, consultas = [], []
    _prohibir_red(monkeypatch)  # las sesiones por POST tampoco deben abrirse
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append((url, json["model"])) or _Stream())
    def catalogo_caido(*a, **kw):
        consultas.append(1)
        raise asistente_ia.httpx.ConnectError("sin conexión")
    monkeypatch.setattr(asistente_ia.httpx, "get", catalogo_caido)
    asistente = AsistenteIA(api_key="gho_x", modelo=modelo, max_caracteres_bloque=300, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(TEXTO_LARGO)
    assert enviados == []
    assert consultas == []  # con un modelo fijo ni siquiera se consulta el catálogo
    assert modelo in str(error.value) and familia in str(error.value) and "autorizad" in str(error.value)


def _simular_auto(monkeypatch, sesiones, catalogo):
    """Copilot en modo auto: cada apertura de sesión recibe la siguiente de `sesiones`; `catalogo` da los
    endpoints de cada modelo ({id: [endpoints]})."""
    respuestas = iter(sesiones)
    monkeypatch.setattr(asistente_ia.copilot.httpx, "post", lambda *a, **kw: _Respuesta(next(respuestas)))
    monkeypatch.setattr(asistente_ia.copilot.httpx, "get", lambda *a, **kw: _Respuesta(
        {"data": [{"id": i, "supported_endpoints": e} for i, e in catalogo.items()]}))


def test_auto_envia_todas_las_peticiones_al_modelo_autorizado(monkeypatch):
    _simular_auto(monkeypatch,
                  [{"available_models": ["kimi-k3", "mistral-medium-3", "gpt-5.4"], "selected_model": "kimi-k3",
                    "session_token": "st", "expires_at": 9999999999}],
                  {"kimi-k3": ["/chat/completions"], "mistral-medium-3": ["/chat/completions"],
                   "gpt-5.4": ["/chat/completions"]})
    enviados = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append(json["model"]) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo="auto", max_caracteres_bloque=300, revision_fidelidad=False)
    asistente.generar_minuta(TEXTO_LARGO)
    assert len(enviados) > 1  # varias partes: todas las peticiones pasan por la elección de auto
    assert set(enviados) == {"gpt-5.4"}
    assert asistente.modelo_usado == "auto → gpt-5.4"


def test_auto_tras_401_tampoco_usa_un_modelo_excluido(monkeypatch):
    _simular_auto(monkeypatch,
                  [{"available_models": ["gpt-5.4"], "selected_model": "gpt-5.4",
                    "session_token": "st1", "expires_at": 9999999999},
                   {"available_models": ["kimi-k3", "gpt-5.4"], "selected_model": "kimi-k3",
                    "session_token": "st2", "expires_at": 9999999999}],
                  {"kimi-k3": ["/chat/completions"], "gpt-5.4": ["/chat/completions"]})
    respuestas = iter([_Stream(401), _Stream()])
    enviados = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append((json["model"], headers["Copilot-Session-Token"])) or next(respuestas))
    assert AsistenteIA(api_key="gho_x", modelo="auto")._completar("hola") == "OK"
    assert enviados == [("gpt-5.4", "st1"), ("gpt-5.4", "st2")]  # el reintento usa la sesión nueva, con gpt-5.4


def test_auto_sin_modelo_autorizado_no_envia_nada(monkeypatch):
    _simular_auto(monkeypatch,
                  [{"available_models": ["mistral-medium-3", "gpt-5.3-codex"], "selected_model": "mistral-medium-3",
                    "session_token": "st", "expires_at": 9999999999}],
                  {"mistral-medium-3": ["/chat/completions"], "gpt-5.3-codex": ["/responses"]})
    enviados = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append(json["model"]) or _Stream())
    with pytest.raises(ErrorAsistenteIA) as error:
        AsistenteIA(api_key="gho_x", modelo="auto")._completar("hola")
    assert enviados == []
    assert "mistral-medium-3" in str(error.value) and "gpt-5.3-codex" in str(error.value)
    assert "autorizado" in str(error.value)


@pytest.mark.parametrize("modelo", [None, ""])
def test_modelo_vacio_no_envia_nada_y_explica_el_motivo(monkeypatch, modelo):
    enviados = []
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append(json["model"]) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo=modelo, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_resumen("hola")
    assert enviados == []
    assert str(error.value) == ("No hay ningún modelo de IA configurado. Elige uno en el selector o en "
                                "`ia.modelo` de config/settings.yaml.")


def test_auto_tras_caducar_la_sesion_tampoco_usa_un_modelo_excluido(monkeypatch):
    import time
    _simular_auto(monkeypatch,
                  [{"available_models": ["gpt-5.4"], "selected_model": "gpt-5.4",
                    "session_token": "st1", "expires_at": time.time() + 60},  # vence en 1 min: no vigente (margen 5)
                   {"available_models": ["kimi-k3", "gpt-5.4"], "selected_model": "kimi-k3",
                    "session_token": "st2", "expires_at": 9999999999}],
                  {"kimi-k3": ["/chat/completions"], "gpt-5.4": ["/chat/completions"]})
    enviados = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append((json["model"], headers["Copilot-Session-Token"])) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo="auto", revision_fidelidad=False)
    asistente._completar("uno")
    asistente._completar("dos")  # la sesión caducada se renueva aquí
    assert enviados == [("gpt-5.4", "st1"), ("gpt-5.4", "st2")]


def test_auto_con_catalogo_caido_tambien_salta_las_familias_excluidas(monkeypatch):
    _simular_auto(monkeypatch,
                  [{"available_models": ["kimi-k3", "gpt-5.4"], "selected_model": "kimi-k3",
                    "session_token": "st", "expires_at": 9999999999}],
                  {})
    def catalogo_caido(*a, **kw):
        raise asistente_ia.httpx.ConnectError("sin conexión")
    monkeypatch.setattr(asistente_ia.httpx, "get", catalogo_caido)
    enviados = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append(json["model"]) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo="auto", revision_fidelidad=False)
    assert asistente._completar("hola") == "OK"
    assert enviados == ["gpt-5.4"]
