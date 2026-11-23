# Convenciones

> Resumen; si algo choca con `docs/`, manda `docs/`. Sacadas del código y del historial de git; actualizadas el 2026-11-22.

## Idioma

- Todo en español: identificadores (`generar_minuta`, `ErrorAsistenteIA`, `cargar_configuracion`), comentarios,
  docstrings, textos de la interfaz, logs y documentación.
- Se conservan los nombres de las bibliotecas y de la API (`httpx`, `x-initiator`, `/chat/completions`).

## Código

- Python con anotaciones de tipo (`Optional[...]`, `list[str]`) y `dataclass` para los datos.
- Funciones y variables en `snake_case`; clases en `PascalCase`; constantes de módulo en `MAYÚSCULAS`.
- Lo privado lleva guion bajo inicial (`_completar`, `_en_ui`).
- Las excepciones propias empiezan por `Error` (`ErrorCopilot`, `ErrorAsistenteIA`, `ErrorSinSesionCopilot`).
- Los imports entre módulos son absolutos: `from src.<módulo> import …`.
- Los loggers cuelgan de `transcriptor` (`transcriptor.ui`, `transcriptor.whisper`, `transcriptor.copilot`,
  `transcriptor.ia`, `transcriptor.configuracion`).
- No hay linter ni formateador configurado: sigue el estilo del archivo que edites.

## Interfaz gráfica

- Los widgets solo se tocan desde el hilo principal; un hilo de fondo llama a `_en_ui(funcion, *args)`.
- Guardar y restablecer la configuración, y iniciar o cerrar la sesión de Copilot desde la vista Configuración, corren
  en el hilo principal y se rechazan con una transcripción o una generación en curso.
- El trabajo largo va en hilos `daemon`; la cancelación es un `threading.Event` (uno para la transcripción y uno por
  cada generación de IA).

## Tests

- `pytest`, en `tests/test_<módulo>.py`.
- Sin red real: `httpx` se simula con `monkeypatch`.
- Las rutas del token se aíslan con la fixture `rutas_aisladas` de `tests/test_copilot.py`; las preferencias del usuario,
  con la fixture `preferencias_aisladas` (automática) de `tests/conftest.py`, que también tiene el doble de Whisper
  (`modelo_whisper_falso`).
- Se ejecutan desde la raíz del repo.

## Git

- La rama de trabajo actual es `tandem/ronda-2`; `main` sigue en el último estado publicado. Los commits
  recientes llevan el asunto en español y en presente (`Quita código y dependencias sin uso…`); los primeros mezclan
  inglés. No hay un formato fijado.
- El usuario hace los commits; un agente no hace commit sin que se lo pidan.

## Documentos

- La arquitectura de hoy está en `docs/disenos/00-actual.md`; lo que el sistema hace, en `docs/specs/` (lo crea
  `/cerrar`); las historias terminadas, en `docs/historias/hechas/`; lo que sigue, en `BACKLOG.md`.
- Los contratos `EGM.md` describen interfaz, invariantes y efectos de cada carpeta con código.
