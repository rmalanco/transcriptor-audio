"""Tests del asistente de IA (sin llamadas reales a la API)."""

import pytest
from src import asistente_ia
from src.asistente_ia import AsistenteIA, dividir_texto


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
