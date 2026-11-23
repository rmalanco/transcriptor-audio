"""Carga y validación de `config/settings.yaml`: el único punto que lee la configuración.

No importa faster_whisper ni customtkinter, para que la CLI pueda validarla sin cargar Whisper.
"""

import copy
import json
import logging
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from src.idiomas import nombre_de_idioma, opciones_de_idioma

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
# Topes solo del panel y de las preferencias (no del YAML): (mínimo, máximo, cómo se describe lo permitido).
TOPES_PANEL = {
    ("transcripcion", "beam_size"): (1, 20, "un número entero entre 1 y 20"),
    ("transcripcion", "best_of"): (1, 20, "un número entero entre 1 y 20"),
    ("transcripcion", "temperature"): (0, 2, "un número entre 0 y 2"),
    ("transcripcion", "no_speech_threshold"): (0, 1, "un número entre 0 y 1"),
    ("ia", "temperatura"): (0, 2, "un número entre 0 y 2"),
    ("ia", "peticiones_paralelas"): (1, 8, "un número entero entre 1 y 8"),
    ("ia", "max_caracteres_bloque"): (5000, 500000, "un número entero entre 5000 y 500000"),
}
# Cómo se describe en el panel lo permitido cuando la clave no tiene tope (el YAML sigue con la tabla de _tabla()).
_ESPERADO_PANEL = {
    ("ia", "copilot_enterprise_url"):
        "un nombre de dominio sin https:// ni barras, como empresa.ghe.com, o estar vacío",
}
# Formas que el formulario acepta antes de convertir (sin «nan», «inf» ni «3.0» para enteros).
_ENTERO_FORMULARIO = re.compile(r"-?[0-9]+")
_NOMBRE_DE_HOST = re.compile(r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+")
_NUMERO_FORMULARIO = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?")


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
    datos = _leer_para_escribir()
    datos["modelo_ia"] = modelo
    _escribir_preferencias_atomico(datos)


def _leer_para_escribir() -> dict:
    try:
        datos = json.loads(RUTA_PREFERENCIAS.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (ValueError, RecursionError):  # JSON inválido, texto que no es UTF-8 o anidamiento extremo
        return {}
    return datos if isinstance(datos, dict) else {}


def guardar_ajustes(proyecto: dict, valores: dict, modelo_ia: Optional[str] = None) -> list[str]:
    if modelo_ia is not None:
        # Import aquí: copilot importa httpx y esta carga no debe pagarlo al importar configuracion.
        from src import copilot
        familia = copilot.familia_excluida(modelo_ia)
        if familia is not None:
            raise ValueError(f"El modelo «{modelo_ia}» es de la familia «{familia}», no autorizada por la empresa")
    datos = _leer_para_escribir()
    grupos = {}
    avisos_descartes = []
    guardados = datos.get(CLAVE_AJUSTES, {})
    if not isinstance(guardados, dict):
        avisos_descartes.append(f"`{CLAVE_AJUSTES}`")
        guardados = {}
    for seccion, claves in guardados.items():
        if not isinstance(claves, dict):
            avisos_descartes.append(f"`{seccion}`")
            continue
        for clave, valor in claves.items():
            if ((seccion, clave) == ("ia", "modelo") or (seccion, clave) not in _tabla()
                    or _motivo_de_rechazo(seccion, clave, valor, con_disco=False)):
                avisos_descartes.append(f"`{seccion}.{clave}`")
                continue
            grupos.setdefault(seccion, {})[clave] = valor
    for (seccion, clave), valor in valores.items():
        if valor == proyecto[seccion][clave]:
            grupos.get(seccion, {}).pop(clave, None)
        else:
            grupos.setdefault(seccion, {})[clave] = valor
    grupos = {seccion: claves for seccion, claves in grupos.items() if claves}
    if grupos:
        datos[CLAVE_AJUSTES] = grupos
    else:
        datos.pop(CLAVE_AJUSTES, None)
    if modelo_ia == proyecto["ia"]["modelo"]:
        datos.pop("modelo_ia", None)
    elif modelo_ia is not None:
        datos["modelo_ia"] = modelo_ia
    _escribir_preferencias_atomico(datos)
    if avisos_descartes:
        return [f"Se descartaron de {RUTA_PREFERENCIAS} claves que no sirven: {', '.join(avisos_descartes)}."]
    return []


def restablecer_ajustes() -> None:
    datos = _leer_para_escribir()
    datos.pop(CLAVE_AJUSTES, None)
    datos.pop("modelo_ia", None)
    _escribir_preferencias_atomico(datos)


def _escribir_preferencias_atomico(datos: dict) -> None:
    RUTA_PREFERENCIAS.parent.mkdir(parents=True, exist_ok=True)
    temporal = RUTA_PREFERENCIAS.with_name(RUTA_PREFERENCIAS.name + ".tmp")
    try:
        temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporal, RUTA_PREFERENCIAS)
    except OSError:
        try:
            temporal.unlink(missing_ok=True)
        except OSError:
            pass  # si tampoco se puede borrar el temporal, importa más el error de la escritura
        raise


def modelo_ia_efectivo(configuracion: dict, preferido: Optional[str]) -> str:
    """El modelo que usa la ventana: el preferido por el usuario si lo hay; si no, `ia.modelo` del YAML."""
    return preferido or configuracion["ia"]["modelo"]


@dataclass(frozen=True)
class AjustesLeidos:
    valores: dict   # (sección, clave) → valor tal como vino del JSON
    avisos: list    # textos para Registro
    ilegible: bool  # True solo si el archivo existe y no es JSON o no es un objeto


CLAVE_AJUSTES = "configuracion"


def _mensaje_invalido(seccion: str, clave: str, valor, panel: bool = False) -> str:
    """Mensaje de un valor no válido. En el panel y las preferencias, el tope (si lo tiene) manda sobre la tabla."""
    esperado = _tabla()[(seccion, clave)].esperado
    if panel and (seccion, clave) in TOPES_PANEL:
        esperado = TOPES_PANEL[(seccion, clave)][2]
    elif panel and (seccion, clave) in _ESPERADO_PANEL:
        esperado = _ESPERADO_PANEL[(seccion, clave)]
    return f"`{seccion}.{clave}` debe ser {esperado} (vale «{valor}»)"


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
        motivo = _motivo_de_rechazo(seccion, clave, valor, con_disco=False)
        if motivo is not None:
            avisos.append(f"En {RUTA_PREFERENCIAS}, {motivo}; se usa el valor de config/settings.yaml.")
            continue
        efectiva[seccion][clave] = valor
    return efectiva, avisos


def claves_cambiadas(anterior: dict, nueva: dict) -> set:
    """Claves de `_tabla()` cuyo valor en `nueva` no es el de `anterior`."""
    return {(seccion, clave) for seccion, clave in _tabla() if anterior[seccion][clave] != nueva[seccion][clave]}


def valores_laterales(cambiadas: set, configuracion: dict) -> dict:
    """Valores de los controles del panel lateral de las claves de `cambiadas` que los tienen. Las claves del dict
    son los nombres de las variables de la ventana; el idioma añade sus opciones."""
    directos = {
        ("modelo", "nombre"): "var_modelo",
        ("modelo", "dispositivo"): "var_dispositivo",
        ("modelo", "compute_type"): "var_compute",
        ("salida", "formato"): "var_formato",
        ("salida", "incluir_timestamps"): "var_timestamps",
    }
    valores = {nombre: configuracion[seccion][clave] for (seccion, clave), nombre in directos.items()
               if (seccion, clave) in cambiadas}
    if ("transcripcion", "idioma") in cambiadas:
        codigo = configuracion["transcripcion"]["idioma"]
        valores["var_idioma"] = nombre_de_idioma(codigo)
        valores["opciones_idioma"] = opciones_de_idioma(codigo)
    return valores


def valor_desde_formulario(seccion: str, clave: str, valor_widget):
    """Convierte el valor de un campo del formulario al tipo del valor por defecto de su clave y lo comprueba.

    Lanza ErrorConfiguracion con el mensaje para el usuario (con punto final). Una clave desconocida lanza KeyError.
    """
    defecto = _tabla()[(seccion, clave)].defecto
    if isinstance(defecto, bool):
        if isinstance(valor_widget, bool):
            return valor_widget
        raise ErrorConfiguracion(_mensaje_invalido(seccion, clave, valor_widget, panel=True) + ".")
    if not isinstance(valor_widget, str):
        raise ErrorConfiguracion(_mensaje_invalido(seccion, clave, valor_widget, panel=True) + ".")
    texto = valor_widget.strip()
    convertido = texto
    if isinstance(defecto, int):
        convertido = int(texto) if _ENTERO_FORMULARIO.fullmatch(texto) else None
    elif isinstance(defecto, float):
        numero = texto.replace(",", ".")
        convertido = float(numero) if _NUMERO_FORMULARIO.fullmatch(numero) else None
    if convertido is None:
        raise ErrorConfiguracion(_mensaje_invalido(seccion, clave, texto, panel=True) + ".")
    motivo = _motivo_de_rechazo(seccion, clave, convertido, mostrado=texto)
    if motivo is not None:
        raise ErrorConfiguracion(motivo + ".")
    return convertido


def _motivo_de_rechazo(seccion: str, clave: str, valor, mostrado: Optional[str] = None,
                       con_disco: bool = True) -> Optional[str]:
    """Qué falla en un valor ya convertido, sin punto final; None si vale. Lo usan el formulario y las preferencias.

    `mostrado` es el texto que va en «vale» (por defecto, `str(valor)`). `con_disco=False` omite la comprobación de
    que la carpeta de `historial.ruta` se puede crear o escribir (las preferencias al abrir no miran el disco).
    """
    texto = str(valor) if mostrado is None else mostrado
    if isinstance(valor, float) and not math.isfinite(valor):
        return _mensaje_invalido(seccion, clave, texto, panel=True)
    tope = TOPES_PANEL.get((seccion, clave))
    if not _tabla()[(seccion, clave)].valida(valor) or (tope is not None and not tope[0] <= valor <= tope[1]):
        return _mensaje_invalido(seccion, clave, texto, panel=True)
    if (seccion, clave) == ("ia", "copilot_enterprise_url") and valor and not _NOMBRE_DE_HOST.fullmatch(valor):
        return _mensaje_invalido(seccion, clave, texto, panel=True)
    if (seccion, clave) == ("historial", "ruta"):
        return _motivo_de_ruta(valor, texto, con_disco)
    return None


def _motivo_de_ruta(ruta_texto: str, mostrado: str, con_disco: bool) -> Optional[str]:
    """`historial.ruta` no puede caer dentro del repo salvo en data/ (regla 8) y, si `con_disco`, su carpeta debe
    existir y ser escribible o poder crearse. No crea ninguna carpeta."""
    raiz = Path(RAIZ_PROYECTO).resolve()
    ruta = Path(ruta_texto)
    ruta = (ruta if ruta.is_absolute() else raiz / ruta).resolve()
    if ruta.is_relative_to(raiz) and not ruta.is_relative_to((raiz / "data").resolve()):
        return f"`historial.ruta` no puede estar dentro de la carpeta del proyecto salvo en data/ (vale «{mostrado}»)"
    if con_disco and not _carpeta_escribible(ruta.parent):
        return f"`historial.ruta` está en una carpeta que no se puede crear ni escribir (vale «{mostrado}»)"
    return None


def _carpeta_escribible(carpeta: Path) -> bool:
    """True si `carpeta` existe y se puede escribir, o no existe y su primer antecesor existente es una carpeta
    escribible. Mira el disco sin crear nada."""
    existente = carpeta
    while not existente.exists() and existente != existente.parent:
        existente = existente.parent
    return existente.is_dir() and os.access(existente, os.W_OK)


def validar_formulario(valores_widget: dict, modelo_ia: Optional[str] = None) -> tuple[dict, dict]:
    """Convierte y comprueba un subconjunto de campos del formulario. Devuelve (convertidos, errores).

    Los errores van en el orden de entrada y, al final, el del modelo de IA (regla 7). Una clave desconocida o
    `ia.modelo` entre `valores_widget` es un error de programación (ValueError), no de usuario.
    """
    convertidos: dict = {}
    errores: dict = {}
    for (seccion, clave), valor in valores_widget.items():
        if (seccion, clave) == ("ia", "modelo"):
            raise ValueError("`ia.modelo` no va en valores_widget: se pasa como modelo_ia")
        if (seccion, clave) not in _tabla():
            raise ValueError(f"`{seccion}.{clave}` no es una clave de la configuración")
        try:
            convertidos[(seccion, clave)] = valor_desde_formulario(seccion, clave, valor)
        except ErrorConfiguracion as e:
            errores[(seccion, clave)] = str(e)
    if modelo_ia is not None:
        # Import aquí: copilot importa httpx y esta carga no debe pagarlo al importar configuracion.
        from src import copilot
        familia = copilot.familia_excluida(modelo_ia)
        if familia is not None:
            errores[("ia", "modelo")] = (f"El modelo «{modelo_ia}» es de la familia «{familia}», que no está "
                                         "autorizada por la empresa. Elige otro modelo.")
    return convertidos, errores


REQUIEREN_REINICIO = frozenset({("historial", "ruta")})  # cambiar estas claves pide reiniciar


@dataclass(frozen=True)
class ResultadoGuardado:
    """Lo que devuelve guardar_formulario: la vista solo lo lee. `efectiva` es None si no se guardó nada."""
    errores: dict               # (sección, clave) → texto; vacío si se intentó escribir
    efectiva: Optional[dict]    # configuración tras guardar y releer; None si no se guardó
    modelo_preferido: Optional[str]  # modelo de IA que quedó guardado (None = ninguno); solo si efectiva no es None
    avisos: list                # descartes de guardar_ajustes y avisos de combinar tras releer
    cambiadas: set              # claves que cambiaron respecto de `anterior` (y ("ia", "modelo") si cambió)
    mensaje: str                # pie de la vista


def guardar_formulario(proyecto: dict, anterior: dict, valores_widget: dict, modelo_ia: Optional[str] = None,
                       preferido_anterior: Optional[str] = None) -> ResultadoGuardado:
    """Valida el formulario y, si está bien, guarda las diferencias. Con errores no escribe nada."""
    convertidos, errores = validar_formulario(valores_widget, modelo_ia)
    if errores:
        return ResultadoGuardado(errores, None, None, [], set(), resumen_errores(len(errores)))
    try:
        descartes = guardar_ajustes(proyecto, convertidos, modelo_ia)
    except OSError as e:
        return ResultadoGuardado({}, None, None, [], set(),
                                 f"No se pudo guardar la configuración: {e.strerror or str(e)}.")
    return _resultado_tras_escribir(proyecto, anterior, preferido_anterior, descartes, "Configuración guardada")


def restablecer_formulario(proyecto: dict, anterior: dict, preferido_anterior: Optional[str]) -> ResultadoGuardado:
    """Borra la configuración y el modelo de IA guardados (lo que deja el YAML) y devuelve el resultado para la vista.
    Si la escritura falla, no devuelve configuración efectiva."""
    try:
        restablecer_ajustes()
    except OSError as e:
        return ResultadoGuardado({}, None, None, [], set(),
                                 f"No se pudo restablecer la configuración: {e.strerror or str(e)}.")
    return _resultado_tras_escribir(proyecto, anterior, preferido_anterior, [],
                                    "Se restablecieron los valores de config/settings.yaml")


def _resultado_tras_escribir(proyecto: dict, anterior: dict, preferido_anterior: Optional[str], avisos_previos: list,
                             mensaje: str) -> ResultadoGuardado:
    """Relee los ajustes ya escritos y arma el resultado: claves cambiadas, modelo de IA y nota de reinicio."""
    efectiva, avisos = combinar(proyecto, leer_ajustes())
    preferido = leer_modelo_preferido()
    cambiadas = claves_cambiadas(anterior, efectiva)
    if modelo_ia_efectivo(anterior, preferido_anterior) != modelo_ia_efectivo(efectiva, preferido):
        cambiadas.add(("ia", "modelo"))
    if cambiadas & REQUIEREN_REINICIO:
        mensaje += " · el historial nuevo se abrirá al reiniciar la app"
    return ResultadoGuardado({}, efectiva, preferido, avisos_previos + avisos, cambiadas, mensaje)


def resumen_errores(n: int) -> str:
    """Texto del pie del formulario cuando hay errores: «corrige 1 valor» o «corrige N valores»."""
    return "No se guardó nada: corrige 1 valor." if n == 1 else f"No se guardó nada: corrige {n} valores."
