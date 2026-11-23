"""Idiomas del selector de transcripción: nombres y códigos. Sin Tk ni dependencias del proyecto."""

IDIOMAS_DISPONIBLES = {
    "auto": "Auto-detectar",
    "es": "Español",
    "en": "Inglés",
    "fr": "Francés",
    "de": "Alemán",
    "it": "Italiano",
    "pt": "Portugués",
    "ca": "Catalán",
    "ru": "Ruso",
    "zh": "Chino",
    "ja": "Japonés",
    "ko": "Coreano"
}


def opciones_de_idioma(idioma_configurado: str) -> list[str]:
    """Nombres del selector de idioma. Si el código configurado no está en él (p. ej. `nl`, que Whisper admite),
    se añade tal cual, para que la ventana transcriba en ese idioma igual que la CLI."""
    opciones = list(IDIOMAS_DISPONIBLES.values())
    if idioma_configurado not in IDIOMAS_DISPONIBLES:
        opciones.append(idioma_configurado)
    return opciones


def codigo_de_idioma(opcion: str) -> str:
    """Código de una opción del selector; una opción que no es un nombre conocido se devuelve tal cual."""
    return next((codigo for codigo, nombre in IDIOMAS_DISPONIBLES.items() if nombre == opcion), opcion)


def nombre_de_idioma(codigo: str) -> str:
    """Nombre del selector de un código; un código que no está en el selector se devuelve tal cual."""
    return IDIOMAS_DISPONIBLES.get(codigo, codigo)
