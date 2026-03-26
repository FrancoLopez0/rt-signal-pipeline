import os
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QFileDialog, QLabel, QFrame, QSplitter, 
                             QMessageBox, QComboBox, QCheckBox, QSlider, QTabWidget,
                             QSpinBox, QDoubleSpinBox)
from PyQt6.QtCore import Qt, pyqtSlot
from core.orchestrator import Orchestrator

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RT Signal Pipeline - PyQt DSP")
        self.resize(1200, 900)
        
        # El Orquestador (Presenter)
        self.orchestrator = Orchestrator()
        
        # Buffers para visualización
        self.buffer_size = 8192 
        self.display_size = 1024 
        self.input_buffer = np.zeros(self.buffer_size)
        self.output_buffer = np.zeros(self.buffer_size)
        
        self.trigger_enabled = True
        self.trigger_level = 0.0
        self.show_fft = True
        self.scatter_mode = False
        
        # Buffer para suavizado espectral (Persistancia)
        self.fft_smoothed = None
        self.fft_alpha = 0.15 # Factor de suavizado (0.0 a 1.0)
        
        # Sistema de double-buffering para evitar bloqueos de UI
        self._input_data_ready = False
        self._output_data_ready = False
        self._pending_input_data = None
        self._pending_output_data = None
        
        # Pre-allocated arrays para evitar allocations en cada frame
        self._display_input = np.zeros(1024, dtype=np.float32)
        self._display_output = np.zeros(1024, dtype=np.float32)
        
        self._init_ui()
        self._apply_styles()
        self._connect_signals()
        
        # Iniciar pipeline con bypass por defecto
        self.load_plugin_file("plugins/bypass.py")
        self.orchestrator.start_pipeline()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Splitter para separar gráficos de controles
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)
        
        # --- PANEL DE GRÁFICOS CON TABS ---
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)
        
        # Tab Widget para diferentes vistas
        self.graph_tabs = QTabWidget()
        graph_layout.addWidget(self.graph_tabs)
        
        # Configuración de pyqtgraph - Tema Oscuro High-Tech
        # Opciones para optimizar rendimiento
        pg.setConfigOptions(antialias=False, background='#0d1117', foreground='#c9d1d9')
        pg.setConfigOption('leftButtonPan', False)  # Deshabilitar pan para mejor rendimiento
        
        # Rangos iniciales
        self.plot_y_min = -1000.0
        self.plot_y_max = 1000.0
        self.plot_x_max = 1024  # Ventana de visualización
        
        # Colores de las señales
        self.pen_input = pg.mkPen(color='#f0e68c', width=1.5)      # Amarillo dorado
        self.pen_output = pg.mkPen(color='#00d9ff', width=1.5)      # Cyan brillante
        self.pen_fft = pg.mkPen(color='#00ff88', width=1.5)          # Verde neón
        
        # ===== TAB 1: Tiempo Separado =====
        tab_separado = QWidget()
        tab_separado.setStyleSheet("background-color: #0d1117;")
        tab_separado_layout = QVBoxLayout(tab_separado)
        tab_separado_layout.setContentsMargins(4, 4, 4, 4)
        
        # Plot de entrada
        self.input_plot = pg.PlotWidget(title="<span style='color: #f0e68c;'>⬤</span> Entrada (Tiempo) - Trigger: Zero Crossing")
        self.input_plot.setStyleSheet("background-color: #161b22; border-radius: 6px;")
        self.input_plot.setLimits(xMin=0, xMax=self.plot_x_max*2, yMin=-10000, yMax=10000)  # Limitar rangos
        self.input_plot.setXRange(0, self.plot_x_max, padding=0)
        self.input_plot.setYRange(self.plot_y_min, self.plot_y_max, padding=0)
        self.input_plot.showGrid(x=True, y=True, alpha=0.3)
        self.input_plot.getAxis('bottom').setPen('#484f58')
        self.input_plot.getAxis('left').setPen('#484f58')
        self.input_plot.getAxis('bottom').setTextPen('#8b949e')
        self.input_plot.getAxis('left').setTextPen('#8b949e')
        # Crear curva line y scatter para entrada
        self.input_curve = self.input_plot.plot(pen=self.pen_input, clipToView=False)
        self.input_scatter = pg.ScatterPlotItem(pen=None, brush='#f0e68c', size=3, symbol='o')
        tab_separado_layout.addWidget(self.input_plot)
        
        # Plot de salida
        self.output_plot = pg.PlotWidget(title="<span style='color: #00d9ff;'>⬤</span> Procesada (Tiempo)")
        self.output_plot.setStyleSheet("background-color: #161b22; border-radius: 6px;")
        self.output_plot.setLimits(xMin=0, xMax=self.plot_x_max*2, yMin=-10000, yMax=10000)
        self.output_plot.setXRange(0, self.plot_x_max, padding=0)
        self.output_plot.setYRange(self.plot_y_min, self.plot_y_max, padding=0)
        self.output_plot.showGrid(x=True, y=True, alpha=0.3)
        self.output_plot.getAxis('bottom').setPen('#484f58')
        self.output_plot.getAxis('left').setPen('#484f58')
        self.output_plot.getAxis('bottom').setTextPen('#8b949e')
        self.output_plot.getAxis('left').setTextPen('#8b949e')
        # Crear curva line y scatter para salida
        self.output_curve = self.output_plot.plot(pen=self.pen_output, clipToView=False)
        self.output_scatter = pg.ScatterPlotItem(pen=None, brush='#00d9ff', size=3, symbol='o')
        tab_separado_layout.addWidget(self.output_plot)
        
        # FFT plot
        self.fft_plot = pg.PlotWidget(title="<span style='color: #00ff88;'>⬤</span> Espectro de Frecuencia (FFT)")
        self.fft_plot.setStyleSheet("background-color: #161b22; border-radius: 6px;")
        self.fft_curve = self.fft_plot.plot(pen=self.pen_fft, clipToView=False)
        self.fft_plot.setLogMode(x=True, y=False)
        self.fft_plot.showGrid(x=True, y=True, alpha=0.3)
        self.fft_plot.getAxis('bottom').setPen('#484f58')
        self.fft_plot.getAxis('left').setPen('#484f58')
        self.fft_plot.getAxis('bottom').setTextPen('#8b949e')
        self.fft_plot.getAxis('left').setTextPen('#8b949e')
        self.fft_plot.setYRange(-60, 40, padding=0)
        self.fft_plot.setVisible(False)
        tab_separado_layout.addWidget(self.fft_plot)
        
        self.graph_tabs.addTab(tab_separado, "Tiempo")
        
        # ===== TAB 2: Combinado (Entrada + Salida en un solo gráfico) =====
        tab_combinado = QWidget()
        tab_combinado.setStyleSheet("background-color: #0d1117;")
        tab_combinado_layout = QVBoxLayout(tab_combinado)
        tab_combinado_layout.setContentsMargins(4, 4, 4, 4)
        
        self.combined_plot = pg.PlotWidget(title="Entrada y Salida Combinadas")
        self.combined_plot.setStyleSheet("background-color: #161b22; border-radius: 6px;")
        self.combined_plot.setLimits(xMin=0, xMax=self.plot_x_max*2, yMin=-10, yMax=10)
        self.combined_plot.setXRange(0, self.plot_x_max, padding=0)
        self.combined_plot.setYRange(self.plot_y_min, self.plot_y_max, padding=0)
        self.combined_plot.showGrid(x=True, y=True, alpha=0.3)
        self.combined_plot.getAxis('bottom').setPen('#484f58')
        self.combined_plot.getAxis('left').setPen('#484f58')
        self.combined_plot.getAxis('bottom').setTextPen('#8b949e')
        self.combined_plot.getAxis('left').setTextPen('#8b949e')
        # dos curvas line y scatter para combinado
        self.combined_input_curve = self.combined_plot.plot(pen=self.pen_input, clipToView=False, name='<span style="color: #f0e68c;">●</span> Entrada')
        self.combined_input_scatter = pg.ScatterPlotItem(pen=None, brush='#f0e68c', size=3, symbol='o')
        self.combined_output_curve = self.combined_plot.plot(pen=self.pen_output, clipToView=False, name='<span style="color: #00d9ff;">●</span> Salida')
        self.combined_output_scatter = pg.ScatterPlotItem(pen=None, brush='#00d9ff', size=3, symbol='o')
        # Agregar leyenda
        self.combined_plot.addLegend(offset=(10, 10))
        tab_combinado_layout.addWidget(self.combined_plot)
        
        self.graph_tabs.addTab(tab_combinado, "Combinado")
        
        # --- PANEL DE CONTROL (SIDEBAR) ---
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(320)
        self.sidebar.setStyleSheet("""
            QFrame#sidebar {
                background-color: #161b22;
                border-left: 2px solid #30363d;
                border-radius: 0px;
                padding: 12px;
            }
        """)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 12)
        sidebar_layout.setSpacing(10)
        
        # Selección de Entrada
        sidebar_layout.addWidget(QLabel("<b>Fuente de Entrada</b>"))
        self.combo_source = QComboBox()
        self.combo_source.addItems(["Generador", "Audio (Mic)", "Serial (USB)"])
        self.combo_source.currentIndexChanged.connect(self.on_source_changed)
        sidebar_layout.addWidget(self.combo_source)
        
        # Controles del Generador
        self.group_gen = QFrame()
        gen_layout = QVBoxLayout(self.group_gen)
        
        gen_layout.addWidget(QLabel("Tipo de Onda:"))
        self.combo_wave = QComboBox()
        self.combo_wave.addItems(["Seno", "Cuadrada", "Diente de Sierra", "Ruido"])
        self.combo_wave.currentTextChanged.connect(self.on_wave_changed)
        gen_layout.addWidget(self.combo_wave)
        
        # Frecuencia
        self.lbl_freq = QLabel("Frecuencia: 440 Hz")
        gen_layout.addWidget(self.lbl_freq)
        self.slider_freq = QSlider(Qt.Orientation.Horizontal)
        self.slider_freq.setRange(20, 5000)
        self.slider_freq.setValue(440)
        self.slider_freq.valueChanged.connect(self.on_freq_changed)
        gen_layout.addWidget(self.slider_freq)
        
        # Amplitud
        self.lbl_amp = QLabel("Amplitud: 0.50")
        gen_layout.addWidget(self.lbl_amp)
        self.slider_amp = QSlider(Qt.Orientation.Horizontal)
        self.slider_amp.setRange(0, 100)
        self.slider_amp.setValue(50)
        self.slider_amp.valueChanged.connect(self.on_amp_changed)
        gen_layout.addWidget(self.slider_amp)
        
        sidebar_layout.addWidget(self.group_gen)
        
        # Controles Serial
        self.group_serial = QFrame()
        serial_layout = QVBoxLayout(self.group_serial)
        
        serial_layout.addWidget(QLabel("Puerto:"))
        port_layout = QHBoxLayout()
        self.combo_port = QComboBox()
        port_layout.addWidget(self.combo_port)
        self.btn_refresh_ports = QPushButton("↻")
        self.btn_refresh_ports.setFixedWidth(30)
        self.btn_refresh_ports.clicked.connect(self.refresh_serial_ports)
        port_layout.addWidget(self.btn_refresh_ports)
        serial_layout.addLayout(port_layout)
        
        serial_layout.addWidget(QLabel("Velocidad (Bauds):"))
        self.combo_baud = QComboBox()
        self.combo_baud.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600"])
        self.combo_baud.setCurrentText("115200")
        serial_layout.addWidget(self.combo_baud)
        
        serial_layout.addWidget(QLabel("Modo Serial:"))
        self.combo_serial_mode = QComboBox()
        self.combo_serial_mode.addItems(["Audio RAW", "FFT x,y"])
        self.combo_serial_mode.currentTextChanged.connect(self.on_serial_mode_changed)
        serial_layout.addWidget(self.combo_serial_mode)
        
        self.btn_connect = QPushButton("Conectar")
        self.btn_connect.setCheckable(True)
        self.btn_connect.clicked.connect(self.toggle_serial_connection)
        serial_layout.addWidget(self.btn_connect)
        
        # Conectar cambios de config serial
        self.combo_port.currentTextChanged.connect(lambda p: self.orchestrator.update_serial_params(port=p))
        self.combo_baud.currentTextChanged.connect(lambda b: self.orchestrator.update_serial_params(baudrate=b))
        
        self.group_serial.hide()
        sidebar_layout.addWidget(self.group_serial)
        
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(QLabel("<b>Visualización / Audio</b>"))
        
        # Trigger Toggle
        self.btn_trigger = QPushButton("Trigger: ON")
        self.btn_trigger.setCheckable(True)
        self.btn_trigger.setChecked(True)
        self.btn_trigger.clicked.connect(self.toggle_trigger)
        sidebar_layout.addWidget(self.btn_trigger)
        
        # FFT Toggle
        self.check_fft = QCheckBox("Mostrar FFT")
        self.check_fft.setChecked(True)
        self.check_fft.toggled.connect(self.toggle_fft_visibility)
        sidebar_layout.addWidget(self.check_fft)
        
        # Scatter Mode Toggle
        self.check_scatter = QCheckBox("Modo Scatter")
        self.check_scatter.setChecked(False)
        self.check_scatter.toggled.connect(self.toggle_scatter_mode)
        sidebar_layout.addWidget(self.check_scatter)
        
        # Controles de Ventana Y
        sidebar_layout.addSpacing(5)
        y_range_label = QLabel("Rango Y:")
        sidebar_layout.addWidget(y_range_label)
        
        y_range_layout = QHBoxLayout()
        self.lbl_y_min = QLabel("-1.0")
        y_range_layout.addWidget(self.lbl_y_min)
        y_range_layout.addWidget(QLabel("to"))
        self.spin_y_max = QDoubleSpinBox()
        self.spin_y_max.setRange(0.1, 10.0)
        self.spin_y_max.setValue(1.0)
        self.spin_y_max.setDecimals(1)
        self.spin_y_max.valueChanged.connect(self.on_y_range_changed)
        y_range_layout.addWidget(self.spin_y_max)
        self.lbl_y_max = QLabel("1.0")
        y_range_layout.addWidget(self.lbl_y_max)
        sidebar_layout.addLayout(y_range_layout)
        
        # Controles de Ventana X
        sidebar_layout.addSpacing(5)
        x_range_label = QLabel("Ventana X (muestras):")
        sidebar_layout.addWidget(x_range_label)
        
        x_range_layout = QHBoxLayout()
        self.spin_x_range = QSpinBox()
        self.spin_x_range.setRange(256, 8192)
        self.spin_x_range.setValue(1024)
        self.spin_x_range.valueChanged.connect(self.on_x_range_changed)
        x_range_layout.addWidget(self.spin_x_range)
        sidebar_layout.addLayout(x_range_layout)
        
        # Audio Out Toggle
        self.check_audio_out = QCheckBox("Salida de Audio (Hardware)")
        self.check_audio_out.toggled.connect(self.orchestrator.toggle_audio_output)
        sidebar_layout.addWidget(self.check_audio_out)
        
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(QLabel("<b>Gestión de Plugins</b>"))
        self.btn_load = QPushButton("Cargar Plugin (.py)")
        self.btn_load.clicked.connect(self.on_load_plugin_clicked)
        sidebar_layout.addWidget(self.btn_load)
        
        # Espacio para la UI dinámica del Plugin
        sidebar_layout.addSpacing(20)
        sidebar_layout.addWidget(QLabel("<b>Interfaz del Plugin</b>"))
        self.plugin_ui_container = QFrame()
        self.plugin_ui_container.setFrameShape(QFrame.Shape.Box)
        self.plugin_ui_layout = QVBoxLayout(self.plugin_ui_container)
        sidebar_layout.addWidget(self.plugin_ui_container)
        
        sidebar_layout.addStretch()
        
        # Agregar al splitter
        self.splitter.addWidget(graph_container)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)

    def on_source_changed(self, index):
        sources = ['generator', 'audio', 'serial']
        source = sources[index]
        
        # Siempre detener worker de adquisición anterior antes de cambiar
        if "acquisition" in self.orchestrator.workers:
            self.orchestrator._stop_worker("acquisition")
        
        # Si había una conexión serial activa, desconectar
        if self.orchestrator.serial_in.ser:
            try:
                self.orchestrator.serial_in.data_updated.disconnect(self.update_serial_plot)
            except TypeError:
                pass  # Señal no estaba conectada
            self.orchestrator.serial_in.stop()
            self.btn_connect.setText("Conectar")
            self.btn_connect.setChecked(False)
        
        # Para serial, no llamar set_input_source (el botón Conectar lo maneja)
        if source != 'serial':
            self.orchestrator.set_input_source(source)
        
        self.orchestrator.current_source = source
        
        # Mostrar/Ocultar controles específicos
        self.group_gen.setVisible(source == 'generator')
        self.group_serial.setVisible(source == 'serial')

    def on_wave_changed(self, text):
        wave_map = {"Seno": "sine", "Cuadrada": "square", "Diente de Sierra": "sawtooth", "Ruido": "noise"}
        self.orchestrator.generator.update_params(wave_type=wave_map[text])

    def on_freq_changed(self, value):
        self.lbl_freq.setText(f"Frecuencia: {value} Hz")
        self.orchestrator.generator.update_params(frequency=float(value))

    def on_amp_changed(self, value):
        amp = value / 100.0
        self.lbl_amp.setText(f"Amplitud: {amp:.2f}")
        self.orchestrator.generator.update_params(amplitude=amp)

    def on_serial_mode_changed(self, text):
        mode = "raw" if "RAW" in text else "fft"
        self.orchestrator.serial_in.mode = mode
        # Forzar reinicio para aplicar modo
        if self.orchestrator.current_source == 'serial':
            self.orchestrator.set_input_source('serial', force_restart=True)

    def refresh_serial_ports(self):
        """Escanea y actualiza la lista de puertos seriales."""
        from core.inputs.serial_in import SerialInput
        ports = SerialInput.get_available_ports()
        current = self.combo_port.currentText()
        self.combo_port.blockSignals(True) # Evitar disparar cambios durante el borrado
        self.combo_port.clear()
        self.combo_port.addItems(ports)
        if current in ports:
            self.combo_port.setCurrentText(current)
        elif ports:
            self.combo_port.setCurrentIndex(0)
        self.combo_port.blockSignals(False)

    def toggle_serial_connection(self):
        """Conecta o desconecta el puerto serial."""
        if not self.orchestrator.serial_in.ser:
            # Conectar
            port = self.combo_port.currentText()
            baudrate = int(self.combo_baud.currentText())
            self.orchestrator.serial_in.update_config(port=port, baudrate=baudrate)
            
            if self.orchestrator.serial_in.start():
                # Conectar señal para actualizar gráfico en tiempo real
                self.orchestrator.serial_in.data_updated.connect(self.update_serial_plot)
                self.btn_connect.setText("Desconectar")
                self.statusBar().showMessage(f"Serial conectado: {port}")
            else:
                self.btn_connect.setChecked(False)
                self.statusBar().showMessage("Error: No se pudo conectar al puerto serial")
        else:
            # Desconectar
            self.orchestrator.serial_in.data_updated.disconnect(self.update_serial_plot)
            self.orchestrator.serial_in.stop()
            self.btn_connect.setText("Conectar")
            self.btn_connect.setChecked(False)
            self.statusBar().showMessage("Serial desconectado")

    def _connect_signals(self):
        self.orchestrator.data_acquired.connect(self.update_input_plot)
        self.orchestrator.data_processed.connect(self.update_output_plot)
        self.orchestrator.error_occurred.connect(self.show_error)
        
        # Escaneo inicial de puertos
        self.refresh_serial_ports()

    def _apply_styles(self):
        """Aplica estilo visual moderno 'High-Tech Lab' a la aplicación."""
        # Configurar pyqtgraph con colores del tema
        pg.setConfigOption('background', '#1a1a2e')
        pg.setConfigOption('foreground', '#e8e8e8')
        
        self.setStyleSheet("""
            /* ===== ESTILO HIGH-TECH LAB ===== */
            
            QMainWindow {
                background-color: #0d1117;
            }
            
            QWidget {
                background-color: #0d1117;
                color: #c9d1d9;
                font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
                font-size: 13px;
            }
            
            /* Paneles y frames */
            QFrame {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 8px;
            }
            
            /* Labels */
            QLabel {
                color: #c9d1d9;
                background-color: transparent;
                padding: 2px;
            }
            
            QLabel[heading="true"] {
                font-weight: bold;
                color: #58a6ff;
                font-size: 14px;
            }
            
            /* Botones */
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                min-height: 20px;
            }
            
            QPushButton:hover {
                background-color: #30363d;
                border-color: #58a6ff;
                color: #58a6ff;
            }
            
            QPushButton:pressed {
                background-color: #1f6feb;
                border-color: #1f6feb;
                color: #ffffff;
            }
            
            QPushButton:checked {
                background-color: #1f6feb;
                border-color: #1f6feb;
                color: #ffffff;
            }
            
            QPushButton:disabled {
                background-color: #21262d;
                color: #484f58;
                border-color: #21262d;
            }
            
            /* ComboBox */
            QComboBox {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 12px;
                min-height: 20px;
            }
            
            QComboBox:hover {
                border-color: #58a6ff;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #8b949e;
                margin-right: 10px;
            }
            
            QComboBox QAbstractItemView {
                background-color: #0d1117;
                color: #c9d1d9;
                border: 1px solid #30363d;
                selection-background-color: #1f6feb;
                padding: 4px;
            }
            
            /* Checkboxes */
            QCheckBox {
                color: #c9d1d9;
                spacing: 10px;
                padding: 4px;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #30363d;
                border-radius: 4px;
                background-color: #0d1117;
            }
            
            QCheckBox::indicator:hover {
                border-color: #58a6ff;
            }
            
            QCheckBox::indicator:checked {
                background-color: #1f6feb;
                border-color: #1f6feb;
            }
            
            QCheckBox::indicator:checked:hover {
                background-color: #388bfd;
            }
            
            /* SpinBoxes */
            QSpinBox, QDoubleSpinBox {
                background-color: #0d1117;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 10px;
                min-height: 20px;
            }
            
            QSpinBox:hover, QDoubleSpinBox:hover {
                border-color: #58a6ff;
            }
            
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                border: none;
                width: 16px;
                background-color: transparent;
            }
            
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                border: none;
                width: 16px;
                background-color: transparent;
            }
            
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 4px solid #8b949e;
            }
            
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #8b949e;
            }
            
            /* Sliders */
            QSlider::groove:horizontal {
                border: none;
                height: 6px;
                background-color: #30363d;
                border-radius: 3px;
            }
            
            QSlider::handle:horizontal {
                background-color: #58a6ff;
                border: none;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            
            QSlider::handle:horizontal:hover {
                background-color: #79c0ff;
            }
            
            QSlider::sub-page:horizontal {
                background-color: #1f6feb;
                border-radius: 3px;
            }
            
            /* Tabs */
            QTabWidget::pane {
                border: 1px solid #30363d;
                border-radius: 8px;
                background-color: #0d1117;
                padding: 8px;
            }
            
            QTabBar::tab {
                background-color: #21262d;
                color: #8b949e;
                padding: 10px 24px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 500;
            }
            
            QTabBar::tab:hover {
                background-color: #30363d;
                color: #c9d1d9;
            }
            
            QTabBar::tab:selected {
                background-color: #0d1117;
                color: #58a6ff;
                border-bottom: 2px solid #58a6ff;
            }
            
            /* Scrollbars */
            QScrollBar:vertical {
                background-color: #0d1117;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #30363d;
                border-radius: 6px;
                min-height: 30px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #484f58;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            /* Status Bar */
            QStatusBar {
                background-color: #161b22;
                color: #8b949e;
                border-top: 1px solid #30363d;
                padding: 4px;
            }
            
            /* Tooltips */
            QToolTip {
                background-color: #21262d;
                color: #c9d1d9;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 4px;
            }
            
            /* Message Boxes */
            QMessageBox {
                background-color: #0d1117;
            }
            
            QMessageBox QLabel {
                color: #c9d1d9;
            }
            
            QMessageBox QPushButton {
                min-width: 80px;
            }
        """)

    def toggle_trigger(self):
        self.trigger_enabled = self.btn_trigger.isChecked()
        self.btn_trigger.setText(f"Trigger: {'ON' if self.trigger_enabled else 'OFF'}")

    def toggle_fft_visibility(self, checked):
        """Muestra u oculta el gráfico de FFT."""
        self.show_fft = checked
        self.fft_plot.setVisible(checked)
    
    def toggle_scatter_mode(self, checked):
        """Alterna entre modo línea y modo scatter."""
        self.scatter_mode = checked
        
        # Mostrar/ocultar elementos según el modo
        # Input plot
        if checked:
            self.input_plot.addItem(self.input_scatter)
            self.input_curve.setData([])
        else:
            self.input_plot.removeItem(self.input_scatter)
        
        # Output plot
        if checked:
            self.output_plot.addItem(self.output_scatter)
            self.output_curve.setData([])
        else:
            self.output_plot.removeItem(self.output_scatter)
        
        # Combined plot
        if checked:
            self.combined_plot.addItem(self.combined_input_scatter)
            self.combined_plot.addItem(self.combined_output_scatter)
            self.combined_input_curve.setData([])
            self.combined_output_curve.setData([])
        else:
            self.combined_plot.removeItem(self.combined_input_scatter)
            self.combined_plot.removeItem(self.combined_output_scatter)
    
    def on_y_range_changed(self, value):
        """Actualiza el rango Y de los gráficos de tiempo."""
        y_max = value
        y_min = -y_max
        self.lbl_y_min.setText(f"{-y_max:.1f}")
        self.lbl_y_max.setText(f"{y_max:.1f}")
        
        # Actualizar todos los gráficos de tiempo
        self.input_plot.setYRange(y_min, y_max)
        self.output_plot.setYRange(y_min, y_max)
        self.combined_plot.setYRange(y_min, y_max)
    
    def on_x_range_changed(self, value):
        """Actualiza la cantidad de muestras visibles en X."""
        self.display_size = value
        # Actualizar el rango del eje X
        self.input_plot.setXRange(0, value)
        self.output_plot.setXRange(0, value)
        self.combined_plot.setXRange(0, value)

    def _apply_trigger(self, data_buffer):
        """Busca el primer cruce por cero ascendente para estabilizar la señal."""
        if not self.trigger_enabled:
            return data_buffer[-self.display_size:]
            
        # Buscar cruce por cero (de negativo a positivo)
        # Buscamos en la primera mitad del buffer para tener margen de visualización
        search_range = self.buffer_size - self.display_size
        indices = np.where((data_buffer[:search_range-1] < self.trigger_level) & 
                           (data_buffer[1:search_range] >= self.trigger_level))[0]
        
        if len(indices) > 0:
            start_idx = indices[0]
            return data_buffer[start_idx : start_idx + self.display_size]
        
        return data_buffer[-self.display_size:]

    @pyqtSlot(object)
    def update_input_plot(self, data):
        """Callback de datos de entrada - actualiza gráficos directamente."""
        # Actualizar buffer - sin np.roll, el deque ya maneja la ventana
        self.input_buffer[-len(data):] = data
        
        # Calcular datos para display
        display_data = self._apply_trigger(self.input_buffer)
        
        # Actualizar según modo scatter o line
        if self.scatter_mode:
            x_data = np.arange(len(display_data))
            self.input_scatter.setData(x_data, display_data)
            self.combined_input_scatter.setData(x_data, display_data)
        else:
            self.input_curve.setData(display_data)
            self.combined_input_curve.setData(display_data)

    @pyqtSlot(np.ndarray)
    def update_serial_plot(self, data):
        """Actualiza el gráfico de entrada con datos del serial."""
        # Actualizar buffer sin np.roll
        self.input_buffer[-len(data):] = data
        
        # Actualizar según modo
        if self.scatter_mode:
            x_data = np.arange(len(data))
            self.input_scatter.setData(x_data, data)
            self.combined_input_scatter.setData(x_data, data)
        else:
            self.input_curve.setData(data)
            self.combined_input_curve.setData(data)

    @pyqtSlot(object)
    def update_output_plot(self, data):
        """Callback de datos procesados - actualiza gráficos directamente."""
        # Actualizar buffer sin np.roll
        self.output_buffer[-len(data):] = data
        
        # Calcular datos para display
        display_data = self._apply_trigger(self.output_buffer)
        
        # Actualizar según modo
        if self.scatter_mode:
            x_data = np.arange(len(display_data))
            self.output_scatter.setData(x_data, display_data)
            self.combined_output_scatter.setData(x_data, display_data)
        else:
            self.output_curve.setData(display_data)
            self.combined_output_curve.setData(display_data)
        
        # FFT solo si no es serial FFT mode
        if self.orchestrator.current_source != 'serial' or self.orchestrator.serial_in.mode == 'raw':
            self.update_fft(display_data)
        else:
            # Serial FFT mode - los datos ya contienen x,y
            self._update_fft_from_serial(data)

    def update_fft(self, data):
        """Calcula y grafica la FFT de los datos locales con enventanado y suavizado."""
        try:
            n = len(data)
            if n < 2: return
            
            # 1. Aplicar ventana de Hanning para reducir fugas espectrales
            window = np.hanning(n)
            windowed_data = data * window
            
            # 2. Calcular FFT real
            freqs = np.fft.rfftfreq(n, d=1/self.orchestrator.sample_rate)
            mag = np.abs(np.fft.rfft(windowed_data))
            
            # 3. Convertir a dB con protección contra ceros
            mag_db = 20 * np.log10(mag + 1e-6)
            
            # 4. Suavizado Temporal (Filtro de Persistencia)
            if self.fft_smoothed is None or len(self.fft_smoothed) != len(mag_db):
                self.fft_smoothed = mag_db
            else:
                # mag_db_new = alpha * actual + (1-alpha) * previa
                self.fft_smoothed = self.fft_alpha * mag_db + (1 - self.fft_alpha) * self.fft_smoothed
            
            # 5. Dibujar (frecuencias a partir de la 1 para ignorar DC)
            self.fft_curve.setData(freqs[1:], self.fft_smoothed[1:])
            # Ya no necesitamos setYRange aquí porque está configurado en __init__
            
        except Exception as e:
            print(f"Error en FFT: {e}")

    def _update_fft_from_serial(self, data):
        """Actualiza FFT desde datos seriales que contienen x,y directamente."""
        x = []
        y = []
        if isinstance(data, np.ndarray):
            for d in data:
                if isinstance(d, tuple) and len(d) >= 2:
                    x.append(d[0])
                    y.append(d[1])
        if x:
            self.fft_curve.setData(x, y)

    def on_load_plugin_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Plugin", "plugins", "Python Files (*.py)"
        )
        if file_path:
            self.load_plugin_file(file_path)

    def load_plugin_file(self, path):
        # Limpiar UI anterior de forma segura
        for i in reversed(range(self.plugin_ui_layout.count())): 
            item = self.plugin_ui_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
            
        # Cargar nuevo plugin vía orquestador
        plugin_ui = self.orchestrator.load_plugin(path)
        if plugin_ui:
            self.plugin_ui_layout.addWidget(plugin_ui)
            self.statusBar().showMessage(f"Plugin cargado: {os.path.basename(path)}")
        else:
            # Si el orquestador no emite el error, lo forzamos aquí
            self.show_error(f"No se pudo cargar el plugin: {os.path.basename(path)}")

    def show_error(self, message):
        """Muestra un diálogo de error y actualiza la barra de estado."""
        self.statusBar().showMessage(f"ERROR: {message}")
        QMessageBox.critical(self, "Error de Pipeline", message)

    def closeEvent(self, event):
        self.orchestrator.stop_pipeline()
        event.accept()
