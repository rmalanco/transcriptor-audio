"""Tests del asistente de IA (sin llamadas reales a la API)."""

import pytest
from src import asistente_ia, copilot
from src.asistente_ia import AsistenteIA, ErrorAsistenteIA, ErrorModeloIA, dividir_texto


class _Respuesta:
    def __init__(self, datos, status_code=200, headers=None):
        self.datos, self.status_code, self.text = datos, status_code, ""
        self.headers = headers or {}

    def json(self):
        return self.datos


class _Stream:
    """Respuesta de chat simulada; con `status_code` distinto de 200 simula un error (el contenido no importa)."""
    def __init__(self, status_code=200, headers=None):
        self.status_code, self.text = status_code, ""
        self.headers = headers or {}
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
    resumen = asistente.generar_resumen("texto")
    assert resumen.startswith(completo)
    assert ("\n---\n\n> Nota de la aplicación: la revisión de fidelidad se descartó porque quitaba secciones "
            "obligatorias; este documento no está revisado.") in resumen


def test_revision_que_pierde_secciones_lo_dice_y_no_cuenta_como_revisada(monkeypatch):
    completo = "## Resumen\nt\n### Puntos clave\n- a\n### Conclusiones\n- b"
    respuestas = iter([completo, "## Resumen\nsolo esto"])
    prompts = []
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar",
                        lambda prompt, cancelar=None: prompts.append(prompt) or next(respuestas))
    resumen = asistente.generar_resumen("texto")
    assert resumen.startswith(completo)
    assert ("\n---\n\n> Nota de la aplicación: la revisión de fidelidad se descartó porque quitaba secciones "
            "obligatorias; este documento no está revisado.") in resumen
    assert not any("Nota de la aplicación" in prompt for prompt in prompts)


def _minuta(tareas=("Enviar el informe",), acuerdos=("Se aprueba el presupuesto",), frase="Revisar el plan"):
    """Minuta completa con las secciones obligatorias; `tareas` y `acuerdos` son el contenido variable."""
    filas = "".join(f"| {t} | Ana | Sin fecha |\n" for t in tareas)
    vinetas = "".join(f"- {a}\n" for a in acuerdos)
    return ("# Minuta: Reunión de prueba\n\n**Fecha:** 22 de noviembre de 2026\n**Participantes:** Ana\n\n"
            "## Objetivo\nRevisar el proyecto.\n\n"
            f"## Temas tratados\n1. **Plan:** {frase}.\n\n"
            f"## Acuerdos\n{vinetas}\n"
            "## Tareas y pendientes\n| Tarea | Responsable | Fecha límite |\n|-------|-------------|--------------|\n"
            f"{filas}\n"
            "## Próximos pasos\n- Nada más.\n")


def test_contar_filas_de_tareas():
    from src.asistente_ia import contar_filas_tareas
    assert contar_filas_tareas(_minuta(tareas=("A", "B", "C"))) == 3
    assert contar_filas_tareas(_minuta(tareas=())) == 0  # solo cabecera y separador
    assert contar_filas_tareas("## Acuerdos\n- algo\n") == 0  # sin tabla de tareas


def test_contar_vinetas_de_acuerdos():
    from src.asistente_ia import contar_vinetas_acuerdos
    minuta = _minuta(acuerdos=("uno", "dos")) + "\n- Viñeta fuera de acuerdos\n"
    assert contar_vinetas_acuerdos(minuta) == 2
    assert contar_vinetas_acuerdos(_minuta(acuerdos=())) == 0


def test_revision_de_minuta_que_borra_una_tarea_se_repone_marcada(monkeypatch):
    redaccion = _minuta(tareas=("Enviar el informe", "Pagar el proveedor", "Revisar el contrato"))
    revision = _minuta(tareas=("Enviar el informe", "Pagar el proveedor"))
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert "Revisar el contrato" in minuta  # la tarea que la revisión borró sigue en el documento final
    assert "| Revisar el contrato [comprobar] | Ana | Sin fecha |" in minuta


def test_revision_de_minuta_que_borra_un_acuerdo_se_repone_marcado(monkeypatch):
    redaccion = _minuta(acuerdos=("Se aprueba el presupuesto", "Se contrata a Ana"))
    revision = _minuta(acuerdos=("Se aprueba el presupuesto",))
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert "- Se contrata a Ana [comprobar]" in minuta


def test_revision_de_minuta_que_conserva_tareas_y_acuerdos_se_acepta(monkeypatch):
    redaccion = _minuta(frase="la entrega está sujeta a validación")
    revision = _minuta(frase="la entrega llega si me llegan los datos")
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert "la entrega llega si me llegan los datos" in minuta


def test_revision_de_resumen_no_aplica_la_regla_de_tareas(monkeypatch):
    redaccion = "## Resumen\nt\n### Puntos clave\n- a\n- b\n### Conclusiones\n- c"
    revision = "## Resumen\nt\n### Puntos clave\n- a\n### Conclusiones\n- c"
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    resumen = asistente.generar_resumen("texto")

    assert "- b" not in resumen  # la revisión sin el punto «b» se acepta


def test_revision_aceptada_no_lleva_nota_de_descartada(monkeypatch):
    redaccion = _minuta(frase="la entrega está sujeta a validación")
    revision = _minuta(frase="la entrega llega si me llegan los datos")
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert "la entrega llega si me llegan los datos" in minuta
    assert "se descartó" not in minuta


def test_revision_descartada_con_varias_partes_no_dice_que_se_reviso(monkeypatch):
    _prohibir_red(monkeypatch)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    assert len(dividir_texto(texto, 900)) == 2
    revision = MINUTA_MODELO.split("## Próximos pasos")[0].rstrip()  # pierde una sección obligatoria
    _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo)
                  else revision if "DOCUMENTO:" in cuerpo["messages"][-1]["content"] else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=True)

    minuta = asistente.generar_minuta(texto, fecha="29 de septiembre de 2026")

    descartada = ("> Nota de la aplicación: la revisión de fidelidad se descartó porque quitaba secciones obligatorias; "
                  "este documento no está revisado.")
    partes = "> Nota de la aplicación: la transcripción se procesó en 2 partes"
    assert descartada in minuta
    assert minuta.index(descartada) < minuta.index(partes)
    assert minuta.count("\n---\n") == 1  # las dos notas bajo una sola línea horizontal
    assert minuta.endswith("antes de darlo por bueno.")
    assert "La revisión de fidelidad se hizo" not in minuta


def test_revision_que_pierde_secciones_y_tareas_da_el_motivo_de_secciones(monkeypatch):
    redaccion = _minuta(tareas=("Enviar el informe", "Pagar el proveedor"))
    revision = _minuta(tareas=("Enviar el informe",)).split("## Próximos pasos")[0].rstrip()  # pierde sección y tarea
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert ("la revisión de fidelidad se descartó porque quitaba secciones obligatorias; este documento no está "
            "revisado.") in minuta
    assert "quitaba tareas o acuerdos" not in minuta
    assert "[comprobar]" not in minuta


def test_lo_repuesto_no_se_envia_a_copilot(monkeypatch):
    import json
    _prohibir_red(monkeypatch)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    assert len(dividir_texto(texto, 900)) == 2
    revision = MINUTA_MODELO.replace("| Enviar cifras de octubre | Ana | No asignado |\n", "")  # quita la tarea
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo)
                            else revision if "DOCUMENTO:" in cuerpo["messages"][-1]["content"] else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=True)

    minuta = asistente.generar_minuta(texto)

    assert "Enviar cifras de octubre [comprobar]" in minuta  # la app lo repone...
    assert "quiso quitar" in minuta  # ...y lo dice
    assert len(cuerpos) == 4  # dos notas, la minuta y la revisión
    assert not any("[comprobar]" in json.dumps(c, ensure_ascii=False) or "quiso quitar" in json.dumps(c, ensure_ascii=False)
                   for c in cuerpos)


def test_nota_de_lo_repuesto_formato_y_tope():
    from src.asistente_ia import notas_de_la_aplicacion
    cabecera = ("\n---\n\n> Nota de la aplicación: la revisión de fidelidad quiso quitar de la minuta lo siguiente por no "
                "encontrarlo en la transcripción; la app lo ha repuesto marcado con «[comprobar]»: ")
    cola = ". Compruébalo con la transcripción y bórralo si no se dijo."
    assert notas_de_la_aplicacion([], 1, True, repuestas=["A"]) == cabecera + "«A»" + cola
    assert notas_de_la_aplicacion([], 1, True, repuestas=["A", "B"]) == cabecera + "«A» y «B»" + cola
    assert notas_de_la_aplicacion([], 1, True, repuestas=list("ABCDEF")) == (
        cabecera + "«A», «B», «C», «D», «E» y 1 más" + cola)
    assert notas_de_la_aplicacion([], 1, True, repuestas=["x" * 200]) == cabecera + "«" + "x" * 120 + "…»" + cola
    assert "«Se contrata a Ana.»" in notas_de_la_aplicacion([], 1, True, repuestas=["Se contrata a Ana."])
    assert notas_de_la_aplicacion([], 1, True, repuestas=[]) == ""
    bloque = notas_de_la_aplicacion(["## Próximos pasos"], 2, True, repuestas=["A"])
    assert bloque.index("faltan secciones") < bloque.index("repuesto marcado") < bloque.index("se procesó en 2 partes")


def test_reponer_lo_quitado_sin_bajar_no_cambia_nada():
    from src.asistente_ia import reponer_lo_quitado
    antes = _minuta(tareas=("Enviar el informe", "Revisar el contrato"))
    despues = _minuta(tareas=("Enviar el informe final", "Revisar el contrato"))  # mismo número de filas
    assert reponer_lo_quitado(antes, despues) == (despues, [])


def test_tarea_reescrita_y_otra_quitada_solo_repone_la_quitada(monkeypatch):
    redaccion = _minuta(tareas=("Enviar el informe", "Revisar el contrato", "Pagar el proveedor"))
    revision = _minuta(tareas=("Enviar el informe final", "Pagar el proveedor"))
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert "| Revisar el contrato [comprobar] | Ana | Sin fecha |" in minuta
    assert "| Enviar el informe final | Ana | Sin fecha |" in minuta  # reescrita: sin marca
    assert "Enviar el informe [comprobar]" not in minuta  # y no se repone la que sigue
    # sin contar la nota (que cita la marca): una sola fila marcada
    assert sum("[comprobar]" in linea for linea in minuta.splitlines() if not linea.startswith("> ")) == 1


def test_tarea_cambiada_por_sin_tareas_se_repone(monkeypatch):
    redaccion = _minuta(tareas=("Enviar el informe",)).replace("| Enviar el informe | Ana |", "| Enviar el informe | No asignado |")
    revision = _minuta(tareas=("Sin tareas",))  # la única tarea se ha vuelto la fila de relleno
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert "| Enviar el informe [comprobar] | No asignado | Sin fecha |" in minuta
    assert "| Sin tareas" not in minuta  # la fila de relleno sale porque ya hay tareas
    assert "«Enviar el informe»" in minuta  # sin responsable conocido, sin paréntesis


def test_acuerdo_quitado_se_repone_marcado(monkeypatch):
    redaccion = _minuta(acuerdos=("Se aprueba el presupuesto", "Se contrata a Ana"))
    revision = _minuta(acuerdos=()).replace("## Acuerdos\n\n", "## Acuerdos\n* Se aprueba el presupuesto.\n\n")
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert "* Se aprueba el presupuesto." in minuta
    assert "- Se contrata a Ana [comprobar]" in minuta
    # la nota también cita «[comprobar]»: se cuentan las líneas marcadas, no las apariciones
    assert sum(linea.endswith("[comprobar]") for linea in minuta.splitlines()) == 1


def test_prompt_de_revision_permite_quitar_solo_lo_no_respaldado():
    from src.asistente_ia import PROMPT_REVISION
    assert "no elimines secciones." in PROMPT_REVISION
    assert "un acuerdo con responsable también es una tarea" in PROMPT_REVISION
    assert "ni tareas" not in PROMPT_REVISION


def test_sin_la_seccion_donde_reponer_se_descarta(monkeypatch):
    # El borrador no tiene «## Acuerdos» (no hay nada que reponer ahí) y la revisión quita tareas sin su título
    redaccion = _minuta(tareas=("Enviar el informe", "Pagar el proveedor")).replace(
        "## Acuerdos\n- Se aprueba el presupuesto\n\n", "")
    revision = _minuta(tareas=("Enviar el informe",)).split("## Tareas y pendientes")[0] + "## Próximos pasos\n- Nada más.\n"
    respuestas = iter([redaccion, redaccion, revision])  # el reintento de secciones no devuelve Acuerdos
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert ("la revisión de fidelidad se descartó porque quitaba secciones obligatorias; este documento no está "
            "revisado.") in minuta
    assert "[comprobar]" not in minuta
    assert "| Enviar el informe | Ana | Sin fecha |" in minuta  # el borrador conserva sus tareas
    assert "| Pagar el proveedor | Ana | Sin fecha |" in minuta


def test_revision_que_quita_una_tarea_se_aplica_y_la_repone_marcada(monkeypatch):
    redaccion = _minuta(tareas=("Enviar las cifras de octubre", "Revisar el plan"),
                        frase="la entrega está sujeta a validación")
    revision = _minuta(tareas=("Revisar el plan",), frase="la entrega llega si me llegan los datos")
    respuestas = iter([redaccion, revision])
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    monkeypatch.setattr(asistente, "_completar", lambda prompt, cancelar=None: next(respuestas))

    minuta = asistente.generar_minuta("texto de prueba")

    assert "la entrega llega si me llegan los datos" in minuta
    assert "| Revisar el plan | Ana | Sin fecha |\n| Enviar las cifras de octubre [comprobar] | Ana | Sin fecha |" in minuta
    assert ("la app lo ha repuesto marcado con «[comprobar]»: «Enviar las cifras de octubre (Ana)». Compruébalo con "
            "la transcripción y bórralo si no se dijo.") in minuta
    assert "se descartó" not in minuta


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


class _StreamQueCancelaAlTerminar(_Stream):
    """Respuesta completa: el usuario cancela justo cuando termina de llegar (al cerrarse la conexión)."""
    def __init__(self, cancelar, contenido="OK"):
        super().__init__()
        self._cancelar, self._contenido = cancelar, contenido
    def __exit__(self, *a):
        self._cancelar.set()
        return False
    def iter_lines(self):
        import json
        yield "data: " + json.dumps({"choices": [{"delta": {"content": self._contenido}, "finish_reason": "stop"}]})
        yield "data: [DONE]"


def test_cancelar_no_inicia_las_partes_en_cola(monkeypatch):
    import threading
    cancelar = threading.Event()
    peticiones = []
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia.httpx, "stream",
                        lambda metodo, url, json, headers, timeout: peticiones.append(url)
                        or _StreamQueCancelaAlTerminar(cancelar))
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=300, peticiones_paralelas=1,
                            revision_fidelidad=False)
    assert len(dividir_texto(TEXTO_LARGO, 300)) > 1  # la transcripción se procesaría en varias partes
    with pytest.raises(InterruptedError):
        asistente.generar_resumen(TEXTO_LARGO, cancelar=cancelar)
    assert len(peticiones) == 1  # la primera parte terminó; las demás no se enviaron


def test_cancelar_durante_la_espera_de_reintento_no_reintenta(monkeypatch):
    import threading
    import time
    cancelar = threading.Event()
    peticiones = []
    _prohibir_red(monkeypatch)
    def stream(metodo, url, json, headers, timeout):
        peticiones.append(url)
        threading.Timer(0.1, cancelar.set).start()  # se cancela mientras espera el reintento (2 s)
        return _Stream(status_code=429)
    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    inicio = time.monotonic()
    with pytest.raises(InterruptedError):
        asistente.generar_resumen("texto corto", cancelar=cancelar)
    assert time.monotonic() - inicio < 1  # no espera los 2 s del reintento
    assert len(peticiones) == 1


def test_cancelar_tras_fallo_de_conexion_no_reintenta(monkeypatch):
    import threading
    import time
    cancelar = threading.Event()
    peticiones = []
    _prohibir_red(monkeypatch)
    def stream(metodo, url, json, headers, timeout):
        peticiones.append(url)
        threading.Timer(0.1, cancelar.set).start()  # se cancela mientras espera el reintento (1 s)
        raise asistente_ia.httpx.ConnectError("conexión rechazada")
    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    inicio = time.monotonic()
    with pytest.raises(InterruptedError):
        asistente.generar_resumen("texto corto", cancelar=cancelar)
    assert time.monotonic() - inicio < 0.5  # no espera el segundo de la espera del reintento
    assert len(peticiones) == 1


def test_cancelar_antes_de_la_revision_de_fidelidad_no_la_envia(monkeypatch):
    import threading
    cancelar = threading.Event()
    completo = "## Resumen\nt\n### Puntos clave\n- a\n### Conclusiones\n- b"
    peticiones = []
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia.httpx, "stream",
                        lambda metodo, url, json, headers, timeout: peticiones.append(url)
                        or _StreamQueCancelaAlTerminar(cancelar, completo))
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    with pytest.raises(InterruptedError):
        asistente.generar_resumen("texto corto", cancelar=cancelar)  # el documento ya estaba completo
    assert len(peticiones) == 1  # solo la redacción; la revisión no se inicia


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


def test_401_al_abrir_la_sesion_auto_es_falta_de_sesion(monkeypatch):
    from src.asistente_ia import ErrorSinSesionCopilot
    copilot.guardar_token("gho_revocado")
    monkeypatch.setattr(asistente_ia.copilot.httpx, "post", lambda *a, **kw: _Respuesta({}, 401))
    peticiones_de_chat = []
    monkeypatch.setattr(asistente_ia.httpx, "stream",
                        lambda *a, **kw: peticiones_de_chat.append(1) or _Stream())
    with pytest.raises(ErrorSinSesionCopilot):
        AsistenteIA(modelo="auto")._completar("hola")
    assert peticiones_de_chat == []
    assert copilot.leer_token() is None  # el token rechazado se invalida, como en /chat/completions


def test_401_en_chat_con_token_de_la_variable_de_entorno_lo_dice_y_no_pide_login(monkeypatch):
    copilot.guardar_token("gho_propio")
    monkeypatch.setenv(copilot.VARIABLE_ENTORNO, "gho_env")
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: _Stream(401))
    with pytest.raises(ErrorAsistenteIA) as error:
        AsistenteIA()._completar("hola")
    assert type(error.value) is ErrorAsistenteIA  # no es ErrorSinSesionCopilot: iniciar sesión no lo arregla
    assert str(error.value) == ("GitHub Copilot rechazó el token de la variable de entorno COPILOT_GITHUB_TOKEN. "
                                "Corrígela o quítala para usar la sesión guardada con el inicio de sesión de la app.")
    assert "gho_propio" in copilot.RUTA_TOKEN.read_text(encoding="utf-8")  # el archivo propio no se borra


def test_401_al_abrir_auto_con_token_de_la_variable_de_entorno_lo_dice_y_no_pide_login(monkeypatch):
    copilot.guardar_token("gho_propio")
    monkeypatch.setenv(copilot.VARIABLE_ENTORNO, "gho_env")
    monkeypatch.setattr(asistente_ia.copilot.httpx, "post", lambda *a, **kw: _Respuesta({}, 401))
    peticiones_de_chat = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: peticiones_de_chat.append(1) or _Stream())
    with pytest.raises(ErrorAsistenteIA) as error:
        AsistenteIA(modelo="auto")._completar("hola")
    assert type(error.value) is ErrorAsistenteIA
    assert str(error.value) == ("GitHub Copilot rechazó el token de la variable de entorno COPILOT_GITHUB_TOKEN. "
                                "Corrígela o quítala para usar la sesión guardada con el inicio de sesión de la app.")
    assert peticiones_de_chat == []
    assert "gho_propio" in copilot.RUTA_TOKEN.read_text(encoding="utf-8")


def test_429_con_retry_after_espera_lo_que_pide_copilot(monkeypatch):
    esperas = []
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: esperas.append(segundos))
    respuestas = iter([_Stream(429, headers={"Retry-After": "7"}), _Stream()])
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: next(respuestas))
    assert AsistenteIA(api_key="x")._completar("hola") == "OK"
    assert esperas == [7]  # en vez de la espera fija de 2 s


def test_429_sin_retry_after_usa_la_espera_fija(monkeypatch):
    esperas = []
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: esperas.append(segundos))
    respuestas = iter([_Stream(429), _Stream()])
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: next(respuestas))
    assert AsistenteIA(api_key="x")._completar("hola") == "OK"
    assert esperas == [2]


@pytest.mark.parametrize("valor", ["abc", "Wed, 21 Oct 2026 07:28:00 GMT", "-5", "nan"])
def test_429_con_retry_after_que_no_es_un_numero_usa_la_espera_fija(monkeypatch, valor):
    esperas = []
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: esperas.append(segundos))
    respuestas = iter([_Stream(429, headers={"Retry-After": valor}), _Stream()])
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: next(respuestas))
    assert AsistenteIA(api_key="x")._completar("hola") == "OK"
    assert esperas == [2]


def test_429_con_retry_after_por_encima_del_tope_no_espera_y_lo_dice(monkeypatch):
    esperas, peticiones = [], []
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: esperas.append(segundos))
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: peticiones.append(1)
                        or _ErrorHTTP(429, "límite de peticiones", {"Retry-After": "600"}))
    with pytest.raises(ErrorAsistenteIA) as error:
        AsistenteIA(api_key="x")._completar("hola")
    assert esperas == [] and len(peticiones) == 1  # ni espera ni reintenta
    assert str(error.value) == ("GitHub Copilot respondió 429: límite de peticiones. "
                                "Copilot pide esperar 600 s antes de reintentar.")


def test_fallo_al_completar_secciones_entrega_el_borrador_con_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    borrador = "## Resumen\nt\n### Puntos clave\n- a"  # le falta "### Conclusiones"
    # La petición de completar lleva system + usuario + asistente + usuario = 4 mensajes: esa es la que falla
    _simular_chat_con_estados(monkeypatch, lambda cuerpo: 429 if len(cuerpo["messages"]) == 4 else borrador)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    resumen = asistente.generar_resumen("Texto corto de la reunión.")
    assert resumen == (borrador + "\n\n---\n\n"
                       "> Nota de la aplicación: no se pudieron pedir de nuevo a Copilot las secciones que faltaban "
                       "(GitHub Copilot respondió 429: límite de peticiones).\n\n"
                       "> Nota de la aplicación: a este documento le faltan secciones obligatorias: Conclusiones. "
                       "No lo des por completo: vuelve a generarlo o complétalo con la transcripción.")


def test_fallo_en_la_revision_entrega_el_documento_sin_revisar_con_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    # La revisión es la petición cuyo último mensaje lleva «DOCUMENTO:»; la redacción no
    _simular_chat_con_estados(monkeypatch, lambda cuerpo: 429 if "DOCUMENTO:" in cuerpo["messages"][-1]["content"]
                              else RESUMEN_MODELO)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    resumen = asistente.generar_resumen("Texto corto de la reunión.")
    assert resumen == (RESUMEN_MODELO + "\n\n---\n\n"
                       "> Nota de la aplicación: la revisión de fidelidad no se pudo completar (GitHub Copilot respondió "
                       "429: límite de peticiones); este documento no está revisado.")


def test_fallo_en_la_revision_con_varias_partes_no_dice_que_se_reviso(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    assert len(dividir_texto(texto, 900)) == 2
    _simular_chat_con_estados(monkeypatch, lambda cuerpo: 429 if "DOCUMENTO:" in cuerpo["messages"][-1]["content"]
                              else "- Nota de una parte" if _es_prompt_de_notas(cuerpo) else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=True)
    minuta = asistente.generar_minuta(texto, fecha="29 de septiembre de 2026")
    assert minuta.endswith(
        "\n\n---\n\n> Nota de la aplicación: la revisión de fidelidad no se pudo completar (GitHub Copilot respondió "
        "429: límite de peticiones); este documento no está revisado.\n\n"
        "> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento se redactó a partir de notas "
        "extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, cifras y condiciones con la "
        "transcripción antes de darlo por bueno.")
    assert "La revisión de fidelidad se hizo" not in minuta


def test_cancelar_durante_la_revision_no_entrega_documento(monkeypatch):
    import threading
    cancelar = threading.Event()
    _prohibir_red(monkeypatch)
    def stream(metodo, url, json, headers, timeout):
        if "DOCUMENTO:" in json["messages"][-1]["content"]:
            cancelar.set()  # el usuario cancela mientras se revisa
        return _StreamConTexto(RESUMEN_MODELO)
    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    with pytest.raises(InterruptedError):
        asistente.generar_resumen("texto corto", cancelar=cancelar)


def test_401_durante_la_revision_no_entrega_documento(monkeypatch):
    from src.asistente_ia import ErrorSinSesionCopilot
    _prohibir_red(monkeypatch)
    _simular_chat_con_estados(monkeypatch, lambda cuerpo: 401 if "DOCUMENTO:" in cuerpo["messages"][-1]["content"]
                              else RESUMEN_MODELO)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    with pytest.raises(ErrorSinSesionCopilot):
        asistente.generar_resumen("texto corto")


def test_las_notas_nuevas_no_se_envian_a_copilot(monkeypatch):
    import json
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    sin_tareas = MINUTA_MODELO.split("## Tareas y pendientes")[0] + "## Próximos pasos\n- Próxima reunión, si se menciona."
    # Fallan la petición de completar (4 mensajes) y la revisión: salen las dos notas nuevas
    cuerpos = _simular_chat_con_estados(monkeypatch, lambda cuerpo: 429 if len(cuerpo["messages"]) == 4
                                        or "DOCUMENTO:" in cuerpo["messages"][-1]["content"]
                                        else "- Nota de una parte" if _es_prompt_de_notas(cuerpo) else sin_tareas)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=True)
    minuta = asistente.generar_minuta(texto)
    assert "la revisión de fidelidad no se pudo completar" in minuta
    assert "no se pudieron pedir de nuevo a Copilot" in minuta
    assert not any("Nota de la aplicación" in json.dumps(cuerpo, ensure_ascii=False) for cuerpo in cuerpos)


def test_modelo_no_autorizado_al_renovar_la_sesion_en_la_revision_no_entrega_documento(monkeypatch):
    import time
    _simular_auto(monkeypatch,
                  [{"available_models": ["gpt-5.4"], "selected_model": "gpt-5.4",
                    "session_token": "st1", "expires_at": time.time() + 60},  # no vigente: se renueva en la revisión
                   {"available_models": ["kimi-k3"], "selected_model": "kimi-k3",
                    "session_token": "st2", "expires_at": 9999999999}],
                  {"kimi-k3": ["/chat/completions"], "gpt-5.4": ["/chat/completions"]})
    _simular_chat(monkeypatch, lambda cuerpo: RESUMEN_MODELO)
    asistente = AsistenteIA(api_key="gho_x", modelo="auto", revision_fidelidad=True)
    with pytest.raises(ErrorModeloIA) as error:
        asistente.generar_resumen("texto corto")
    assert str(error.value).startswith("El modo auto no ofrece ningún modelo autorizado")


def test_modelo_no_autorizado_a_mitad_de_las_partes_no_se_envuelve(monkeypatch):
    _prohibir_red(monkeypatch)
    import time
    # La validación del modelo abre la primera sesión (gpt-5.4); cada parte reabre la sesión (no vigente) y la segunda
    # solo ofrece un modelo de familia excluida: el error aparece a mitad de las partes
    _simular_auto(monkeypatch,
                  [{"available_models": ["gpt-5.4"], "selected_model": "gpt-5.4",
                    "session_token": "st1", "expires_at": time.time() + 60},
                   {"available_models": ["kimi-k3"], "selected_model": "kimi-k3",
                    "session_token": "st2", "expires_at": 9999999999}],
                  {"kimi-k3": ["/chat/completions"], "gpt-5.4": ["/chat/completions"]})
    enviados = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append(json["model"]) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo="auto", max_caracteres_bloque=300, peticiones_paralelas=1,
                            revision_fidelidad=False)
    assert len(dividir_texto(TEXTO_LARGO, 300)) > 1  # se procesaría en varias partes
    with pytest.raises(ErrorModeloIA) as error:
        asistente.generar_resumen(TEXTO_LARGO)
    assert "falló la parte" not in str(error.value)
    assert enviados == []  # ninguna parte llegó a enviarse


def test_nota_de_notas_dice_el_numero_de_partes():
    from src.asistente_ia import nota_de_notas
    assert nota_de_notas(2, False) == (
        "\n---\n\n> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento se redactó a "
        "partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, cifras "
        "y condiciones con la transcripción antes de darlo por bueno.")


def test_nota_de_notas_con_revision_anade_la_frase_de_la_revision():
    from src.asistente_ia import nota_de_notas
    nota = nota_de_notas(3, True)
    assert "en 3 partes" in nota
    assert nota.endswith("bueno. La revisión de fidelidad se hizo contra esas notas, no contra la transcripción.")


def test_nota_de_notas_con_revision_contra_la_transcripcion():
    from src.asistente_ia import nota_de_notas
    assert nota_de_notas(2, True, fuente_revision="transcripcion").endswith(
        "bueno. La revisión de fidelidad lo contrastó después con la transcripción completa, pero es automática: no "
        "sustituye a esa comprobación.")
    assert nota_de_notas(2, False, fuente_revision="transcripcion") == nota_de_notas(2, False)


class _StreamConTexto(_Stream):
    """Respuesta de chat simulada con el contenido indicado."""
    def __init__(self, contenido):
        super().__init__()
        self._contenido = contenido
    def iter_lines(self):
        import json
        yield "data: " + json.dumps({"choices": [{"delta": {"content": self._contenido}, "finish_reason": "stop"}]})
        yield "data: [DONE]"


def _simular_chat(monkeypatch, respuesta):
    """Chat simulado: `respuesta(cuerpo)` dice qué contesta el modelo a cada petición. Devuelve los cuerpos enviados."""
    cuerpos = []
    def stream(metodo, url, json, headers, timeout):
        cuerpos.append(json)
        return _StreamConTexto(respuesta(json))
    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    return cuerpos


def _es_prompt_de_notas(cuerpo) -> bool:
    return "Esta es la parte" in cuerpo["messages"][-1]["content"]


MINUTA_MODELO = """# Minuta: Revisión del presupuesto

**Fecha:** Viernes 15 de noviembre
**Participantes:** Ana y Luis

## Objetivo
Revisar el presupuesto trimestral.

## Temas tratados
1. **Presupuesto:** se revisaron las cifras de octubre.

## Acuerdos
- Sin acuerdos explícitos.

## Tareas y pendientes
| Tarea | Responsable | Fecha límite |
|-------|-------------|--------------|
| Enviar cifras de octubre | Ana | No asignado |

## Próximos pasos
- Próxima reunión, si se menciona."""


def test_minuta_de_varias_partes_termina_con_la_nota_de_la_aplicacion(monkeypatch):
    from src.asistente_ia import SECCIONES_MINUTA
    from src.historial import titulo_desde_minuta
    _prohibir_red(monkeypatch)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    assert len(dividir_texto(texto, 900)) == 2  # la transcripción se procesa en 2 partes
    _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo) else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=False)
    minuta = asistente.generar_minuta(texto, fecha="29 de septiembre de 2026")
    assert minuta.endswith("\n\n---\n\n> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento "
                           "se redactó a partir de notas extraídas de cada parte, no de la transcripción completa. "
                           "Contrasta nombres, fechas, cifras y condiciones con la transcripción antes de darlo por bueno.")
    assert minuta.splitlines()[0] == "# Minuta: Revisión del presupuesto"
    assert titulo_desde_minuta(minuta) == "Revisión del presupuesto"
    assert "**Fecha:** 29 de septiembre de 2026" in minuta and "Viernes 15" not in minuta
    assert all(seccion in minuta for seccion in SECCIONES_MINUTA)


def test_la_nota_no_se_envia_a_copilot(monkeypatch):
    import json
    _prohibir_red(monkeypatch)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo)
                            else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=True)
    minuta = asistente.generar_minuta(texto)
    assert "Nota de la aplicación" in minuta
    assert len(cuerpos) == 4  # 2 partes de notas, la minuta y la revisión: todas las pasadas del modelo
    assert not any("Nota de la aplicación" in json.dumps(cuerpo, ensure_ascii=False) for cuerpo in cuerpos)


RESUMEN_MODELO = """## Resumen
Se revisó el presupuesto trimestral.

### Puntos clave
- Cifras de octubre.

### Conclusiones
- Sin conclusiones explícitas."""


def test_resumen_con_notas_reutilizadas_tambien_lleva_la_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo)
                            else RESUMEN_MODELO if "Redacta un resumen" in cuerpo["messages"][-1]["content"]
                            else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=False)
    asistente.generar_minuta(texto)
    peticiones_minuta = len(cuerpos)
    resumen = asistente.generar_resumen(texto)
    nuevas = cuerpos[peticiones_minuta:]
    assert len(nuevas) == 1 and not _es_prompt_de_notas(nuevas[0])  # las notas se reutilizan: solo el resumen
    assert resumen.startswith("## Resumen")
    assert resumen.endswith("\n\n---\n\n> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento "
                            "se redactó a partir de notas extraídas de cada parte, no de la transcripción completa. "
                            "Contrasta nombres, fechas, cifras y condiciones con la transcripción antes de darlo por bueno.")


TEXTO2 = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))  # 2 partes con max 900
BASE_DOS_PARTES = ("> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento se redactó a "
                   "partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, "
                   "fechas, cifras y condiciones con la transcripción antes de darlo por bueno.")


def test_revision_con_varias_partes_usa_la_transcripcion_completa(monkeypatch):
    _prohibir_red(monkeypatch)
    assert len(dividir_texto(TEXTO2, 900)) == 2
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo)
                            else MINUTA_MODELO)
    progreso = []
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=True)
    minuta = asistente.generar_minuta(TEXTO2, on_progreso=progreso.append)
    assert "Revisando fidelidad con la transcripción completa…" in progreso
    revision = cuerpos[-1]["messages"][-1]["content"]
    assert "DOCUMENTO:" in revision  # es la petición de revisión
    assert all(linea in revision for linea in TEXTO2.splitlines())  # la transcripción entera
    assert "Notas de la parte" not in revision
    assert minuta.endswith("\n\n---\n\n" + BASE_DOS_PARTES + " La revisión de fidelidad lo contrastó después con la "
                           "transcripción completa, pero es automática: no sustituye a esa comprobación.")


def test_resumen_con_notas_reutilizadas_revisa_contra_la_transcripcion(monkeypatch):
    _prohibir_red(monkeypatch)

    def respuesta(cuerpo):  # la revisión lleva «DOCUMENTO:» y se decide antes que la redacción del resumen
        ultimo = cuerpo["messages"][-1]["content"]
        if "DOCUMENTO:" in ultimo:
            return RESUMEN_MODELO if "## Resumen" in ultimo.split("DOCUMENTO:")[1] else MINUTA_MODELO
        if _es_prompt_de_notas(cuerpo):
            return "- Nota de una parte"
        return RESUMEN_MODELO if "Redacta un resumen" in ultimo else MINUTA_MODELO

    cuerpos = _simular_chat(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=True)
    asistente.generar_minuta(TEXTO2)
    peticiones_minuta = len(cuerpos)
    resumen = asistente.generar_resumen(TEXTO2)
    nuevas = cuerpos[peticiones_minuta:]
    assert len(nuevas) == 2  # el resumen y su revisión: las notas se reutilizan
    assert not any(_es_prompt_de_notas(cuerpo) for cuerpo in nuevas)
    revision = nuevas[-1]["messages"][-1]["content"]
    assert "DOCUMENTO:" in revision
    assert all(linea in revision for linea in TEXTO2.splitlines())
    assert "Notas de la parte" not in revision
    assert resumen.endswith("\n\n---\n\n" + BASE_DOS_PARTES + " La revisión de fidelidad lo contrastó después con la "
                            "transcripción completa, pero es automática: no sustituye a esa comprobación.")


def test_una_sola_parte_no_lleva_nota_y_revisa_contra_la_transcripcion(monkeypatch):
    _prohibir_red(monkeypatch)
    texto = ("Línea con contenido de prueba para la reunión.\n" * 30)[:900]  # exactamente el límite: una parte
    assert len(texto) == 900 and len(dividir_texto(texto, 900)) == 1
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: MINUTA_MODELO)
    progreso = []
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=True)
    minuta = asistente.generar_minuta(texto, on_progreso=progreso.append)
    assert "Nota de la aplicación" not in minuta
    assert minuta.endswith("- Próxima reunión, si se menciona.")
    assert "Revisando fidelidad con la transcripción…" in progreso
    assert len(cuerpos) == 2  # la minuta y la revisión, sin notas por parte
    assert texto in cuerpos[-1]["messages"][-1]["content"]  # la revisión recibe la transcripción completa


def test_un_caracter_mas_del_limite_se_procesa_en_dos_partes_y_lleva_la_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    texto = ("Línea con contenido de prueba para la reunión.\n" * 30)[:900] + "x"  # límite + 1
    assert len(dividir_texto(texto, 900)) == 2
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo)
                            else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=False)
    minuta = asistente.generar_minuta(texto)
    assert "\n\n---\n\n> Nota de la aplicación: la transcripción se procesó en 2 partes" in minuta
    assert len(cuerpos) == 3  # 2 partes de notas y la minuta


def test_sin_revision_la_nota_no_menciona_la_revision(monkeypatch):
    _prohibir_red(monkeypatch)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo) else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=False)
    minuta = asistente.generar_minuta(texto)
    assert "> Nota de la aplicación: la transcripción se procesó en 2 partes" in minuta
    assert "La revisión de fidelidad" not in minuta


def test_notas_de_la_aplicacion_sin_nada_que_avisar_es_vacio():
    from src.asistente_ia import notas_de_la_aplicacion
    assert notas_de_la_aplicacion([], 1, True) == ""


def test_nota_de_secciones_que_faltan_las_nombra():
    from src.asistente_ia import notas_de_la_aplicacion
    assert notas_de_la_aplicacion(["## Tareas y pendientes", "## Próximos pasos"], 1, False) == (
        "\n---\n\n> Nota de la aplicación: a este documento le faltan secciones obligatorias que Copilot no devolvió "
        "ni al pedírselas de nuevo: Tareas y pendientes, Próximos pasos. No lo des por completo: vuelve a generarlo "
        "o complétalo con la transcripción.")


def test_dos_notas_van_bajo_una_sola_linea_horizontal():
    from src.asistente_ia import notas_de_la_aplicacion
    bloque = notas_de_la_aplicacion(["## Tareas y pendientes"], 2, False)
    assert [linea for linea in bloque.splitlines() if linea.strip() == "---"] == ["---"]
    seccion, partes = bloque.split("\n\n> Nota de la aplicación: la transcripción")
    assert seccion.startswith("\n---\n\n> Nota de la aplicación: a este documento le faltan secciones obligatorias")
    assert seccion.endswith("Tareas y pendientes. No lo des por completo: vuelve a generarlo o complétalo con la "
                            "transcripción.")
    assert partes.startswith(" se procesó en 2 partes y este documento se redactó a partir de notas")
    assert partes.endswith("Contrasta nombres, fechas, cifras y condiciones con la transcripción antes de darlo por bueno.")


def test_minuta_a_la_que_le_falta_una_seccion_tras_el_reintento_lleva_la_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    sin_tareas = MINUTA_MODELO.split("## Tareas y pendientes")[0] + "## Próximos pasos\n- Próxima reunión, si se menciona."
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: sin_tareas)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    minuta = asistente.generar_minuta("Texto corto de la reunión.", fecha="29 de septiembre de 2026")
    assert len(cuerpos) == 2  # la redacción y el reintento; ninguna nota en los cuerpos
    assert minuta.startswith("# Minuta: Revisión del presupuesto\n")
    assert "**Fecha:** 29 de septiembre de 2026" in minuta
    assert minuta.endswith("\n\n---\n\n> Nota de la aplicación: a este documento le faltan secciones obligatorias que "
                           "Copilot no devolvió ni al pedírselas de nuevo: Tareas y pendientes. No lo des por completo: "
                           "vuelve a generarlo o complétalo con la transcripción.")


def test_la_nota_de_secciones_no_se_envia_a_copilot(monkeypatch):
    import json
    _prohibir_red(monkeypatch)
    sin_tareas = MINUTA_MODELO.split("## Tareas y pendientes")[0] + "## Próximos pasos\n- Próxima reunión, si se menciona."
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: sin_tareas)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    minuta = asistente.generar_minuta("Texto corto de la reunión.")
    assert "Nota de la aplicación" in minuta
    assert len(cuerpos) == 3  # redacción, reintento y revisión: todas las pasadas del modelo
    assert not any("Nota de la aplicación" in json.dumps(cuerpo, ensure_ascii=False) for cuerpo in cuerpos)


def test_documento_completo_tras_el_reintento_no_lleva_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    sin_tareas = MINUTA_MODELO.split("## Tareas y pendientes")[0] + "## Próximos pasos\n- Próxima reunión, si se menciona."
    respuestas = iter([sin_tareas, MINUTA_MODELO])  # la redacción omite la sección y el reintento la trae
    _simular_chat(monkeypatch, lambda cuerpo: next(respuestas))
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    minuta = asistente.generar_minuta("Texto corto de la reunión.")
    assert "Nota de la aplicación" not in minuta
    assert minuta.endswith("- Próxima reunión, si se menciona.")


def test_resumen_al_que_le_falta_una_seccion_tambien_lleva_la_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    sin_conclusiones = RESUMEN_MODELO.split("### Conclusiones")[0].rstrip()
    _simular_chat(monkeypatch, lambda cuerpo: sin_conclusiones)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    resumen = asistente.generar_resumen("Texto corto de la reunión.")
    assert resumen.startswith("## Resumen\nSe revisó el presupuesto trimestral.")
    assert resumen.endswith("\n\n---\n\n> Nota de la aplicación: a este documento le faltan secciones obligatorias que "
                            "Copilot no devolvió ni al pedírselas de nuevo: Conclusiones. No lo des por completo: "
                            "vuelve a generarlo o complétalo con la transcripción.")


def test_minuta_de_varias_partes_y_seccion_que_falta_lleva_las_dos_notas(monkeypatch):
    _prohibir_red(monkeypatch)
    sin_tareas = MINUTA_MODELO.split("## Tareas y pendientes")[0] + "## Próximos pasos\n- Próxima reunión, si se menciona."
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    assert len(dividir_texto(texto, 900)) == 2
    _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo) else sin_tareas)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=False)
    minuta = asistente.generar_minuta(texto)
    assert minuta.endswith(
        "\n\n---\n\n> Nota de la aplicación: a este documento le faltan secciones obligatorias que Copilot no devolvió "
        "ni al pedírselas de nuevo: Tareas y pendientes. No lo des por completo: vuelve a generarlo o complétalo con la "
        "transcripción.\n\n> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento se redactó "
        "a partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, cifras "
        "y condiciones con la transcripción antes de darlo por bueno.")
    assert minuta.count("\n---\n") == 1


class _ErrorHTTP(_Stream):
    """Respuesta de error de Copilot con un cuerpo de texto y, si se pasan, cabeceras (p. ej. Retry-After)."""
    def __init__(self, status_code, texto, headers=None):
        super().__init__(status_code, headers)
        self.text = texto


def _simular_chat_con_estados(monkeypatch, respuesta):
    """Como `_simular_chat`, pero `respuesta(cuerpo)` puede devolver un código HTTP de error en vez de texto."""
    cuerpos = []
    def stream(metodo, url, json, headers, timeout):
        cuerpos.append(json)
        valor = respuesta(json)
        return _ErrorHTTP(valor, "límite de peticiones") if isinstance(valor, int) else _StreamConTexto(valor)
    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    return cuerpos


def _numero_de_parte(cuerpo):
    import re
    coincidencia = re.search(r"Esta es la parte (\d+) de", cuerpo["messages"][-1]["content"])
    return int(coincidencia.group(1)) if coincidencia else None


TEXTO_OCHO_PARTES = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(360))


def test_fallo_de_una_parte_dice_cual_y_cuantas_se_conservan(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)  # sin esperas entre reintentos
    assert len(dividir_texto(TEXTO_OCHO_PARTES, 1800)) == 8
    cuerpos = _simular_chat_con_estados(monkeypatch, lambda c: 429 if _numero_de_parte(c) == 7
                                        else "- Nota" if _numero_de_parte(c) else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=1800, peticiones_paralelas=1, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(TEXTO_OCHO_PARTES)
    mensaje = str(error.value)
    assert mensaje.startswith("falló la parte 7 de 8: GitHub Copilot respondió 429: límite de peticiones. ")
    assert "Se conservan las notas de las 6 partes que terminaron; al volver a generar solo se pedirán las que faltan." \
        in mensaje
    assert not any("Redacta la minuta" in c["messages"][-1]["content"] for c in cuerpos)  # no hay redacción


def test_reintentar_tras_el_fallo_solo_pide_las_partes_que_faltan(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    caida = {"activa": True}
    def respuesta(cuerpo):
        parte = _numero_de_parte(cuerpo)
        if parte == 7 and caida["activa"]:
            return 429
        return f"- Nota de la parte {parte}" if parte else MINUTA_MODELO
    cuerpos = _simular_chat_con_estados(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=1800, peticiones_paralelas=1, revision_fidelidad=False)
    bloques = dividir_texto(TEXTO_OCHO_PARTES, 1800)
    with pytest.raises(ErrorAsistenteIA):
        asistente.generar_minuta(TEXTO_OCHO_PARTES)
    caida["activa"] = False
    cuerpos.clear()
    minuta = asistente.generar_minuta(TEXTO_OCHO_PARTES)
    assert len(cuerpos) == 3  # notas de la parte 7, notas de la parte 8 y la redacción
    assert [_numero_de_parte(c) for c in cuerpos[:2]] == [7, 8]
    assert _numero_de_parte(cuerpos[2]) is None
    assert not any(bloque in c["messages"][-1]["content"] for c in cuerpos for bloque in bloques[:6])
    redaccion = cuerpos[2]["messages"][-1]["content"]
    posiciones = [redaccion.index(f"Notas de la parte {n}:") for n in range(1, 9)]
    assert posiciones == sorted(posiciones)
    assert "- Nota de la parte 7" in redaccion and minuta.startswith("# Minuta")


def test_las_notas_conservadas_sirven_tambien_para_el_otro_documento(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    caida = {"activa": True}
    def respuesta(cuerpo):
        parte = _numero_de_parte(cuerpo)
        if parte == 7 and caida["activa"]:
            return 429
        if parte:
            return f"- Nota de la parte {parte}"
        return RESUMEN_MODELO if "Redacta un resumen" in cuerpo["messages"][-1]["content"] else MINUTA_MODELO
    cuerpos = _simular_chat_con_estados(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=1800, peticiones_paralelas=1, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA):
        asistente.generar_minuta(TEXTO_OCHO_PARTES)
    caida["activa"] = False
    cuerpos.clear()
    resumen = asistente.generar_resumen(TEXTO_OCHO_PARTES)
    assert [_numero_de_parte(c) for c in cuerpos[:2]] == [7, 8]  # solo las partes que faltaban
    assert len(cuerpos) == 3 and "Redacta un resumen" in cuerpos[2]["messages"][-1]["content"]
    assert resumen.startswith("## Resumen")


def test_cancelar_durante_las_notas_no_se_convierte_en_fallo_de_parte(monkeypatch):
    import threading
    cancelar = threading.Event()
    peticiones = []
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout: peticiones.append(url)
                        or _StreamQueCancelaAlTerminar(cancelar, "- Nota de una parte"))
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=1800, peticiones_paralelas=1, revision_fidelidad=False)
    with pytest.raises(InterruptedError):  # no ErrorAsistenteIA: la cancelación no es un fallo de parte
        asistente.generar_minuta(TEXTO_OCHO_PARTES, cancelar=cancelar)
    assert len(peticiones) == 1


def test_modelo_excluido_con_varias_partes_da_su_error_exacto_sin_hablar_de_partes(monkeypatch):
    enviados = []
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append(json["model"]) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo="kimi-k3-mini", max_caracteres_bloque=300, revision_fidelidad=False)
    assert len(dividir_texto(TEXTO_LARGO, 300)) > 1  # la transcripción se procesaría en varias partes
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(TEXTO_LARGO)
    assert enviados == []
    assert str(error.value) == ("El modelo «kimi-k3-mini» es de la familia «kimi», que no está autorizada por la empresa. "
                                "Elige otro modelo en el selector o en `ia.modelo` de config/settings.yaml.")


@pytest.mark.parametrize("modelo", [None, ""])
def test_modelo_vacio_con_varias_partes_da_su_error_exacto(monkeypatch, modelo):
    enviados = []
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append(json["model"]) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo=modelo, max_caracteres_bloque=300, revision_fidelidad=False)
    assert len(dividir_texto(TEXTO_LARGO, 300)) > 1
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_resumen(TEXTO_LARGO)
    assert enviados == []
    assert str(error.value) == ("No hay ningún modelo de IA configurado. Elige uno en el selector o en "
                                "`ia.modelo` de config/settings.yaml.")


def test_auto_sin_modelo_autorizado_con_varias_partes_no_habla_de_partes(monkeypatch):
    sesion = {"available_models": ["mistral-medium-3", "gpt-5.3-codex"], "selected_model": "mistral-medium-3",
              "session_token": "st", "expires_at": 9999999999}
    _simular_auto(monkeypatch, [sesion, sesion],
                  {"mistral-medium-3": ["/chat/completions"], "gpt-5.3-codex": ["/responses"]})
    enviados = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append(json["model"]) or _Stream())
    with pytest.raises(ErrorAsistenteIA) as una_parte:
        AsistenteIA(api_key="gho_x", modelo="auto", revision_fidelidad=False).generar_resumen("hola")
    with pytest.raises(ErrorAsistenteIA) as varias_partes:
        AsistenteIA(api_key="gho_x", modelo="auto", max_caracteres_bloque=300,
                    revision_fidelidad=False).generar_resumen(TEXTO_LARGO)
    assert enviados == []
    assert type(varias_partes.value) is type(una_parte.value)
    assert str(varias_partes.value) == str(una_parte.value)
    assert "falló la parte" not in str(varias_partes.value) and "notas" not in str(varias_partes.value)


def test_con_mas_partes_que_el_limite_de_la_cache_se_conservan_todas_las_que_terminaron(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    monkeypatch.setattr(asistente_ia, "LIMITE_NOTAS_EN_CACHE", 4)  # menos que las 8 partes de la generación
    caida = {"activa": True}
    def respuesta(cuerpo):
        parte = _numero_de_parte(cuerpo)
        if parte == 7 and caida["activa"]:
            return 429
        return f"- Nota de la parte {parte}" if parte else MINUTA_MODELO
    cuerpos = _simular_chat_con_estados(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=1800, peticiones_paralelas=1, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(TEXTO_OCHO_PARTES)
    assert "Se conservan las notas de las 6 partes que terminaron" in str(error.value)
    caida["activa"] = False
    cuerpos.clear()
    asistente.generar_minuta(TEXTO_OCHO_PARTES)
    assert [_numero_de_parte(c) for c in cuerpos] == [7, 8, None]  # las 6 conservadas no se vuelven a pedir


def test_fallo_con_tres_partes_en_paralelo_conserva_las_que_estaban_en_curso(monkeypatch):
    import threading
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    fase = {"paralela": False, "caida": True}
    llegadas = threading.Barrier(2)  # en la segunda generación, las partes 7 y 8 están dentro de su petición a la vez
    fallo_de_la_7 = threading.Event()  # la 7 ha agotado sus reintentos: la 8 puede terminar
    intentos_7, primeras_entradas, cerrojo, enviadas = [0], set(), threading.Lock(), []

    def stream(metodo, url, json, headers, timeout):
        parte = _numero_de_parte(json)
        with cerrojo:
            enviadas.append(parte)
            primera_vez = parte not in primeras_entradas
            primeras_entradas.add(parte)
        if fase["paralela"] and parte in (7, 8) and primera_vez:
            llegadas.wait(timeout=5)
        if parte == 7 and fase["caida"]:
            with cerrojo:
                intentos_7[0] += 1
                if intentos_7[0] == 4:
                    fallo_de_la_7.set()
            return _ErrorHTTP(429, "límite de peticiones")
        if parte == 8 and fase["paralela"]:
            fallo_de_la_7.wait(timeout=5)
        return _StreamConTexto(f"- Nota de la parte {parte}" if parte else MINUTA_MODELO)

    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=1800, peticiones_paralelas=1, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA):  # primera generación, una parte a la vez: 1 a 6 terminan, la 7 falla
        asistente.generar_minuta(TEXTO_OCHO_PARTES)
    assert 8 not in enviadas  # con un solo hilo, la 8 queda sin empezar y no se envía

    fase["paralela"] = True  # segunda generación, tres hilos: solo quedan pendientes la 7 y la 8
    fallo_de_la_7.clear()
    intentos_7[0] = 0
    primeras_entradas.clear()
    asistente.peticiones_paralelas = 3
    enviadas.clear()
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(TEXTO_OCHO_PARTES)
    assert str(error.value) == ("falló la parte 7 de 8: GitHub Copilot respondió 429: límite de peticiones. "
                                "Se conservan las notas de las 7 partes que terminaron; al volver a generar solo se "
                                "pedirán las que faltan.")  # 1 a 6 de antes, más la 8, que estaba en curso
    assert set(enviadas) == {7, 8}  # la 7 reintenta cuatro veces; la 8 se envía una
    assert not [t for t in threading.enumerate() if t.name.startswith("ia-parte")]  # no quedan hilos vivos

    fase["caida"], fase["paralela"] = False, False  # tercera generación: el recuento coincide con la caché
    enviadas.clear()
    minuta = asistente.generar_minuta(TEXTO_OCHO_PARTES)
    assert enviadas == [7, None]  # solo la parte 7 y la redacción: las 1 a 6 y la 8 estaban en la caché
    assert minuta.startswith("# Minuta")


def test_401_en_una_parte_no_se_envuelve(monkeypatch):
    from src.asistente_ia import ErrorSinSesionCopilot
    _prohibir_red(monkeypatch)
    _simular_chat_con_estados(monkeypatch, lambda c: 401 if _numero_de_parte(c) == 2 else
                              (f"- Nota de la parte {_numero_de_parte(c)}" if _numero_de_parte(c) else MINUTA_MODELO))
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=1800, peticiones_paralelas=1, revision_fidelidad=False)
    with pytest.raises(ErrorSinSesionCopilot) as error:
        asistente.generar_minuta(TEXTO_OCHO_PARTES)
    assert type(error.value) is ErrorSinSesionCopilot
    assert "falló la parte" not in str(error.value)


def test_una_sola_parte_conservada_usa_el_singular(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    assert len(dividir_texto(texto, 900)) == 2
    _simular_chat_con_estados(monkeypatch, lambda c: 429 if _numero_de_parte(c) == 2 else "- Nota de la parte 1")
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, peticiones_paralelas=1, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(texto)
    assert str(error.value).endswith(". Se conserva la nota de la parte que terminó; al volver a generar solo se "
                                     "pedirán las que faltan.")


def test_ninguna_parte_conservada_lo_dice(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    _simular_chat_con_estados(monkeypatch, lambda c: 429)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, peticiones_paralelas=1, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(texto)
    assert str(error.value).endswith(". No se conserva ninguna nota: al volver a generar se pedirán todas las partes.")


def test_revision_que_restituye_la_seccion_no_lleva_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    sin_tareas = MINUTA_MODELO.split("## Tareas y pendientes")[0] + "## Próximos pasos\n- Próxima reunión, si se menciona."
    respuestas = iter([sin_tareas, sin_tareas, MINUTA_MODELO])  # redacción y reintento sin la sección; la revisión la trae
    _simular_chat(monkeypatch, lambda cuerpo: next(respuestas))
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    minuta = asistente.generar_minuta("Texto corto de la reunión.")
    assert "Tareas y pendientes" in minuta
    assert "Nota de la aplicación" not in minuta


def test_cancelar_cuando_falla_la_pasada_de_secciones_no_entrega_documento(monkeypatch):
    import threading
    cancelar = threading.Event()
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    borrador = "## Resumen\nt\n### Puntos clave\n- a"  # le falta "### Conclusiones"
    def respuesta(cuerpo):
        if len(cuerpo["messages"]) == 4:  # la petición de completar secciones
            cancelar.set()  # el usuario cancela justo cuando esa petición falla
            return 400
        return borrador
    _simular_chat_con_estados(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    with pytest.raises(InterruptedError):
        asistente.generar_resumen("Texto corto de la reunión.", cancelar=cancelar)


def test_cancelar_cuando_falla_la_revision_no_entrega_documento(monkeypatch):
    import threading
    cancelar = threading.Event()
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    def respuesta(cuerpo):
        if "DOCUMENTO:" in cuerpo["messages"][-1]["content"]:  # la revisión de fidelidad
            cancelar.set()  # el usuario cancela justo cuando esa petición falla
            return 400
        return RESUMEN_MODELO
    _simular_chat_con_estados(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    with pytest.raises(InterruptedError):
        asistente.generar_resumen("texto corto", cancelar=cancelar)


def _nota_con_error_de_secciones(monkeypatch, cuerpo_de_error):
    """Genera un resumen cuya pasada de completar secciones falla con un 400 cuyo cuerpo es `cuerpo_de_error`.
    Devuelve (borrador, resumen)."""
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    borrador = "## Resumen\nt\n### Puntos clave\n- a"  # le falta "### Conclusiones"
    def stream(metodo, url, json, headers, timeout):
        if len(json["messages"]) == 4:  # la petición de completar secciones
            return _ErrorHTTP(400, cuerpo_de_error)
        return _StreamConTexto(borrador)
    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    return borrador, asistente.generar_resumen("Texto corto de la reunión.")


def test_motivo_de_la_nota_es_de_una_sola_linea(monkeypatch):
    import re
    borrador, resumen = _nota_con_error_de_secciones(
        monkeypatch, "<h1>Error interno</h1>\n## Resumen\nAlgo inesperado\n<h2>Detalle</h2>")
    nota = resumen[len(borrador):]
    assert "<h1>Error interno</h1>" in nota  # el texto del error se conserva, aplanado
    assert not re.search(r"^## Resumen", nota, re.M)  # no empieza ningún título dentro de la nota
    assert all(linea == "---" or linea.startswith("> Nota de la aplicación")
               for linea in nota.split("\n") if linea.strip())


def test_motivo_de_la_nota_largo_se_recorta(monkeypatch):
    import re
    borrador, resumen = _nota_con_error_de_secciones(monkeypatch, "a" * 500)
    motivo = re.search(r"faltaban \((.*)\)\.", resumen[len(borrador):]).group(1)
    assert motivo.startswith("GitHub Copilot respondió 400: aaa")
    assert motivo.endswith("…") and len(motivo) <= 121  # 120 caracteres y «…»


def test_seccion_recuperada_por_la_revision_no_deja_nota_de_secciones(monkeypatch):
    _prohibir_red(monkeypatch)
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: None)
    borrador = "## Resumen\nt\n### Puntos clave\n- a"  # le falta "### Conclusiones"
    def respuesta(cuerpo):
        if len(cuerpo["messages"]) == 4:  # la petición de completar secciones falla...
            return 400
        if "DOCUMENTO:" in cuerpo["messages"][-1]["content"]:  # ...pero la revisión devuelve el documento completo
            return RESUMEN_MODELO
        return borrador
    _simular_chat_con_estados(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    assert asistente.generar_resumen("Texto corto de la reunión.") == RESUMEN_MODELO  # sin ninguna nota


def test_cancelar_durante_la_espera_de_retry_after_no_reintenta(monkeypatch):
    import threading
    import time
    cancelar = threading.Event()
    peticiones = []
    _prohibir_red(monkeypatch)
    def stream(metodo, url, json, headers, timeout):
        peticiones.append(url)
        threading.Timer(0.1, cancelar.set).start()  # se cancela mientras espera el Retry-After (30 s)
        return _Stream(status_code=429, headers={"Retry-After": "30"})
    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    inicio = time.monotonic()
    with pytest.raises(InterruptedError):
        asistente.generar_resumen("texto corto", cancelar=cancelar)
    assert time.monotonic() - inicio < 1  # no espera los 30 s
    assert len(peticiones) == 1


def test_retry_after_cero_reintenta_sin_esperar(monkeypatch):
    esperas = []
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: esperas.append(segundos))
    respuestas = iter([_Stream(429, headers={"Retry-After": "0"}), _Stream()])
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: next(respuestas))
    assert AsistenteIA(api_key="x")._completar("hola") == "OK"
    assert esperas == [0]  # reintenta de inmediato


def test_retry_after_igual_al_tope_espera_el_tope(monkeypatch):
    esperas = []
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: esperas.append(segundos))
    respuestas = iter([_Stream(429, headers={"Retry-After": "60"}), _Stream()])
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: next(respuestas))
    assert AsistenteIA(api_key="x")._completar("hola") == "OK"
    assert esperas == [60]  # el límite exacto se acepta


def test_5xx_con_retry_after_tambien_lo_respeta(monkeypatch):
    esperas = []
    monkeypatch.setattr(asistente_ia, "_esperar", lambda segundos, cancelar: esperas.append(segundos))
    respuestas = iter([_Stream(503, headers={"Retry-After": "4"}), _Stream()])
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: next(respuestas))
    assert AsistenteIA(api_key="x")._completar("hola") == "OK"
    assert esperas == [4]


def test_401_con_token_de_opencode_no_borra_el_token_propio(monkeypatch):
    import json
    from src.asistente_ia import ErrorSinSesionCopilot
    copilot.guardar_token("gho_propio")  # archivo propio presente...
    copilot.RUTA_AUTH_OPENCODE.parent.mkdir(parents=True)
    copilot.RUTA_AUTH_OPENCODE.write_text(json.dumps({"github-copilot": {"refresh": "gho_oc"}}))
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda *a, **kw: _Stream(401))
    # ...pero el token rechazado es el de opencode (token pasado explícitamente)
    with pytest.raises(ErrorSinSesionCopilot):
        AsistenteIA(api_key="gho_oc")._completar("hola")
    assert copilot.leer_token().token == "gho_propio"  # el archivo propio no se toca
    assert "gho_oc" in copilot.RUTA_AUTH_OPENCODE.read_text(encoding="utf-8")  # ni la sesión de opencode


def test_modelo_no_autorizado_tras_terminar_una_parte_no_se_envuelve(monkeypatch):
    _prohibir_red(monkeypatch)
    import time
    # Validación (gpt-5.4, caduca en 1 min), parte 1 (gpt-5.4, caduca en 1 min: la siguiente parte renueva) y
    # parte 2: la sesión nueva solo ofrece kimi-k3
    _simular_auto(monkeypatch,
                  [{"available_models": ["gpt-5.4"], "selected_model": "gpt-5.4",
                    "session_token": "st1", "expires_at": time.time() + 60},
                   {"available_models": ["gpt-5.4"], "selected_model": "gpt-5.4",
                    "session_token": "st2", "expires_at": time.time() + 60},
                   {"available_models": ["kimi-k3"], "selected_model": "kimi-k3",
                    "session_token": "st3", "expires_at": 9999999999}],
                  {"kimi-k3": ["/chat/completions"], "gpt-5.4": ["/chat/completions"]})
    enviados = []
    monkeypatch.setattr(asistente_ia.httpx, "stream", lambda metodo, url, json, headers, timeout:
                        enviados.append(json["model"]) or _Stream())
    asistente = AsistenteIA(api_key="gho_x", modelo="auto", max_caracteres_bloque=300, peticiones_paralelas=1,
                            revision_fidelidad=False)
    assert len(dividir_texto(TEXTO_LARGO, 300)) > 1  # se procesa en varias partes
    with pytest.raises(ErrorModeloIA) as error:
        asistente.generar_resumen(TEXTO_LARGO)
    assert str(error.value) == ("El modo auto no ofrece ningún modelo autorizado y compatible con /chat/completions "
                                "(kimi-k3). Elige un modelo concreto en `ia.modelo`.")
    assert enviados == ["gpt-5.4"]  # solo la parte 1 llegó a enviarse


class _StreamConCierre(_Stream):
    """Respuesta de chat con el contenido, el `finish_reason` (None: ninguno) y si llega la marca [DONE]."""
    def __init__(self, contenido, fin="stop", done=True):
        super().__init__()
        self._contenido, self._fin, self._done = contenido, fin, done
    def iter_lines(self):
        import json
        opcion = {"delta": {"content": self._contenido}}
        if self._fin:
            opcion["finish_reason"] = self._fin
        yield "data: " + json.dumps({"choices": [opcion]})
        if self._done:
            yield "data: [DONE]"


def _simular_chat_con_cierre(monkeypatch, respuesta):
    """Chat simulado: `respuesta(cuerpo)` devuelve el contenido (cierre normal) o una tupla (contenido, fin, done).
    Devuelve los cuerpos enviados."""
    cuerpos = []
    def stream(metodo, url, json, headers, timeout):
        cuerpos.append(json)
        valor = respuesta(json)
        return _StreamConCierre(valor) if isinstance(valor, str) else _StreamConCierre(*valor)
    monkeypatch.setattr(asistente_ia.httpx, "stream", stream)
    return cuerpos


def test_redaccion_cortada_por_longitud_lleva_la_nota_de_respuesta_cortada(monkeypatch):
    import json
    _prohibir_red(monkeypatch)
    cuerpos = _simular_chat_con_cierre(monkeypatch, lambda cuerpo: (MINUTA_MODELO, "length", True))
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    minuta = asistente.generar_minuta("Texto corto de la reunión.", fecha="29 de septiembre de 2026")
    assert minuta.endswith("\n\n---\n\n> Nota de la aplicación: Copilot cortó su respuesta antes de terminarla "
                           "(límite de longitud del modelo); este documento puede estar incompleto. "
                           "No lo des por completo: vuelve a generarlo o complétalo con la transcripción.")
    assert minuta.startswith("# Minuta: Revisión del presupuesto\n")
    assert "**Fecha:** 29 de septiembre de 2026" in minuta
    assert len(cuerpos) == 1
    assert not any("Nota de la aplicación" in json.dumps(cuerpo, ensure_ascii=False) for cuerpo in cuerpos)


def test_redaccion_cortada_por_el_filtro_de_contenido_lo_dice(monkeypatch):
    _prohibir_red(monkeypatch)
    _simular_chat_con_cierre(monkeypatch, lambda cuerpo: (MINUTA_MODELO, "content_filter", True))
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    minuta = asistente.generar_minuta("Texto corto de la reunión.")
    assert minuta.endswith("\n\n---\n\n> Nota de la aplicación: Copilot cortó su respuesta antes de terminarla "
                           "(filtro de contenido de Copilot); este documento puede estar incompleto. "
                           "No lo des por completo: vuelve a generarlo o complétalo con la transcripción.")


def test_stream_sin_done_ni_finish_reason_cuenta_como_cortado(monkeypatch):
    _prohibir_red(monkeypatch)
    _simular_chat_con_cierre(monkeypatch, lambda cuerpo: (MINUTA_MODELO, None, False))
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    minuta = asistente.generar_minuta("Texto corto de la reunión.")
    assert minuta.endswith("\n\n---\n\n> Nota de la aplicación: Copilot cortó su respuesta antes de terminarla "
                           "(la respuesta terminó sin la marca de cierre); este documento puede estar incompleto. "
                           "No lo des por completo: vuelve a generarlo o complétalo con la "
                           "transcripción.")


@pytest.mark.parametrize("fin, cerrado", [("stop", True), ("stop", False), (None, True)])
def test_respuesta_completa_no_lleva_nota_de_corte(monkeypatch, fin, cerrado):
    _prohibir_red(monkeypatch)
    _simular_chat_con_cierre(monkeypatch, lambda cuerpo: (RESUMEN_MODELO, fin, cerrado)
                             if "Redacta un resumen" in cuerpo["messages"][-1]["content"] else (MINUTA_MODELO, fin, cerrado))
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    assert asistente.generar_resumen("Texto corto de la reunión.") == RESUMEN_MODELO
    assert asistente.generar_minuta("Texto corto de la reunión.").endswith("- Próxima reunión, si se menciona.")


def test_notas_de_una_parte_cortadas_llevan_la_nota_y_no_se_conservan(monkeypatch):
    _prohibir_red(monkeypatch)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    assert len(dividir_texto(texto, 600)) == 3
    cortar = {"activa": True}
    def respuesta(cuerpo):
        parte = _numero_de_parte(cuerpo)
        if parte == 2 and cortar["activa"]:
            cortar["activa"] = False  # solo la primera vez: la segunda petición de la parte 2 llega completa
            return (f"- Nota de la parte {parte}", "length", True)
        if parte:
            return f"- Nota de la parte {parte}"
        return RESUMEN_MODELO if "Redacta un resumen" in cuerpo["messages"][-1]["content"] else MINUTA_MODELO
    cuerpos = _simular_chat_con_cierre(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=600, peticiones_paralelas=1, revision_fidelidad=False)
    minuta = asistente.generar_minuta(texto)
    nota_de_partes = ("> Nota de la aplicación: la transcripción se procesó en 3 partes y este documento se redactó a "
                      "partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, "
                      "fechas, cifras y condiciones con la transcripción antes de darlo por bueno.")
    assert minuta.endswith("\n\n---\n\n> Nota de la aplicación: Copilot cortó antes de terminarlas las notas de la parte 2 "
                           "de 3 (límite de longitud del modelo); lo que se dijo en esa parte puede faltar en este "
                           "documento.\n\n" + nota_de_partes)
    peticiones_minuta = len(cuerpos)
    resumen = asistente.generar_resumen(texto)
    nuevas = cuerpos[peticiones_minuta:]
    assert len(nuevas) == 2  # la parte 2 otra vez, y la redacción: las partes 1 y 3 se reutilizan
    assert _numero_de_parte(nuevas[0]) == 2 and "Redacta un resumen" in nuevas[1]["messages"][-1]["content"]
    assert "Copilot cortó antes de terminarlas" not in resumen
    assert resumen.endswith("\n\n---\n\n" + nota_de_partes)


def test_varias_partes_cortadas_se_nombran_en_una_sola_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    assert len(dividir_texto(TEXTO_OCHO_PARTES, 1800)) == 8
    motivos = {2: "length", 5: "content_filter"}
    def respuesta(cuerpo):
        parte = _numero_de_parte(cuerpo)
        if parte in motivos:
            return (f"- Nota de la parte {parte}", motivos[parte], True)
        if parte:
            return f"- Nota de la parte {parte}"
        return MINUTA_MODELO
    _simular_chat_con_cierre(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=1800, peticiones_paralelas=1, revision_fidelidad=False)
    minuta = asistente.generar_minuta(TEXTO_OCHO_PARTES)
    assert minuta.endswith(
        "\n\n---\n\n> Nota de la aplicación: Copilot cortó antes de terminarlas las notas de las partes 2 "
        "(límite de longitud del modelo) y 5 (filtro de contenido de Copilot) de 8; lo que se dijo en esas partes puede "
        "faltar en este documento.\n\n> Nota de la aplicación: la transcripción se procesó en 8 partes y este documento "
        "se redactó a partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, "
        "cifras y condiciones con la transcripción antes de darlo por bueno.")


@pytest.mark.parametrize("fin, cerrado, motivo", [
    ("length", True, "límite de longitud del modelo"),
    ("content_filter", True, "filtro de contenido de Copilot"),
    (None, False, "la respuesta terminó sin la marca de cierre"),
])
def test_revision_cortada_se_descarta_y_lo_dice(monkeypatch, fin, cerrado, motivo):
    _prohibir_red(monkeypatch)
    def respuesta(cuerpo):
        if "DOCUMENTO:" in cuerpo["messages"][-1]["content"]:  # la revisión conserva las secciones, pero llega cortada
            return (RESUMEN_MODELO + "\n- Revisado.", fin, cerrado)
        return RESUMEN_MODELO
    _simular_chat_con_cierre(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=True)
    resumen = asistente.generar_resumen("Texto corto de la reunión.")
    assert resumen == (RESUMEN_MODELO + "\n\n---\n\n> Nota de la aplicación: la revisión de fidelidad no se pudo "
                       f"completar (Copilot cortó la respuesta: {motivo}); este documento no está revisado.")


def test_reintento_de_secciones_cortado_entrega_el_borrador_con_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    borrador = "## Resumen\nt\n### Puntos clave\n- a"  # le falta "### Conclusiones"
    def respuesta(cuerpo):
        if len(cuerpo["messages"]) == 4:  # la petición de completar secciones: llega cortada
            return ("## Resumen\nt\n### Puntos clave\n- a\n### Conclusiones\n- b", "length", True)
        return borrador
    _simular_chat_con_cierre(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    resumen = asistente.generar_resumen("Texto corto de la reunión.")
    assert resumen == (borrador + "\n\n---\n\n"
                       "> Nota de la aplicación: no se pudieron pedir de nuevo a Copilot las secciones que faltaban "
                       "(Copilot cortó la respuesta: límite de longitud del modelo).\n\n"
                       "> Nota de la aplicación: a este documento le faltan secciones obligatorias: Conclusiones. "
                       "No lo des por completo: vuelve a generarlo o complétalo con la transcripción.")


def test_notas_de_corte_van_primero_bajo_una_sola_linea_horizontal(monkeypatch):
    _prohibir_red(monkeypatch)
    texto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    assert len(dividir_texto(texto, 900)) == 2
    def respuesta(cuerpo):
        if _numero_de_parte(cuerpo) == 2:
            return ("- Nota de la parte 2", "length", True)
        if _numero_de_parte(cuerpo):
            return "- Nota de la parte 1"
        return (MINUTA_MODELO, "length", True)  # la redacción también se corta
    _simular_chat_con_cierre(monkeypatch, respuesta)
    asistente = AsistenteIA(api_key="x", max_caracteres_bloque=900, revision_fidelidad=False)
    minuta = asistente.generar_minuta(texto, fecha="29 de septiembre de 2026")
    assert [linea for linea in minuta.splitlines() if linea.strip() == "---"] == ["---"]
    assert minuta.startswith("# Minuta: Revisión del presupuesto\n\n**Fecha:** 29 de septiembre de 2026\n")
    assert minuta.endswith(
        "\n\n---\n\n"
        "> Nota de la aplicación: Copilot cortó su respuesta antes de terminarla (límite de longitud del modelo); este "
        "documento puede estar incompleto. No lo des por completo: vuelve a generarlo o "
        "complétalo con la transcripción.\n\n"
        "> Nota de la aplicación: Copilot cortó antes de terminarlas las notas de la parte 2 de 2 (límite de longitud del "
        "modelo); lo que se dijo en esa parte puede faltar en este documento.\n\n"
        "> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento se redactó a partir de notas "
        "extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, cifras y condiciones con la "
        "transcripción antes de darlo por bueno.")


def test_reintento_completo_sustituye_a_la_redaccion_cortada_y_no_lleva_nota(monkeypatch):
    _prohibir_red(monkeypatch)
    sin_tareas = MINUTA_MODELO.split("## Tareas y pendientes")[0] + "## Próximos pasos\n- Próxima reunión, si se menciona."
    respuestas = iter([(sin_tareas, "length", True), (MINUTA_MODELO, "stop", True)])  # redacción cortada; reintento entero
    _simular_chat_con_cierre(monkeypatch, lambda cuerpo: next(respuestas))
    asistente = AsistenteIA(api_key="x", revision_fidelidad=False)
    minuta = asistente.generar_minuta("Texto corto de la reunión.")
    assert "Nota de la aplicación" not in minuta  # el documento que queda es el del reintento, completo
    assert minuta.endswith("- Próxima reunión, si se menciona.")


# ------------------------------------------------------------------ Límite de entrada del modelo (historia 16)

def _relleno(caracteres: int) -> str:
    """Texto de relleno de exactamente `caracteres` caracteres (respuesta de notas simulada)."""
    return ("Nota de relleno. " * caracteres)[:caracteres]


def _simular_catalogo(monkeypatch, respuesta):
    """Catálogo de Copilot simulado: `respuesta` es la respuesta a devolver o una excepción a lanzar. Devuelve las
    consultas recibidas."""
    consultas = []
    def get(url, headers, timeout):
        consultas.append(url)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta
    monkeypatch.setattr(asistente_ia.httpx, "get", get)
    return consultas


def _catalogo_con_limite(modelo: str, limite) -> _Respuesta:
    return _Respuesta({"data": [{"id": modelo, "capabilities": {"limits": {"max_prompt_tokens": limite}}}]})


def test_estimar_tokens_usa_la_relacion_medida():
    assert asistente_ia.CARACTERES_POR_TOKEN == 2.3
    assert asistente_ia.estimar_tokens("x" * 230) == 100  # sin error de coma flotante: 230 / 2,3 es exacto
    assert asistente_ia.estimar_tokens("x" * 231) == 101  # y lo que pasa de 100 tokens cuenta como uno más
    assert asistente_ia.estimar_tokens("") == 0


def test_notas_cortas_o_una_sola_parte_no_consultan_el_catalogo(monkeypatch):
    _prohibir_red(monkeypatch)  # ni catálogo ni sesión: el test falla si se llama
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: "- Nota de una parte" if _es_prompt_de_notas(cuerpo)
                            else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=900, revision_fidelidad=False)
    texto_corto = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(40))
    assert len(dividir_texto(texto_corto, 900)) == 2  # varias partes, con notas cortas
    asistente.generar_minuta(texto_corto)
    una_parte = _relleno(150_000)  # una sola parte, pero su redacción supera el umbral de 32 000 tokens
    assert len(dividir_texto(una_parte, 200_000)) == 1
    AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=200_000,
                revision_fidelidad=False).generar_minuta(una_parte)
    assert len(cuerpos) == 4  # primera: 2 notas y la minuta; la de una parte: solo la minuta


TEXTO_TRES_PARTES_LARGO = "\n".join(f"Segmento {i:03d} con algo de contenido." for i in range(90))


def test_notas_que_superan_el_limite_no_envian_la_redaccion(monkeypatch):
    import re
    consultas = _simular_catalogo(monkeypatch, _catalogo_con_limite("gpt-4.1", 64000))
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: _relleno(100_000) if _es_prompt_de_notas(cuerpo)
                            else MINUTA_MODELO)
    assert len(dividir_texto(TEXTO_TRES_PARTES_LARGO, 1200)) == 3
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=1200, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(TEXTO_TRES_PARTES_LARGO)
    estimado = int(re.search(r"unos (\d+) tokens", str(error.value)).group(1))
    assert 129_000 <= estimado <= 134_000  # el criterio dice unos 131 000 tokens
    assert str(error.value) == (
        f"las notas de las 3 partes suman unos {estimado} tokens y el modelo «gpt-4.1» admite como máximo 64000 "
        "tokens de entrada, así que no se envió la redacción. Elige en el selector un modelo con más contexto y vuelve "
        "a generar; con otro modelo se pedirán de nuevo las notas de todas las partes.")
    assert len(cuerpos) == 3 and all(_es_prompt_de_notas(cuerpo) for cuerpo in cuerpos)  # ninguna redacción
    assert len(consultas) == 1


def test_notas_que_cabian_con_cuatro_caracteres_por_token_ya_no_se_envian(monkeypatch):
    import re
    consultas = _simular_catalogo(monkeypatch, _catalogo_con_limite("gpt-4.1", 64000))
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: _relleno(60_000) if _es_prompt_de_notas(cuerpo)
                            else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=1200, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA) as error:
        asistente.generar_minuta(TEXTO_TRES_PARTES_LARGO)
    estimado = int(re.search(r"unos (\d+) tokens", str(error.value)).group(1))
    assert 78_000 <= estimado <= 81_000
    assert str(error.value) == (
        f"las notas de las 3 partes suman unos {estimado} tokens y el modelo «gpt-4.1» admite como máximo 64000 "
        "tokens de entrada, así que no se envió la redacción. Elige en el selector un modelo con más contexto y vuelve "
        "a generar; con otro modelo se pedirán de nuevo las notas de todas las partes.")
    assert len(cuerpos) == 3 and all(_es_prompt_de_notas(cuerpo) for cuerpo in cuerpos)  # ninguna redacción
    assert len(consultas) == 1


def test_repetir_con_el_mismo_modelo_no_pide_nada_y_repite_el_error(monkeypatch):
    import re
    consultas = _simular_catalogo(monkeypatch, _catalogo_con_limite("gpt-4.1", 64000))
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: _relleno(100_000) if _es_prompt_de_notas(cuerpo)
                            else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=1200, revision_fidelidad=False)
    with pytest.raises(ErrorAsistenteIA) as primera:
        asistente.generar_minuta(TEXTO_TRES_PARTES_LARGO)
    peticiones_previas, consultas_previas = len(cuerpos), len(consultas)
    with pytest.raises(ErrorAsistenteIA) as segunda:
        asistente.generar_resumen(TEXTO_TRES_PARTES_LARGO)
    # Ni notas, ni redacción, ni catálogo
    assert len(cuerpos) == peticiones_previas and len(consultas) == consultas_previas
    # El resumen tiene otra plantilla, así que su estimación difiere un poco: el resto del error es el mismo
    assert re.sub(r"unos \d+ tokens", "unos N tokens", str(segunda.value)) == \
        re.sub(r"unos \d+ tokens", "unos N tokens", str(primera.value))
    assert "no se envió la redacción" in str(segunda.value)


def test_notas_que_caben_consultan_el_catalogo_una_vez_y_redactan(monkeypatch):
    consultas = _simular_catalogo(monkeypatch, _catalogo_con_limite("gpt-4.1", 64000))
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: _relleno(40_000) if _es_prompt_de_notas(cuerpo)
                            else RESUMEN_MODELO if "Redacta un resumen" in cuerpo["messages"][-1]["content"]
                            else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=1200, revision_fidelidad=False)
    minuta = asistente.generar_minuta(TEXTO_TRES_PARTES_LARGO)  # notas de 40 000 caracteres: unos 53 000 tokens
    resumen = asistente.generar_resumen(TEXTO_TRES_PARTES_LARGO)
    assert len(consultas) == 1  # una sola consulta del catálogo para la minuta y el resumen
    assert len(cuerpos) == 3 + 2  # 3 notas, y después la minuta y el resumen, que sí se envían
    assert minuta.startswith("# Minuta") and resumen.startswith("## Resumen")


def _responder_minuta_o_notas(cuerpo):
    return "- Nota de una parte" if _es_prompt_de_notas(cuerpo) else MINUTA_MODELO


def test_revision_que_cabe_consulta_el_catalogo_una_sola_vez(monkeypatch):
    monkeypatch.setattr(asistente_ia, "UMBRAL_COMPROBAR_LIMITE", 500)  # redacción (1 021) y revisión (1 676) pasan
    consultas = _simular_catalogo(monkeypatch, _catalogo_con_limite("gpt-4.1", 100_000))
    cuerpos = _simular_chat(monkeypatch, _responder_minuta_o_notas)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=900, revision_fidelidad=True)
    asistente.generar_minuta(TEXTO2)
    assert len(consultas) == 1  # la revisión reutiliza el límite de la redacción
    revision = cuerpos[-1]["messages"][-1]["content"]
    assert all(linea in revision for linea in TEXTO2.splitlines())


def test_revision_que_no_cabe_vuelve_a_las_notas(monkeypatch, caplog):
    monkeypatch.setattr(asistente_ia, "UMBRAL_COMPROBAR_LIMITE", 500)  # revisión con la transcripción: 1 676 > 1 300
    consultas = _simular_catalogo(monkeypatch, _catalogo_con_limite("gpt-4.1", 1300))
    cuerpos = _simular_chat(monkeypatch, _responder_minuta_o_notas)
    progreso = []
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=900, revision_fidelidad=True)
    with caplog.at_level("INFO", logger="transcriptor.ia"):
        minuta = asistente.generar_minuta(TEXTO2, on_progreso=progreso.append)
    assert len(consultas) == 1
    assert "Revisando fidelidad con las notas de las 2 partes…" in progreso
    revision = cuerpos[-1]["messages"][-1]["content"]
    assert "Notas de la parte 1" in revision
    assert not any(linea in revision for linea in TEXTO2.splitlines())
    assert minuta.endswith("\n\n---\n\n" + BASE_DOS_PARTES
                           + " La revisión de fidelidad se hizo contra esas notas, no contra la transcripción.")
    estimado = asistente_ia.estimar_tokens(asistente_ia.PROMPT_SISTEMA + asistente_ia.PROMPT_REVISION.format(
        texto=TEXTO2, documento=MINUTA_MODELO))
    assert ("La revisión con la transcripción completa suma unos " f"{estimado} tokens y «gpt-4.1» admite 1300; "
            "se revisa con las notas de las 2 partes.") in caplog.text


def test_catalogo_caido_se_consulta_una_vez_y_se_revisa_con_la_transcripcion(monkeypatch, caplog):
    monkeypatch.setattr(asistente_ia, "UMBRAL_COMPROBAR_LIMITE", 500)
    consultas = _simular_catalogo(monkeypatch, asistente_ia.httpx.ConnectError("sin conexión"))
    cuerpos = _simular_chat(monkeypatch, _responder_minuta_o_notas)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=900, revision_fidelidad=True)
    with caplog.at_level("WARNING", logger="transcriptor.ia"):
        asistente.generar_minuta(TEXTO2)
    assert len(consultas) == 1  # la redacción y la revisión comparten el fallo
    revision = cuerpos[-1]["messages"][-1]["content"]
    assert all(linea in revision for linea in TEXTO2.splitlines())
    assert ("No se pudo comprobar el límite de entrada de «gpt-4.1» para la revisión (No se pudo conectar con GitHub "
            "Copilot: sin conexión); se revisa con la transcripción completa.") in caplog.text
    asistente.generar_resumen(TEXTO2)  # otra generación sí vuelve a consultar
    assert len(consultas) == 2


def test_catalogo_sin_el_modelo_revisa_con_la_transcripcion(monkeypatch, caplog):
    monkeypatch.setattr(asistente_ia, "UMBRAL_COMPROBAR_LIMITE", 500)
    consultas = _simular_catalogo(monkeypatch, _catalogo_con_limite("otro-modelo", 64000))
    cuerpos = _simular_chat(monkeypatch, _responder_minuta_o_notas)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=900, revision_fidelidad=True)
    with caplog.at_level("WARNING", logger="transcriptor.ia"):
        asistente.generar_minuta(TEXTO2)
    assert len(consultas) == 1
    revision = cuerpos[-1]["messages"][-1]["content"]
    assert all(linea in revision for linea in TEXTO2.splitlines())
    assert ("No se pudo comprobar el límite de entrada de «gpt-4.1» para la revisión: el catálogo no lo informa; se "
            "revisa con la transcripción completa.") in caplog.text


@pytest.mark.parametrize("respuesta", [
    pytest.param(asistente_ia.httpx.ConnectError("sin conexión"), id="conexion-caida"),
    pytest.param(_Respuesta({}, 401), id="401"),
    pytest.param(_Respuesta({}, 500), id="500"),
    pytest.param(_Respuesta({"data": "no es una lista"}), id="data-inesperado"),
    pytest.param(_catalogo_con_limite("otro-modelo", 64000), id="modelo-ausente"),
    pytest.param(_Respuesta({"data": [{"id": "gpt-4.1", "capabilities": {}}]}), id="sin-limits"),
    pytest.param(_catalogo_con_limite("gpt-4.1", 0), id="limite-cero"),
    pytest.param(_catalogo_con_limite("gpt-4.1", -5), id="limite-negativo"),
    pytest.param(_catalogo_con_limite("gpt-4.1", "64000"), id="limite-texto"),
])
def test_sin_limite_conocido_se_redacta_como_hoy(monkeypatch, caplog, respuesta):
    consultas = _simular_catalogo(monkeypatch, respuesta)
    cuerpos = _simular_chat(monkeypatch, lambda cuerpo: _relleno(100_000) if _es_prompt_de_notas(cuerpo)
                            else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=1200, revision_fidelidad=False)
    with caplog.at_level("WARNING", logger="transcriptor.ia"):
        minuta = asistente.generar_minuta(TEXTO_TRES_PARTES_LARGO)  # no es un error: se redacta
    assert len(consultas) == 1
    assert len(cuerpos) == 4 and not _es_prompt_de_notas(cuerpos[-1])  # 3 notas y la redacción
    assert minuta.startswith("# Minuta")
    assert "no se pudo comprobar el límite de entrada" in caplog.text.lower()


@pytest.mark.parametrize("respuesta, registro", [
    pytest.param(asistente_ia.httpx.ConnectError("sin conexión"),
                 "No se pudo comprobar el límite de entrada de «gpt-4.1» (No se pudo conectar con GitHub Copilot: "
                 "sin conexión); se envía la redacción como hoy.",
                 id="conexion-caida"),
    pytest.param(_catalogo_con_limite("otro-modelo", 64000),
                 "No se pudo comprobar el límite de entrada de «gpt-4.1»: el catálogo no lo informa; se envía la "
                 "redacción como hoy.",
                 id="modelo-ausente"),
])
def test_registro_de_la_redaccion_sin_limite_no_cambia(monkeypatch, caplog, respuesta, registro):
    _simular_catalogo(monkeypatch, respuesta)
    _simular_chat(monkeypatch, lambda cuerpo: _relleno(100_000) if _es_prompt_de_notas(cuerpo) else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=1200, revision_fidelidad=False)
    with caplog.at_level("WARNING", logger="transcriptor.ia"):
        asistente.generar_minuta(TEXTO_TRES_PARTES_LARGO)
    assert registro in caplog.text  # el texto literal, con mayúscula y tildes: lo que ve quien lee el registro


def test_limite_del_modelo_no_repite_un_catalogo_caido_en_la_misma_generacion(monkeypatch):
    consultas = _simular_catalogo(monkeypatch, asistente_ia.httpx.ConnectError("sin conexión"))
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=1200, revision_fidelidad=False)
    consulta = asistente_ia._ConsultaDeLimite()
    assert asistente._limite_del_modelo(consulta, None) == ("gpt-4.1", None)
    assert asistente._limite_del_modelo(consulta, None) == ("gpt-4.1", None)  # misma generación: no se repite
    assert len(consultas) == 1
    assert "No se pudo conectar con GitHub Copilot: sin conexión" in consulta.error
    # Otra generación (otra consulta) sí vuelve a preguntar: el fallo no se guardó en el asistente
    assert asistente._limite_del_modelo(asistente_ia._ConsultaDeLimite(), None) == ("gpt-4.1", None)
    assert len(consultas) == 2


def test_limite_del_modelo_guarda_el_catalogo_entre_generaciones(monkeypatch):
    consultas = _simular_catalogo(monkeypatch, _catalogo_con_limite("gpt-4.1", 64000))
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=1200, revision_fidelidad=False)
    primera, segunda = asistente_ia._ConsultaDeLimite(), asistente_ia._ConsultaDeLimite()
    assert asistente._limite_del_modelo(primera, None) == ("gpt-4.1", 64000)
    assert asistente._limite_del_modelo(segunda, None) == ("gpt-4.1", 64000)  # otra generación: no vuelve a consultar
    assert len(consultas) == 1
    assert primera.error is None and segunda.error is None


def test_si_el_catalogo_falla_se_vuelve_a_consultar_en_la_siguiente_generacion(monkeypatch):
    respuestas = iter([asistente_ia.httpx.ConnectError("sin conexión"), _catalogo_con_limite("gpt-4.1", 64000)])
    llamadas = []

    def get(*args, **kwargs):
        llamadas.append(1)
        respuesta = next(respuestas)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    monkeypatch.setattr(copilot.httpx, "get", get)
    _simular_chat(monkeypatch, lambda cuerpo: _relleno(100_000) if _es_prompt_de_notas(cuerpo) else MINUTA_MODELO)
    asistente = AsistenteIA(api_key="x", modelo="gpt-4.1", max_caracteres_bloque=1200, revision_fidelidad=False)
    assert asistente.generar_minuta(TEXTO_TRES_PARTES_LARGO).startswith("# Minuta")  # sin límite: se redacta
    with pytest.raises(ErrorAsistenteIA, match="no se envió la redacción"):
        asistente.generar_resumen(TEXTO_TRES_PARTES_LARGO)  # el catálogo ya responde: se comprueba
    assert len(llamadas) == 2
