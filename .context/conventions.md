# Convenciones

> Resumen; si algo choca con `docs/`, manda `docs/`. Sacadas del código y del historial de git al 2026-11-22.

## Idioma

- Todo en español: identificadores (`generar_minuta`, `ErrorAsistenteIA`, `cargar_configuracion`), comentarios,
  docstrings, textos de la interfaz, logs y documentación.
- Se conservan los nombres de las bibliotecas y de la API (`httpx`, `x-initiator`, `/chat/completions`).

## Código

- Python con anotaciones de tipo (`Optional[...]`, `list[str]`) y `dataclass` para los datos.
- Funciones y variables en `snake_case`; clases en `PascalCase`; constantes de módulo en `MAYÚSCULAS`.
- Lo privado lleva guion bajo inicial (`_completar`, `_en_ui`).
- Las excepciones propias empiezan por `Error` (`ErrorCopilot`, `ErrorAsistenteIA`, `ErrorSinSesionCopilot`).
- Los imports entre módulos son absolutos: `from src.<módulo> import …` (salvo `src/__init__.py`, que usa relativos).
- Los loggers cuelgan de `transcriptor` (`transcriptor.ui`, `transcriptor.whisper`).
- No hay linter ni formateador configurado: sigue el estilo del archivo que edites.

## Interfaz gráfica

- Los widgets solo se tocan desde el hilo principal; un hilo de fondo llama a `_en_ui(funcion, *args)`.
- El trabajo largo va en hilos `daemon`; la cancelación es un `threading.Event`.

## Tests

- `pytest`, en `tests/test_<módulo>.py`.
- Sin red real: `httpx` se simula con `monkeypatch`.
- Las rutas del token se aíslan con la fixture `rutas_aisladas` de `tests/test_copilot.py`.
- Se ejecutan desde la raíz del repo.

## Git

- Rama única `main`. Los mensajes de commit mezclan español e inglés; no hay un formato fijado.
- El usuario hace los commits; un agente no hace commit sin que se lo pidan.

## Documentos

- La arquitectura de hoy está en `docs/disenos/00-actual.md`; lo que el sistema hace, en `docs/specs/` (lo crea
  `/cerrar`).
- Los contratos `EGM.md` describen interfaz, invariantes y efectos de cada carpeta con código.
