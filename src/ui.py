"""Interfaz gráfica de escritorio para el transcriptor de audio/video."""

import logging
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKDND_DISPONIBLE = True
except ImportError:
    TKDND_DISPONIBLE = False

from src.asistente_ia import (MODELO_POR_DEFECTO, NOMBRE_PROVEEDOR, AsistenteIA, ErrorAsistenteIA,
                              ErrorSinSesionCopilot)
from src import copilot
from src.historial import Historial
from src.registro import configurar_logging
from src.transcriber import TranscriptorAudio, cargar_configuracion, guardar_modelo_ia
from src.ui_copilot import DialogoLoginCopilot
from src.utils import validar_archivo, obtener_info_archivo, guardar_transcripcion


MODELOS_DISPONIBLES = ["tiny", "base", "small", "medium", "large-v3-turbo", "large-v1", "large-v2", "large-v3"]
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
FORMATOS_DISPONIBLES = ["txt", "srt", "vtt", "json"]
log = logging.getLogger("transcriptor.ui")
TEMAS = {"Sistema": "System", "Claro": "Light", "Oscuro": "Dark"}
VISTA_TRANSCRIBIR = "🎙  Transcribir"
VISTA_HISTORIAL = "📚  Historial"
TAB_TEXTO = "Texto"  # nombre corto: las pestañas se recortan en ventanas estrechas
DOCUMENTOS_IA = {
    "resumen": {"pestana": "Resumen", "sufijo": "_resumen.md",
                "vacio": "Transcribe un archivo y pulsa «Generar resumen» para crear un resumen con IA."},
    "minuta": {"pestana": "Minuta", "sufijo": "_minuta.md",
               "vacio": "Transcribe una reunión y pulsa «Generar minuta» para obtener objetivo, temas, "
                        "acuerdos y tareas."},
}

COLOR_BORDE = ("gray75", "gray30")
COLOR_BORDE_ACTIVO = ("#3B8ED0", "#1F6AA5")
COLOR_TEXTO_SECUNDARIO = ("gray40", "gray65")
COLOR_TRANSCRIBIR = ("#2E8B57", "#2E7D4F")
COLOR_TRANSCRIBIR_HOVER = ("#256F46", "#23613D")
COLOR_CANCELAR = ("#C0392B", "#A93226")
COLOR_CANCELAR_HOVER = ("#992D22", "#86281E")


def formatear_duracion(segundos: float) -> str:
    """Formato corto legible: 1:05:09 o 05:09."""
    segundos = int(max(segundos, 0))
    horas, resto = divmod(segundos, 3600)
    minutos, segs = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{segs:02d}"
    return f"{minutos:02d}:{segs:02d}"


if TKDND_DISPONIBLE:
    _BaseDnD = TkinterDnD.DnDWrapper
else:
    _BaseDnD = object


class AppTranscriptor(ctk.CTk, _BaseDnD):
    def __init__(self):
        super().__init__()

        # Carga tkdnd sobre el mismo intérprete Tcl de CTk (no crear un segundo Tk)
        self.dnd_habilitado = False
        if TKDND_DISPONIBLE:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_habilitado = True
            except RuntimeError:
                pass

        self.configuracion = cargar_configuracion("config/settings.yaml")
        self.title("Transcriptor de Audio/Video")
        self.geometry("1100x720")
        self.minsize(900, 640)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.archivo_actual: Optional[str] = None
        self.resultado_actual = None
        self.ruta_guardada: Optional[str] = None
        self.transcripcion_thread: Optional[threading.Thread] = None
        self.cancelar_flag = threading.Event()
        self._transcriptor: Optional[TranscriptorAudio] = None
        self._inicio_transcripcion: Optional[float] = None
        self._progreso = 0.0
        self._cerrando = False
        self._asistente: Optional[AsistenteIA] = None
        self._hilo_ia: Optional[threading.Thread] = None
        self.tabs_ia: dict = {}
        self.id_historial: Optional[int] = None        # entrada del historial mostrada ahora
        self._fecha_historial: Optional[str] = None     # fecha de creación si el audio ya no existe
        self.panel_historial = None                     # se construye la primera vez que se muestra
        self.vista_actual = VISTA_TRANSCRIBIR
        self._titulo_mostrado = ""
        try:
            self.historial: Optional[Historial] = Historial(self.configuracion.get("historial", {}).get("ruta"))
        except Exception as e:  # el historial no debe impedir usar la app
            self.historial = None
            log.exception("No se pudo abrir el historial: %s", e)

        # Variables de control
        idioma_cfg = self.configuracion["transcripcion"]["idioma"]
        self.var_modelo = tk.StringVar(value=self.configuracion["modelo"]["nombre"])
        self.var_idioma = tk.StringVar(value=IDIOMAS_DISPONIBLES.get(idioma_cfg, "Auto-detectar"))
        self.var_formato = tk.StringVar(value=self.configuracion["salida"]["formato"])
        self.var_dispositivo = tk.StringVar(value=self.configuracion["modelo"]["dispositivo"])
        self.var_compute = tk.StringVar(value=self.configuracion["modelo"]["compute_type"])
        self.var_timestamps = tk.BooleanVar(value=self.configuracion["salida"]["incluir_timestamps"])
        self.var_modelo_ia = tk.StringVar(value=self._modelo_ia_configurado())

        self._construir_ui()
        self._configurar_drag_drop()
        self._configurar_atajos()
        self._cargar_modelos_ia()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

    # ------------------------------------------------------------------ UI

    def _construir_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._construir_encabezado()

        # Cada vista ocupa la misma celda (fila 1); la barra de navegación alterna entre ellas
        self.vista_transcribir = ctk.CTkFrame(self, fg_color="transparent")
        self.vista_transcribir.grid(row=1, column=0, sticky="nsew")
        self.vista_transcribir.grid_columnconfigure(1, weight=1)
        self.vista_transcribir.grid_rowconfigure(0, weight=1)

        self._construir_panel_lateral()
        self._construir_panel_resultado()
        self._construir_barra_estado()

    def _construir_encabezado(self):
        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.grid(row=0, column=0, padx=20, pady=(14, 6), sticky="ew")
        encabezado.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            encabezado,
            text="Transcriptor de Audio/Video",
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        self.nav = ctk.CTkSegmentedButton(
            encabezado,
            values=[VISTA_TRANSCRIBIR, VISTA_HISTORIAL],
            command=self.mostrar_vista,
            height=34,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.nav.set(VISTA_TRANSCRIBIR)
        self.nav.grid(row=0, column=1, padx=12)

        self.selector_tema = ctk.CTkOptionMenu(
            encabezado,
            values=list(TEMAS.keys()),
            width=110,
            command=lambda v: ctk.set_appearance_mode(TEMAS[v])
        )
        self.selector_tema.set("Sistema")
        self.selector_tema.grid(row=0, column=2, sticky="e")

    def _construir_panel_lateral(self):
        lateral = ctk.CTkFrame(self.vista_transcribir, width=320, fg_color="transparent")
        lateral.grid(row=0, column=0, padx=(20, 10), pady=8, sticky="nsew")
        lateral.grid_columnconfigure(0, weight=1)
        lateral.grid_rowconfigure(2, weight=1)

        # --- Zona de archivo (arrastrar o clic)
        self.frame_drop = ctk.CTkFrame(lateral, border_width=2, border_color=COLOR_BORDE, corner_radius=12)
        self.frame_drop.grid(row=0, column=0, sticky="ew")
        self.frame_drop.grid_columnconfigure(0, weight=1)

        self.label_drop_icono = ctk.CTkLabel(self.frame_drop, text="📁", font=ctk.CTkFont(size=32))
        self.label_drop_icono.grid(row=0, column=0, pady=(18, 0))

        texto_drop = "Arrastra un archivo aquí\no haz clic para elegirlo" if self.dnd_habilitado \
            else "Haz clic para elegir un archivo"
        self.label_drop = ctk.CTkLabel(self.frame_drop, text=texto_drop, font=ctk.CTkFont(size=14, weight="bold"),
                                       wraplength=260)
        self.label_drop.grid(row=1, column=0, padx=16, pady=(4, 0))

        self.label_drop_detalle = ctk.CTkLabel(
            self.frame_drop, text="Audio o video · mp3, wav, m4a, mp4, mkv…",
            text_color=COLOR_TEXTO_SECUNDARIO, font=ctk.CTkFont(size=12), wraplength=260
        )
        self.label_drop_detalle.grid(row=2, column=0, padx=16, pady=(2, 18))

        for widget in (self.frame_drop, self.label_drop_icono, self.label_drop, self.label_drop_detalle):
            widget.bind("<Button-1>", lambda e: self._seleccionar_archivo())
            widget.configure(cursor="hand2")

        # --- Opciones
        opciones = ctk.CTkFrame(lateral, corner_radius=12)
        opciones.grid(row=1, column=0, pady=(12, 0), sticky="ew")
        opciones.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(opciones, text="Opciones", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=14, pady=(12, 6), sticky="w"
        )

        self._etiqueta(opciones, "Modelo", 1, 0)
        self.combo_modelo = ctk.CTkOptionMenu(opciones, values=MODELOS_DISPONIBLES, variable=self.var_modelo)
        self.combo_modelo.grid(row=2, column=0, padx=(14, 6), pady=(0, 8), sticky="ew")

        self._etiqueta(opciones, "Idioma", 1, 1)
        self.combo_idioma = ctk.CTkOptionMenu(
            opciones, values=list(IDIOMAS_DISPONIBLES.values()), variable=self.var_idioma
        )
        self.combo_idioma.grid(row=2, column=1, padx=(6, 14), pady=(0, 8), sticky="ew")

        self._etiqueta(opciones, "Formato de salida", 3, 0, columnspan=2)
        self.combo_formato = ctk.CTkSegmentedButton(
            opciones, values=FORMATOS_DISPONIBLES, variable=self.var_formato
        )
        self.combo_formato.grid(row=4, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="ew")

        self.check_timestamps = ctk.CTkSwitch(opciones, text="Incluir marcas de tiempo", variable=self.var_timestamps)
        self.check_timestamps.grid(row=5, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="w")

        # Al arrancar solo se conoce el modelo configurado; la lista se completa al consultar Copilot
        self._etiqueta(opciones, "Modelo de IA (resumen y minuta)", 6, 0, columnspan=2)
        self.combo_modelo_ia = ctk.CTkOptionMenu(
            opciones, values=[self.var_modelo_ia.get()], variable=self.var_modelo_ia,
            command=self._al_cambiar_modelo_ia
        )
        self.combo_modelo_ia.grid(row=7, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="ew")

        # Avanzado (plegable)
        self.btn_avanzado = ctk.CTkButton(
            opciones, text="▸ Opciones avanzadas", fg_color="transparent", anchor="w",
            text_color=COLOR_TEXTO_SECUNDARIO, hover_color=COLOR_BORDE, height=24,
            command=self._alternar_avanzado
        )
        self.btn_avanzado.grid(row=8, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")

        self.frame_avanzado = ctk.CTkFrame(opciones, fg_color="transparent")
        self.frame_avanzado.grid(row=9, column=0, columnspan=2, sticky="ew")
        self.frame_avanzado.grid_columnconfigure((0, 1), weight=1)
        self._etiqueta(self.frame_avanzado, "Dispositivo", 0, 0)
        self.combo_dispositivo = ctk.CTkOptionMenu(
            self.frame_avanzado, values=["cpu", "cuda", "auto"], variable=self.var_dispositivo
        )
        self.combo_dispositivo.grid(row=1, column=0, padx=(14, 6), pady=(0, 12), sticky="ew")
        self._etiqueta(self.frame_avanzado, "Precisión", 0, 1)
        self.combo_compute = ctk.CTkOptionMenu(
            self.frame_avanzado, values=["int8", "int16", "float16", "float32"], variable=self.var_compute
        )
        self.combo_compute.grid(row=1, column=1, padx=(6, 14), pady=(0, 12), sticky="ew")
        self.frame_avanzado.grid_remove()

        # --- Botón principal (Transcribir / Cancelar)
        self.btn_transcribir = ctk.CTkButton(
            lateral,
            text="▶  Transcribir",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._alternar_transcripcion,
            state="disabled",
            fg_color=COLOR_TRANSCRIBIR,
            hover_color=COLOR_TRANSCRIBIR_HOVER
        )
        self.btn_transcribir.grid(row=3, column=0, pady=(12, 0), sticky="ew")

    def _construir_panel_resultado(self):
        self.tabs = ctk.CTkTabview(self.vista_transcribir, corner_radius=12)
        self.tabs.grid(row=0, column=1, padx=(10, 20), pady=(0, 8), sticky="nsew")

        tab_texto = self.tabs.add(TAB_TEXTO)
        tabs_ia = {clave: self.tabs.add(doc["pestana"]) for clave, doc in DOCUMENTOS_IA.items()}
        tab_log = self.tabs.add("Registro")
        for tab in (tab_texto, tab_log):
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)

        tab_texto.grid_rowconfigure(0, weight=0)
        tab_texto.grid_rowconfigure(1, weight=1)
        fila_titulo = ctk.CTkFrame(tab_texto, fg_color="transparent")
        fila_titulo.grid(row=0, column=0, pady=(0, 8), sticky="ew")
        fila_titulo.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(fila_titulo, text="Título", text_color=COLOR_TEXTO_SECUNDARIO).grid(row=0, column=0, padx=(2, 8))
        self.entry_titulo = ctk.CTkEntry(fila_titulo, placeholder_text="Se asigna al terminar la transcripción",
                                         font=ctk.CTkFont(size=14, weight="bold"))
        self.entry_titulo.grid(row=0, column=1, sticky="ew")
        self.entry_titulo.configure(state="disabled")
        self.entry_titulo.bind("<Return>", lambda e: self._guardar_titulo())
        self.entry_titulo.bind("<FocusOut>", lambda e: self._guardar_titulo())

        self.text_resultado = ctk.CTkTextbox(tab_texto, wrap="word", font=ctk.CTkFont(size=14))
        self.text_resultado.grid(row=1, column=0, sticky="nsew")
        self.text_resultado.tag_config("tiempo", foreground="#3B8ED0")
        self._mostrar_marcador()

        acciones = ctk.CTkFrame(tab_texto, fg_color="transparent")
        acciones.grid(row=2, column=0, pady=(8, 0), sticky="ew")
        acciones.grid_columnconfigure(0, weight=1)

        self.label_resumen = ctk.CTkLabel(acciones, text="", text_color=COLOR_TEXTO_SECUNDARIO, anchor="w")
        self.label_resumen.grid(row=0, column=0, sticky="w")

        self.btn_copiar = ctk.CTkButton(acciones, text="Copiar", width=90, state="disabled",
                                        command=self._copiar_texto)
        self.btn_copiar.grid(row=0, column=1, padx=(6, 0))
        self.btn_guardar = ctk.CTkButton(acciones, text="Guardar como…", width=120, state="disabled",
                                         command=self._guardar_resultado)
        self.btn_guardar.grid(row=0, column=2, padx=(6, 0))
        self.btn_abrir_carpeta = ctk.CTkButton(acciones, text="Abrir carpeta", width=110, state="disabled",
                                               fg_color="transparent", border_width=1,
                                               text_color=("gray10", "gray90"),
                                               command=self._abrir_carpeta)
        self.btn_abrir_carpeta.grid(row=0, column=3, padx=(6, 0))

        for clave, tab in tabs_ia.items():
            tab.grid_columnconfigure(0, weight=1)
            tab.grid_rowconfigure(0, weight=1)
            self._construir_tab_ia(tab, clave)

        self.text_log = ctk.CTkTextbox(tab_log, wrap="word", font=ctk.CTkFont(family="monospace", size=12))
        self.text_log.grid(row=0, column=0, sticky="nsew")
        self.text_log.configure(state="disabled")

    def _construir_tab_ia(self, tab, clave: str):
        doc = DOCUMENTOS_IA[clave]
        texto = ctk.CTkTextbox(tab, wrap="word", font=ctk.CTkFont(size=14))
        texto.grid(row=0, column=0, sticky="nsew")
        texto.insert("end", doc["vacio"])
        texto.configure(state="disabled", text_color=COLOR_TEXTO_SECUNDARIO)

        acciones = ctk.CTkFrame(tab, fg_color="transparent")
        acciones.grid(row=1, column=0, pady=(8, 0), sticky="ew")
        acciones.grid_columnconfigure((0, 1, 2), weight=1, uniform="acciones")

        self._configurar_estilos_markdown(texto)

        estado = ctk.CTkLabel(acciones, text=self._texto_modelo_ia(),
                              text_color=COLOR_TEXTO_SECUNDARIO, anchor="w")
        estado.grid(row=1, column=0, columnspan=3, pady=(4, 0), sticky="w")

        btn_generar = ctk.CTkButton(acciones, text=f"✨ Generar {doc['pestana'].lower()}", width=60,
                                    state="disabled", command=lambda: self._generar_documento_ia(clave))
        btn_generar.grid(row=0, column=0, padx=(0, 3), sticky="ew")
        btn_copiar = ctk.CTkButton(acciones, text="Copiar", width=60, state="disabled",
                                   command=lambda: self._copiar_documento_ia(clave))
        btn_copiar.grid(row=0, column=1, padx=3, sticky="ew")
        btn_guardar = ctk.CTkButton(acciones, text="Guardar como…", width=60, state="disabled",
                                    command=lambda: self._guardar_documento_ia(clave))
        btn_guardar.grid(row=0, column=2, padx=(3, 0), sticky="ew")

        self.tabs_ia[clave] = {
            "texto": texto, "estado": estado, "generar": btn_generar,
            "copiar": btn_copiar, "guardar": btn_guardar, "contenido": None,
        }

    def _construir_barra_estado(self):
        barra = ctk.CTkFrame(self, corner_radius=0, height=48)
        barra.grid(row=2, column=0, sticky="ew")
        barra.grid_columnconfigure(1, weight=1)

        self.label_estado = ctk.CTkLabel(barra, text="Listo", anchor="w", width=260)
        self.label_estado.grid(row=0, column=0, padx=(20, 10), pady=10, sticky="w")

        self.progress = ctk.CTkProgressBar(barra, height=10)
        self.progress.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.progress.set(0)

        self.label_tiempo = ctk.CTkLabel(barra, text="", anchor="e", width=200, text_color=COLOR_TEXTO_SECUNDARIO)
        self.label_tiempo.grid(row=0, column=2, padx=(10, 20), pady=10, sticky="e")

    def _etiqueta(self, padre, texto, fila, columna, columnspan=1):
        ctk.CTkLabel(padre, text=texto, font=ctk.CTkFont(size=12), text_color=COLOR_TEXTO_SECUNDARIO).grid(
            row=fila, column=columna, columnspan=columnspan, padx=14, pady=(2, 0), sticky="w"
        )

    def _alternar_avanzado(self):
        if self.frame_avanzado.winfo_ismapped():
            self.frame_avanzado.grid_remove()
            self.btn_avanzado.configure(text="▸ Opciones avanzadas")
        else:
            self.frame_avanzado.grid()
            self.btn_avanzado.configure(text="▾ Opciones avanzadas")

    def _mostrar_marcador(self):
        self.text_resultado.configure(state="normal")
        self.text_resultado.delete("1.0", "end")
        self.text_resultado.insert(
            "end",
            "Aquí aparecerá el texto a medida que se transcribe.\n\n"
            "1. Elige o arrastra un archivo de audio o video.\n"
            "2. Ajusta modelo e idioma si lo necesitas.\n"
            "3. Pulsa Transcribir (Ctrl+Enter)."
        )
        self.text_resultado.configure(state="disabled", text_color=COLOR_TEXTO_SECUNDARIO)

    # ------------------------------------------------------ Eventos / atajos

    def _configurar_atajos(self):
        self.bind("<Control-o>", lambda e: self._seleccionar_archivo())
        self.bind("<Control-s>", lambda e: self._guardar_resultado() if self.resultado_actual else None)
        self.bind("<Control-Return>",
                  lambda e: self._alternar_transcripcion() if self.vista_actual == VISTA_TRANSCRIBIR else None)
        self.bind("<Escape>", lambda e: self._cancelar_transcripcion() if self._transcribiendo() else None)
        self.bind("<Control-Key-1>", lambda e: self.mostrar_vista(VISTA_TRANSCRIBIR))
        self.bind("<Control-Key-2>", lambda e: self.mostrar_vista(VISTA_HISTORIAL))
        self.bind("<Control-h>", lambda e: self.mostrar_vista(VISTA_HISTORIAL))

    def _configurar_drag_drop(self):
        """Configura soporte de arrastrar y soltar."""
        if self.dnd_habilitado:
            try:
                for widget in (self.frame_drop, self.label_drop_icono, self.label_drop, self.label_drop_detalle):
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind('<<Drop>>', self._on_drop_tkdnd)
                    widget.dnd_bind('<<DropEnter>>', lambda e: self._resaltar_drop(True, e))
                    widget.dnd_bind('<<DropLeave>>', lambda e: self._resaltar_drop(False, e))
                self._log("Drag & drop habilitado")
            except Exception as e:
                self._log(f"No se pudo habilitar drag & drop: {e}")
        else:
            self._log("Drag & drop no disponible. Usa el botón de selección.")

    def _resaltar_drop(self, activo: bool, event=None):
        self.frame_drop.configure(border_color=COLOR_BORDE_ACTIVO if activo else COLOR_BORDE)
        return event.action if event is not None else None

    def _on_drop_tkdnd(self, event):
        """Callback para tkinterdnd2."""
        self._resaltar_drop(False)
        archivos = self.tk.splitlist(event.data)
        if archivos:
            self._cargar_archivo(archivos[0])
        return event.action

    def _on_drop(self, archivos):
        """Callback cuando se suelta un archivo."""
        if archivos:
            self._cargar_archivo(archivos[0])

    def _al_cerrar(self):
        if self._transcribiendo():
            if not messagebox.askyesno("Salir", "Hay una transcripción en curso. ¿Cancelarla y salir?"):
                return
            self.cancelar_flag.set()
        self._cerrando = True
        self.destroy()

    # ------------------------------------------------------------ Archivo

    def _seleccionar_archivo(self):
        if self._transcribiendo():
            return
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo de audio/video",
            filetypes=[
                ("Archivos multimedia", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.opus *.wma *.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v"),
                ("Audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.opus *.wma"),
                ("Video", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.wmv *.m4v"),
                ("Todos los archivos", "*.*")
            ]
        )
        if archivo:
            self._cargar_archivo(archivo)

    def _cargar_archivo(self, ruta: str):
        if self._transcribiendo():
            return
        try:
            validar_archivo(ruta)
            info = obtener_info_archivo(ruta)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el archivo:\n{e}")
            self._log(f"Error cargando archivo: {e}")
            return

        self.archivo_actual = ruta
        self.duracion_archivo = info.duracion_segundos

        detalles = [
            formatear_duracion(info.duracion_segundos) if info.duracion_segundos else "duración desconocida",
            f"{info.tamaño_bytes / 1024 / 1024:.1f} MB",
        ]
        if info.codec_audio:
            detalles.append(f"{info.codec_audio} {info.sample_rate or '?'} Hz")

        self.label_drop_icono.configure(text="🎬" if info.es_video else "🎵")
        self.label_drop.configure(text=Path(ruta).name)
        self.label_drop_detalle.configure(text=" · ".join(detalles) + "\nClic o arrastra otro para cambiar")
        self.btn_transcribir.configure(state="normal")
        self._actualizar_estado("Archivo listo para transcribir", 0)
        self._log(f"Archivo cargado: {info.ruta}")

    # -------------------------------------------------------- Transcripción

    def _transcribiendo(self) -> bool:
        return self.transcripcion_thread is not None and self.transcripcion_thread.is_alive()

    def _alternar_transcripcion(self):
        if self._generando_ia():
            return
        if self._transcribiendo():
            self._cancelar_transcripcion()
        else:
            self._iniciar_transcripcion()

    def _codigo_idioma(self) -> str:
        nombre = self.var_idioma.get()
        return next((codigo for codigo, n in IDIOMAS_DISPONIBLES.items() if n == nombre), "auto")

    def _iniciar_transcripcion(self):
        if not self.archivo_actual:
            messagebox.showwarning("Atención", "Primero selecciona un archivo")
            return

        # Se leen las opciones en el hilo principal (Tkinter no es thread-safe)
        opciones = {
            "archivo": self.archivo_actual,
            "modelo": self.var_modelo.get(),
            "idioma": self._codigo_idioma(),
            "dispositivo": self.var_dispositivo.get(),
            "compute": self.var_compute.get(),
            "formato": self.var_formato.get(),
            "timestamps": self.var_timestamps.get(),
        }

        self.cancelar_flag.clear()
        self.resultado_actual = None
        self.ruta_guardada = None
        self._mostrar_titulo(None)
        self._progreso = 0.0
        self._inicio_transcripcion = time.monotonic()

        self.text_resultado.configure(state="normal", text_color=("gray10", "gray90"))
        self.text_resultado.delete("1.0", "end")
        self.text_resultado.configure(state="disabled")
        self.label_resumen.configure(text="")
        for btn in (self.btn_copiar, self.btn_guardar, self.btn_abrir_carpeta):
            btn.configure(state="disabled")
        for clave in self.tabs_ia:
            self._reiniciar_tab_ia(clave)
        self._bloquear_opciones(True)
        self.btn_transcribir.configure(text="■  Cancelar", fg_color=COLOR_CANCELAR, hover_color=COLOR_CANCELAR_HOVER)
        self.progress.set(0)
        self.tabs.set(TAB_TEXTO)

        self.transcripcion_thread = threading.Thread(
            target=self._procesar_transcripcion, args=(opciones,), daemon=True
        )
        self.transcripcion_thread.start()
        self._tick_tiempo()

    def _bloquear_opciones(self, bloquear: bool):
        estado = "disabled" if bloquear else "normal"
        for widget in (self.combo_modelo, self.combo_idioma, self.combo_formato, self.check_timestamps,
                       self.combo_dispositivo, self.combo_compute):
            widget.configure(state=estado)

    def _obtener_transcriptor(self, modelo: str, dispositivo: str, compute: str) -> TranscriptorAudio:
        """Reutiliza el modelo ya cargado si no cambiaron sus parámetros."""
        t = self._transcriptor
        if t is None or (t.modelo_nombre, t.dispositivo, t.compute_type) != (modelo, dispositivo, compute):
            t = TranscriptorAudio(modelo_nombre=modelo, dispositivo=dispositivo, compute_type=compute)
            _ = t.modelo  # fuerza la carga/descarga aquí para poder informar del estado
            self._transcriptor = t
        return t

    def _procesar_transcripcion(self, opciones: dict):
        cfg = self.configuracion["transcripcion"]
        try:
            self._actualizar_estado(f"Cargando modelo {opciones['modelo']}…")
            self._log(f"Iniciando transcripción con modelo: {opciones['modelo']}")
            transcriptor = self._obtener_transcriptor(opciones["modelo"], opciones["dispositivo"], opciones["compute"])

            if self.cancelar_flag.is_set():
                raise InterruptedError

            self._actualizar_estado("Transcribiendo…", 0)

            def on_segmento(segmento, duracion_total):
                progreso = min(segmento.fin / duracion_total, 1.0) if duracion_total else -1
                self._en_ui(self._agregar_segmento, segmento, progreso)

            resultado = transcriptor.transcribir(
                opciones["archivo"],
                idioma=opciones["idioma"],
                task="transcribe",
                beam_size=cfg["beam_size"],
                best_of=cfg["best_of"],
                temperature=cfg["temperature"],
                condition_on_previous_text=cfg["condition_on_previous_text"],
                compression_ratio_threshold=cfg["compression_ratio_threshold"],
                logprob_threshold=cfg["logprob_threshold"],
                no_speech_threshold=cfg["no_speech_threshold"],
                word_timestamps=self.configuracion["salida"]["palabra_por_palabra"],
                on_segmento=on_segmento,
                cancelar=self.cancelar_flag,
            )

            if self.cancelar_flag.is_set():
                raise InterruptedError

            # Guardado automático junto al archivo original
            ruta_salida = self._generar_ruta_salida(opciones["archivo"], opciones["formato"])
            guardar_transcripcion(
                resultado, ruta_salida, formato=opciones["formato"], incluir_timestamps=opciones["timestamps"]
            )
            self._en_ui(self._finalizar_ok, resultado, ruta_salida, opciones["archivo"], opciones["modelo"])

        except InterruptedError:
            self._en_ui(self._finalizar, "Transcripción cancelada", 0)
            self._log("Transcripción cancelada")
        except Exception as e:
            import traceback
            self._log(f"Error: {e}\n{traceback.format_exc()}")
            self._en_ui(self._finalizar, "Error en la transcripción", 0)
            self._en_ui(messagebox.showerror, "Error", str(e))

    def _agregar_segmento(self, segmento, progreso: float):
        self.text_resultado.configure(state="normal")
        self.text_resultado.insert("end", f"[{formatear_duracion(segmento.inicio)}] ", "tiempo")
        self.text_resultado.insert("end", segmento.texto + "\n")
        self.text_resultado.see("end")
        self.text_resultado.configure(state="disabled")
        if progreso >= 0:
            self._progreso = progreso
            self.progress.set(progreso)
            self.label_estado.configure(text=f"Transcribiendo… {progreso:.0%}")

    def _finalizar_ok(self, resultado, ruta_salida: str, archivo: str, modelo_whisper: str):
        self.resultado_actual = resultado
        self.ruta_guardada = ruta_salida
        self._fecha_historial = None
        if self.historial:
            try:
                self._mostrar_titulo(self.historial.crear(archivo, resultado, modelo_whisper=modelo_whisper))
                self._log(f"Guardado en el historial (#{self.id_historial})")
            except Exception as e:
                self._log(f"No se pudo guardar en el historial: {e}")
        idioma = IDIOMAS_DISPONIBLES.get(resultado.idioma_detectado, resultado.idioma_detectado)
        self.label_resumen.configure(
            text=f"{idioma} ({resultado.probabilidad_idioma:.0%}) · {len(resultado.segmentos)} segmentos · "
                 f"{formatear_duracion(resultado.duracion_total)}"
        )
        for btn in (self.btn_copiar, self.btn_guardar, self.btn_abrir_carpeta):
            btn.configure(state="normal")
        for tab in self.tabs_ia.values():
            tab["generar"].configure(state="normal")
        self._log(f"Transcripción completada. Guardado automático en: {ruta_salida}")
        self._finalizar(f"Completado · guardado como {Path(ruta_salida).name}", 1.0)
        self._refrescar_historial()

    def _finalizar(self, mensaje: str, progreso: float):
        if self._inicio_transcripcion is not None:
            total = time.monotonic() - self._inicio_transcripcion
            self.label_tiempo.configure(text=f"Duró {formatear_duracion(total)}" if progreso == 1.0 else "")
        self._inicio_transcripcion = None
        self._bloquear_opciones(False)
        self.btn_transcribir.configure(
            text="▶  Transcribir", state="normal", fg_color=COLOR_TRANSCRIBIR, hover_color=COLOR_TRANSCRIBIR_HOVER
        )
        self.label_estado.configure(text=mensaje)
        self.progress.set(progreso)

    def _cancelar_transcripcion(self):
        self.cancelar_flag.set()
        self.btn_transcribir.configure(state="disabled", text="Cancelando…")
        self._actualizar_estado("Cancelando… (termina el segmento actual)")
        self._log("Solicitando cancelación...")

    def _tick_tiempo(self):
        """Actualiza tiempo transcurrido y estimado mientras hay transcripción."""
        if self._inicio_transcripcion is None:
            return
        transcurrido = time.monotonic() - self._inicio_transcripcion
        texto = f"Transcurrido {formatear_duracion(transcurrido)}"
        if 0.02 < self._progreso < 1:
            restante = transcurrido * (1 - self._progreso) / self._progreso
            texto += f" · quedan ~{formatear_duracion(restante)}"
        self.label_tiempo.configure(text=texto)
        self.after(500, self._tick_tiempo)

    # ------------------------------------------------------------ Resumen / minuta (IA)

    def _generando_ia(self) -> bool:
        return self._hilo_ia is not None and self._hilo_ia.is_alive()

    def _configurar_estilos_markdown(self, texto: ctk.CTkTextbox):
        # CTkTextbox no permite fuentes en tag_config; se usa el widget tk interno
        # Se parte de la fuente real (ya escalada por CTk) para que títulos y negritas sean proporcionales
        import tkinter.font as tkfont
        base = tkfont.Font(font=texto._textbox.cget("font")).actual()
        familia, tam = base["family"], abs(base["size"])
        interno = texto._textbox
        interno.tag_configure("h1", font=(familia, round(tam * 1.4), "bold"), spacing1=6, spacing3=6)
        interno.tag_configure("h2", font=(familia, round(tam * 1.2), "bold"), spacing1=10, spacing3=4)
        interno.tag_configure("h3", font=(familia, round(tam * 1.05), "bold"), spacing1=8, spacing3=2)
        interno.tag_configure("negrita", font=(familia, tam, "bold"))

    def _insertar_markdown(self, texto: ctk.CTkTextbox, contenido: str):
        """Render sencillo: títulos (#) y **negritas**. El Markdown original se conserva para copiar/guardar."""
        interno = texto._textbox
        for linea in contenido.splitlines():
            nivel = len(linea) - len(linea.lstrip("#"))
            if 1 <= nivel <= 3 and linea[nivel:nivel + 1] == " ":
                interno.insert("end", linea[nivel + 1:].replace("**", "") + "\n", f"h{nivel}")
                continue
            if linea.strip() == "---":
                continue
            partes = linea.split("**")
            for i, parte in enumerate(partes):
                interno.insert("end", parte, "negrita" if i % 2 and len(partes) % 2 else ())
            interno.insert("end", "\n")

    def _escribir_tab_ia(self, clave: str, contenido: str, secundario: bool = False):
        texto = self.tabs_ia[clave]["texto"]
        texto.configure(state="normal", text_color=COLOR_TEXTO_SECUNDARIO if secundario else ("gray10", "gray90"))
        texto.delete("1.0", "end")
        if secundario:
            texto.insert("end", contenido)
        else:
            self._insertar_markdown(texto, contenido)
        texto.configure(state="disabled")

    def _reiniciar_tab_ia(self, clave: str):
        tab = self.tabs_ia[clave]
        tab["contenido"] = None
        self._escribir_tab_ia(clave, DOCUMENTOS_IA[clave]["vacio"], secundario=True)
        for boton in ("generar", "copiar", "guardar"):
            tab[boton].configure(state="disabled")
        tab["generar"].configure(text=f"✨ Generar {DOCUMENTOS_IA[clave]['pestana'].lower()}")

    def _generar_documento_ia(self, clave: str):
        if not self.resultado_actual or self._generando_ia() or self._transcribiendo():
            return
        cfg = self.configuracion.get("ia", {})
        try:
            if self._asistente is None:
                self._asistente = AsistenteIA(
                    modelo=self._modelo_ia_configurado(),
                    temperatura=cfg.get("temperatura", 0.3),
                    max_caracteres_bloque=cfg.get("max_caracteres_bloque", 60000),
                    revision_fidelidad=cfg.get("revision_fidelidad", True),
                    peticiones_paralelas=cfg.get("peticiones_paralelas", 3),
                    enterprise_url=cfg.get("copilot_enterprise_url") or None,
                )
        except ErrorSinSesionCopilot:
            self._iniciar_sesion_copilot(lambda: self._generar_documento_ia(clave))
            return
        except ErrorAsistenteIA as e:
            messagebox.showerror("Asistente IA", str(e))
            return

        # Una línea por segmento: facilita dividir transcripciones largas en bloques
        texto = "\n".join(seg.texto for seg in self.resultado_actual.segmentos)
        # Si el audio se abrió desde el historial y ya no existe, el documento solo se guarda en el historial
        base = Path(self.archivo_actual)
        ruta_salida = str(base.with_name(base.stem + DOCUMENTOS_IA[clave]["sufijo"])) if base.exists() else None

        for tab in self.tabs_ia.values():
            tab["generar"].configure(state="disabled")
        self.btn_transcribir.configure(state="disabled")
        self.combo_modelo_ia.configure(state="disabled")
        self._escribir_tab_ia(clave, f"Generando con {self._asistente.nombre_proveedor} ({self._asistente.modelo})…", secundario=True)
        self.tabs_ia[clave]["estado"].configure(text=f"Enviando transcripción a {self._asistente.nombre_proveedor}…")
        self.label_estado.configure(text=f"Generando {DOCUMENTOS_IA[clave]['pestana'].lower()}…")
        self._log(f"Generando {clave} con {self._asistente.modelo}")

        self._hilo_ia = threading.Thread(
            target=self._procesar_documento_ia, args=(clave, texto, ruta_salida, self.id_historial), daemon=True
        )
        self._hilo_ia.start()

    def _procesar_documento_ia(self, clave: str, texto: str, ruta_salida: Optional[str], id_historial: Optional[int]):
        if clave == "resumen":
            generar = self._asistente.generar_resumen
        else:
            fecha = self._fecha_archivo()
            generar = lambda t, **kw: self._asistente.generar_minuta(t, fecha=fecha, **kw)
        estado = self.tabs_ia[clave]["estado"]
        try:
            inicio = time.monotonic()
            contenido = generar(texto, on_progreso=lambda m: self._en_ui(lambda: estado.configure(text=m)))
            if ruta_salida:
                Path(ruta_salida).write_text(contenido + "\n", encoding="utf-8")
            if self.historial and id_historial is not None:
                self.historial.guardar_documento(id_historial, clave, contenido, modelo=self._asistente.modelo_usado)
            self._en_ui(self._finalizar_documento_ia, clave, contenido, ruta_salida, time.monotonic() - inicio)
        except ErrorSinSesionCopilot as e:
            self._log(f"Error generando {clave}: {e}")
            self._asistente = None  # se recrea con el token nuevo tras iniciar sesión
            self._en_ui(self._finalizar_documento_ia, clave, None, None, 0, str(e))
            self._en_ui(self._iniciar_sesion_copilot, lambda: self._generar_documento_ia(clave))
        except Exception as e:
            self._log(f"Error generando {clave}: {e}")
            self._en_ui(self._finalizar_documento_ia, clave, None, None, 0, str(e))

    def _finalizar_documento_ia(self, clave, contenido, ruta_salida, segundos, error=None):
        tab = self.tabs_ia[clave]
        nombre = DOCUMENTOS_IA[clave]["pestana"]
        for t in self.tabs_ia.values():
            t["generar"].configure(state="normal")
        self.btn_transcribir.configure(state="normal")
        self.combo_modelo_ia.configure(state="normal")

        if error:
            self._escribir_tab_ia(clave, f"No se pudo generar: {error}", secundario=True)
            tab["estado"].configure(text="Error al generar")
            self.label_estado.configure(text=f"Error al generar {nombre.lower()}")
            messagebox.showerror("Asistente IA", error)
            return

        tab["contenido"] = contenido
        self._escribir_tab_ia(clave, contenido)
        tab["generar"].configure(text="↻ Regenerar")
        tab["copiar"].configure(state="normal")
        tab["guardar"].configure(state="normal")
        destino = f"guardado como {Path(ruta_salida).name}" if ruta_salida else "guardado en el historial"
        tab["estado"].configure(text=f"Listo en {segundos:.0f} s con {self._asistente.modelo_usado} · {destino}")
        if ruta_salida:
            self.ruta_guardada = ruta_salida
        self.label_estado.configure(text=f"Listo: {nombre.lower()}")
        self._log(f"{nombre} {destino}")
        if clave == "minuta" and self.historial and self.id_historial is not None:
            # La minuta puede haber dado título a la entrada
            entrada = self.historial.obtener(self.id_historial)
            if entrada:
                self._mostrar_titulo(entrada.id, entrada.titulo)
        self._refrescar_historial()

    def _modelo_ia_configurado(self) -> str:
        return self.configuracion.get("ia", {}).get("modelo", MODELO_POR_DEFECTO)

    def _texto_modelo_ia(self) -> str:
        return f"Modelo: {NOMBRE_PROVEEDOR} · {self._modelo_ia_configurado()}"

    def _cargar_modelos_ia(self):
        """Consulta en segundo plano qué modelos económicos (y si el modo auto) puede usar la cuenta."""
        enterprise_url = self.configuracion.get("ia", {}).get("copilot_enterprise_url") or None

        def consultar():
            sesion = copilot.leer_token(enterprise_url)
            if not sesion:
                self._log("Sin sesión de GitHub Copilot: la lista de modelos de IA se cargará al iniciar sesión")
                return
            try:
                modelos = copilot.modelos_economicos(sesion)
            except copilot.ErrorCopilot as e:
                self._log(f"No se pudo consultar los modelos de GitHub Copilot: {e}")
                return
            try:
                copilot.abrir_sesion_auto(sesion)
                modelos.insert(0, copilot.MODELO_AUTO)
            except copilot.ErrorCopilot as e:
                self._log(f"Modo auto no disponible: {e}")
            self._en_ui(self._mostrar_modelos_ia, modelos)

        threading.Thread(target=consultar, daemon=True).start()

    def _mostrar_modelos_ia(self, modelos: list[str]):
        actual = self._modelo_ia_configurado()
        if actual not in modelos:
            # Se respeta el modelo elegido en settings.yaml aunque no esté en la lista de económicos
            modelos.append(actual)
            self._log(f"El modelo configurado ({actual}) no está entre los económicos disponibles; se mantiene")
        self.combo_modelo_ia.configure(values=modelos)
        self._log(f"Modelos de IA disponibles: {', '.join(modelos)}")

    def _al_cambiar_modelo_ia(self, modelo: str):
        if modelo == self._modelo_ia_configurado():
            return
        texto_anterior = self._texto_modelo_ia()
        self.configuracion.setdefault("ia", {})["modelo"] = modelo
        self._asistente = None  # se recrea con el modelo nuevo en la próxima generación
        for tab in self.tabs_ia.values():
            if tab["estado"].cget("text") == texto_anterior:
                tab["estado"].configure(text=self._texto_modelo_ia())
        try:
            guardado = guardar_modelo_ia(modelo)
        except OSError as e:
            log.warning("No se pudo guardar el modelo en settings.yaml: %s", e)
            guardado = False
        self._log(f"Modelo de IA: {modelo}" + ("" if guardado else " (solo para esta sesión; no se guardó en settings.yaml)"))

    def _iniciar_sesion_copilot(self, al_conectar):
        """Abre el diálogo de inicio de sesión; si termina bien, ejecuta `al_conectar`."""
        def al_terminar(ok: bool):
            if ok:
                self._log("Sesión de GitHub Copilot iniciada")
                self._cargar_modelos_ia()
                al_conectar()
            else:
                self.label_estado.configure(text="Inicio de sesión en GitHub Copilot cancelado")
        enterprise_url = self.configuracion.get("ia", {}).get("copilot_enterprise_url") or None
        DialogoLoginCopilot(self, enterprise_url, al_terminar)

    def _fecha_archivo(self) -> str:
        """Fecha de modificación del archivo de audio, como aproximación a la fecha de la reunión."""
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
                 "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
        if os.path.exists(self.archivo_actual):
            t = time.localtime(os.path.getmtime(self.archivo_actual))
            origen = "fecha del archivo"
        elif self._fecha_historial:
            t = time.strptime(self._fecha_historial[:10], "%Y-%m-%d")
            origen = "fecha de transcripción"
        else:
            return "No especificada"
        return f"{t.tm_mday} de {meses[t.tm_mon - 1]} de {t.tm_year} ({origen})"

    def _copiar_documento_ia(self, clave: str):
        contenido = self.tabs_ia[clave]["contenido"]
        if contenido:
            self.clipboard_clear()
            self.clipboard_append(contenido)
            self.label_estado.configure(text=f"{DOCUMENTOS_IA[clave]['pestana']} copiado al portapapeles")

    def _guardar_documento_ia(self, clave: str):
        contenido = self.tabs_ia[clave]["contenido"]
        if not contenido:
            return
        archivo = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Texto", "*.txt")],
            initialfile=Path(self.archivo_actual).stem + DOCUMENTOS_IA[clave]["sufijo"],
        )
        if archivo:
            Path(archivo).write_text(contenido + "\n", encoding="utf-8")
            self._log(f"Guardado en: {archivo}")
            self.label_estado.configure(text=f"Guardado como {Path(archivo).name}")

    # ------------------------------------------------------------ Historial

    def _mostrar_titulo(self, id_historial: Optional[int], titulo: Optional[str] = None):
        """Vincula la vista con una entrada del historial y muestra su título."""
        self.id_historial = id_historial
        if id_historial is not None and titulo is None and self.historial:
            entrada = self.historial.obtener(id_historial)
            titulo = entrada.titulo if entrada else ""
        self.entry_titulo.configure(state="normal")
        self.entry_titulo.delete(0, "end")
        if id_historial is not None:
            self.entry_titulo.insert(0, titulo or "")
        else:
            self.entry_titulo.configure(state="disabled")
        self._titulo_mostrado = titulo or ""

    def _guardar_titulo(self):
        if self.id_historial is None or not self.historial:
            return
        nuevo = self.entry_titulo.get().strip()
        if not nuevo:
            self.entry_titulo.insert(0, self._titulo_mostrado)  # no se permite dejarlo vacío
            return
        if nuevo == self._titulo_mostrado:
            return
        self.historial.renombrar(self.id_historial, nuevo)
        self._titulo_mostrado = nuevo
        self.label_estado.configure(text="Título actualizado")
        self._refrescar_historial()

    def mostrar_vista(self, vista: str):
        """Alterna entre las vistas de la barra de navegación, dentro de la misma ventana."""
        if vista == VISTA_HISTORIAL and not self.historial:
            messagebox.showerror("Historial", "No se pudo abrir la base de datos del historial.")
            vista = VISTA_TRANSCRIBIR
        self.nav.set(vista)
        self.vista_actual = vista

        if vista == VISTA_HISTORIAL:
            if self.panel_historial is None:
                from src.ui_historial import PanelHistorial
                self.panel_historial = PanelHistorial(self, self, self.historial)
                self.panel_historial.grid(row=1, column=0, sticky="nsew")
            else:
                self.panel_historial.refrescar()
            self.vista_transcribir.grid_remove()
            self.panel_historial.grid()
        else:
            if self.panel_historial is not None:
                self.panel_historial.grid_remove()
            self.vista_transcribir.grid()

    def _refrescar_historial(self):
        if self.panel_historial is not None:
            self.panel_historial.refrescar()

    def cargar_desde_historial(self, id_historial: int) -> bool:
        """Muestra en la ventana principal una transcripción guardada, con su resumen y minuta."""
        if self._transcribiendo() or self._generando_ia():
            messagebox.showwarning("Historial", "Espera a que termine el proceso en curso.")
            return False
        entrada = self.historial.obtener(id_historial) if self.historial else None
        if entrada is None:
            return False

        if entrada.archivo_existe:
            self._cargar_archivo(entrada.archivo_ruta)
        else:
            self.label_drop_icono.configure(text="🗂")
            self.label_drop.configure(text=entrada.archivo_nombre)
            self.label_drop_detalle.configure(text="El archivo original ya no está disponible\n"
                                                   "Clic o arrastra otro para transcribir")
            self.btn_transcribir.configure(state="disabled")
        self.archivo_actual = entrada.archivo_ruta
        self._fecha_historial = entrada.creado_en

        resultado = entrada.a_resultado()
        self.resultado_actual = resultado
        self.ruta_guardada = entrada.archivo_ruta if entrada.archivo_existe else None
        self.text_resultado.configure(state="normal", text_color=("gray10", "gray90"))
        self.text_resultado.delete("1.0", "end")
        self.text_resultado.configure(state="disabled")
        for segmento in resultado.segmentos:
            self._agregar_segmento(segmento, -1)
        self.text_resultado.see("1.0")
        idioma = IDIOMAS_DISPONIBLES.get(resultado.idioma_detectado, resultado.idioma_detectado)
        self.label_resumen.configure(
            text=f"{idioma} · {len(resultado.segmentos)} segmentos · {formatear_duracion(resultado.duracion_total)}"
        )
        self.btn_copiar.configure(state="normal")
        self.btn_guardar.configure(state="normal")
        self.btn_abrir_carpeta.configure(state="normal" if entrada.archivo_existe else "disabled")

        for clave in self.tabs_ia:
            self._reiniciar_tab_ia(clave)
            tab = self.tabs_ia[clave]
            tab["generar"].configure(state="normal")
            contenido = getattr(entrada, clave)
            if contenido:
                tab["contenido"] = contenido
                self._escribir_tab_ia(clave, contenido)
                tab["generar"].configure(text="↻ Regenerar")
                tab["copiar"].configure(state="normal")
                tab["guardar"].configure(state="normal")
                tab["estado"].configure(text=f"Desde el historial · {getattr(entrada, clave + '_modelo') or ''}")

        self._mostrar_titulo(entrada.id, entrada.titulo)
        self.progress.set(0)
        self.label_tiempo.configure(text="")
        # Por la cola de eventos, para que no lo pise el "Archivo listo" que programa _cargar_archivo
        self._actualizar_estado(f"Abierto desde el historial: {entrada.titulo}", 0)
        self.tabs.set(TAB_TEXTO)
        self.mostrar_vista(VISTA_TRANSCRIBIR)
        self._log(f"Abierto desde el historial (#{entrada.id}): {entrada.titulo}")
        return True

    def historial_eliminado(self, id_historial: int):
        """Si se borra la entrada que se está mostrando, se desvincula (el contenido en pantalla se conserva)."""
        if self.id_historial == id_historial:
            self._mostrar_titulo(None)

    # ------------------------------------------------------------ Resultado

    def _generar_ruta_salida(self, archivo: Optional[str] = None, formato: Optional[str] = None) -> str:
        base = Path(archivo or self.archivo_actual)
        formato = formato or self.var_formato.get()
        return str(base.parent / f"{base.stem}_transcripcion.{formato}")

    def _copiar_texto(self):
        if not self.resultado_actual:
            return
        self.clipboard_clear()
        self.clipboard_append(self.resultado_actual.texto_completo)
        self.label_estado.configure(text="Texto copiado al portapapeles")

    def _guardar_resultado(self):
        if not self.resultado_actual:
            messagebox.showwarning("Atención", "No hay resultado para guardar")
            return

        formato = self.var_formato.get()
        archivo = filedialog.asksaveasfilename(
            defaultextension=f".{formato}",
            filetypes=[
                ("Texto", "*.txt"),
                ("Subtítulos SRT", "*.srt"),
                ("WebVTT", "*.vtt"),
                ("JSON", "*.json")
            ],
            initialfile=Path(self._generar_ruta_salida()).name
        )
        if archivo:
            # El formato se deduce de la extensión elegida en el diálogo
            ext = Path(archivo).suffix.lstrip(".").lower()
            guardar_transcripcion(
                self.resultado_actual,
                archivo,
                formato=ext if ext in FORMATOS_DISPONIBLES else formato,
                incluir_timestamps=self.var_timestamps.get()
            )
            self.ruta_guardada = archivo
            self._log(f"Guardado en: {archivo}")
            self.label_estado.configure(text=f"Guardado como {Path(archivo).name}")

    def _abrir_carpeta(self):
        if not self.ruta_guardada:
            return
        carpeta = str(Path(self.ruta_guardada).parent)
        try:
            if sys.platform.startswith("win"):
                os.startfile(carpeta)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", carpeta])
            else:
                subprocess.Popen(["xdg-open", carpeta])
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir la carpeta:\n{e}")

    # ------------------------------------------------------------ Utilidades

    def _en_ui(self, funcion, *args):
        """Ejecuta `funcion` en el hilo principal de Tkinter."""
        if self._cerrando:
            return
        try:
            self.after(0, funcion, *args)
        except (RuntimeError, tk.TclError):
            pass  # la ventana ya se cerró

    def report_callback_exception(self, tipo, valor, traza):
        """Errores en callbacks de Tkinter: a la consola en vez de perderse."""
        log.error("Error en la interfaz", exc_info=(tipo, valor, traza))

    def _log(self, mensaje: str):
        if threading.current_thread() is threading.main_thread():
            log.info(mensaje)  # desde otros hilos se registra al volver a entrar aquí
        # Tkinter no es thread-safe: desde el hilo de transcripción se delega al hilo principal
        if threading.current_thread() is not threading.main_thread():
            self._en_ui(self._log, mensaje)
            return
        marca = time.strftime("%H:%M:%S")
        self.text_log.configure(state="normal")
        self.text_log.insert("end", f"{marca}  {mensaje}\n")
        self.text_log.see("end")
        self.text_log.configure(state="disabled")

    def _actualizar_estado(self, mensaje: str, progreso: float = -1):
        def _update():
            self.label_estado.configure(text=mensaje)
            if 0 <= progreso <= 1:
                self.progress.set(progreso)
        self._en_ui(_update)


def main():
    configurar_logging()
    log.info("Iniciando interfaz (nivel de log %s; cámbialo con TRANSCRIPTOR_LOG=DEBUG)",
             logging.getLevelName(logging.getLogger("transcriptor").level))
    app = AppTranscriptor()
    app.mainloop()


if __name__ == "__main__":
    main()
