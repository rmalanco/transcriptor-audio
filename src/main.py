#!/usr/bin/env python3
"""Punto de entrada principal del transcriptor."""

import argparse
import logging
import sys

from src.registro import configurar_logging
from src.transcriber import TranscriptorAudio, cargar_configuracion
from src.utils import validar_archivo, obtener_info_archivo, guardar_transcripcion


MODELOS_DISPONIBLES = ["tiny", "base", "small", "medium", "large-v3-turbo", "large-v1", "large-v2", "large-v3"]


def listar_modelos():
    print("Modelos disponibles:")
    for m in MODELOS_DISPONIBLES:
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
    for m in modelos:
        facturacion = m.get("billing") or {}
        coste = f"  ×{facturacion['multiplier']} premium" if facturacion.get("is_premium") and "multiplier" in facturacion else ""
        limite = ((m.get("capabilities") or {}).get("limits") or {}).get("max_prompt_tokens")
        entrada = f"  (entrada máx. {limite // 1000}k tokens)" if limite else ""
        print(f"  - {m['id']:<22} {m.get('name', ''):<18}{entrada}{coste}")
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
  python -m src.main archivo.wav --idioma en --formato srt
  python -m src.main --listar-modelos
  python -m src.main --copilot-login
  python -m src.main --copilot-modelos
  python -m src.main --ui
        """
    )
    
    parser.add_argument("archivo", nargs="?", help="Archivo de audio/video a transcribir")
    parser.add_argument("-o", "--salida", help="Archivo de salida (por defecto: stdout)")
    parser.add_argument("-m", "--modelo", choices=MODELOS_DISPONIBLES, help="Modelo Whisper (por defecto: el de config/settings.yaml)")
    parser.add_argument("-d", "--dispositivo", choices=["cpu", "cuda", "auto"], help="Dispositivo de cómputo (por defecto: config)")
    parser.add_argument("-c", "--compute-type", choices=["int8", "int16", "float16", "float32"], help="Tipo de computación (por defecto: config)")
    parser.add_argument("-l", "--idioma", default="es", help="Idioma (es, en, fr, auto, etc.)")
    parser.add_argument("-t", "--task", default="transcribe", choices=["transcribe", "translate"], help="Tarea: transcribir o traducir a inglés")
    parser.add_argument("-f", "--formato", default="txt", choices=["txt", "srt", "vtt", "json"], help="Formato de salida")
    parser.add_argument("--no-timestamps", action="store_true", help="No incluir timestamps en salida")
    parser.add_argument("--word-timestamps", action="store_true", help="Timestamps por palabra (JSON)")
    parser.add_argument("--config", default="config/settings.yaml", help="Archivo de configuración YAML")
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
        enterprise_url = cargar_configuracion(args.config).get("ia", {}).get("copilot_enterprise_url") or None
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
    
    config = cargar_configuracion(args.config)
    
    modelo_nombre = args.modelo or config['modelo']['nombre']
    dispositivo = args.dispositivo or config['modelo']['dispositivo']
    compute_type = args.compute_type or config['modelo']['compute_type']
    
    if args.verbose:
        info = obtener_info_archivo(args.archivo)
        print(f"Archivo: {info.nombre}{info.extension}")
        print(f"Tamaño: {info.tamaño_bytes / 1024 / 1024:.2f} MB")
        print(f"Duración: {info.duracion_segundos:.1f}s" if info.duracion_segundos else "Duración: desconocida")
        print(f"Codec audio: {info.codec_audio}" if info.codec_audio else "Codec audio: desconocido")
        print(f"Sample rate: {info.sample_rate}Hz" if info.sample_rate else "Sample rate: desconocido")
        print(f"Canales: {info.canales}" if info.canales else "Canales: desconocido")
        print(f"Es video: {'Sí' if info.es_video else 'No'}")
        print(f"Modelo: {modelo_nombre} ({dispositivo}, {compute_type})")
        print(f"Idioma: {args.idioma}")
        print(f"Task: {args.task}")
        print("-" * 50)
    
    transcriptor = TranscriptorAudio(
        modelo_nombre=modelo_nombre,
        dispositivo=dispositivo,
        compute_type=compute_type
    )
    
    try:
        resultado = transcriptor.transcribir(
            args.archivo,
            idioma=args.idioma,
            task=args.task,
            beam_size=config['transcripcion']['beam_size'],
            best_of=config['transcripcion']['best_of'],
            temperature=config['transcripcion']['temperature'],
            condition_on_previous_text=config['transcripcion']['condition_on_previous_text'],
            compression_ratio_threshold=config['transcripcion']['compression_ratio_threshold'],
            logprob_threshold=config['transcripcion']['logprob_threshold'],
            no_speech_threshold=config['transcripcion']['no_speech_threshold'],
            word_timestamps=args.word_timestamps
        )
        
        if args.verbose:
            print(f"Idioma detectado: {resultado.idioma_detectado} ({resultado.probabilidad_idioma:.2%})")
            print(f"Duración: {resultado.duracion_total:.1f}s")
            print(f"Segmentos: {len(resultado.segmentos)}")
            print("-" * 50)
        
        if args.salida:
            guardar_transcripcion(
                resultado,
                args.salida,
                formato=args.formato,
                incluir_timestamps=not args.no_timestamps
            )
            print(f"Transcripción guardada en: {args.salida}")
        else:
            if args.formato == "txt":
                if not args.no_timestamps:
                    for seg in resultado.segmentos:
                        print(f"[{seg.inicio:.2f}s --> {seg.fin:.2f}s] {seg.texto}")
                else:
                    print(resultado.texto_completo)
            elif args.formato == "json":
                import json
                print(json.dumps({
                    "texto": resultado.texto_completo,
                    "idioma": resultado.idioma_detectado,
                    "segmentos": [
                        {"inicio": s.inicio, "fin": s.fin, "texto": s.texto}
                        for s in resultado.segmentos
                    ]
                }, ensure_ascii=False, indent=2))
            else:
                print("Para formatos srt/vtt use --salida", file=sys.stderr)
                sys.exit(1)
                
    except Exception as e:
        logging.getLogger("transcriptor").error("Error durante la transcripción: %s", e, exc_info=args.verbose)
        sys.exit(1)


if __name__ == "__main__":
    main()