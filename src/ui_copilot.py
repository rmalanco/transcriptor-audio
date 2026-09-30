"""Diálogo de inicio de sesión en GitHub Copilot (device flow de OAuth)."""

import logging
import threading
import webbrowser
from typing import Callable, Optional

import customtkinter as ctk

from src import copilot

log = logging.getLogger("transcriptor.ui")

COLOR_TEXTO_SECUNDARIO = ("gray40", "gray65")


class DialogoLoginCopilot(ctk.CTkToplevel):
    """Muestra el código de dispositivo, abre GitHub y espera la autorización en segundo plano.

    `al_terminar` se llama en el hilo de la interfaz con True si se inició sesión.
    """

    def __init__(self, master, enterprise_url: Optional[str], al_terminar: Callable[[bool], None]):
        super().__init__(master)
        self.title("Iniciar sesión en GitHub Copilot")
        self.resizable(False, False)
        self.transient(master)
        self._al_terminar = al_terminar
        self._enterprise_url = enterprise_url
        self._cancelar = threading.Event()
        self._codigo: Optional[copilot.CodigoDispositivo] = None
        self._terminado = False

        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Iniciar sesión en GitHub Copilot",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, padx=24, pady=(20, 6))
        ctk.CTkLabel(self, justify="left", wraplength=380, text=(
            "Los resúmenes y minutas se generan con los modelos de tu cuenta de GitHub Copilot.\n\n"
            "1. Pulsa «Copiar código y abrir GitHub».\n"
            "2. Pega el código en la página y autoriza el acceso.\n"
            "3. Vuelve aquí: la sesión se detecta sola."
        )).grid(row=1, column=0, padx=24, pady=6, sticky="w")

        self.label_codigo = ctk.CTkLabel(self, text="· · · ·", font=ctk.CTkFont(family="monospace", size=28, weight="bold"))
        self.label_codigo.grid(row=2, column=0, padx=24, pady=10)

        self.btn_abrir = ctk.CTkButton(self, text="Copiar código y abrir GitHub", state="disabled",
                                       command=self._abrir_github)
        self.btn_abrir.grid(row=3, column=0, padx=24, pady=4, sticky="ew")
        ctk.CTkButton(self, text="Cancelar", fg_color="transparent", border_width=1,
                      text_color=("gray10", "gray90"), command=self._cerrar).grid(row=4, column=0, padx=24, pady=4, sticky="ew")

        self.label_estado = ctk.CTkLabel(self, text="Solicitando código a GitHub…", text_color=COLOR_TEXTO_SECUNDARIO,
                                         wraplength=380)
        self.label_estado.grid(row=5, column=0, padx=24, pady=(6, 18))

        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.after(100, self.grab_set)  # modal; se retrasa porque la ventana aún no es visible
        threading.Thread(target=self._iniciar, daemon=True, name="login-copilot").start()

    def _en_ui(self, funcion, *args):
        try:
            self.after(0, funcion, *args)
        except Exception:
            pass  # el diálogo ya se cerró

    def _iniciar(self):
        try:
            self._codigo = copilot.iniciar_login(self._enterprise_url)
            self._en_ui(self._mostrar_codigo)
            copilot.esperar_login(self._codigo, self._cancelar)
            self._en_ui(self._terminar, True)
        except InterruptedError:
            pass
        except copilot.ErrorCopilot as e:
            log.error("Inicio de sesión en GitHub Copilot fallido: %s", e)
            self._en_ui(lambda: self.label_estado.configure(text=str(e), text_color=("#C0392B", "#E74C3C")))

    def _mostrar_codigo(self):
        self.label_codigo.configure(text=self._codigo.user_code)
        self.btn_abrir.configure(state="normal")
        self.label_estado.configure(text=f"Esperando autorización en {self._codigo.verification_uri}…")

    def _abrir_github(self):
        self.clipboard_clear()
        self.clipboard_append(self._codigo.user_code)
        webbrowser.open(self._codigo.verification_uri)
        self.label_estado.configure(text="Código copiado. Pégalo en GitHub y autoriza; esta ventana se cerrará sola.")

    def _terminar(self, ok: bool):
        if self._terminado:
            return
        self._terminado = True
        self._cancelar.set()
        self.grab_release()
        self.destroy()
        self._al_terminar(ok)

    def _cerrar(self):
        self._terminar(False)
