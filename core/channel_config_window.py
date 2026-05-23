from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QColorDialog, QScrollArea, QWidget, QCheckBox, QFrame
)
from PyQt6.QtGui import QColor
from PyQt6.QtCore import pyqtSignal, pyqtSlot

class ChannelConfigWindow(QDialog):
    # Emit signal when config is changed: (channel_configs_dict)
    config_changed = pyqtSignal(dict)
    
    DEFAULT_COLORS = [
        '#f0e68c', # Yellow / Khaki
        '#00d9ff', # Cyan
        '#00ff88', # Green
        '#ff5555', # Red
        '#ff00ff', # Magenta
        '#ffa500', # Orange
        '#a78bfa', # Purple
        '#ffffff'  # White
    ]

    def __init__(self, current_num_channels=0, current_configs=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Canales (Vista)")
        self.resize(300, 400)
        # Modeless
        self.setModal(False)
        
        self.channel_configs = current_configs if current_configs is not None else {}
        self.channel_widgets = []
        
        self._init_ui()
        self.update_channel_rows(current_num_channels)
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>Configuración de Canales Detectados</b>"))
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background-color: #0d1117; }")
        
        self.channels_container = QWidget()
        self.channels_container.setStyleSheet("background-color: #0d1117;")
        self.channels_layout = QVBoxLayout(self.channels_container)
        self.channels_layout.setContentsMargins(0, 0, 0, 0)
        self.channels_layout.addStretch()
        
        self.scroll.setWidget(self.channels_container)
        layout.addWidget(self.scroll)
        
        # Botones
        btn_layout = QHBoxLayout()
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.close)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _ensure_channel_config(self, ch_idx):
        if ch_idx not in self.channel_configs:
            color_hex = self.DEFAULT_COLORS[ch_idx % len(self.DEFAULT_COLORS)]
            self.channel_configs[ch_idx] = {
                'visible': True,
                'color': color_hex
            }
            return True
        return False

    @pyqtSlot(int)
    def update_channel_rows(self, num_channels):
        if num_channels <= len(self.channel_widgets):
            return

        # Remove stretch at the end
        if self.channels_layout.count() > 0:
            item = self.channels_layout.takeAt(self.channels_layout.count() - 1)
            if item.widget() is None: # it's a stretch
                del item

        for i in range(len(self.channel_widgets), num_channels):
            self._ensure_channel_config(i)
            conf = self.channel_configs[i]
            
            row = QFrame()
            row.setStyleSheet("QFrame { background-color: #21262d; border-radius: 4px; padding: 4px; }")
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(8, 4, 8, 4)
            
            chk = QCheckBox(f"Canal {i+1}")
            chk.setChecked(conf['visible'])
            chk.stateChanged.connect(lambda state, idx=i: self._on_visibility_changed(idx, state))
            r_layout.addWidget(chk)
            
            r_layout.addStretch()
            
            btn_color = QPushButton()
            btn_color.setFixedSize(24, 24)
            self._set_btn_color(btn_color, conf['color'])
            btn_color.clicked.connect(lambda checked, idx=i, btn=btn_color: self._on_color_clicked(idx, btn))
            r_layout.addWidget(btn_color)
            
            self.channels_layout.addWidget(row)
            self.channel_widgets.append(row)
            
        self.channels_layout.addStretch()
        self.config_changed.emit(self.channel_configs)

    def _on_visibility_changed(self, idx, state):
        self.channel_configs[idx]['visible'] = (state != 0)
        self.config_changed.emit(self.channel_configs)

    def _on_color_clicked(self, idx, btn):
        current_color = QColor(self.channel_configs[idx]['color'])
        color = QColorDialog.getColor(current_color, self, f"Seleccionar Color - Canal {idx+1}")
        if color.isValid():
            hex_color = color.name()
            self.channel_configs[idx]['color'] = hex_color
            self._set_btn_color(btn, hex_color)
            self.config_changed.emit(self.channel_configs)

    def _set_btn_color(self, btn, hex_color):
        btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #c9d1d9; border-radius: 12px;")
