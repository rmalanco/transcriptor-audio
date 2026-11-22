#!/usr/bin/env python3
"""Punto de entrada principal del transcriptor."""

import argparse
import logging
import sys

from src.registro import configurar_logging
from src.configuracion import MODELOS_WHISPER, ErrorConfiguracion, cargar_configuracion
from src.transcriber import TranscriptorAudio
from src.utils import validar_archivo, obtener_info_archivo, guardar_transcripcion, serializar_transcripcion


def _informar(texto):
    """Mensaje informativo (`--verbose`): va a stderr para no mezclarse con la transcripción de stdout."""
    print(texto, file=sys.stderr)


def _cargar_configuracion_o_salir(ruta):
    try:
        return cargar_configuracion(ruta)
    except ErrorConfiguracion as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def listar_modelos():
    print("Modelos disponibles:")
    for m in MODELOS_WHISPER:
        print(f"  - {m}")
    sys.exit(0)


def login_copilot(enterprise_url):
    from src import copilot
    try:
        codigo = copilot.iniciar_login(enterprise_url)
        print(f"Abre {codigo.verification_uri} e introduce el código:  {codigo.user_code}")
        print("Esperando autorización… (Ctrl+C para cancelar)")
        copilot.esperar_login(codigo)
    except copilot.ErrorCopilot as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
    print(f"Sesión iniciada; token guardado en {copilot.RUTA_TOKEN}")
    sys.exit(0)


def listar_modelos_copilot(enterprise_url):
    from src import copilot
    sesion = copilot.leer_token(enterprise_url)
    if not sesion:
        print("No has iniciado sesión. Ejecuta: python -m src.main --copilot-login", file=sys.stderr)
        sys.exit(1)
    try:
        modelos = copilot.listar_modelos(sesion)
    except copilot.ErrorCopilot as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Modelos de GitHub Copilot disponibles (sesión de {sesion.origen}):")
    try:
        auto = copilot.abrir_sesion_auto(sesion)
        descuento = max(auto.descuentos.values(), default=0)
        print(f"  - {'auto':<22} {'Copilot elige':<18}  (ahora: {auto.modelo}; descuento premium {descuento:.0%})")
    except copilot.ErrorCopilot as e:
        print(f"  - auto no disponible: {e}")
    autorizados = [m for m in modelos if not copilot.familia_excluida(m["id"])]
    for m in autorizados:
        facturacion = m.get("billing") or {}
        coste = f"  ×{facturacion['multiplier']} premium" if facturacion.get("is_premium") and "multiplier" in facturacion else ""
        limite = ((m.get("capabilities") or {}).get("limits") or {}).get("max_prompt_tokens")
        entrada = f"  (entrada máx. {limite // 1000}k tokens)" if limite else ""
        print(f"  - {m['id']:<22} {m.get('name', ''):<18}{entrada}{coste}")
    omitidos = len(modelos) - len(autorizados)
    if omitidos == 1:
        print("Se omite 1 modelo de una familia no autorizada por la empresa.")
    elif omitidos:
        print(f"Se omiten {omitidos} modelos de familias no autorizadas por la empresa.")
    print("\nPara usar uno, pon su id en `ia.modelo` de config/settings.yaml")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Transcriptor de audio/video a texto usando faster-whisper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python -m src.main audio.mp3
  python -m src.main video.mp4 -o transcripcion.txt --modelo small
  python -m src.main archivo.wav --idioma en --formato srt -o archivo.srt
  python -m src.main --listar-modelos
  python -m src.main --copilot-login
  python -m src.main --copilot-modelos
  python -m src.main --ui
        """
    )
    
    parser.add_argument("archivo", nargs="?", help="Archivo de audio/video a transcribir")
    parser.add_argument("-o", "--salida", help="Archivo de salida (por defecto: stdout)")
    parser.add_argument("-m", "--modelo", choices=MODELOS_WHISPER, help="Modelo Whisper (por defecto: el de config/settings.yaml)")
    parser.add_argument("-d", "--dispositivo", choices=["cpu", "cuda", "auto"], help="Dispositivo de cómputo (por defecto: config)")
    parser.add_argument("-c", "--compute-type", choices=["int8", "int16", "float16", "float32"], help="Tipo de computación (por defecto: config)")
    parser.add_argument("-l", "--idioma", help="Idioma (es, en, fr, auto, etc.) (por defecto: el de la configuración)")
    parser.add_argument("-t", "--task", default="transcribe", choices=["transcribe", "translate"], help="Tarea: transcribir o traducir a inglés")
    parser.add_argument("-f", "--formato", choices=["txt", "srt", "vtt", "json"], help="Formato de salida (por defecto: el de la configuración)")
    parser.add_argument("--no-timestamps", action="store_true", help="No incluir timestamps en salida (por defecto: el de la configuración)")
    parser.add_argument("--word-timestamps", action="store_true", help="Timestamps por palabra (por defecto: el de la configuración)")
    parser.add_argument("--config", help="Archivo de configuración YAML (por defecto: config/settings.yaml del proyecto)")
    parser.add_argument("--listar-modelos", action="store_true", help="Listar modelos disponibles y salir")
    parser.add_argument("--copilot-login", action="store_true", help="Iniciar sesión en GitHub Copilot y salir")
    parser.add_argument("--copilot-logout", action="store_true", help="Cerrar la sesión de GitHub Copilot y salir")
    parser.add_argument("--copilot-modelos", action="store_true", help="Listar los modelos de GitHub Copilot disponibles y salir")
    parser.add_argument("--ui", action="store_true", help="Lanzar interfaz gráfica de escritorio")
    parser.add_argument("-v", "--verbose", action="store_true", help="Salida detallada")
    parser.add_argument("--log", choices=["DEBUG", "INFO", "WARNING", "ERROR"], type=str.upper,
                        help="Nivel del log por consola (por defecto INFO, o DEBUG con --verbose)")
    
    args = parser.parse_args()
    configurar_logging(args.log or ("DEBUG" if args.verbose else None))
    
    if args.ui:
        from src.ui import main as ui_main
        ui_main()
        return
    
    if args.listar_modelos:
        listar_modelos()

    if args.copilot_login or args.copilot_modelos or args.copilot_logout:
        enterprise_url = _cargar_configuracion_o_salir(args.config)["ia"]["copilot_enterprise_url"] or None
        if args.copilot_logout:
            from src import copilot
            print("Sesión cerrada" if copilot.cerrar_sesion() else "No había sesión guardada por esta app")
            sys.exit(0)
        if args.copilot_login:
            login_copilot(enterprise_url)
        listar_modelos_copilot(enterprise_url)
    
    if not args.archivo:
        parser.error("Se requiere un archivo de entrada")
    
    try:
        validar_archivo(args.archivo)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    config = _cargar_configuracion_o_salir(args.config)
    idioma = args.idioma or config["transcripcion"]["idioma"]
    formato = args.formato or config["salida"]["formato"]
    # Antes de cargar Whisper: srt y vtt sin archivo no tienen a dónde ir, y transcribir para fallar después no sirve
    if formato in ("srt", "vtt") and not args.salida:
        print(f"Error: el formato {formato} necesita un archivo de salida: añade -o <archivo>.", file=sys.stderr)
        sys.exit(1)
    incluir_timestamps = not args.no_timestamps and config["salida"]["incluir_timestamps"]
    palabra_por_palabra = args.word_timestamps or config["salida"]["palabra_por_palabra"]

    modelo_nombre = args.modelo or config['modelo']['nombre']
    dispositivo = args.dispositivo or config['modelo']['dispositivo']
    compute_type = args.compute_type or config['modelo']['compute_type']

    # Lo informativo va a stderr: así la salida estándar solo contiene la transcripción
    if args.verbose:
        info = obtener_info_archivo(args.archivo)
        _informar(f"Archivo: {info.nombre}{info.extension}")
        _informar(f"Tamaño: {info.tamaño_bytes / 1024 / 1024:.2f} MB")
        _informar(f"Duración: {info.duracion_segundos:.1f}s" if info.duracion_segundos else "Duración: desconocida")
        _informar(f"Codec audio: {info.codec_audio}" if info.codec_audio else "Codec audio: desconocido")
        _informar(f"Sample rate: {info.sample_rate}Hz" if info.sample_rate else "Sample rate: desconocido")
        _informar(f"Canales: {info.canales}" if info.canales else "Canales: desconocido")
        _informar(f"Es video: {'Sí' if info.es_video else 'No'}")
        _informar(f"Modelo: {modelo_nombre} ({dispositivo}, {compute_type})")
        _informar(f"Idioma: {idioma}")
        _informar(f"Task: {args.task}")
        _informar("-" * 50)
    
    transcriptor = TranscriptorAudio(
        modelo_nombre=modelo_nombre,
        dispositivo=dispositivo,
        compute_type=compute_type
    )
    
    try:
        resultado = transcriptor.transcribir(
            args.archivo,
            idioma=idioma,
            task=args.task,
            beam_size=config['transcripcion']['beam_size'],
            best_of=config['transcripcion']['best_of'],
            temperature=config['transcripcion']['temperature'],
            condition_on_previous_text=config['transcripcion']['condition_on_previous_text'],
            compression_ratio_threshold=config['transcripcion']['compression_ratio_threshold'],
            logprob_threshold=config['transcripcion']['logprob_threshold'],
            no_speech_threshold=config['transcripcion']['no_speech_threshold'],
            word_timestamps=palabra_por_palabra
        )
        
        if args.verbose:
            _informar(f"Idioma detectado: {resultado.idioma_detectado} ({resultado.probabilidad_idioma:.2%})")
            _informar(f"Duración: {resultado.duracion_total:.1f}s")
            _informar(f"Segmentos: {len(resultado.segmentos)}")
            _informar("-" * 50)

        if args.salida:
            guardar_transcripcion(
                resultado,
                args.salida,
                formato=formato,
                incluir_timestamps=incluir_timestamps
            )
            print(f"Transcripción guardada en: {args.salida}")
        else:
            # Mismo texto que escribiría `-o`, sin añadir nada más
            sys.stdout.write(serializar_transcripcion(resultado, formato, incluir_timestamps))

    except Exception as e:
        logging.getLogger("transcriptor").error("Error durante la transcripción: %s", e, exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()