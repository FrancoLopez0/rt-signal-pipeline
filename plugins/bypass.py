from plugin_interface import BaseProcessUI, BaseProcessDSP, BasePlugin
from PyQt6.QtWidgets import QVBoxLayout, QLabel
import numpy as np

class BypassUI(BaseProcessUI):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Bypass: Señal sin procesamiento"))

class BypassDSP(BaseProcessDSP):
    def process(self, data: np.ndarray) -> np.ndarray:
        # No modifica la señal
        return data

    def update_parameter(self, name: str, value: object):
        pass

class Plugin(BasePlugin):
    def get_ui(self) -> BaseProcessUI:
        return BypassUI()

    def get_dsp(self) -> BaseProcessDSP:
        return BypassDSP()
