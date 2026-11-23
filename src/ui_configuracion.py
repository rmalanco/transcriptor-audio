"""Vista «Configuración» de la ventana: los valores por defecto de la transcripción y de la salida."""

import tkinter as tk
from dataclasses import dataclass
from typing import Optional

import customtkinter as ctk

from src.configuracion import DISPOSITIVOS, FORMATOS, MODELOS_WHISPER, TIPOS_COMPUTO, ResultadoGuardado
from src.idiomas import codigo_de_idioma, nombre_de_idioma, opciones_de_idioma

COLOR_TEXTO_SECUNDARIO = ("gray40", "gray65")
COLOR_ERROR = ("#C0392B", "#E06C5F")
COLOR_AVISO = ("#8A6D00", "#E0C36C")


@dataclass(frozen=True)
class Campo:
    seccion: str
    clave: str
    etiqueta: str
    control: str          # "lista" | "lista_editable" | "botones" | "interruptor" | "texto"
    grupo: str            # "Transcripción" | "Salida" | "Historial"
    avanzado: bool = False
    opciones: tuple = ()  # para "lista" y "botones"
    nota: str = ""        # texto bajo el campo (p. ej. «Se aplica al reiniciar la app.»)


CAMPOS = (
    Campo("modelo", "nombre", "Modelo de Whisper", "lista", "Transcripción", opciones=MODELOS_WHISPER),
    Campo("transcripcion", "idioma", "Idioma", "lista_editable", "Transcripción"),
    Campo("modelo", "dispositivo", "Dispositivo", "lista", "Transcripción", opciones=DISPOSITIVOS),
    Campo("modelo", "compute_type", "Precisión", "lista", "Transcripción", opciones=TIPOS_COMPUTO),
    Campo("transcripcion", "beam_size", "Haz de búsqueda", "texto", "Transcripción", avanzado=True),
    Campo("transcripcion", "best_of", "Candidatos", "texto", "Transcripción", avanzado=True),
    Campo("transcripcion", "temperature", "Temperatura de Whisper", "texto", "Transcripción", avanzado=True),
    Campo("transcripcion", "condition_on_previous_text", "Usar el texto anterior como contexto", "interruptor",
          "Transcripción", avanzado=True),
    Campo("transcripcion", "compression_ratio_threshold", "Umbral de compresión", "texto", "Transcripción",
          avanzado=True),
    Campo("transcripcion", "logprob_threshold", "Umbral de probabilidad", "texto", "Transcripción", avanzado=True),
    Campo("transcripcion", "no_speech_threshold", "Umbral de silencio", "texto", "Transcripción", avanzado=True),
    Campo("salida", "formato", "Formato de salida", "botones", "Salida", opciones=FORMATOS),
    Campo("salida", "incluir_timestamps", "Incluir marcas de tiempo", "interruptor", "Salida"),
    Campo("salida", "palabra_por_palabra", "Marcas por palabra", "interruptor", "Salida"),
    Campo("historial", "ruta", "Archivo del historial (relativo a la carpeta del proyecto)", "texto", "Historial",
          nota="Se aplica al reiniciar la app."),
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
        self.grid_rowconfigure(1, weight=1)
        self._avanzado_abierto = False
        self._construir()
        self.refrescar()

    # ------------------------------------------------------------ Construcción

    def _construir(self):
        # Recuadro de avisos de las preferencias: se muestra en `refrescar` solo si hay avisos
        self.marco_avisos = ctk.CTkFrame(self, corner_radius=8)
        self.marco_avisos.grid(row=0, column=0, padx=20, pady=(8, 0), sticky="ew")
        self.marco_avisos.grid_columnconfigure(0, weight=1)
        self.label_avisos = ctk.CTkLabel(self.marco_avisos, text="", anchor="w", justify="left", wraplength=640,
                                         text_color=COLOR_AVISO)
        self.label_avisos.grid(row=0, column=0, padx=12, pady=8, sticky="ew")
        self.marco_avisos.grid_remove()

        formulario = ctk.CTkScrollableFrame(self, fg_color="transparent")
        formulario.grid(row=1, column=0, padx=20, pady=(8, 0), sticky="nsew")
        formulario.grid_columnconfigure(0, weight=1)

        fila = 0
        grupo_actual = None
        marco_avanzado = None
        fila_avanzada = 0
        for campo in CAMPOS:
            if campo.grupo != grupo_actual:
                grupo_actual = campo.grupo
                ctk.CTkLabel(formulario, text=grupo_actual, font=ctk.CTkFont(size=15, weight="bold")).grid(
                    row=fila, column=0, padx=8, pady=(12, 0), sticky="w")
                fila += 1
            if campo.avanzado:
                if marco_avanzado is None:  # los campos avanzados van juntos, plegados, tras su grupo
                    self.btn_avanzado = ctk.CTkButton(formulario, text="▸ Avanzado", width=140,
                                                      fg_color="transparent", border_width=1,
                                                      text_color=COLOR_TEXTO_SECUNDARIO,
                                                      command=self._alternar_avanzado)
                    self.btn_avanzado.grid(row=fila, column=0, padx=8, pady=(6, 0), sticky="w")
                    fila += 1
                    marco_avanzado = ctk.CTkFrame(formulario, fg_color="transparent")
                    marco_avanzado.grid_columnconfigure(0, weight=1)
                    marco_avanzado.grid(row=fila, column=0, sticky="ew")
                    marco_avanzado.grid_remove()
                    self.marco_avanzado = marco_avanzado
                    fila += 1
                self._construir_campo(marco_avanzado, campo, fila_avanzada)
                fila_avanzada += 1
            else:
                self._construir_campo(formulario, campo, fila)
                fila += 1

        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.grid(row=2, column=0, padx=20, pady=(8, 12), sticky="ew")
        pie.grid_columnconfigure(2, weight=1)
        self.btn_guardar = ctk.CTkButton(pie, text="Guardar", width=120, command=self._guardar)
        self.btn_guardar.grid(row=0, column=0, sticky="w")
        self.btn_restablecer = ctk.CTkButton(pie, text="Restablecer valores del proyecto", width=220,
                                             fg_color="transparent", border_width=1, command=self._restablecer)
        self.btn_restablecer.grid(row=0, column=1, padx=(8, 0), sticky="w")
        self.label_pie = ctk.CTkLabel(pie, text="", anchor="w", text_color=COLOR_TEXTO_SECUNDARIO)
        self.label_pie.grid(row=0, column=2, padx=(12, 0), sticky="ew")

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
        fila_error = 3
        if campo.nota:
            ctk.CTkLabel(bloque, text=campo.nota, font=ctk.CTkFont(size=11),
                         text_color=COLOR_TEXTO_SECUNDARIO).grid(row=3, column=0, sticky="w")
            fila_error = 4
        error = ctk.CTkLabel(bloque, text="", font=ctk.CTkFont(size=12), text_color=COLOR_ERROR, anchor="w",
                             wraplength=520, justify="left")
        error.grid(row=fila_error, column=0, sticky="w")

        self._variables[clave] = variable
        self._widgets[clave] = widget
        self._errores[clave] = error

    @staticmethod
    def _crear_control(padre, campo: Campo, variable: tk.StringVar):
        if campo.control == "lista":
            return ctk.CTkOptionMenu(padre, values=list(campo.opciones), variable=variable, width=260)
        if campo.control == "lista_editable":
            return ctk.CTkComboBox(padre, values=[], variable=variable, width=260)
        if campo.control == "texto":
            return ctk.CTkEntry(padre, textvariable=variable, width=260)
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
        self._pintar_avisos()

    def _pintar_avisos(self):
        avisos = self.app.avisos_preferencias
        if avisos:
            self.label_avisos.configure(text="\n".join(avisos))
            self.marco_avisos.grid()
        else:
            self.marco_avisos.grid_remove()

    def _alternar_avanzado(self):
        self._desplegar_avanzado(not self._avanzado_abierto)

    def _desplegar_avanzado(self, abierto: bool):
        self._avanzado_abierto = abierto
        if abierto:
            self.marco_avanzado.grid()
            self.btn_avanzado.configure(text="▾ Avanzado")
        else:
            self.marco_avanzado.grid_remove()
            self.btn_avanzado.configure(text="▸ Avanzado")

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

    def _restablecer(self):
        resultado = self.app.restablecer_configuracion()
        if resultado is None:  # se respondió «No»: nada cambia
            return
        if resultado.efectiva is not None:
            self.refrescar()  # la configuración del YAML ya está en la ventana; el pie se rellena abajo
        self._pintar(resultado)

    def _pintar(self, resultado: ResultadoGuardado):
        for clave, etiqueta in self._errores.items():
            etiqueta.configure(text=resultado.errores.get(clave, ""))
        if any((c.seccion, c.clave) in resultado.errores for c in CAMPOS if c.avanzado):
            self._desplegar_avanzado(True)  # un error dentro de «Avanzado» se ve sin desplegarlo a mano
        self.label_pie.configure(text=resultado.mensaje)

