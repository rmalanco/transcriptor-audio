"""Carga y validación de `config/settings.yaml`: el único punto que lee la configuración.

No importa faster_whisper, customtkinter ni pydantic, para que la CLI pueda validarla sin cargar Whisper.
"""

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_POR_DEFECTO = RAIZ_PROYECTO / "config" / "settings.yaml"

SECCIONES = ("modelo", "transcripcion", "salida", "ia", "historial")
DISPOSITIVOS = ("cpu", "cuda", "auto")
TIPOS_COMPUTO = ("int8", "int16", "float16", "float32")
FORMATOS = ("txt", "srt", "vtt", "json")


class ErrorConfiguracion(Exception):
    """La configuración no se puede leer o tiene un valor no válido. El mensaje está pensado para el usuario."""


def _cualquiera(valor) -> bool:
    return True


def _es_texto(valor) -> bool:
    return isinstance(valor, str)


def _es_texto_no_vacio(valor) -> bool:
    return isinstance(valor, str) and valor.strip() != ""


def _es_booleano(valor) -> bool:
    return isinstance(valor, bool)


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _es_numero_no_negativo(valor) -> bool:
    return _es_numero(valor) and valor >= 0


def _es_entero_positivo(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


@dataclass(frozen=True)
class _Clave:
    defecto: Any
    esperado: str = ""                      # cómo se describe lo permitido en el mensaje de error
    valida: Callable[[Any], bool] = _cualquiera


def _tabla(modelos_whisper=None) -> dict[tuple[str, str], _Clave]:
    """Las claves que lee la app: (sección, clave) → valor por defecto y comprobación.

    `modelos_whisper` es la lista de modelos que admite la CLI o la ventana; se pasa desde fuera porque
    este módulo no puede importarla sin crear un ciclo (`main` y `ui` importan este módulo).
    """
    if modelos_whisper:
        nombre = _Clave("large-v3-turbo", "uno de " + ", ".join(modelos_whisper), lambda v: v in modelos_whisper)
    else:
        nombre = _Clave("large-v3-turbo", "un texto", _es_texto)
    entero = "un número entero mayor que 0"
    numero = "un número"
    no_negativo = "un número mayor o igual que 0"
    booleano = "true o false"
    return {
        ("modelo", "nombre"): nombre,
        ("modelo", "dispositivo"): _Clave("cpu", "uno de " + ", ".join(DISPOSITIVOS), lambda v: v in DISPOSITIVOS),
        ("modelo", "compute_type"): _Clave("int8", "uno de " + ", ".join(TIPOS_COMPUTO),
                                           lambda v: v in TIPOS_COMPUTO),
        ("transcripcion", "idioma"): _Clave("es", "un texto no vacío", _es_texto_no_vacio),
        ("transcripcion", "beam_size"): _Clave(5, entero, _es_entero_positivo),
        ("transcripcion", "best_of"): _Clave(5, entero, _es_entero_positivo),
        ("transcripcion", "temperature"): _Clave(0.0, no_negativo, _es_numero_no_negativo),
        ("transcripcion", "condition_on_previous_text"): _Clave(False, booleano, _es_booleano),
        ("transcripcion", "compression_ratio_threshold"): _Clave(2.4, numero, _es_numero),
        ("transcripcion", "logprob_threshold"): _Clave(-1.0, numero, _es_numero),
        ("transcripcion", "no_speech_threshold"): _Clave(0.6, numero, _es_numero),
        ("salida", "formato"): _Clave("txt", "uno de " + ", ".join(FORMATOS), lambda v: v in FORMATOS),
        ("salida", "incluir_timestamps"): _Clave(True, booleano, _es_booleano),
        ("salida", "palabra_por_palabra"): _Clave(False, booleano, _es_booleano),
        ("ia", "modelo"): _Clave("gpt-4.1", "un texto", _es_texto),
        ("ia", "copilot_enterprise_url"): _Clave("", "un texto", _es_texto),
        ("ia", "temperatura"): _Clave(0.3, no_negativo, _es_numero_no_negativo),
        ("ia", "max_caracteres_bloque"): _Clave(60000, entero, _es_entero_positivo),
        ("ia", "peticiones_paralelas"): _Clave(3, entero, _es_entero_positivo),
        ("ia", "revision_fidelidad"): _Clave(True, booleano, _es_booleano),
        ("historial", "ruta"): _Clave("data/historial.db", "un texto no vacío", _es_texto_no_vacio),
    }


def _leer_yaml(ruta) -> Any:
    try:
        with open(ruta, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise ErrorConfiguracion(f"No se encontró la configuración {ruta}.") from None
    except yaml.YAMLError as e:
        marca = getattr(e, "problem_mark", None)
        detalle = f" (línea {marca.line + 1}, columna {marca.column + 1})" if marca else ""
        raise ErrorConfiguracion(f"La configuración {ruta} no es un YAML válido{detalle}.") from None


def cargar_configuracion(ruta=None, *, modelos_whisper=None) -> dict:
    ruta = RUTA_POR_DEFECTO if ruta is None else ruta
    datos = _leer_yaml(ruta)
    if datos is None:
        datos = {}
    if not isinstance(datos, dict):
        raise ErrorConfiguracion(f"La configuración {ruta} no es un mapa de secciones.")
    resultado = copy.deepcopy(datos)
    for seccion in SECCIONES:
        valores = resultado.get(seccion)
        if valores is None:
            valores = {}
        if not isinstance(valores, dict):
            raise ErrorConfiguracion(f"En la configuración {ruta}, `{seccion}` debe ser una sección con claves "
                                     f"(vale «{valores}»).")
        resultado[seccion] = valores
    for (seccion, clave), entrada in _tabla(modelos_whisper).items():
        valor = resultado[seccion].get(clave)
        if valor is None:
            resultado[seccion][clave] = entrada.defecto
        elif not entrada.valida(valor):
            raise ErrorConfiguracion(f"En la configuración {ruta}, `{seccion}.{clave}` debe ser "
                                     f"{entrada.esperado} (vale «{valor}»).")
    return resultado


def guardar_modelo_ia(modelo: str, ruta=None) -> bool:
    """Cambia `ia.modelo` en el archivo editando solo esa línea, para no perder los comentarios del YAML.
    Devuelve False si no encuentra la clave."""
    ruta = RUTA_POR_DEFECTO if ruta is None else ruta
    lineas = Path(ruta).read_text(encoding="utf-8").splitlines(keepends=True)
    en_ia = False
    for i, linea in enumerate(lineas):
        if linea.strip() and not linea[0].isspace():
            en_ia = linea.startswith("ia:")
            continue
        if en_ia:
            nueva, cambios = re.subn(r'^(\s+modelo:\s*)("[^"]*"|[^\s#]+)', lambda m: f'{m[1]}"{modelo}"', linea)
            if cambios:
                lineas[i] = nueva
                Path(ruta).write_text("".join(lineas), encoding="utf-8")
                return True
    return False
