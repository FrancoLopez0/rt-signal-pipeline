from plugin_interface import BaseProcessUI, BaseProcessDSP, BasePlugin
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QLineEdit
from PyQt6.QtCore import Qt, pyqtSignal
import numpy as np
from scipy.signal import firwin, lfilter, lfilter_zi


class LowPassFIRUI(BaseProcessUI):
    print_coeffs_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Filtro FIR Pasa-Bajos"))

        self.cutoff_label = QLabel("Frecuencia de corte: 1000 Hz")
        layout.addWidget(self.cutoff_label)

        self.cutoff_slider = QSlider(Qt.Orientation.Horizontal)
        self.cutoff_slider.setRange(1, 20000)
        self.cutoff_slider.setValue(1000)
        self.cutoff_slider.valueChanged.connect(self.on_cutoff_changed)
        layout.addWidget(self.cutoff_slider)

        self.order_label = QLabel("Orden del filtro: 64")
        layout.addWidget(self.order_label)

        self.order_slider = QSlider(Qt.Orientation.Horizontal)
        self.order_slider.setRange(1, 256)
        self.order_slider.setValue(64)
        self.order_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.order_slider.setTickInterval(16)
        self.order_slider.valueChanged.connect(self.on_order_changed)
        layout.addWidget(self.order_slider)

        self.coeffs_label = QLabel("Coeficientes: 65")
        layout.addWidget(self.coeffs_label)

        rate_layout = QHBoxLayout()
        rate_layout.addWidget(QLabel("Sample Rate:"))
        self.rate_input = QLineEdit("44100")
        self.rate_input.setMaximumWidth(100)
        self.rate_input.returnPressed.connect(self.on_rate_changed)
        rate_layout.addWidget(self.rate_input)
        rate_layout.addStretch()
        layout.addLayout(rate_layout)

        self.apply_button = QPushButton("Aplicar")
        self.apply_button.clicked.connect(self.on_apply_clicked)
        layout.addWidget(self.apply_button)

        self.print_coeffs_button = QPushButton("Print C Coeffs")
        self.print_coeffs_button.clicked.connect(self.on_print_coeffs_clicked)
        layout.addWidget(self.print_coeffs_button)

        self.config = {
            "cutoff": 1000,
            "order": 64,
            "sample_rate": 44100
        }

    def on_cutoff_changed(self, value):
        self.cutoff_label.setText(f"Frecuencia de corte: {value} Hz")
        self.config["cutoff"] = value

    def on_order_changed(self, value):
        if value % 2 != 0:
            value += 1
            self.order_slider.blockSignals(True)
            self.order_slider.setValue(value)
            self.order_slider.blockSignals(False)
        self.order_label.setText(f"Orden del filtro: {value}")
        self.coeffs_label.setText(f"Coeficientes: {value + 1}")
        self.config["order"] = value

    def on_rate_changed(self):
        try:
            rate = int(self.rate_input.text())
            rate = max(1000, min(192000, rate))
            self.rate_input.setText(str(rate))
            self.config["sample_rate"] = rate
        except ValueError:
            self.rate_input.setText(str(self.config["sample_rate"]))

    def on_apply_clicked(self):
        self.parameter_changed.emit("config", self.config.copy())

    def on_print_coeffs_clicked(self):
        self.print_coeffs_requested.emit()


class LowPassFIRDSP(BaseProcessDSP):
    def __init__(self):
        self.cutoff = 1000
        self.order = 64
        self.sample_rate = 44100
        self.coeffs = None
        self.zi = None
        self._calculate_coeffs()

    def _calculate_coeffs(self):
        numtaps = self.order + 1
        fc_norm = self.cutoff / (self.sample_rate / 2)
        self.coeffs = firwin(numtaps, fc_norm, window='hamming')
        self.zi = lfilter_zi(self.coeffs, 1.0) * 0.0

    def print_coeffs(self):
        """Print coefficients in C float array format for copying to embedded code."""
        if self.coeffs is None:
            print("Error: coefficients not calculated")
            return
        print("static const float coeffs[] = {")
        for i, c in enumerate(self.coeffs):
            if i % 6 == 0:
                print("    ", end="")
            print(f"{c:.15f}f", end="")
            if i < len(self.coeffs) - 1:
                print(", ", end="")
            if i % 6 == 5:
                print()
        print("\n};")

    def update_parameter(self, name: str, value: object):
        if name == "config":
            config = value
            needs_recalc = False
            if "cutoff" in config and config["cutoff"] != self.cutoff:
                self.cutoff = config["cutoff"]
                needs_recalc = True
            if "order" in config and config["order"] != self.order:
                self.order = config["order"]
                needs_recalc = True
            if "sample_rate" in config and config["sample_rate"] != self.sample_rate:
                self.sample_rate = config["sample_rate"]
                needs_recalc = True
            if needs_recalc:
                self._calculate_coeffs()

    def process(self, data: np.ndarray) -> np.ndarray:
        if data.size == 0:
            return data
        if self.coeffs is None:
            self._calculate_coeffs()
        filtered, self.zi = lfilter(self.coeffs, 1.0, data, zi=self.zi)
        return filtered


class Plugin(BasePlugin):
    def get_ui(self) -> BaseProcessUI:
        return LowPassFIRUI()

    def get_dsp(self) -> BaseProcessDSP:
        return LowPassFIRDSP()
