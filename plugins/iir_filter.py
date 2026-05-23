from plugin_interface import BaseProcessUI, BaseProcessDSP, BasePlugin
from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
                             QSpinBox, QDoubleSpinBox, QPushButton, QGroupBox,
                             QFormLayout, QLineEdit)
from PyQt6.QtCore import pyqtSignal
import numpy as np
from scipy.signal import (butter, cheby1, cheby2, ellip, bessel,
                          sosfilt, sosfilt_zi)


# ─────────────────────────────────────────────────────────────────
#  UI  (Main Thread)
# ─────────────────────────────────────────────────────────────────

class IIRFilterUI(BaseProcessUI):
    """Panel de configuración del filtro IIR."""
    print_coeffs_requested = pyqtSignal()

    # Mapeo interno de familias y tipos
    FAMILIES = ["Butterworth", "Chebyshev I", "Chebyshev II", "Elliptic", "Bessel"]
    TYPES    = ["Lowpass", "Highpass", "Bandpass", "Bandstop"]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Filtro IIR Configurable</b>"))

        # ── Formulario principal ──
        form = QFormLayout()

        # Familia
        self.combo_family = QComboBox()
        self.combo_family.addItems(self.FAMILIES)
        self.combo_family.currentIndexChanged.connect(self._on_family_changed)
        form.addRow("Familia:", self.combo_family)

        # Tipo
        self.combo_type = QComboBox()
        self.combo_type.addItems(self.TYPES)
        self.combo_type.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Tipo:", self.combo_type)

        # Orden
        self.spin_order = QSpinBox()
        self.spin_order.setRange(1, 20)
        self.spin_order.setValue(4)
        form.addRow("Orden:", self.spin_order)

        # Frecuencia de corte 1 (siempre visible)
        self.spin_fc1 = QDoubleSpinBox()
        self.spin_fc1.setRange(1.0, 22050.0)
        self.spin_fc1.setValue(1000.0)
        self.spin_fc1.setSuffix(" Hz")
        self.spin_fc1.setDecimals(1)
        self.spin_fc1.valueChanged.connect(self._validate_fcs)
        self.lbl_fc1 = QLabel("Frecuencia de corte:")
        form.addRow(self.lbl_fc1, self.spin_fc1)

        # Frecuencia de corte 2 (solo BP / BS)
        self.spin_fc2 = QDoubleSpinBox()
        self.spin_fc2.setRange(1.0, 22050.0)
        self.spin_fc2.setValue(4000.0)
        self.spin_fc2.setSuffix(" Hz")
        self.spin_fc2.setDecimals(1)
        self.spin_fc2.valueChanged.connect(self._validate_fcs)
        self.lbl_fc2 = QLabel("Frecuencia superior:")
        form.addRow(self.lbl_fc2, self.spin_fc2)

        # Sample rate
        self.spin_sr = QSpinBox()
        self.spin_sr.setRange(0, 192000)
        self.spin_sr.setValue(44100)
        self.spin_sr.setSuffix(" Hz")
        self.spin_sr.valueChanged.connect(self._on_sr_changed)
        form.addRow("Sample Rate:", self.spin_sr)

        # Warning validation
        self.lbl_warning = QLabel("Warning: Frecuencia superior debe ser mayor a la inferior.")
        self.lbl_warning.setStyleSheet("color: red; font-weight: bold;")
        self.lbl_warning.setVisible(False)
        form.addRow(self.lbl_warning)

        layout.addLayout(form)

        # ── Parámetros específicos de familia ──
        self.group_ripple = QGroupBox("Parámetros de rizado")
        ripple_layout = QFormLayout(self.group_ripple)

        # Ripple (Chebyshev I, Elliptic)
        self.spin_rp = QDoubleSpinBox()
        self.spin_rp.setRange(0.01, 20.0)
        self.spin_rp.setValue(1.0)
        self.spin_rp.setSuffix(" dB")
        self.spin_rp.setDecimals(2)
        self.lbl_rp = QLabel("Ripple passband (rp):")
        ripple_layout.addRow(self.lbl_rp, self.spin_rp)

        # Stopband attenuation (Chebyshev II, Elliptic)
        self.spin_rs = QDoubleSpinBox()
        self.spin_rs.setRange(1.0, 120.0)
        self.spin_rs.setValue(40.0)
        self.spin_rs.setSuffix(" dB")
        self.spin_rs.setDecimals(1)
        self.lbl_rs = QLabel("Atenuación stopband (rs):")
        ripple_layout.addRow(self.lbl_rs, self.spin_rs)

        layout.addWidget(self.group_ripple)

        # ── Botones ──
        btn_layout = QHBoxLayout()

        self.btn_apply = QPushButton("Aplicar")
        self.btn_apply.clicked.connect(self._on_apply)
        btn_layout.addWidget(self.btn_apply)

        self.btn_print = QPushButton("Print Coefficients")
        self.btn_print.clicked.connect(self._on_print_coeffs)
        btn_layout.addWidget(self.btn_print)

        layout.addLayout(btn_layout)
        layout.addStretch()

        # Estado inicial de visibilidad
        self._on_family_changed(0)
        self._on_type_changed(0)

    # ── Slots internos ──

    def _on_family_changed(self, index):
        """Mostrar / ocultar parámetros según la familia seleccionada."""
        family = self.FAMILIES[index]

        needs_rp = family in ("Chebyshev I", "Elliptic")
        needs_rs = family in ("Chebyshev II", "Elliptic")

        self.lbl_rp.setVisible(needs_rp)
        self.spin_rp.setVisible(needs_rp)
        self.lbl_rs.setVisible(needs_rs)
        self.spin_rs.setVisible(needs_rs)

        # Ocultar todo el grupo si no se necesita nada
        self.group_ripple.setVisible(needs_rp or needs_rs)

    def _on_type_changed(self, index):
        """Mostrar / ocultar segunda frecuencia de corte según tipo."""
        ftype = self.TYPES[index]
        needs_two = ftype in ("Bandpass", "Bandstop")
        self.lbl_fc2.setVisible(needs_two)
        self.spin_fc2.setVisible(needs_two)

        # Ajustar etiqueta de fc1
        if needs_two:
            self.lbl_fc1.setText("Frecuencia inferior:")
        else:
            self.lbl_fc1.setText("Frecuencia de corte:")

        self._validate_fcs()

    def _on_sr_changed(self, sr):
        nyq = sr / 2.0
        self.spin_fc1.setMaximum(nyq)
        self.spin_fc2.setMaximum(nyq)
        self._validate_fcs()

    def _validate_fcs(self):
        ftype = self.TYPES[self.combo_type.currentIndex()]
        if ftype in ("Bandpass", "Bandstop"):
            if self.spin_fc2.value() <= self.spin_fc1.value():
                self.lbl_warning.setVisible(True)
            else:
                self.lbl_warning.setVisible(False)
        else:
            self.lbl_warning.setVisible(False)

    def _build_config(self) -> dict:
        """Construye el diccionario de configuración desde los widgets."""
        sr = self.spin_sr.value()

        ftype = self.TYPES[self.combo_type.currentIndex()]
        config = {
            "family":      self.FAMILIES[self.combo_family.currentIndex()],
            "ftype":       ftype,
            "order":       self.spin_order.value(),
            "fc1":         self.spin_fc1.value(),
            "sample_rate": sr,
            "rp":          self.spin_rp.value(),
            "rs":          self.spin_rs.value(),
        }
        if ftype in ("Bandpass", "Bandstop"):
            config["fc2"] = self.spin_fc2.value()
        return config

    def _on_apply(self):
        config = self._build_config()
        self.parameter_changed.emit("config", config)

    def _on_print_coeffs(self):
        self.print_coeffs_requested.emit()


# ─────────────────────────────────────────────────────────────────
#  DSP  (Worker Thread)
# ─────────────────────────────────────────────────────────────────

class IIRFilterDSP(BaseProcessDSP):
    """Aplica un filtro IIR diseñado con scipy.signal en streaming."""

    # Mapeo familia → función de diseño de scipy
    _DESIGN_FUNCS = {
        "Butterworth":  butter,
        "Chebyshev I":  cheby1,
        "Chebyshev II": cheby2,
        "Elliptic":     ellip,
        "Bessel":       bessel,
    }

    # Mapeo tipo legible → argumento btype de scipy
    _BTYPE_MAP = {
        "Lowpass":  "lowpass",
        "Highpass": "highpass",
        "Bandpass": "bandpass",
        "Bandstop": "bandstop",
    }

    def __init__(self):
        self.family = "Butterworth"
        self.ftype  = "Lowpass"
        self.order  = 4
        self.fc1    = 1000.0
        self.fc2    = 4000.0
        self.rp     = 1.0
        self.rs     = 40.0
        self.sample_rate = 44100

        self._filter_state = (None, None)

        self._calculate_coeffs()

    # ── Diseño del filtro ──

    def _calculate_coeffs(self):
        """Calcula los coeficientes en formato SOS y el estado inicial zi."""
        try:
            nyq = self.sample_rate / 2.0
            btype = self._BTYPE_MAP[self.ftype]

            # Normalizar frecuencias respecto a Nyquist
            if btype in ("bandpass", "bandstop"):
                Wn = [self.fc1 / nyq, self.fc2 / nyq]
                # Asegurar rango válido
                Wn = [max(1e-6, min(w, 1.0 - 1e-6)) for w in Wn]
                if Wn[0] >= Wn[1]:
                    Wn[1] = Wn[0] + 0.01
            else:
                Wn = self.fc1 / nyq
                Wn = max(1e-6, min(Wn, 1.0 - 1e-6))

            design_fn = self._DESIGN_FUNCS[self.family]

            # Construir argumentos según la familia
            if self.family == "Butterworth":
                sos = design_fn(self.order, Wn, btype=btype, output='sos')
            elif self.family == "Chebyshev I":
                sos = design_fn(self.order, self.rp, Wn, btype=btype, output='sos')
            elif self.family == "Chebyshev II":
                sos = design_fn(self.order, self.rs, Wn, btype=btype, output='sos')
            elif self.family == "Elliptic":
                sos = design_fn(self.order, self.rp, self.rs, Wn, btype=btype, output='sos')
            elif self.family == "Bessel":
                sos = design_fn(self.order, Wn, btype=btype, norm='phase', output='sos')

            # Estado inicial para sosfilt (preservar continuidad entre chunks)
            zi = sosfilt_zi(sos)
            
            # Swap atómico
            self._filter_state = (sos, zi)

            print(f"[IIR Filter] Filtro diseñado: {self.family} {self.ftype} "
                  f"orden={self.order}  Wn={Wn}")

        except Exception as e:
            print(f"[IIR Filter] Error al diseñar filtro: {e}")
            # Fallback: bypass equivalente (1 sección SOS)
            sos = np.array([[1.0, 0.0, 0.0, 1.0, 0.0, 0.0]])
            zi = sosfilt_zi(sos)
            self._filter_state = (sos, zi)

    # ── Interfaz del plugin ──

    def print_coeffs(self):
        """Imprime los coeficientes en formato SOS en la terminal."""
        sos, _ = self._filter_state
        if sos is None:
            print("[IIR Filter] Error: coeficientes no calculados")
            return
        print("=" * 60)
        print(f"  Filtro IIR: {self.family} | {self.ftype} | Orden {self.order}")
        print("=" * 60)
        print(f"\nSOS (Second-Order Sections) [{sos.shape[0]} secciones]:")
        print(repr(sos))
        print("=" * 60)

    def update_parameter(self, name: str, value: object):
        if name == "config":
            config = value
            needs_recalc = False

            if "family" in config and config["family"] != self.family:
                self.family = config["family"]
                needs_recalc = True
            if "ftype" in config and config["ftype"] != self.ftype:
                self.ftype = config["ftype"]
                needs_recalc = True
            if "order" in config and config["order"] != self.order:
                self.order = config["order"]
                needs_recalc = True
            if "fc1" in config and config["fc1"] != self.fc1:
                self.fc1 = config["fc1"]
                needs_recalc = True
            if "fc2" in config and config.get("fc2", self.fc2) != self.fc2:
                self.fc2 = config.get("fc2", self.fc2)
                needs_recalc = True
            if "sample_rate" in config and config["sample_rate"] != self.sample_rate:
                self.sample_rate = config["sample_rate"]
                needs_recalc = True
            if "rp" in config and config["rp"] != self.rp:
                self.rp = config["rp"]
                needs_recalc = True
            if "rs" in config and config["rs"] != self.rs:
                self.rs = config["rs"]
                needs_recalc = True

            if needs_recalc:
                self._calculate_coeffs()

    def process(self, data: np.ndarray) -> np.ndarray:
        if data.size == 0:
            return data
        
        # Lectura atómica del estado actual
        sos, zi = self._filter_state
        
        if sos is None:
            return data
            
        try:
            # Validar dimensión del estado por si hubo corrupción en cambios concurrentes
            expected_zi_shape = (sos.shape[0], 2)
            if zi is None or zi.shape != expected_zi_shape:
                zi = sosfilt_zi(sos)
                
            filtered, new_zi = sosfilt(sos, data, zi=zi)
            
            # Guardar el nuevo estado (el SOS sigue siendo el mismo)
            self._filter_state = (sos, new_zi)
            
            return filtered
        except Exception as e:
            print(f"[IIR Filter] Error en process: {e}")
            return data


# ─────────────────────────────────────────────────────────────────
#  Plugin Factory
# ─────────────────────────────────────────────────────────────────

class Plugin(BasePlugin):
    def get_ui(self) -> BaseProcessUI:
        return IIRFilterUI()

    def get_dsp(self) -> BaseProcessDSP:
        return IIRFilterDSP()
