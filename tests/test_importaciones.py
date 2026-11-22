"""Importaciones perezosas: `faster_whisper` solo se carga al cargar un modelo (historia 08)."""

import subprocess
import sys
import types
from pathlib import Path

import pytest

from src.transcriber import TranscriptorAudio

RAIZ = Path(__file__).resolve().parent.parent

# Orden del criterio 1 de la historia 08.
MODULOS = [
    "src", "src.registro", "src.configuracion", "src.utils", "src.transcriber", "src.historial",
    "src.persistencia", "src.flujo_transcripcion", "src.copilot", "src.asistente_ia", "src.flujo_documentos",
    "src.main", "src.ui_copilot", "src.ui_historial", "src.ui",
]
# Módulos que no deben cargar tkinter ni customtkinter: `src.flujo_transcripcion` (historia 09) y
# `src.flujo_documentos` (historia 10).
SIN_TK: list[str] = ["src.flujo_transcripcion", "src.flujo_documentos"]

GUION = """
import importlib
import sys
import traceback

MODULOS = %r
SIN_TK = %r
anotados = []
for nombre in MODULOS:
    try:
        importlib.import_module(nombre)
    except Exception:
        print("FALLO al importar", nombre, file=sys.stderr)
        traceback.print_exc()
        sys.exit(2)
    if "faster_whisper" in sys.modules:
        anotados.append(f"{nombre}: carga faster_whisper")
    if nombre in SIN_TK:
        for gui in ("tkinter", "customtkinter"):
            if gui in sys.modules:
                anotados.append(f"{nombre}: carga {gui}")
import src
for nombre in ("TranscriptorAudio", "validar_archivo", "obtener_info_archivo"):
    if hasattr(src, nombre):
        anotados.append(f"src expone {nombre}")
if anotados:
    print("\\n".join(anotados))
    sys.exit(1)
""" % (MODULOS, SIN_TK)


def test_ningun_modulo_carga_faster_whisper_al_importarse():
    resultado = subprocess.run(
        [sys.executable, "-c", GUION], cwd=RAIZ, capture_output=True, text=True
    )
    assert resultado.returncode == 0, (
        f"stdout:\n{resultado.stdout}\nstderr:\n{resultado.stderr}"
    )


def _modulo_falso(llamadas):
    """Un `faster_whisper` falso cuyo `WhisperModel` anota sus argumentos en `llamadas`."""
    class WhisperModelFalso:
        def __init__(self, nombre, **kwargs):
            llamadas.append((nombre, kwargs))

    modulo = types.ModuleType("faster_whisper")
    modulo.WhisperModel = WhisperModelFalso
    return modulo


def test_modelo_importa_faster_whisper_al_cargarse(monkeypatch, tmp_path):
    transcriptor = TranscriptorAudio("small", "cpu", "int8", cache_dir=str(tmp_path))
    llamadas = []
    monkeypatch.setitem(sys.modules, "faster_whisper", _modulo_falso(llamadas))

    primero = transcriptor.modelo
    segundo = transcriptor.modelo

    assert llamadas == [("small", {"device": "cpu", "compute_type": "int8", "download_root": str(tmp_path)})]
    assert primero is segundo


def test_si_falla_el_import_se_reintenta_al_volver_a_pedir_el_modelo(monkeypatch, tmp_path):
    transcriptor = TranscriptorAudio("small", "cpu", "int8", cache_dir=str(tmp_path))
    monkeypatch.setitem(sys.modules, "faster_whisper", None)

    with pytest.raises(ImportError):
        _ = transcriptor.modelo
    assert transcriptor._modelo is None

    llamadas = []
    monkeypatch.setitem(sys.modules, "faster_whisper", _modulo_falso(llamadas))
    modelo = transcriptor.modelo

    assert modelo is not None
    assert llamadas == [("small", {"device": "cpu", "compute_type": "int8", "download_root": str(tmp_path)})]
