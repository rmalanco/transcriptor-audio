"""Tests de la persistencia de transcripciones y documentos (historial y archivo junto al audio)."""

import sqlite3
from pathlib import Path

import pytest
from src.historial import Historial
from src.persistencia import (Persistencia, motivo_de_error, persistir_documento,
                             persistir_transcripcion, texto_destino_documento, texto_sin_guardado)
from src.transcriber import ResultadoTranscripcion, SegmentoTranscripcion


@pytest.fixture
def historial(tmp_path):
    return Historial(str(tmp_path / "historial.db"))


def _resultado(texto="Hola mundo. Segunda frase."):
    return ResultadoTranscripcion(
        texto_completo=texto,
        segmentos=[SegmentoTranscripcion(0.0, 2.0, "Hola mundo."), SegmentoTranscripcion(2.0, 4.5, "Segunda frase.")],
        idioma_detectado="es",
        probabilidad_idioma=0.98,
        duracion_total=4.5,
    )


def test_transcripcion_guarda_en_historial_y_exporta(historial, tmp_path):
    archivo = str(tmp_path / "reunion.mp3")
    ruta = str(tmp_path / "reunion_transcripcion.txt")
    p = persistir_transcripcion(historial, archivo, _resultado(), "base", ruta, "txt", True)
    assert p.id_historial is not None
    assert p.ruta_exportada == ruta
    assert p.motivo_historial is None and p.motivo_exportacion is None
    assert historial.obtener(p.id_historial).texto == "Hola mundo. Segunda frase."
    assert Path(ruta).exists()


def test_transcripcion_exportacion_fallida_deja_entrada_en_historial(historial, tmp_path):
    (tmp_path / "bloqueo").write_text("no es una carpeta")          # el destino no se puede crear
    archivo = str(tmp_path / "reunion.mp3")
    ruta = str(tmp_path / "bloqueo" / "reunion_transcripcion.txt")
    p = persistir_transcripcion(historial, archivo, _resultado(), "base", ruta, "txt", True)
    assert p.id_historial is not None
    assert historial.obtener(p.id_historial).texto == "Hola mundo. Segunda frase."
    assert p.ruta_exportada is None
    assert "reunion_transcripcion.txt" in p.motivo_exportacion
    assert p.motivo_historial is None
    segmentos = historial.obtener(p.id_historial).a_resultado().segmentos
    assert [seg.texto for seg in segmentos] == ["Hola mundo.", "Segunda frase."]


class _HistorialLleno:
    """Doble de Historial cuyo guardado falla, como con el disco lleno."""

    def crear(self, *args, **kwargs):
        raise sqlite3.OperationalError("database or disk is full")


def test_motivo_de_exportacion_no_repite_la_ruta(historial, tmp_path):
    (tmp_path / "bloqueo").write_text("no es una carpeta")          # el destino no se puede crear
    archivo = str(tmp_path / "reunion.mp3")
    ruta = str(tmp_path / "bloqueo" / "reunion_transcripcion.txt")
    p = persistir_transcripcion(historial, archivo, _resultado(), "base", ruta, "txt", True)
    assert p.motivo_exportacion.startswith("reunion_transcripcion.txt: ")
    assert str(tmp_path) not in p.motivo_exportacion
    assert "Errno" not in p.motivo_exportacion


def test_transcripcion_historial_fallido_exporta_igual(tmp_path):
    archivo = str(tmp_path / "reunion.mp3")
    ruta = str(tmp_path / "reunion_transcripcion.txt")
    p = persistir_transcripcion(_HistorialLleno(), archivo, _resultado(), "base", ruta, "txt", True)
    assert p.id_historial is None
    assert "database or disk is full" in p.motivo_historial
    assert p.ruta_exportada == ruta and Path(ruta).exists()
    assert p.motivo_exportacion is None


def test_transcripcion_sin_historial_ni_exportacion_no_guarda_en_ningun_sitio(tmp_path):
    (tmp_path / "bloqueo").write_text("no es una carpeta")
    archivo = str(tmp_path / "reunion.mp3")
    ruta = str(tmp_path / "bloqueo" / "reunion_transcripcion.txt")
    p = persistir_transcripcion(None, archivo, _resultado(), "base", ruta, "txt", True)
    assert p.id_historial is None and p.ruta_exportada is None
    assert p.motivo_historial == "Historial no disponible"
    assert "reunion_transcripcion.txt" in p.motivo_exportacion


def test_transcripcion_sin_historial_exporta_con_aviso_de_historial(tmp_path):
    archivo = str(tmp_path / "reunion.mp3")
    ruta = str(tmp_path / "reunion_transcripcion.txt")
    p = persistir_transcripcion(None, archivo, _resultado(), "base", ruta, "txt", True)
    assert p.id_historial is None
    assert p.motivo_historial == "Historial no disponible"
    assert p.ruta_exportada == ruta and Path(ruta).exists()
    assert p.motivo_exportacion is None


def test_documento_se_guarda_en_historial_y_exporta(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    ruta = str(tmp_path / "reunion_minuta.md")
    p = persistir_documento(historial, id_, "minuta", "# Minuta: Revisión\n- Acuerdo", "gpt-5.4", ruta)
    entrada = historial.obtener(id_)
    assert entrada.minuta.startswith("# Minuta") and entrada.minuta_modelo == "gpt-5.4"
    assert Path(ruta).read_text(encoding="utf-8").startswith("# Minuta")
    assert p.ruta_exportada == ruta
    assert p.motivo_exportacion is None and p.motivo_historial is None


def test_documento_exportacion_fallida_conserva_contenido_y_modelo(historial, tmp_path):
    (tmp_path / "bloqueo").write_text("no es una carpeta")
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    ruta = str(tmp_path / "bloqueo" / "reunion_minuta.md")
    p = persistir_documento(historial, id_, "minuta", "# Minuta: Revisión\n- Acuerdo", "gpt-5.4", ruta)
    entrada = historial.obtener(id_)
    assert entrada.minuta.startswith("# Minuta") and entrada.minuta_modelo == "gpt-5.4"
    assert p.ruta_exportada is None
    assert "reunion_minuta.md" in p.motivo_exportacion
    assert p.motivo_historial is None


def test_motivo_de_exportacion_de_documento_no_repite_la_ruta(historial, tmp_path):
    (tmp_path / "bloqueo").write_text("no es una carpeta")
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    ruta = str(tmp_path / "bloqueo" / "reunion_minuta.md")
    p = persistir_documento(historial, id_, "minuta", "# Minuta: Revisión", "gpt-5.4", ruta)
    assert p.motivo_exportacion.startswith("reunion_minuta.md: ")
    assert str(tmp_path) not in p.motivo_exportacion
    assert "Errno" not in p.motivo_exportacion


def test_documento_minuta_sin_titulo_editado_toma_titulo_de_la_minuta(historial, tmp_path):
    (tmp_path / "bloqueo").write_text("no es una carpeta")
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    ruta = str(tmp_path / "bloqueo" / "reunion_minuta.md")
    persistir_documento(historial, id_, "minuta", "# Minuta: Revisión de lanzamiento\n- Acuerdo", "gpt-5.4", ruta)
    assert historial.obtener(id_).titulo == "Revisión de lanzamiento"


def test_documento_sin_ruta_de_exportacion_solo_guarda_en_historial(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    p = persistir_documento(historial, id_, "resumen", "## Resumen\ntexto", "gpt-5.4", None)
    assert historial.obtener(id_).resumen == "## Resumen\ntexto"
    assert p.ruta_exportada is None and p.motivo_exportacion is None and p.motivo_historial is None


def test_documento_historial_fallido_exporta_y_avisa(historial, tmp_path):
    class _HistorialLlenoAlGuardar(Historial):
        def guardar_documento(self, *args, **kwargs):
            raise sqlite3.OperationalError("database or disk is full")

    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    historial_lleno = _HistorialLlenoAlGuardar(str(tmp_path / "historial.db"))
    ruta = str(tmp_path / "reunion_resumen.md")
    p = persistir_documento(historial_lleno, id_, "resumen", "## Resumen", "gpt-5.4", ruta)
    assert "database or disk is full" in p.motivo_historial
    assert Path(ruta).read_text(encoding="utf-8").startswith("## Resumen")
    assert p.ruta_exportada == ruta and p.motivo_exportacion is None


def test_documento_ambos_fallan_devuelve_los_dos_motivos(historial, tmp_path):
    class _HistorialLlenoAlGuardar(Historial):
        def guardar_documento(self, *args, **kwargs):
            raise sqlite3.OperationalError("database or disk is full")

    (tmp_path / "bloqueo").write_text("no es una carpeta")
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    historial_lleno = _HistorialLlenoAlGuardar(str(tmp_path / "historial.db"))
    ruta = str(tmp_path / "bloqueo" / "reunion_minuta.md")
    p = persistir_documento(historial_lleno, id_, "minuta", "# Minuta: X", "gpt-5.4", ruta)
    assert "database or disk is full" in p.motivo_historial
    assert "reunion_minuta.md" in p.motivo_exportacion
    assert p.ruta_exportada is None
    assert "Guardar como…" in texto_sin_guardado(p)


def test_aviso_sin_guardado_remite_a_guardar_como(tmp_path):
    nada = Persistencia(motivo_historial="Historial no disponible", motivo_exportacion="x_transcripcion.txt: error")
    assert "Guardar como…" in texto_sin_guardado(nada)
    con_historial = Persistencia(id_historial=3, motivo_exportacion="x_transcripcion.txt: error")
    assert texto_sin_guardado(con_historial) is None


def test_documento_sin_historial_exporta_con_aviso(tmp_path):
    ruta = str(tmp_path / "reunion_resumen.md")
    p = persistir_documento(None, None, "resumen", "## Resumen", "gpt-5.4", ruta)
    assert p.id_historial is None
    assert p.motivo_historial == "Historial no disponible"
    assert p.ruta_exportada == ruta and Path(ruta).read_text(encoding="utf-8").startswith("## Resumen")


def test_documento_sin_entrada_en_historial_exporta_con_aviso(historial, tmp_path):
    ruta = str(tmp_path / "reunion_resumen.md")
    p = persistir_documento(historial, None, "resumen", "## Resumen", "gpt-5.4", ruta)
    assert p.id_historial is None
    assert p.motivo_historial == "La transcripción no está en el historial"
    assert p.ruta_exportada == ruta and Path(ruta).exists()


def test_documento_historial_fallido_no_informa_id(historial, tmp_path):
    class _HistorialLlenoAlGuardar(Historial):
        def guardar_documento(self, *args, **kwargs):
            raise sqlite3.OperationalError("database or disk is full")

    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    ruta = str(tmp_path / "reunion_resumen.md")
    p = persistir_documento(_HistorialLlenoAlGuardar(str(tmp_path / "historial.db")), id_, "resumen", "## Resumen",
                            "gpt-5.4", ruta)
    assert p.id_historial is None
    assert p.ruta_exportada == ruta


def test_transcripcion_error_inesperado_al_exportar_no_lanza(historial, tmp_path):
    archivo = str(tmp_path / "reunion.mp3")
    ruta = str(tmp_path / "reunion_transcripcion.xyz")
    p = persistir_transcripcion(historial, archivo, _resultado(), "base", ruta, "xyz", True)
    assert p.id_historial is not None
    assert p.ruta_exportada is None
    assert "reunion_transcripcion.xyz" in p.motivo_exportacion


def test_transcripcion_error_inesperado_en_historial_no_lanza(tmp_path):
    class _HistorialRoto:
        def crear(self, *args, **kwargs):
            raise ValueError("dato no válido para el historial")

    archivo = str(tmp_path / "reunion.mp3")
    ruta = str(tmp_path / "reunion_transcripcion.txt")
    p = persistir_transcripcion(_HistorialRoto(), archivo, _resultado(), "base", ruta, "txt", True)
    assert p.id_historial is None
    assert "dato no válido" in p.motivo_historial
    assert p.ruta_exportada == ruta and Path(ruta).exists()


def test_documento_error_inesperado_en_historial_no_lanza(historial, tmp_path):
    class _HistorialRoto(Historial):
        def guardar_documento(self, *args, **kwargs):
            raise ValueError("dato no válido para el historial")

    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    ruta = str(tmp_path / "reunion_resumen.md")
    p = persistir_documento(_HistorialRoto(str(tmp_path / "historial.db")), id_, "resumen", "## Resumen",
                            "gpt-5.4", ruta)
    assert p.id_historial is None
    assert "dato no válido" in p.motivo_historial
    assert p.ruta_exportada == ruta


def test_documento_error_inesperado_al_exportar_no_lanza(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    ruta = str(tmp_path / "reunion\0resumen.md")          # un byte nulo en la ruta hace fallar la escritura
    p = persistir_documento(historial, id_, "resumen", "## Resumen", "gpt-5.4", ruta)
    assert p.id_historial == id_ and p.motivo_historial is None
    assert p.ruta_exportada is None
    assert "resumen.md" in p.motivo_exportacion


def test_motivo_de_fallo_sin_mensaje_usa_el_tipo_de_error(tmp_path):
    class _HistorialSinMensaje:
        def crear(self, *args, **kwargs):
            raise RuntimeError()

    ruta = str(tmp_path / "reunion_transcripcion.txt")
    p = persistir_transcripcion(_HistorialSinMensaje(), str(tmp_path / "reunion.mp3"), _resultado(), "base",
                                ruta, "txt", True)
    assert p.motivo_historial == "RuntimeError"


def test_destino_documento_exportado_y_en_historial():
    p = Persistencia(id_historial=3, ruta_exportada="/casa/reunion_minuta.md")
    assert texto_destino_documento(p) == "guardado como reunion_minuta.md; guardado en el historial"


def test_destino_documento_exportacion_fallida_nombra_archivo_y_motivo():
    p = Persistencia(id_historial=3, motivo_exportacion="reunion_minuta.md: Permiso denegado")
    texto = texto_destino_documento(p)
    assert "reunion_minuta.md" in texto and "Permiso denegado" in texto
    assert "guardado en el historial" in texto


def test_destino_documento_solo_historial_sin_ruta():
    assert texto_destino_documento(Persistencia(id_historial=3)) == "guardado en el historial"


def test_destino_documento_sin_ruta_e_historial_fallido_avisa_sin_guardado():
    texto = texto_destino_documento(Persistencia(motivo_historial="disco lleno"))
    assert "disco lleno" in texto and "Guardar como…" in texto


def test_destino_documento_nada_guardado_remite_a_guardar_como():
    p = Persistencia(motivo_historial="Historial no disponible", motivo_exportacion="reunion_minuta.md: error")
    assert "Guardar como…" in texto_destino_documento(p)


def test_documento_de_entrada_eliminada_avisa_y_exporta(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    historial.eliminar(id_)                                  # el usuario la borra mientras Copilot genera
    ruta = str(tmp_path / "reunion_minuta.md")
    p = persistir_documento(historial, id_, "minuta", "# Minuta: Revisión", "gpt-5.4", ruta)
    assert p.id_historial is None
    assert p.motivo_historial == "La entrada ya no está en el historial"
    assert Path(ruta).read_text(encoding="utf-8").startswith("# Minuta")
    assert p.ruta_exportada == ruta


def test_documento_de_entrada_eliminada_sin_exportacion_remite_a_guardar_como(historial, tmp_path):
    (tmp_path / "bloqueo").write_text("no es una carpeta")
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    historial.eliminar(id_)
    ruta = str(tmp_path / "bloqueo" / "reunion_minuta.md")
    p = persistir_documento(historial, id_, "minuta", "# Minuta: Revisión", "gpt-5.4", ruta)
    assert p.id_historial is None and p.ruta_exportada is None
    assert "Guardar como…" in texto_destino_documento(p)


def test_motivo_de_error_de_sistema_usa_solo_la_causa():
    error = PermissionError(13, "Permiso denegado", "/casa/secreta/reunion_minuta.md")
    assert motivo_de_error(error) == "Permiso denegado"


def test_motivo_de_error_sin_mensaje_usa_el_tipo():
    assert motivo_de_error(RuntimeError()) == "RuntimeError"


def test_documento_con_nota_de_la_aplicacion_se_guarda_y_exporta_intacto(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    ruta = str(tmp_path / "reunion_minuta.md")
    minuta = ("# Minuta: Revisión del presupuesto\n\n**Fecha:** 29 de septiembre de 2026\n\n"
              "## Próximos pasos\n- Próxima reunión, si se menciona."
              "\n\n---\n\n> Nota de la aplicación: la transcripción se procesó en 2 partes y este documento se redactó "
              "a partir de notas extraídas de cada parte, no de la transcripción completa. Contrasta nombres, fechas, "
              "cifras y condiciones con la transcripción antes de darlo por bueno. La revisión de fidelidad se hizo "
              "contra esas notas, no contra la transcripción.")
    p = persistir_documento(historial, id_, "minuta", minuta, "gpt-5.4", ruta)
    assert historial.obtener(id_).minuta == minuta
    assert Path(ruta).read_text(encoding="utf-8") == minuta + "\n"
    assert historial.obtener(id_).titulo == "Revisión del presupuesto"
    assert p.ruta_exportada == ruta and p.motivo_exportacion is None and p.motivo_historial is None


def test_documento_incompleto_con_nota_se_guarda_y_exporta(historial, tmp_path):
    id_ = historial.crear(str(tmp_path / "reunion.mp3"), _resultado())
    ruta = str(tmp_path / "reunion_minuta.md")
    minuta = ("# Minuta: Revisión del presupuesto\n\n**Fecha:** 29 de septiembre de 2026\n\n"
              "## Objetivo\nRevisar el presupuesto trimestral.\n\n"
              "\n---\n\n> Nota de la aplicación: a este documento le faltan secciones obligatorias que Copilot no "
              "devolvió ni al pedírselas de nuevo: Tareas y pendientes, Próximos pasos. No lo des por completo: vuelve "
              "a generarlo o complétalo con la transcripción.")
    p = persistir_documento(historial, id_, "minuta", minuta, "gpt-5.4", ruta)
    assert historial.obtener(id_).minuta == minuta
    assert Path(ruta).read_text(encoding="utf-8") == minuta + "\n"
    assert historial.obtener(id_).titulo == "Revisión del presupuesto"
    assert p.ruta_exportada == ruta and p.motivo_exportacion is None and p.motivo_historial is None
