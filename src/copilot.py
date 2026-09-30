"""Acceso a los modelos de GitHub Copilot, replicando la integración de opencode (v1.x).

Flujo:
1. Inicio de sesión con el "device flow" de OAuth de GitHub: se pide un código, el usuario lo introduce en
   github.com/login/device y la app consulta periódicamente hasta recibir el token de GitHub.
2. Ese token se usa directamente como `Bearer` contra la API de Copilot (compatible con OpenAI:
   /chat/completions y /models). No hay intercambio por un token temporal.

El token se guarda en ~/.local/share/transcriptor-audio/copilot.json (permisos 600). Si ya se inició sesión
en opencode con GitHub Copilot, también se reutiliza el suyo.
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx

log = logging.getLogger("transcriptor.copilot")

# App OAuth de opencode (pública: el device flow no usa secreto). GitHub la reconoce como integración de Copilot.
CLIENT_ID = "Ov23li8tweQw6odWQebz"
API_VERSION = "2026-06-01"
USER_AGENT = "transcriptor-audio/1.0"
ESPERA_EXTRA = 3.0  # segundos que opencode suma al intervalo de consulta para no recibir "slow_down"

RUTA_TOKEN = Path("~/.local/share/transcriptor-audio/copilot.json").expanduser()
RUTA_AUTH_OPENCODE = Path("~/.local/share/opencode/auth.json").expanduser()
VARIABLE_ENTORNO = "COPILOT_GITHUB_TOKEN"


class ErrorCopilot(Exception):
    pass


@dataclass
class Sesion:
    token: str
    enterprise_url: Optional[str] = None  # dominio de GitHub Enterprise (p. ej. "empresa.ghe.com"); None = github.com
    origen: str = ""


@dataclass
class CodigoDispositivo:
    device_code: str
    user_code: str
    verification_uri: str
    interval: int
    expires_in: int
    enterprise_url: Optional[str] = None


def normalizar_dominio(url: Optional[str]) -> Optional[str]:
    """"https://empresa.ghe.com/" -> "empresa.ghe.com"; vacío o github.com -> None."""
    if not url or not url.strip():
        return None
    dominio = url.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    return None if dominio == "github.com" else dominio


def url_api(enterprise_url: Optional[str] = None) -> str:
    dominio = normalizar_dominio(enterprise_url)
    return f"https://copilot-api.{dominio}" if dominio else "https://api.githubcopilot.com"


def cabeceras(token: str, iniciador: str = "user") -> dict:
    """`iniciador`: "user" si la petición la provoca una acción del usuario, "agent" si es un paso automático
    posterior (igual que opencode: Copilot solo cuenta como petición premium las de "user")."""
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": API_VERSION,
        "Openai-Intent": "conversation-edits",
        "x-initiator": iniciador,
        "Content-Type": "application/json",
    }


# ------------------------------------------------------------------ Token guardado

def leer_token(enterprise_url: Optional[str] = None) -> Optional[Sesion]:
    """Busca el token en: variable de entorno, archivo propio de la app y sesión de opencode."""
    dominio = normalizar_dominio(enterprise_url)
    token = os.environ.get(VARIABLE_ENTORNO, "").strip()
    if token:
        return Sesion(token, dominio, VARIABLE_ENTORNO)

    for ruta, extraer in (
        (RUTA_TOKEN, lambda d: (d.get("token"), d.get("enterprise_url"))),
        (RUTA_AUTH_OPENCODE, lambda d: (d.get("github-copilot", {}).get("refresh"),
                                        d.get("github-copilot", {}).get("enterpriseUrl"))),
    ):
        if not ruta.exists():
            continue
        try:
            token, dominio_guardado = extraer(json.loads(ruta.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, AttributeError):
            continue
        # Un token de github.com no sirve para GitHub Enterprise, ni al revés
        if token and normalizar_dominio(dominio_guardado) == dominio:
            return Sesion(token.strip(), dominio, str(ruta))
    return None


def guardar_token(token: str, enterprise_url: Optional[str] = None) -> None:
    RUTA_TOKEN.parent.mkdir(parents=True, exist_ok=True)
    datos = {"token": token, "enterprise_url": normalizar_dominio(enterprise_url)}
    # Se crea con permisos 600 desde el principio: el token da acceso a la cuenta de GitHub
    descriptor = os.open(RUTA_TOKEN, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
        json.dump(datos, archivo)
    log.info("Sesión de GitHub Copilot guardada en %s", RUTA_TOKEN)


def cerrar_sesion() -> bool:
    """Borra el token propio de la app (el de opencode no se toca). Devuelve si había uno."""
    if RUTA_TOKEN.exists():
        RUTA_TOKEN.unlink()
        log.info("Sesión de GitHub Copilot eliminada")
        return True
    return False


def invalidar_token(token: str) -> None:
    """Tras un 401, borra el token propio si es el rechazado, para que se pida iniciar sesión de nuevo."""
    try:
        if json.loads(RUTA_TOKEN.read_text(encoding="utf-8")).get("token") == token:
            cerrar_sesion()
    except (OSError, json.JSONDecodeError, AttributeError):
        pass


# ------------------------------------------------------------------ Inicio de sesión (device flow)

def iniciar_login(enterprise_url: Optional[str] = None) -> CodigoDispositivo:
    dominio = normalizar_dominio(enterprise_url)
    try:
        respuesta = httpx.post(
            f"https://{dominio or 'github.com'}/login/device/code",
            json={"client_id": CLIENT_ID, "scope": "read:user"},
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=30,
        )
    except httpx.HTTPError as e:
        raise ErrorCopilot(f"No se pudo conectar con GitHub: {e}") from e
    if respuesta.status_code >= 400:
        raise ErrorCopilot(f"GitHub rechazó el inicio de sesión ({respuesta.status_code}): {respuesta.text[:200]}")
    datos = respuesta.json()
    log.info("Código de dispositivo recibido: introdúcelo en %s", datos["verification_uri"])
    return CodigoDispositivo(
        device_code=datos["device_code"], user_code=datos["user_code"],
        verification_uri=datos["verification_uri"], interval=int(datos.get("interval", 5)),
        expires_in=int(datos.get("expires_in", 900)), enterprise_url=dominio,
    )


def esperar_login(
    codigo: CodigoDispositivo,
    cancelar: Optional[threading.Event] = None,
    dormir: Callable[[float], None] = time.sleep,
) -> str:
    """Consulta a GitHub hasta que el usuario autorice el código; guarda y devuelve el token."""
    url = f"https://{codigo.enterprise_url or 'github.com'}/login/oauth/access_token"
    limite = time.monotonic() + codigo.expires_in
    intervalo = codigo.interval
    while time.monotonic() < limite:
        if cancelar and cancelar.is_set():
            raise InterruptedError
        try:
            respuesta = httpx.post(
                url,
                json={"client_id": CLIENT_ID, "device_code": codigo.device_code,
                      "grant_type": "urn:ietf:params:oauth:grant-type:device_code"},
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                timeout=30,
            )
        except httpx.HTTPError as e:
            log.warning("Fallo de conexión esperando la autorización: %r", e)
            dormir(intervalo + ESPERA_EXTRA)
            continue
        if respuesta.status_code >= 400:
            raise ErrorCopilot(f"GitHub respondió {respuesta.status_code}: {respuesta.text[:200]}")
        datos = respuesta.json()
        if datos.get("access_token"):
            guardar_token(datos["access_token"], codigo.enterprise_url)
            return datos["access_token"]
        error = datos.get("error")
        if error == "slow_down":
            intervalo = int(datos.get("interval") or intervalo + 5)
        elif error == "expired_token":
            break
        elif error == "access_denied":
            raise ErrorCopilot("Se canceló la autorización en GitHub.")
        elif error and error != "authorization_pending":
            raise ErrorCopilot(f"GitHub rechazó la autorización: {datos.get('error_description') or error}")
        dormir(intervalo + ESPERA_EXTRA)
    raise ErrorCopilot("El código caducó antes de autorizarse. Vuelve a iniciar sesión.")


# ------------------------------------------------------------------ Modelos

def listar_modelos(sesion: Sesion) -> list[dict]:
    """Modelos de chat que la cuenta puede usar por /chat/completions.

    La señal fiable es `policy.state == "enabled"` (lo que la licencia u organización permite);
    `model_picker_enabled` viene en False para todos en algunas cuentas, así que solo se usa como alternativa.
    """
    try:
        respuesta = httpx.get(f"{url_api(sesion.enterprise_url)}/models", headers=cabeceras(sesion.token), timeout=30)
    except httpx.HTTPError as e:
        raise ErrorCopilot(f"No se pudo conectar con GitHub Copilot: {e}") from e
    if respuesta.status_code == 401:
        raise ErrorCopilot("La sesión de GitHub Copilot no es válida (401). Vuelve a iniciar sesión.")
    if respuesta.status_code >= 400:
        raise ErrorCopilot(f"GitHub Copilot respondió {respuesta.status_code}: {respuesta.text[:200]}")
    modelos = []
    for modelo in respuesta.json().get("data", []):
        endpoints = modelo.get("supported_endpoints")
        habilitado = (modelo.get("policy") or {}).get("state") == "enabled" or modelo.get("model_picker_enabled")
        if not habilitado:
            continue
        if endpoints and "/chat/completions" not in endpoints:
            continue  # modelos solo disponibles por /responses
        if (modelo.get("capabilities") or {}).get("type", "chat") != "chat":
            continue
        modelos.append(modelo)
    return sorted(modelos, key=lambda m: m["id"])


# ------------------------------------------------------------------ Modo "auto"

MODELO_AUTO = "auto"
MARGEN_RENOVACION_AUTO = 5 * 60  # la sesión se renueva 5 min antes de caducar, como la extensión de VS Code


@dataclass
class SesionAuto:
    """Sesión del modo auto: Copilot elige entre los modelos que tenga disponibles en ese momento y aplica un
    descuento (10 %) en las peticiones premium. Las peticiones llevan `session_token` en `Copilot-Session-Token`."""
    modelo: str
    session_token: str
    expires_at: float
    disponibles: list[str]
    descuentos: dict

    def vigente(self) -> bool:
        return self.expires_at - time.time() > MARGEN_RENOVACION_AUTO


def abrir_sesion_auto(sesion: Sesion) -> SesionAuto:
    """Abre una sesión auto (POST /models/session) y elige el modelo, igual que VS Code y Crush.

    El servidor propone `selected_model`, pero puede ser uno que solo funciona por /responses; la app habla
    /chat/completions, así que se usa el primero de los disponibles que lo admita.
    """
    base = url_api(sesion.enterprise_url)
    try:
        respuesta = httpx.post(f"{base}/models/session", headers=cabeceras(sesion.token),
                               json={"auto_mode": {"model_hints": ["auto"]}}, timeout=30)
    except httpx.HTTPError as e:
        raise ErrorCopilot(f"No se pudo conectar con GitHub Copilot: {e}") from e
    if respuesta.status_code == 401:
        raise ErrorCopilot("La sesión de GitHub Copilot no es válida (401). Vuelve a iniciar sesión.")
    if respuesta.status_code >= 400:
        raise ErrorCopilot(f"GitHub Copilot no permitió el modo auto ({respuesta.status_code}): {respuesta.text[:200]}")
    datos = respuesta.json()
    # El propuesto primero, sin repetir y en el orden del servidor
    disponibles = [m for m in dict.fromkeys([datos.get("selected_model"), *datos.get("available_models", [])]) if m]
    if not datos.get("session_token") or not disponibles:
        raise ErrorCopilot("El modo auto de GitHub Copilot no ofreció ningún modelo.")

    try:
        catalogo = httpx.get(f"{base}/models", headers=cabeceras(sesion.token), timeout=30).json().get("data", [])
        endpoints = {m["id"]: m.get("supported_endpoints") for m in catalogo}
    except (httpx.HTTPError, ValueError) as e:
        log.warning("No se pudo leer el catálogo de modelos; se usa el que propone Copilot: %r", e)
        endpoints = {}
    # Sin metadatos de endpoints = modelo anterior a /responses, que funciona por /chat/completions
    compatibles = [m for m in disponibles if not endpoints.get(m) or "/chat/completions" in endpoints[m]]
    if not compatibles:
        raise ErrorCopilot("El modo auto solo ofrece modelos que no admiten /chat/completions "
                           f"({', '.join(disponibles)}). Elige un modelo concreto en `ia.modelo`.")
    log.info("Modo auto de GitHub Copilot: usando %s (disponibles: %s)", compatibles[0], ", ".join(disponibles))
    return SesionAuto(compatibles[0], datos["session_token"], float(datos.get("expires_at") or time.time() + 3600),
                      disponibles, datos.get("discounted_costs") or {})
