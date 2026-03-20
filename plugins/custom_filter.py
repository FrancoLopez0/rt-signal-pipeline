from plugin_interface import BaseProcessUI, BaseProcessDSP, BasePlugin
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QSlider
from PyQt6.QtCore import Qt
import numpy as np

class GainUI(BaseProcessUI):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        
        self.label = QLabel("Ganancia: 1.0")
        layout.addWidget(self.label)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 200) # 0.0 a 2.0
        self.slider.setValue(100)
        self.slider.valueChanged.connect(self.on_value_changed)
        layout.addWidget(self.slider)

    def on_value_changed(self, value):
        gain = value / 100.0
        self.label.setText(f"Ganancia: {gain:.2f}")
        # Emitir señal al orquestador para actualizar el DSP
        self.parameter_changed.emit("gain", gain)

class GainDSP(BaseProcessDSP):
    def __init__(self):
        self.gain = 1.0

    def process(self, data: np.ndarray) -> np.ndarray:
        return data * self.gain

    def update_parameter(self, name: str, value: object):
        if name == "gain":
            self.gain = float(value)

class Plugin(BasePlugin):
    def get_ui(self) -> BaseProcessUI:
        return GainUI()

    def get_dsp(self) -> BaseProcessDSP:
        return GainDSP()
