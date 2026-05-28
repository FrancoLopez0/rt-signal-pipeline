import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QLineEdit, QSpinBox, QPushButton, QFrame
)
from PyQt6.QtCore import pyqtSignal

class RawFormatDialog(QDialog):
    # Emit signal when config is applied: (data_type, hex_separator, num_channels)
    config_applied = pyqtSignal(str, str, int)

    def __init__(self, current_data_type="int16", current_hex_sep="", current_num_channels=1, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Formato Serial RAW")
        self.resize(300, 200)
        
        self._init_ui(current_data_type, current_hex_sep, current_num_channels)
        
    def _init_ui(self, data_type, hex_sep, num_channels):
        layout = QVBoxLayout(self)
        
        frame_format = QFrame()
        frame_format.setStyleSheet("QFrame { background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 8px; }")
        format_layout = QVBoxLayout(frame_format)
        
        format_layout.addWidget(QLabel("<b>Formato de Datos</b>"))
        
        # Data type
        dt_layout = QHBoxLayout()
        dt_layout.addWidget(QLabel("Tipo de Dato:"))
        self.combo_dt = QComboBox()
        self.combo_dt.addItems(["int8", "uint8", "int16", "uint16", "int32", "uint32", "float32", "float64"])
        self.combo_dt.setCurrentText(data_type)
        dt_layout.addWidget(self.combo_dt)
        format_layout.addLayout(dt_layout)
        
        # Hex separator
        hex_layout = QHBoxLayout()
        hex_layout.addWidget(QLabel("Separador Hex (opcional):"))
        self.txt_hex = QLineEdit(hex_sep)
        self.txt_hex.setPlaceholderText("Ej: ' ' para 'FF 0A'")
        hex_layout.addWidget(self.txt_hex)
        format_layout.addLayout(hex_layout)
        
        # Num channels
        ch_layout = QHBoxLayout()
        ch_layout.addWidget(QLabel("Número de Canales:"))
        self.spin_ch = QSpinBox()
        self.spin_ch.setRange(1, 16)
        self.spin_ch.setValue(num_channels)
        ch_layout.addWidget(self.spin_ch)
        format_layout.addLayout(ch_layout)
        
        layout.addWidget(frame_format)
        
        # Botones
        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("Aplicar")
        btn_apply.clicked.connect(self._on_apply)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_apply)
        layout.addLayout(btn_layout)

    def _on_apply(self):
        dt = self.combo_dt.currentText()
        hex_sep = self.txt_hex.text()
        ch = self.spin_ch.value()
        
        self.config_applied.emit(dt, hex_sep, ch)
        self.accept()
