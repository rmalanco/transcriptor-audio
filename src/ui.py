"""Interfaz gráfica de escritorio para el transcriptor de audio/video."""

import logging
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    TKDND_DISPONIBLE = True
except ImportError:
    TKDND_DISPONIBLE = False

from src.asistente_ia import (NOMBRE_PROVEEDOR, AsistenteIA, ErrorAsistenteIA,
                              ErrorSinSesionCopilot)
from src import copilot
from src.historial import Historial
from src.registro import configurar_logging
from src.configuracion import (MODELOS_WHISPER, ErrorConfiguracion, cargar_configuracion, guardar_modelo_preferido,
                               leer_modelo_preferido, modelo_ia_efectivo)
from src.transcriber import TranscriptorAudio
from src.flujo_transcripcion import OpcionesTranscripcion, ruta_transcripcion, transcribir, transcriptor_para
from src.flujo_documentos import SUFIJOS_DOCUMENTO, fecha_de_la_reunion, ruta_documento, texto_para_ia
from src.ui_copilot import DialogoLoginCopilot
from src.persistencia import (Persistencia, motivo_de_error, persistir_documento_si_vigente, persistir_transcripcion,
                              texto_destino_documento, texto_sin_guardado)
from src.utils import (validar_archivo, obtener_info_archivo, guardar_transcripcion, filtros_seleccion_archivo,
                       formatear_duracion, ruta_junto_al_audio)


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


FORMATOS_DISPONIBLES = ["txt", "srt", "vtt", "json"]
log = logging.getLogger("transcriptor.ui")
TEMAS = {"Sistema": "System", "Claro": "Light", "Oscuro": "Dark"}
VISTA_TRANSCRIBIR = "🎙  Transcribir"
VISTA_HISTORIAL = "📚  Historial"
TAB_TEXTO = "Texto"  # nombre corto: las pestañas se recortan en ventanas estrechas
DOCUMENTOS_IA = {
    "resumen": {"pestana": "Resumen", "sufijo": SUFIJOS_DOCUMENTO["resumen"], "genitivo": "del resumen",
                "anterior": "el resumen anterior",
                "vacio": "Transcribe un archivo y pulsa «Generar resumen» para crear un resumen con IA."},
    "minuta": {"pestana": "Minuta", "sufijo": SUFIJOS_DOCUMENTO["minuta"], "genitivo": "de la minuta",
               "anterior": "la minuta anterior",
               "vacio": "Transcribe una reunión y pulsa «Generar minuta» para obtener objetivo, temas, "
                        "acuerdos y tareas."},
}


@dataclass
class _GeneracionIA:
    """Una generación de resumen o minuta en curso. Cada una tiene su propia señal de cancelación: si se cancela,
    el hilo abandonado no afecta a la siguiente generación."""
    clave: str
    asistente: AsistenteIA
    ruta_salida: Optional[str]
    id_historial: Optional[int]
    contenido_previo: Optional[str]     # documento que había en la pestaña antes de generar
    texto_boton_previo: str             # texto del botón de generar antes de empezar
    estado_transcribir_previo: str      # estado de «Transcribir» antes de empezar
    cancelar: threading.Event = field(default_factory=threading.Event)


COLOR_BORDE = ("gray75", "gray30")
COLOR_BORDE_ACTIVO = ("#3B8ED0", "#1F6AA5")
COLOR_TEXTO_SECUNDARIO = ("gray40", "gray65")
COLOR_TRANSCRIBIR = ("#2E8B57", "#2E7D4F")
COLOR_TRANSCRIBIR_HOVER = ("#256F46", "#23613D")
COLOR_CANCELAR = ("#C0392B", "#A93226")
COLOR_CANCELAR_HOVER = ("#992D22", "#86281E")


if TKDND_DISPONIBLE:
    _BaseDnD = TkinterDnD.DnDWrapper
else:
    _BaseDnD = object


class AppTranscriptor(ctk.CTk, _BaseDnD):
    def __init__(self, configuracion: dict):
        super().__init__()

        # Carga tkdnd sobre el mismo intérprete Tcl de CTk (no crear un segundo Tk)
        self.dnd_habilitado = False
        if TKDND_DISPONIBLE:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
                self.dnd_habilitado = True
            except RuntimeError:
                pass

        self.configuracion = configuracion
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
        self._generacion: Optional[_GeneracionIA] = None  # generación de resumen/minuta activa, si la hay
        self.tabs_ia: dict = {}
        self.id_historial: Optional[int] = None        # entrada del historial mostrada ahora
        self._fecha_historial: Optional[str] = None     # fecha de creación si el audio ya no existe
        self.panel_historial = None                     # se construye la primera vez que se muestra
        self.vista_actual = VISTA_TRANSCRIBIR
        self._titulo_mostrado = ""
        try:
            self.historial: Optional[Historial] = Historial(self.configuracion["historial"]["ruta"])
        except Exception as e:  # el historial no debe impedir usar la app
            self.historial = None
            log.exception("No se pudo abrir el historial: %s", e)

        # Variables de control
        idioma_cfg = self.configuracion["transcripcion"]["idioma"]
        self.var_modelo = tk.StringVar(value=self.configuracion["modelo"]["nombre"])
        self.var_idioma = tk.StringVar(value=IDIOMAS_DISPONIBLES.get(idioma_cfg, idioma_cfg))
        self.var_formato = tk.StringVar(value=self.configuracion["salida"]["formato"])
        self.var_dispositivo = tk.StringVar(value=self.configuracion["modelo"]["dispositivo"])
        self.var_compute = tk.StringVar(value=self.configuracion["modelo"]["compute_type"])
        self.var_timestamps = tk.BooleanVar(value=self.configuracion["salida"]["incluir_timestamps"])
        self._modelo_preferido = leer_modelo_preferido()  # el que eligió el usuario en el selector, si lo hay
        self.var_modelo_ia = tk.StringVar(value=self._modelo_ia_configurado())

        self._construir_ui()
        self._configurar_drag_drop()
        self._configurar_atajos()
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
        self.combo_modelo = ctk.CTkOptionMenu(opciones, values=list(MODELOS_WHISPER), variable=self.var_modelo)
        self.combo_modelo.grid(row=2, column=0, padx=(14, 6), pady=(0, 8), sticky="ew")

        self._etiqueta(opciones, "Idioma", 1, 1)
        self.combo_idioma = ctk.CTkOptionMenu(
            opciones, values=opciones_de_idioma(self.configuracion["transcripcion"]["idioma"]),
            variable=self.var_idioma
        )
        self.combo_idioma.grid(row=2, column=1, padx=(6, 14), pady=(0, 8), sticky="ew")

        self._etiqueta(opciones, "Formato de salida", 3, 0, columnspan=2)
        self.combo_formato = ctk.CTkSegmentedButton(
            opciones, values=FORMATOS_DISPONIBLES, variable=self.var_formato
        )
        self.combo_formato.grid(row=4, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="ew")

        self.check_timestamps = ctk.CTkSwitch(opciones, text="Incluir marcas de tiempo", variable=self.var_timestamps)
        self.check_timestamps.grid(row=5, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="w")

        # Al arrancar no se consulta Copilot: el selector solo ofrece «auto» y el configurado; «↻» carga el resto
        self._etiqueta(opciones, "Modelo de IA (resumen y minuta)", 6, 0, columnspan=2)
        self.combo_modelo_ia = ctk.CTkOptionMenu(
            opciones, values=copilot.opciones_de_modelo([copilot.MODELO_AUTO], self.var_modelo_ia.get()),
            variable=self.var_modelo_ia, command=self._al_cambiar_modelo_ia
        )
        self.combo_modelo_ia.grid(row=7, column=0, padx=(14, 6), pady=(0, 10), sticky="ew")
        self.btn_cargar_modelos_ia = ctk.CTkButton(opciones, text="↻", width=36, command=self._cargar_modelos_ia)
        self.btn_cargar_modelos_ia.grid(row=7, column=1, padx=(6, 14), pady=(0, 10), sticky="e")

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

        estado = ctk.CTkLabel(acciones, text=self._texto_modelo_ia(), justify="left",
                              text_color=COLOR_TEXTO_SECUNDARIO, anchor="w", wraplength=260)
        estado.grid(row=1, column=0, columnspan=3, pady=(4, 0), sticky="w")

        def ajustar_ancho_estado(evento):
            ancho = max(evento.width - 16, 80)
            if int(estado.cget("wraplength")) != ancho:
                estado.configure(wraplength=ancho)
        acciones.bind("<Configure>", ajustar_ancho_estado)

        btn_generar = ctk.CTkButton(acciones, text=f"✨ Generar {doc['pestana'].lower()}", width=60,
                                    state="disabled", command=lambda: self._alternar_documento_ia(clave))
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

    def _al_cerrar(self):
        if self._transcribiendo():
            if not messagebox.askyesno("Salir", "Hay una transcripción en curso. ¿Cancelarla y salir?"):
                return
            self.cancelar_flag.set()
        if self._generando_ia():
            genitivo = DOCUMENTOS_IA[self._generacion.clave]["genitivo"]
            if not messagebox.askyesno("Salir", f"Hay una generación {genitivo} en curso. ¿Cancelarla y salir?"):
                return
            self._cancelar_documento_ia()
        self._cerrando = True
        self.destroy()

    # ------------------------------------------------------------ Archivo

    def _seleccionar_archivo(self):
        if self._transcribiendo() or self._generando_ia():
            messagebox.showwarning("Atención", "Espera a que termine el proceso en curso.")
            return
        archivo = filedialog.askopenfilename(
            title="Seleccionar archivo de audio/video",
            filetypes=filtros_seleccion_archivo()
        )
        if archivo:
            self._cargar_archivo(archivo)

    def _confirmar_descarte(self) -> bool:
        """Pregunta antes de reemplazar un resultado que no quedó guardado en ningún sitio."""
        if self.resultado_actual and self.id_historial is None and self.ruta_guardada is None:
            return messagebox.askyesno("Atención", "La transcripción en pantalla no quedó guardada en ningún sitio "
                                                   "y se perderá al cargar otra. ¿Continuar?")
        return True

    def _cargar_archivo(self, ruta: str, confirmar: bool = True) -> bool:
        """Carga un archivo nuevo y reinicia la vista. Devuelve False si el usuario decide no cargarlo.

        Un archivo inválido ya avisa con un error y devuelve True: quien abre el historial sigue con su entrada.
        """
        if self._transcribiendo() or self._generando_ia():
            messagebox.showwarning("Atención", "Espera a que termine el proceso en curso.")
            return False
        try:
            validar_archivo(ruta)
            info = obtener_info_archivo(ruta)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el archivo:\n{e}")
            self._log(f"Error cargando archivo: {e}")
            return True

        if confirmar and not self._confirmar_descarte():
            return False

        self.archivo_actual = ruta
        self._limpiar_resultado()
        self._mostrar_marcador()

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
        return True

    def _limpiar_resultado(self):
        """Deja la vista sin resultado: texto, título, resumen, botones de resultado y pestañas de IA."""
        self.resultado_actual = None
        self.ruta_guardada = None
        self._fecha_historial = None
        self._mostrar_titulo(None)
        self.text_resultado.configure(state="normal", text_color=("gray10", "gray90"))
        self.text_resultado.delete("1.0", "end")
        self.text_resultado.configure(state="disabled")
        self.label_resumen.configure(text="")
        for btn in (self.btn_copiar, self.btn_guardar, self.btn_abrir_carpeta):
            btn.configure(state="disabled")
        for clave in self.tabs_ia:
            self._reiniciar_tab_ia(clave)

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
        return codigo_de_idioma(self.var_idioma.get())

    def _iniciar_transcripcion(self):
        if not self.archivo_actual:
            messagebox.showwarning("Atención", "Primero selecciona un archivo")
            return

        # Se leen las opciones en el hilo principal (Tkinter no es thread-safe)
        opciones = OpcionesTranscripcion.desde_configuracion(
            self.configuracion, self.archivo_actual,
            modelo=self.var_modelo.get(),
            idioma=self._codigo_idioma(),
            dispositivo=self.var_dispositivo.get(),
            compute_type=self.var_compute.get(),
            formato=self.var_formato.get(),
            incluir_timestamps=self.var_timestamps.get(),
        )

        self.cancelar_flag.clear()
        self._limpiar_resultado()
        self._progreso = 0.0
        self._inicio_transcripcion = time.monotonic()

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

    def _procesar_transcripcion(self, opciones: OpcionesTranscripcion):
        try:
            self._actualizar_estado(f"Cargando modelo {opciones.modelo}…")
            self._log(f"Iniciando transcripción con modelo: {opciones.modelo}")
            transcriptor = transcriptor_para(self._transcriptor, opciones.modelo, opciones.dispositivo,
                                             opciones.compute_type)
            _ = transcriptor.modelo  # fuerza la carga/descarga aquí para poder informar del estado
            self._transcriptor = transcriptor

            if self.cancelar_flag.is_set():
                raise InterruptedError

            self._actualizar_estado("Transcribiendo…", 0)

            def on_segmento(segmento, duracion_total):
                progreso = min(segmento.fin / duracion_total, 1.0) if duracion_total else -1
                self._en_ui(self._agregar_segmento, segmento, progreso)

            resultado = transcribir(transcriptor, opciones, self.configuracion["transcripcion"],
                                    on_segmento=on_segmento, cancelar=self.cancelar_flag)

            if self.cancelar_flag.is_set():
                raise InterruptedError

            # Primero el historial y después el archivo junto al audio (regla 6); no lanza por fallos de guardado
            persistencia = persistir_transcripcion(
                self.historial, opciones.archivo, resultado, opciones.modelo,
                ruta_transcripcion(opciones.archivo, opciones.formato), opciones.formato, opciones.incluir_timestamps,
            )
            self._en_ui(self._finalizar_ok, resultado, persistencia)

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

    def _finalizar_ok(self, resultado, persistencia: Persistencia):
        self.resultado_actual = resultado
        self.ruta_guardada = persistencia.ruta_exportada
        self._fecha_historial = None
        avisos = []
        try:
            self._mostrar_titulo(persistencia.id_historial)
        except Exception as e:
            # Si el historial no se puede leer, el título se toma del nombre del audio
            titulo = Path(self.archivo_actual).stem if self.archivo_actual else ""
            self._mostrar_titulo(persistencia.id_historial, titulo=titulo)
            avisos.append(f"No se pudo leer el título del historial: {e}")
        if persistencia.id_historial is not None:
            self._log(f"Guardado en el historial (#{persistencia.id_historial})")
        if persistencia.motivo_historial:
            avisos.append(f"No se pudo guardar en el historial: {persistencia.motivo_historial}")
        if persistencia.motivo_exportacion:
            avisos.append(f"No se pudo exportar {persistencia.motivo_exportacion}")
        aviso_sin_guardar = texto_sin_guardado(persistencia)
        if aviso_sin_guardar:
            avisos.append(aviso_sin_guardar)
        for aviso in avisos:
            self._log(aviso)
        idioma = IDIOMAS_DISPONIBLES.get(resultado.idioma_detectado, resultado.idioma_detectado)
        self.label_resumen.configure(
            text=f"{idioma} ({resultado.probabilidad_idioma:.0%}) · {len(resultado.segmentos)} segmentos · "
                 f"{formatear_duracion(resultado.duracion_total)}"
        )
        for btn in (self.btn_copiar, self.btn_guardar):
            btn.configure(state="normal")
        self.btn_abrir_carpeta.configure(state="normal" if persistencia.ruta_exportada else "disabled")
        for tab in self.tabs_ia.values():
            tab["generar"].configure(state="normal")
        if persistencia.ruta_exportada:
            self._log(f"Transcripción completada. Guardado automático en: {persistencia.ruta_exportada}")
            mensaje = f"Completado · guardado como {Path(persistencia.ruta_exportada).name}"
        else:
            self._log("Transcripción completada. No se exportó el archivo")
            mensaje = "Completado · no se exportó (ver avisos)"
        self._finalizar(mensaje, 1.0)
        self._refrescar_historial()
        if avisos:
            messagebox.showwarning("Atención", "\n".join(avisos))

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
        return self._generacion is not None

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
        tab["estado"].configure(text=self._texto_modelo_ia())  # sin restos del documento anterior

    def _alternar_documento_ia(self, clave: str):
        if self._generacion is not None and self._generacion.clave == clave:
            self._cancelar_documento_ia()
        else:
            self._generar_documento_ia(clave)

    def _generar_documento_ia(self, clave: str):
        if not self.resultado_actual or self._generando_ia() or self._transcribiendo():
            return
        cfg = self.configuracion["ia"]
        try:
            if self._asistente is None:
                self._asistente = AsistenteIA(
                    modelo=self._modelo_ia_configurado(),
                    temperatura=cfg["temperatura"],
                    max_caracteres_bloque=cfg["max_caracteres_bloque"],
                    revision_fidelidad=cfg["revision_fidelidad"],
                    peticiones_paralelas=cfg["peticiones_paralelas"],
                    enterprise_url=cfg["copilot_enterprise_url"] or None,
                )
        except ErrorSinSesionCopilot:
            self._iniciar_sesion_copilot(lambda: self._generar_documento_ia(clave))
            return
        except ErrorAsistenteIA as e:
            messagebox.showerror("Asistente IA", str(e))
            return

        # Una línea por segmento: facilita dividir transcripciones largas en bloques
        texto = texto_para_ia(self.resultado_actual)
        # Si el audio se abrió desde el historial y ya no existe, el documento solo se guarda en el historial
        ruta_salida = ruta_documento(self.archivo_actual, clave)
        # La fecha se calcula aquí, en el hilo principal, y solo la usa la minuta
        fecha = fecha_de_la_reunion(self.archivo_actual, self._fecha_historial) if clave == "minuta" else None

        tab = self.tabs_ia[clave]
        asistente = self._asistente
        generacion = _GeneracionIA(
            clave=clave, asistente=asistente, ruta_salida=ruta_salida, id_historial=self.id_historial,
            contenido_previo=tab["contenido"], texto_boton_previo=tab["generar"].cget("text"),
            estado_transcribir_previo=self.btn_transcribir.cget("state"),
        )
        self._generacion = generacion
        for k, t in self.tabs_ia.items():
            t["generar"].configure(state="normal" if k == clave else "disabled")
        tab["generar"].configure(text="■ Cancelar")
        self.btn_transcribir.configure(state="disabled")
        self.combo_modelo_ia.configure(state="disabled")
        self._escribir_tab_ia(clave, f"Generando con {asistente.nombre_proveedor} ({asistente.modelo})…",
                              secundario=True)
        tab["estado"].configure(text=f"Enviando transcripción a {asistente.nombre_proveedor}…")
        self.label_estado.configure(text=f"Generando {DOCUMENTOS_IA[clave]['pestana'].lower()}…")
        self._log(f"Generando {clave} con {asistente.modelo}")

        threading.Thread(target=self._procesar_documento_ia, args=(generacion, texto, fecha), daemon=True).start()

    def _procesar_documento_ia(self, generacion: _GeneracionIA, texto: str, fecha: Optional[str]):
        """Hilo de fondo: no toca widgets, el historial ni el archivo; entrega el resultado al hilo principal."""
        asistente, clave = generacion.asistente, generacion.clave
        try:  # cualquier fallo debe llegar al hilo principal: si no, la generación nunca se daría por terminada
            if clave == "resumen":
                generar = asistente.generar_resumen
            else:
                generar = lambda t, **kw: asistente.generar_minuta(t, fecha=fecha, **kw)
            inicio = time.monotonic()
            contenido = generar(texto, on_progreso=lambda m: self._en_ui(self._progreso_documento_ia, generacion, m),
                                cancelar=generacion.cancelar)
            self._en_ui(self._recibir_documento_ia, generacion, contenido, asistente.modelo_usado,
                        time.monotonic() - inicio, None)
        except Exception as e:  # incluye InterruptedError (cancelada) y ErrorSinSesionCopilot
            self._en_ui(self._recibir_documento_ia, generacion, None, None, 0, e)

    def _progreso_documento_ia(self, generacion: _GeneracionIA, mensaje: str):
        if generacion is self._generacion:  # una generación cancelada ya no escribe en su pestaña
            self.tabs_ia[generacion.clave]["estado"].configure(text=mensaje)

    def _recibir_documento_ia(self, generacion: _GeneracionIA, contenido: Optional[str], modelo: Optional[str],
                              segundos: float, error: Optional[Exception]):
        """Único punto de decisión: si la generación se canceló, descarta el resultado sin tocar nada más."""
        clave = generacion.clave
        if generacion is not self._generacion:
            self._log(f"Resultado de {clave} descartado: la generación se canceló")
            return
        self._generacion = None
        tab = self.tabs_ia[clave]
        tab["generar"].configure(text=generacion.texto_boton_previo)
        self.btn_transcribir.configure(state=generacion.estado_transcribir_previo)
        if error is None:
            persistencia = persistir_documento_si_vigente(False, self.historial, generacion.id_historial, clave,
                                                          contenido, modelo, generacion.ruta_salida)
            self._finalizar_documento_ia(clave, contenido, persistencia, segundos)
            return
        self._log(f"Error generando {clave}: {error}")
        mensaje = str(error) or type(error).__name__
        if isinstance(error, ErrorSinSesionCopilot):
            self._asistente = None  # se recrea con el token nuevo tras iniciar sesión
            self._finalizar_documento_ia(clave, None, None, 0, mensaje)
            self._iniciar_sesion_copilot(lambda: self._generar_documento_ia(clave))
        else:
            self._finalizar_documento_ia(clave, None, None, 0, mensaje)

    def _cancelar_documento_ia(self):
        """Devuelve la ventana al instante; el hilo abandonado termina solo y su resultado se descarta."""
        generacion = self._generacion
        if generacion is None:
            return
        clave = generacion.clave
        tab = self.tabs_ia[clave]
        generacion.cancelar.set()
        self._generacion = None
        self._asistente = None  # el hilo abandonado conserva el suyo; la siguiente generación crea otro
        if generacion.contenido_previo is not None:
            self._escribir_tab_ia(clave, generacion.contenido_previo)
            tab["estado"].configure(text=f"Generación cancelada · se conserva {DOCUMENTOS_IA[clave]['anterior']}")
        else:
            self._reiniciar_tab_ia(clave)
            tab["estado"].configure(text="Generación cancelada")
        tab["generar"].configure(text=generacion.texto_boton_previo)
        for t in self.tabs_ia.values():
            t["generar"].configure(state="normal")
        self.combo_modelo_ia.configure(state="normal")
        self.btn_transcribir.configure(state=generacion.estado_transcribir_previo)
        genitivo = DOCUMENTOS_IA[clave]["genitivo"]
        self.label_estado.configure(text=f"Generación {genitivo} cancelada")
        self._log(f"Generación {genitivo} cancelada")

    def _finalizar_documento_ia(self, clave, contenido, persistencia: Optional[Persistencia], segundos, error=None):
        tab = self.tabs_ia[clave]
        nombre = DOCUMENTOS_IA[clave]["pestana"]
        for t in self.tabs_ia.values():
            t["generar"].configure(state="normal")
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
        destino = texto_destino_documento(persistencia)
        tab["estado"].configure(text=f"Listo en {segundos:.0f} s con {self._asistente.modelo_usado} · {destino}")
        if persistencia.ruta_exportada:
            self.ruta_guardada = persistencia.ruta_exportada
            self.btn_abrir_carpeta.configure(state="normal")
        self.label_estado.configure(text=f"Listo: {nombre.lower()}")
        self._log(f"{nombre} {destino}")
        if clave == "minuta" and self.historial and self.id_historial is not None:
            # La minuta puede haber dado título a la entrada
            try:
                entrada = self.historial.obtener(self.id_historial)
                if entrada:
                    self._mostrar_titulo(entrada.id, entrada.titulo)
            except Exception as e:
                self._log(f"No se pudo actualizar el título desde el historial: {e}")
        self._refrescar_historial()

    def _modelo_ia_configurado(self) -> str:
        return modelo_ia_efectivo(self.configuracion, self._modelo_preferido)

    def _texto_modelo_ia(self) -> str:
        return f"Modelo: {NOMBRE_PROVEEDOR} · {self._modelo_ia_configurado()}"

    def _cargar_modelos_ia(self):
        """Pulsación de «↻»: consulta una vez el catálogo de Copilot, en segundo plano, y lo muestra en el selector.
        Sin sesión, abre el inicio de sesión y vuelve a cargar al terminar bien."""
        self.btn_cargar_modelos_ia.configure(state="disabled")
        self.label_estado.configure(text="Consultando los modelos de GitHub Copilot…")
        enterprise_url = self.configuracion["ia"]["copilot_enterprise_url"] or None
        actual = self._modelo_ia_configurado()

        def consultar():
            try:
                sesion = copilot.leer_token(enterprise_url)
                if not sesion:
                    self._en_ui(self._sin_sesion_para_modelos)
                    return
                opciones = copilot.cargar_opciones_de_modelo(sesion, actual)
            except Exception as e:  # siempre se llega al hilo principal, para que «↻» vuelva a estar habilitado
                self._en_ui(self._fallo_cargar_modelos_ia, str(e) or type(e).__name__)
                return
            self._en_ui(self._mostrar_modelos_ia, opciones)

        threading.Thread(target=consultar, daemon=True).start()

    def _sin_sesion_para_modelos(self):
        self.btn_cargar_modelos_ia.configure(state="normal")
        self._log("Sin sesión de GitHub Copilot: se abre el inicio de sesión para cargar los modelos")
        self._iniciar_sesion_copilot(self._cargar_modelos_ia)

    def _fallo_cargar_modelos_ia(self, mensaje: str):
        self.btn_cargar_modelos_ia.configure(state="normal")
        self._log(f"No se pudo consultar los modelos de GitHub Copilot: {mensaje}")
        self.label_estado.configure(text="No se pudieron cargar los modelos de IA")

    def _mostrar_modelos_ia(self, opciones: list[str]):
        self.combo_modelo_ia.configure(values=opciones)
        self.btn_cargar_modelos_ia.configure(state="normal")
        actual = self._modelo_ia_configurado()
        if copilot.familia_excluida(actual):
            self._log(f"El modelo configurado ({actual}) es de una familia no autorizada por la empresa; no se ofrece")
        self._log(f"Modelos de IA disponibles: {', '.join(opciones)}")
        self.label_estado.configure(text="Modelos de IA cargados")

    def _al_cambiar_modelo_ia(self, modelo: str):
        if modelo == self._modelo_ia_configurado():
            return
        texto_anterior = self._texto_modelo_ia()
        self._modelo_preferido = modelo
        self._asistente = None  # se recrea con el modelo nuevo en la próxima generación
        for tab in self.tabs_ia.values():
            if tab["estado"].cget("text") == texto_anterior:
                tab["estado"].configure(text=self._texto_modelo_ia())
        try:
            guardar_modelo_preferido(modelo)
            guardado = True
        except OSError as e:
            log.warning("No se pudo guardar la preferencia de modelo: %s", e)
            guardado = False
        self._log(f"Modelo de IA: {modelo}" + ("" if guardado else " (solo para esta sesión; no se pudo guardar en preferencias.json)"))

    def _iniciar_sesion_copilot(self, al_conectar):
        """Abre el diálogo de inicio de sesión; si termina bien, ejecuta `al_conectar`."""
        def al_terminar(ok: bool):
            if ok:
                self._log("Sesión de GitHub Copilot iniciada")
                al_conectar()
            else:
                self.label_estado.configure(text="Inicio de sesión en GitHub Copilot cancelado")
        enterprise_url = self.configuracion["ia"]["copilot_enterprise_url"] or None
        DialogoLoginCopilot(self, enterprise_url, al_terminar)

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
            initialfile=Path(ruta_junto_al_audio(self.archivo_actual, DOCUMENTOS_IA[clave]["sufijo"])).name,
        )
        if archivo:
            try:
                Path(archivo).write_text(contenido + "\n", encoding="utf-8")
            except Exception as e:
                self._avisar_error_guardar(archivo, e)
                return
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
        if entrada is None or not self._confirmar_descarte():
            return False

        if entrada.archivo_existe:
            if not self._cargar_archivo(entrada.archivo_ruta, confirmar=False):
                return False
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
            initialfile=Path(ruta_transcripcion(self.archivo_actual, self.var_formato.get())).name
        )
        if archivo:
            # El formato se deduce de la extensión elegida en el diálogo
            ext = Path(archivo).suffix.lstrip(".").lower()
            try:
                guardar_transcripcion(
                    self.resultado_actual,
                    archivo,
                    formato=ext if ext in FORMATOS_DISPONIBLES else formato,
                    incluir_timestamps=self.var_timestamps.get()
                )
            except Exception as e:
                self._avisar_error_guardar(archivo, e)
                return
            self.ruta_guardada = archivo
            self.btn_abrir_carpeta.configure(state="normal")
            self._log(f"Guardado en: {archivo}")
            self.label_estado.configure(text=f"Guardado como {Path(archivo).name}")

    def _avisar_error_guardar(self, archivo: str, error: Exception):
        """«Guardar como…» que falla: se ve en pantalla y queda en el Registro."""
        motivo = motivo_de_error(error)
        self._log(f"No se pudo guardar {Path(archivo).name}: {motivo}")
        messagebox.showerror("Error", f"No se pudo guardar el archivo:\n{motivo}")

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
    try:
        configuracion = cargar_configuracion()
    except ErrorConfiguracion as e:
        log.error("%s", e)
        raiz = tk.Tk()  # ventana oculta solo para poder mostrar el diálogo antes de construir la app
        raiz.withdraw()
        messagebox.showerror("Configuración", str(e), parent=raiz)
        raiz.destroy()
        sys.exit(1)
    app = AppTranscriptor(configuracion)
    app.mainloop()


if __name__ == "__main__":
    main()
