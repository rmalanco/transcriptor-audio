"""Vista del historial de transcripciones (se muestra dentro de la ventana principal)."""

from datetime import datetime
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from src.historial import EntradaHistorial, Historial


LIMITE_LISTA = 200
COLOR_TEXTO_SECUNDARIO = ("gray40", "gray65")
COLOR_ITEM = ("gray90", "gray20")
COLOR_ITEM_HOVER = ("gray85", "gray25")
COLOR_ITEM_SELECCIONADO = ("#CFE3F7", "#1F3A57")
COLOR_ELIMINAR = ("#C0392B", "#A93226")
COLOR_ELIMINAR_HOVER = ("#992D22", "#86281E")
VISTAS = {"Transcripción": "texto", "Resumen": "resumen", "Minuta": "minuta"}


def formatear_fecha(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def formatear_duracion(segundos: Optional[float]) -> str:
    if not segundos:
        return "—"
    segundos = int(segundos)
    horas, resto = divmod(segundos, 3600)
    minutos, segs = divmod(resto, 60)
    return f"{horas}:{minutos:02d}:{segs:02d}" if horas else f"{minutos:02d}:{segs:02d}"


class PanelHistorial(ctk.CTkFrame):
    def __init__(self, master, app, historial: Historial):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.historial = historial
        self.seleccion: Optional[int] = None
        self.entrada: Optional[EntradaHistorial] = None
        self._items: dict[int, ctk.CTkFrame] = {}
        self._busqueda_pendiente = None

        # La lista y el detalle se reparten el ancho (2:3) para adaptarse a ventanas pequeñas
        self.grid_columnconfigure(0, weight=2, minsize=240, uniform="columnas")
        self.grid_columnconfigure(1, weight=3, uniform="columnas")
        self.grid_rowconfigure(0, weight=1)

        self._construir_lista()
        self._construir_detalle()
        self.refrescar()

    # ------------------------------------------------------------ Construcción

    def _construir_lista(self):
        panel = ctk.CTkFrame(self, fg_color="transparent")
        panel.grid(row=0, column=0, padx=(20, 8), pady=8, sticky="nsew")
        panel.grid_rowconfigure(2, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        self.entry_busqueda = ctk.CTkEntry(panel, placeholder_text="🔍  Buscar en títulos, textos, resúmenes…")
        self.entry_busqueda.grid(row=0, column=0, sticky="ew")
        self.entry_busqueda.bind("<KeyRelease>", lambda e: self._programar_busqueda())

        self.label_conteo = ctk.CTkLabel(panel, text="", text_color=COLOR_TEXTO_SECUNDARIO, anchor="w")
        self.label_conteo.grid(row=1, column=0, pady=(6, 2), sticky="w")

        self.lista = ctk.CTkScrollableFrame(panel, width=200, fg_color="transparent")
        self.lista.grid(row=2, column=0, sticky="nsew")
        self.lista.grid_columnconfigure(0, weight=1)

    def _construir_detalle(self):
        self.detalle = ctk.CTkFrame(self, corner_radius=12)
        self.detalle.grid(row=0, column=1, padx=(8, 20), pady=(8, 16), sticky="nsew")
        self.detalle.grid_columnconfigure(0, weight=1)
        self.detalle.grid_rowconfigure(3, weight=1)

        fila_titulo = ctk.CTkFrame(self.detalle, fg_color="transparent")
        fila_titulo.grid(row=0, column=0, padx=16, pady=(16, 4), sticky="ew")
        fila_titulo.grid_columnconfigure(0, weight=1)
        self.entry_titulo = ctk.CTkEntry(fila_titulo, font=ctk.CTkFont(size=18, weight="bold"), height=38)
        self.entry_titulo.grid(row=0, column=0, sticky="ew")
        self.entry_titulo.bind("<Return>", lambda e: self._guardar_titulo())
        self.btn_titulo = ctk.CTkButton(fila_titulo, text="Guardar", width=80, command=self._guardar_titulo)
        self.btn_titulo.grid(row=0, column=1, padx=(8, 0))

        self.label_meta = ctk.CTkLabel(self.detalle, text="", text_color=COLOR_TEXTO_SECUNDARIO,
                                       anchor="w", justify="left")
        self.detalle.bind("<Configure>", lambda e: self.label_meta.configure(wraplength=max(e.width - 40, 150)))
        self.label_meta.grid(row=1, column=0, padx=18, pady=(0, 8), sticky="ew")

        self.selector_vista = ctk.CTkSegmentedButton(self.detalle, values=list(VISTAS),
                                                     command=lambda v: self._mostrar_vista())
        self.selector_vista.set("Transcripción")
        self.selector_vista.grid(row=2, column=0, padx=16, sticky="w")

        self.text_vista = ctk.CTkTextbox(self.detalle, wrap="word", font=ctk.CTkFont(size=13))
        self.text_vista.grid(row=3, column=0, padx=16, pady=8, sticky="nsew")
        self.app._configurar_estilos_markdown(self.text_vista)

        acciones = ctk.CTkFrame(self.detalle, fg_color="transparent")
        acciones.grid(row=4, column=0, padx=16, pady=(0, 16), sticky="ew")
        acciones.grid_columnconfigure(0, weight=1)
        self.btn_abrir = ctk.CTkButton(acciones, text="Abrir", width=100, height=36,
                                       command=self._abrir_en_principal)
        self.btn_abrir.grid(row=0, column=0, sticky="w")
        self.btn_eliminar = ctk.CTkButton(acciones, text="Eliminar", width=100, height=36,
                                          fg_color=COLOR_ELIMINAR, hover_color=COLOR_ELIMINAR_HOVER,
                                          command=self._eliminar)
        self.btn_eliminar.grid(row=0, column=1)

        self._mostrar_detalle(None)

    # ------------------------------------------------------------ Lista

    def _programar_busqueda(self):
        # Pequeña espera para no consultar la base de datos en cada tecla
        if self._busqueda_pendiente:
            self.after_cancel(self._busqueda_pendiente)
        self._busqueda_pendiente = self.after(250, self.refrescar)

    def refrescar(self):
        self._busqueda_pendiente = None
        busqueda = self.entry_busqueda.get()
        entradas = self.historial.listar(busqueda, limite=LIMITE_LISTA + 1)
        hay_mas = len(entradas) > LIMITE_LISTA
        entradas = entradas[:LIMITE_LISTA]

        for widget in self.lista.winfo_children():
            widget.destroy()
        self._items.clear()

        if not entradas:
            texto = "Sin resultados para la búsqueda." if busqueda.strip() else \
                "Aún no hay transcripciones.\nAparecerán aquí al terminar cada una."
            ctk.CTkLabel(self.lista, text=texto, text_color=COLOR_TEXTO_SECUNDARIO, justify="center").grid(
                row=0, column=0, pady=40)
        for fila, entrada in enumerate(entradas):
            self._crear_item(fila, entrada)

        conteo = f"{len(entradas)}{'+' if hay_mas else ''} transcripcion{'es' if len(entradas) != 1 else ''}"
        if hay_mas:
            conteo += " · afina la búsqueda para ver más"
        self.label_conteo.configure(text=conteo)

        # Mantener la selección si sigue en la lista; si no, limpiar el detalle
        if self.seleccion in self._items:
            self._seleccionar(self.seleccion)
        else:
            self._mostrar_detalle(None)

    def _crear_item(self, fila: int, entrada: EntradaHistorial):
        item = ctk.CTkFrame(self.lista, fg_color=COLOR_ITEM, corner_radius=8, cursor="hand2")
        item.grid(row=fila, column=0, pady=3, sticky="ew")
        item.grid_columnconfigure(0, weight=1)

        titulo = ctk.CTkLabel(item, text=entrada.titulo, font=ctk.CTkFont(size=14, weight="bold"),
                              anchor="w", justify="left", wraplength=300)
        titulo.grid(row=0, column=0, padx=12, pady=(8, 0), sticky="w")

        detalle = f"{entrada.archivo_nombre}\n{formatear_fecha(entrada.creado_en)} · " \
                  f"{formatear_duracion(entrada.duracion_segundos)}"
        insignias = [n for n, tiene in (("Resumen", entrada.tiene_resumen), ("Minuta", entrada.tiene_minuta)) if tiene]
        if insignias:
            detalle += " · ✓ " + " ✓ ".join(insignias)
        sub = ctk.CTkLabel(item, text=detalle, text_color=COLOR_TEXTO_SECUNDARIO, font=ctk.CTkFont(size=12),
                           anchor="w", justify="left", wraplength=300)
        sub.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        for widget in (item, titulo, sub):
            widget.bind("<Button-1>", lambda e, i=entrada.id: self._seleccionar(i))
            widget.bind("<Double-Button-1>", lambda e, i=entrada.id: self._abrir_en_principal(i))
        item.bind("<Configure>", lambda e, t=titulo, s=sub: (t.configure(wraplength=max(e.width - 30, 120)),
                                                             s.configure(wraplength=max(e.width - 30, 120))))
        self._items[entrada.id] = item

    def _seleccionar(self, id_: int):
        self.seleccion = id_
        for i, item in self._items.items():
            item.configure(fg_color=COLOR_ITEM_SELECCIONADO if i == id_ else COLOR_ITEM)
        self._mostrar_detalle(self.historial.obtener(id_))

    # ------------------------------------------------------------ Detalle

    def _mostrar_detalle(self, entrada: Optional[EntradaHistorial]):
        self.entrada = entrada
        estado = "normal" if entrada else "disabled"
        self.entry_titulo.configure(state="normal")
        self.entry_titulo.delete(0, "end")
        for widget in (self.entry_titulo, self.btn_titulo, self.btn_abrir, self.btn_eliminar, self.selector_vista):
            widget.configure(state=estado)

        if entrada is None:
            self.seleccion = None
            self.label_meta.configure(text="Selecciona una transcripción para ver su detalle.")
            self._escribir_vista("")
            return

        self.entry_titulo.insert(0, entrada.titulo)
        meta = [
            f"📄 {entrada.archivo_nombre}" + ("" if entrada.archivo_existe else "  (el archivo ya no existe)"),
            f"🗓 {formatear_fecha(entrada.creado_en)} · ⏱ {formatear_duracion(entrada.duracion_segundos)}"
            f" · 🌐 {entrada.idioma or '—'} · Whisper {entrada.modelo_whisper or '—'}",
        ]
        modelos = [f"{n}: {m}" for n, m in (("Resumen", entrada.resumen_modelo), ("Minuta", entrada.minuta_modelo)) if m]
        if modelos:
            meta.append("🤖 " + " · ".join(modelos))
        self.label_meta.configure(text="\n".join(meta))
        self._mostrar_vista()

    def _mostrar_vista(self):
        if not self.entrada:
            return
        campo = VISTAS[self.selector_vista.get()]
        if campo == "texto":
            contenido = "\n".join(s["texto"] for s in self.entrada.segmentos) or self.entrada.texto
            self._escribir_vista(contenido)
        else:
            contenido = getattr(self.entrada, campo)
            if contenido:
                self._escribir_vista(contenido, markdown=True)
            else:
                nombre = self.selector_vista.get().lower()
                self._escribir_vista(f"Esta transcripción aún no tiene {nombre}.\n\n"
                                     f"Ábrela en la ventana principal para generarlo.", secundario=True)

    def _escribir_vista(self, contenido: str, markdown: bool = False, secundario: bool = False):
        self.text_vista.configure(state="normal",
                                  text_color=COLOR_TEXTO_SECUNDARIO if secundario else ("gray10", "gray90"))
        self.text_vista.delete("1.0", "end")
        if markdown:
            self.app._insertar_markdown(self.text_vista, contenido)
        else:
            self.text_vista.insert("end", contenido)
        self.text_vista.configure(state="disabled")
        self.text_vista.see("1.0")

    # ------------------------------------------------------------ Acciones

    def _guardar_titulo(self):
        if not self.entrada:
            return
        nuevo = self.entry_titulo.get().strip()
        if not nuevo:
            messagebox.showwarning("Historial", "El título no puede estar vacío.", parent=self.winfo_toplevel())
            return
        if nuevo != self.entrada.titulo:
            self.historial.renombrar(self.entrada.id, nuevo)
            if self.app.id_historial == self.entrada.id:
                self.app._mostrar_titulo(self.entrada.id, nuevo)
            self.refrescar()

    def _abrir_en_principal(self, id_: Optional[int] = None):
        id_ = id_ or (self.entrada.id if self.entrada else None)
        if id_ is not None:
            self.app.cargar_desde_historial(id_)

    def _eliminar(self):
        if not self.entrada:
            return
        if not messagebox.askyesno(
            "Eliminar del historial",
            f"¿Eliminar «{self.entrada.titulo}» del historial?\n\n"
            "Se borran la transcripción, el resumen y la minuta guardados en el historial. "
            "Los archivos exportados junto al audio no se tocan.",
            parent=self.winfo_toplevel(),
        ):
            return
        id_ = self.entrada.id
        self.historial.eliminar(id_)
        self.app.historial_eliminado(id_)
        self.seleccion = None
        self.refrescar()
