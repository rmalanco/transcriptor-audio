"""Carga y validación de `config/settings.yaml`: el único punto que lee la configuración.

No importa faster_whisper ni customtkinter, para que la CLI pueda validarla sin cargar Whisper.
"""

import copy
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

log = logging.getLogger("transcriptor.configuracion")

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_POR_DEFECTO = RAIZ_PROYECTO / "config" / "settings.yaml"
# Preferencias del usuario (p. ej. el modelo de IA elegido): fuera del repo, junto al token de Copilot
RUTA_PREFERENCIAS = Path("~/.local/share/transcriptor-audio/preferencias.json").expanduser()

SECCIONES = ("modelo", "transcripcion", "salida", "ia", "historial")
DISPOSITIVOS = ("cpu", "cuda", "auto")
TIPOS_COMPUTO = ("int8", "int16", "float16", "float32")
FORMATOS = ("txt", "srt", "vtt", "json")
# Única lista de modelos de Whisper: la usan la CLI, la ventana y la validación de `modelo.nombre`.
MODELOS_WHISPER = ("tiny", "base", "small", "medium", "large-v3-turbo", "large-v1", "large-v2", "large-v3")


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


def _tabla() -> dict[tuple[str, str], _Clave]:
    """Las claves que lee la app: (sección, clave) → valor por defecto y comprobación."""
    nombre = _Clave("large-v3-turbo", "uno de " + ", ".join(MODELOS_WHISPER), lambda v: v in MODELOS_WHISPER)
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
        ("ia", "temperatura"): _Clave(0.2, no_negativo, _es_numero_no_negativo),
        ("ia", "max_caracteres_bloque"): _Clave(60000, entero, _es_entero_positivo),
        ("ia", "peticiones_paralelas"): _Clave(3, entero, _es_entero_positivo),
        ("ia", "revision_fidelidad"): _Clave(False, booleano, _es_booleano),
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


def cargar_configuracion(ruta=None) -> dict:
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
    for (seccion, clave), entrada in _tabla().items():
        valor = resultado[seccion].get(clave)
        if valor is None:
            resultado[seccion][clave] = entrada.defecto
        elif not entrada.valida(valor):
            raise ErrorConfiguracion(f"En la configuración {ruta}, {_mensaje_invalido(seccion, clave, valor)}.")
    return resultado


def _leer_preferencias() -> dict:
    """Preferencias del usuario. Si el archivo no existe o no es un objeto JSON, devuelve {}."""
    try:
        datos = json.loads(RUTA_PREFERENCIAS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        log.warning("Las preferencias %s no son un JSON válido; se ignoran", RUTA_PREFERENCIAS)
        return {}
    if not isinstance(datos, dict):
        log.warning("Las preferencias %s no son un objeto JSON; se ignoran", RUTA_PREFERENCIAS)
        return {}
    return datos


def leer_modelo_preferido() -> Optional[str]:
    """Modelo de IA que el usuario eligió en el selector, o None si no hay ninguno válido."""
    datos = _leer_preferencias()
    if "modelo_ia" not in datos:
        return None
    modelo = datos["modelo_ia"]
    if isinstance(modelo, str) and modelo.strip():
        return modelo
    log.warning("En %s, «modelo_ia» no es un texto válido; se usa el de settings.yaml", RUTA_PREFERENCIAS)
    return None


def guardar_modelo_preferido(modelo: str) -> None:
    """Guarda el modelo de IA elegido conservando las demás preferencias. Lanza OSError si no puede escribir."""
    datos = _leer_preferencias()
    datos["modelo_ia"] = modelo
    RUTA_PREFERENCIAS.parent.mkdir(parents=True, exist_ok=True)
    RUTA_PREFERENCIAS.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def modelo_ia_efectivo(configuracion: dict, preferido: Optional[str]) -> str:
    """El modelo que usa la ventana: el preferido por el usuario si lo hay; si no, `ia.modelo` del YAML."""
    return preferido or configuracion["ia"]["modelo"]


@dataclass(frozen=True)
class AjustesLeidos:
    valores: dict   # (sección, clave) → valor tal como vino del JSON
    avisos: list    # textos para Registro
    ilegible: bool  # True solo si el archivo existe y no es JSON o no es un objeto


CLAVE_AJUSTES = "configuracion"


def _mensaje_invalido(seccion: str, clave: str, valor) -> str:
    return f"`{seccion}.{clave}` debe ser {_tabla()[(seccion, clave)].esperado} (vale «{valor}»)"


def leer_ajustes() -> AjustesLeidos:
    try:
        datos = json.loads(RUTA_PREFERENCIAS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return AjustesLeidos({}, [], False)
    except OSError as e:
        motivo = e.strerror or str(e)
        return AjustesLeidos({}, [f"Las preferencias {RUTA_PREFERENCIAS} no se pudieron leer ({motivo}); "
                                  "se usan los valores de config/settings.yaml."], False)
    except (ValueError, RecursionError):  # JSON inválido, texto que no es UTF-8 o anidamiento extremo
        return AjustesLeidos({}, [f"Las preferencias {RUTA_PREFERENCIAS} no son un JSON válido; se usan los "
                                  "valores de config/settings.yaml. Al guardar se reemplazará el archivo."], True)
    if not isinstance(datos, dict):
        return AjustesLeidos({}, [f"Las preferencias {RUTA_PREFERENCIAS} no son un JSON válido; se usan los "
                                  "valores de config/settings.yaml. Al guardar se reemplazará el archivo."], True)
    grupos = datos.get(CLAVE_AJUSTES, {})
    if not isinstance(grupos, dict):
        return AjustesLeidos({}, [f"En {RUTA_PREFERENCIAS}, «configuracion» no es un objeto; se ignora."], False)
    valores = {}
    avisos = []
    for seccion, claves in grupos.items():
        if not isinstance(claves, dict):
            avisos.append(f"En {RUTA_PREFERENCIAS}, la sección `{seccion}` no es un objeto; se ignora.")
            continue
        for clave, valor in claves.items():
            valores[(seccion, clave)] = valor
    return AjustesLeidos(valores, avisos, False)


def combinar(proyecto: dict, ajustes: AjustesLeidos) -> tuple[dict, list]:
    efectiva = copy.deepcopy(proyecto)
    avisos = list(ajustes.avisos)
    for (seccion, clave), valor in ajustes.valores.items():
        if (seccion, clave) == ("ia", "modelo"):
            avisos.append(f"En {RUTA_PREFERENCIAS}, `ia.modelo` no se guarda en «configuracion» "
                          "(el modelo elegido va en «modelo_ia»); se ignora.")
            continue
        entrada = _tabla().get((seccion, clave))
        if entrada is None:
            avisos.append(f"En {RUTA_PREFERENCIAS}, `{seccion}.{clave}` no es una clave de la configuración; "
                          "se ignora.")
            continue
        if (isinstance(valor, float) and not math.isfinite(valor)) or not entrada.valida(valor):
            avisos.append(f"En {RUTA_PREFERENCIAS}, {_mensaje_invalido(seccion, clave, valor)}; "
                          "se usa el valor de config/settings.yaml.")
            continue
        efectiva[seccion][clave] = valor
    return efectiva, avisos
