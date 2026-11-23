"""Vista «Configuración» de la ventana: los valores por defecto de la transcripción y de la salida."""

import tkinter as tk
from dataclasses import dataclass
from typing import Optional

import customtkinter as ctk

from src.configuracion import DISPOSITIVOS, FORMATOS, MODELOS_WHISPER, TIPOS_COMPUTO, ResultadoGuardado
from src.idiomas import codigo_de_idioma, nombre_de_idioma, opciones_de_idioma

COLOR_TEXTO_SECUNDARIO = ("gray40", "gray65")
COLOR_ERROR = ("#C0392B", "#E06C5F")


@dataclass(frozen=True)
class Campo:
    seccion: str
    clave: str
    etiqueta: str
    control: str          # "lista" | "lista_editable" | "botones" | "interruptor"
    grupo: str            # "Transcripción" | "Salida"
    avanzado: bool = False
    opciones: tuple = ()  # para "lista" y "botones"


CAMPOS = (
    Campo("modelo", "nombre", "Modelo de Whisper", "lista", "Transcripción", opciones=MODELOS_WHISPER),
    Campo("transcripcion", "idioma", "Idioma", "lista_editable", "Transcripción"),
    Campo("modelo", "dispositivo", "Dispositivo", "lista", "Transcripción", opciones=DISPOSITIVOS),
    Campo("modelo", "compute_type", "Precisión", "lista", "Transcripción", opciones=TIPOS_COMPUTO),
    Campo("salida", "formato", "Formato de salida", "botones", "Salida", opciones=FORMATOS),
    Campo("salida", "incluir_timestamps", "Incluir marcas de tiempo", "interruptor", "Salida"),
    Campo("salida", "palabra_por_palabra", "Marcas por palabra", "interruptor", "Salida"),
)


def motivo_para_no_guardar(transcribiendo: bool, generando: bool) -> Optional[str]:
    """Por qué no se puede guardar ahora desde la vista, o None si se puede."""
    if transcribiendo or generando:
        return "Espera a que termine el proceso en curso."
    return None


class PanelConfiguracion(ctk.CTkFrame):
    """Formulario con los campos de `CAMPOS`, un botón «Guardar» y una línea de estado (el pie)."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._variables: dict = {}   # (sección, clave) → variable Tk del campo
        self._widgets: dict = {}     # (sección, clave) → control
        self._errores: dict = {}     # (sección, clave) → etiqueta del error bajo el campo

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._construir()
        self.refrescar()

    # ------------------------------------------------------------ Construcción

    def _construir(self):
        formulario = ctk.CTkScrollableFrame(self, fg_color="transparent")
        formulario.grid(row=0, column=0, padx=20, pady=(8, 0), sticky="nsew")
        formulario.grid_columnconfigure(0, weight=1)

        fila = 0
        grupo_actual = None
        for campo in CAMPOS:
            if campo.grupo != grupo_actual:
                grupo_actual = campo.grupo
                ctk.CTkLabel(formulario, text=grupo_actual, font=ctk.CTkFont(size=15, weight="bold")).grid(
                    row=fila, column=0, padx=8, pady=(12, 0), sticky="w")
                fila += 1
            self._construir_campo(formulario, campo, fila)
            fila += 1

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid(row=1, column=0, padx=20, pady=(8, 12), sticky="ew")
        pie.grid_columnconfigure(1, weight=1)
        self.btn_guardar = ctk.CTkButton(pie, text="Guardar", width=120, command=self._guardar)
        self.btn_guardar.grid(row=0, column=0, sticky="w")
        self.label_pie = ctk.CTkLabel(pie, text="", anchor="w", text_color=COLOR_TEXTO_SECUNDARIO)
        self.label_pie.grid(row=0, column=1, padx=(12, 0), sticky="ew")

    def _construir_campo(self, padre, campo: Campo, fila: int):
        clave = (campo.seccion, campo.clave)
        bloque = ctk.CTkFrame(padre, fg_color="transparent")
        bloque.grid(row=fila, column=0, padx=8, pady=6, sticky="ew")
        bloque.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(bloque, text=campo.etiqueta, font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w")
        if campo.control == "interruptor":
            variable = tk.BooleanVar(value=False)
            widget = ctk.CTkSwitch(bloque, text="", variable=variable)
        else:
            variable = tk.StringVar(value="")
            widget = self._crear_control(bloque, campo, variable)
        widget.grid(row=1, column=0, sticky="w", pady=(4, 0))
        ctk.CTkLabel(bloque, text=f"{campo.seccion}.{campo.clave}", font=ctk.CTkFont(size=11),
                     text_color=COLOR_TEXTO_SECUNDARIO).grid(row=2, column=0, sticky="w")
        error = ctk.CTkLabel(bloque, text="", font=ctk.CTkFont(size=12), text_color=COLOR_ERROR, anchor="w",
                             wraplength=520, justify="left")
        error.grid(row=3, column=0, sticky="w")

        self._variables[clave] = variable
        self._widgets[clave] = widget
        self._errores[clave] = error

    @staticmethod
    def _crear_control(padre, campo: Campo, variable: tk.StringVar):
        if campo.control == "lista":
            return ctk.CTkOptionMenu(padre, values=list(campo.opciones), variable=variable, width=260)
        if campo.control == "lista_editable":
            return ctk.CTkComboBox(padre, values=[], variable=variable, width=260)
        return ctk.CTkSegmentedButton(padre, values=list(campo.opciones), variable=variable)

    # ------------------------------------------------------------ Datos

    def refrescar(self):
        """Pone en cada campo el valor de la configuración de la ventana (así descarta lo no guardado) y limpia
        los errores y el pie."""
        for campo in CAMPOS:
            clave = (campo.seccion, campo.clave)
            valor = self.app.configuracion[campo.seccion][campo.clave]
            if campo.control == "lista_editable":
                self._widgets[clave].configure(values=opciones_de_idioma(valor))
                self._variables[clave].set(nombre_de_idioma(valor))
            else:
                self._variables[clave].set(valor)
        for etiqueta in self._errores.values():
            etiqueta.configure(text="")
        self.label_pie.configure(text="")

    def _valores_formulario(self) -> dict:
        valores = {}
        for campo in CAMPOS:
            clave = (campo.seccion, campo.clave)
            valor = self._variables[clave].get()
            valores[clave] = codigo_de_idioma(valor) if campo.control == "lista_editable" else valor
        return valores

    def _guardar(self):
        resultado = self.app.guardar_configuracion(self._valores_formulario())
        if resultado.efectiva is not None:
            self.refrescar()  # la configuración nueva ya está en la ventana; el pie se rellena abajo
        self._pintar(resultado)

    def _pintar(self, resultado: ResultadoGuardado):
        for clave, etiqueta in self._errores.items():
            etiqueta.configure(text=resultado.errores.get(clave, ""))
        self.label_pie.configure(text=resultado.mensaje)

