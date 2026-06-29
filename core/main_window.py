import os
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QFileDialog, QLabel, QFrame, QSplitter, 
                             QMessageBox, QComboBox, QCheckBox, QSlider, QTabWidget,
                             QSpinBox, QDoubleSpinBox, QDialog, QLineEdit, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal
from core.orchestrator import Orchestrator

class MainWindow(QMainWindow):
    channels_detected = pyqtSignal(int)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RT Signal Pipeline - PyQt DSP")
        self.resize(1200, 900)
        
        # El Orquestador (Presenter)
        self.orchestrator = Orchestrator()
        
        # Buffers para visualización
        self.buffer_size = 8192 
        self.display_size = 1024 
        self.input_buffer = np.zeros((self.buffer_size, 1))
        self.output_buffer = np.zeros((self.buffer_size, 1))
        
        # Sistema de double-buffering para evitar bloqueos de UI
        self._input_data_ready = False
        self._output_data_ready = False
        self._pending_input_data = None
        self._pending_output_data = None
        
        # Pre-allocated arrays para evitar allocations en cada frame
        self._display_input = np.zeros(1024, dtype=np.float32)
        self._display_output = np.zeros(1024, dtype=np.float32)
        
        # Plugin window management
        self.plugin_window = None
        self._plugin_ui = None
        self.current_plugin_name = "Ninguno"
        
        # Serial and channel configuration state
        self.channel_configs = {}
        self.serial_num_channels = 1
        self.serial_data_type = "int16"
        self.serial_hex_sep = ""
        self.current_detected_channels = 0
        
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
        self.input_plot = pg.PlotWidget(title="<span style='color: #f0e68c;'>⬤</span> Entrada (Tiempo)")
        self.input_plot.setStyleSheet("background-color: #161b22; border-radius: 6px;")
        self.input_plot.setLimits(xMin=0, xMax=1024, yMin=-10000, yMax=10000)  # Limitar rangos
        self.input_plot.setXRange(0, self.plot_x_max, padding=0)
        self.input_plot.setYRange(self.plot_y_min, self.plot_y_max, padding=0)
        self.input_plot.showGrid(x=True, y=True, alpha=0.3)
        self.input_plot.getAxis('bottom').setPen('#484f58')
        self.input_plot.getAxis('left').setPen('#484f58')
        self.input_plot.getAxis('bottom').setTextPen('#8b949e')
        self.input_plot.getAxis('left').setTextPen('#8b949e')
        # Crear curva para entrada
        self.max_channels = 8
        self.input_curves = []
        for i in range(self.max_channels):
            color = self.pen_input.color().lighter(100 + i * 20)
            pen = pg.mkPen(color=color, width=self.pen_input.width())
            curve = self.input_plot.plot(pen=pen, clipToView=True, autoDownsample=True, name=f"Entrada {i+1}")
            curve.setVisible(False)
            self.input_curves.append(curve)
        tab_separado_layout.addWidget(self.input_plot)
        
        # Plot de salida
        self.output_plot = pg.PlotWidget(title="<span style='color: #00d9ff;'>⬤</span> Procesada (Tiempo)")
        self.output_plot.setStyleSheet("background-color: #161b22; border-radius: 6px;")
        self.output_plot.setLimits(xMin=0, xMax=1024, yMin=-10000, yMax=10000)
        self.output_plot.setXRange(0, self.plot_x_max, padding=0)
        self.output_plot.setYRange(self.plot_y_min, self.plot_y_max, padding=0)
        self.output_plot.showGrid(x=True, y=True, alpha=0.3)
        self.output_plot.getAxis('bottom').setPen('#484f58')
        self.output_plot.getAxis('left').setPen('#484f58')
        self.output_plot.getAxis('bottom').setTextPen('#8b949e')
        self.output_plot.getAxis('left').setTextPen('#8b949e')
        # Crear curva para salida
        self.output_curves = []
        for i in range(self.max_channels):
            color = self.pen_output.color().lighter(100 + i * 20)
            pen = pg.mkPen(color=color, width=self.pen_output.width())
            curve = self.output_plot.plot(pen=pen, clipToView=True, autoDownsample=True, name=f"Salida {i+1}")
            curve.setVisible(False)
            self.output_curves.append(curve)
        tab_separado_layout.addWidget(self.output_plot)
        self.graph_tabs.addTab(tab_separado, "Tiempo")
        
        # ===== TAB 2: Combinado (Entrada + Salida en un solo gráfico) =====
        tab_combinado = QWidget()
        tab_combinado.setStyleSheet("background-color: #0d1117;")
        tab_combinado_layout = QVBoxLayout(tab_combinado)
        tab_combinado_layout.setContentsMargins(4, 4, 4, 4)
        
        self.combined_plot = pg.PlotWidget(title="Entrada y Salida Combinadas")
        self.combined_plot.setStyleSheet("background-color: #161b22; border-radius: 6px;")
        self.combined_plot.setLimits(xMin=0, xMax=1024, yMin=-10, yMax=10)
        self.combined_plot.setXRange(0, self.plot_x_max, padding=0)
        self.combined_plot.setYRange(self.plot_y_min, self.plot_y_max, padding=0)
        self.combined_plot.showGrid(x=True, y=True, alpha=0.3)
        self.combined_plot.getAxis('bottom').setPen('#484f58')
        self.combined_plot.getAxis('left').setPen('#484f58')
        self.combined_plot.getAxis('bottom').setTextPen('#8b949e')
        self.combined_plot.getAxis('left').setTextPen('#8b949e')
        # curvas line para combinado
        self.combined_input_curves = []
        self.combined_output_curves = []
        for i in range(self.max_channels):
            color_in = self.pen_input.color().lighter(100 + i * 20)
            pen_in = pg.mkPen(color=color_in, width=self.pen_input.width())
            curve_in = self.combined_plot.plot(pen=pen_in, clipToView=True, autoDownsample=True, name=f"In {i+1}")
            curve_in.setVisible(False)
            self.combined_input_curves.append(curve_in)
            
            color_out = self.pen_output.color().lighter(100 + i * 20)
            pen_out = pg.mkPen(color=color_out, width=self.pen_output.width())
            curve_out = self.combined_plot.plot(pen=pen_out, clipToView=True, autoDownsample=True, name=f"Out {i+1}")
            curve_out.setVisible(False)
            self.combined_output_curves.append(curve_out)
        # Agregar leyenda
        self.combined_plot.addLegend(offset=(10, 10))
        tab_combinado_layout.addWidget(self.combined_plot)
        
        self.graph_tabs.addTab(tab_combinado, "Combinado")
        
        # ===== TAB 3: FFT =====
        tab_fft = QWidget()
        tab_fft.setStyleSheet("background-color: #0d1117;")
        tab_fft_layout = QVBoxLayout(tab_fft)
        tab_fft_layout.setContentsMargins(4, 4, 4, 4)
        
        self.fft_time_plot = pg.PlotWidget(title="Entrada (Tiempo)")
        self.fft_time_plot.setStyleSheet("background-color: #161b22; border-radius: 6px;")
        self.fft_time_plot.setLimits(xMin=0, xMax=1024, yMin=-10000, yMax=10000)
        self.fft_time_plot.setXRange(0, self.plot_x_max, padding=0)
        self.fft_time_plot.setYRange(self.plot_y_min, self.plot_y_max, padding=0)
        self.fft_time_plot.showGrid(x=True, y=True, alpha=0.3)
        self.fft_time_plot.getAxis('bottom').setPen('#484f58')
        self.fft_time_plot.getAxis('left').setPen('#484f58')
        self.fft_time_plot.getAxis('bottom').setTextPen('#8b949e')
        self.fft_time_plot.getAxis('left').setTextPen('#8b949e')
        self.fft_time_curves = []
        for i in range(self.max_channels):
            color = self.pen_input.color().lighter(100 + i * 20)
            pen = pg.mkPen(color=color, width=self.pen_input.width())
            curve = self.fft_time_plot.plot(pen=pen, clipToView=True, autoDownsample=True, name=f"Entrada {i+1}")
            curve.setVisible(False)
            self.fft_time_curves.append(curve)
        tab_fft_layout.addWidget(self.fft_time_plot)
        
        self.fft_freq_plot = pg.PlotWidget(title="Espectro (FFT)")
        self.fft_freq_plot.setStyleSheet("background-color: #161b22; border-radius: 6px;")
        self.fft_freq_plot.showGrid(x=True, y=True, alpha=0.3)
        self.fft_freq_plot.getAxis('bottom').setPen('#484f58')
        self.fft_freq_plot.getAxis('left').setPen('#484f58')
        self.fft_freq_plot.getAxis('bottom').setTextPen('#8b949e')
        self.fft_freq_plot.getAxis('left').setTextPen('#8b949e')
        self.fft_freq_plot.setLabel('bottom', 'Frecuencia (Hz)')
        self.fft_freq_plot.setLabel('left', 'Magnitud')
        self.fft_freq_plot.getPlotItem().showAxis('bottom')
        self.fft_freq_plot.setLogMode(x=False, y=False)
        self.fft_freq_curves = []
        for i in range(self.max_channels):
            color = self.pen_input.color().lighter(100 + i * 20)
            pen = pg.mkPen(color=color, width=self.pen_input.width())
            curve = self.fft_freq_plot.plot(pen=pen, clipToView=True, autoDownsample=True, name=f"FFT {i+1}")
            curve.setVisible(False)
            self.fft_freq_curves.append(curve)
        tab_fft_layout.addWidget(self.fft_freq_plot)
        
        self.graph_tabs.addTab(tab_fft, "FFT")
        
        # --- PANEL DE CONTROL (SIDEBAR) ---
        self.sidebar = QScrollArea()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setMinimumWidth(320)
        self.sidebar.setWidgetResizable(True)
        self.sidebar.setStyleSheet("""
            QScrollArea#sidebar {
                background-color: #161b22;
                border-left: 2px solid #30363d;
                border-radius: 0px;
                border-top: none;
                border-right: none;
                border-bottom: none;
            }
        """)
        sidebar_content = QWidget()
        sidebar_content.setStyleSheet("background-color: #161b22;")
        self.sidebar.setWidget(sidebar_content)
        sidebar_layout = QVBoxLayout(sidebar_content)
        sidebar_layout.setContentsMargins(12, 16, 12, 12)
        sidebar_layout.setSpacing(10)
        
        # Selección de Entrada
        sidebar_layout.addWidget(QLabel("<b>Fuente de Entrada</b>"))
        self.combo_source = QComboBox()
        self.combo_source.addItems(["Serial (USB)", "Generador", "Audio (Mic)"])
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
        self.combo_serial_mode.addItems(["CSV", "RAW Binary", "XY Colon"])
        self.combo_serial_mode.currentTextChanged.connect(self.on_serial_mode_changed)
        serial_layout.addWidget(self.combo_serial_mode)

        self.btn_raw_format = QPushButton("Formato RAW (Tipo/Hex)")
        self.btn_raw_format.clicked.connect(self.open_raw_format_dialog)
        serial_layout.addWidget(self.btn_raw_format)
        
        self.btn_channel_config = QPushButton("Configurar Canales (Color/Vis)")
        self.btn_channel_config.clicked.connect(self.open_channel_config_window)
        serial_layout.addWidget(self.btn_channel_config)
        
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
        

        # Controles de Ventana Y
        sidebar_layout.addSpacing(5)
        y_range_label = QLabel("Rango Y:")
        sidebar_layout.addWidget(y_range_label)
        
        y_range_layout = QHBoxLayout()
        self.spin_y_min = QDoubleSpinBox()
        self.spin_y_min.setRange(-10000.0, 10000.0)
        self.spin_y_min.setValue(-1.0)
        self.spin_y_min.setDecimals(2)
        self.spin_y_min.valueChanged.connect(self.on_y_range_changed)
        y_range_layout.addWidget(self.spin_y_min)
        
        y_range_layout.addWidget(QLabel("to"))
        
        self.spin_y_max = QDoubleSpinBox()
        self.spin_y_max.setRange(-10000.0, 10000.0)
        self.spin_y_max.setValue(1.0)
        self.spin_y_max.setDecimals(2)
        self.spin_y_max.valueChanged.connect(self.on_y_range_changed)
        y_range_layout.addWidget(self.spin_y_max)
        sidebar_layout.addLayout(y_range_layout)
        
        self.btn_auto_y = QPushButton("Auto-Ajustar Y")
        self.btn_auto_y.clicked.connect(self.auto_adjust_y)
        sidebar_layout.addWidget(self.btn_auto_y)
        
        # Controles de Ventana Y (FFT)
        sidebar_layout.addSpacing(5)
        fft_y_range_label = QLabel("Rango Y (FFT):")
        sidebar_layout.addWidget(fft_y_range_label)
        
        fft_y_range_layout = QHBoxLayout()
        self.fft_spin_y_min = QDoubleSpinBox()
        self.fft_spin_y_min.setRange(-10000.0, 10000.0)
        self.fft_spin_y_min.setValue(0.0)
        self.fft_spin_y_min.setDecimals(2)
        self.fft_spin_y_min.valueChanged.connect(self.on_fft_y_range_changed)
        fft_y_range_layout.addWidget(self.fft_spin_y_min)
        
        fft_y_range_layout.addWidget(QLabel("to"))
        
        self.fft_spin_y_max = QDoubleSpinBox()
        self.fft_spin_y_max.setRange(-10000.0, 10000.0)
        self.fft_spin_y_max.setValue(100.0)
        self.fft_spin_y_max.setDecimals(2)
        self.fft_spin_y_max.valueChanged.connect(self.on_fft_y_range_changed)
        fft_y_range_layout.addWidget(self.fft_spin_y_max)
        sidebar_layout.addLayout(fft_y_range_layout)
        
        self.btn_auto_fft_y = QPushButton("Auto-Ajustar Y FFT")
        self.btn_auto_fft_y.clicked.connect(self.auto_adjust_fft_y)
        sidebar_layout.addWidget(self.btn_auto_fft_y)
        
        # Controles de Ventana X (FFT)
        sidebar_layout.addSpacing(5)
        fft_x_range_label = QLabel("Ventana X (FFT) Hz:")
        sidebar_layout.addWidget(fft_x_range_label)
        
        fft_x_range_layout = QHBoxLayout()
        self.fft_spin_x_min = QDoubleSpinBox()
        self.fft_spin_x_min.setRange(0.0, 1000000.0)
        self.fft_spin_x_min.setValue(0.0)
        self.fft_spin_x_min.setDecimals(1)
        self.fft_spin_x_min.valueChanged.connect(self.on_fft_x_range_changed)
        fft_x_range_layout.addWidget(self.fft_spin_x_min)
        
        fft_x_range_layout.addWidget(QLabel("to"))
        
        self.fft_spin_x_max = QDoubleSpinBox()
        self.fft_spin_x_max.setRange(0.0, 1000000.0)
        self.fft_spin_x_max.setValue(22050.0)
        self.fft_spin_x_max.setDecimals(1)
        self.fft_spin_x_max.valueChanged.connect(self.on_fft_x_range_changed)
        fft_x_range_layout.addWidget(self.fft_spin_x_max)
        sidebar_layout.addLayout(fft_x_range_layout)
        
        self.btn_auto_fft_x = QPushButton("Auto-Ajustar X FFT")
        self.btn_auto_fft_x.clicked.connect(self.auto_adjust_fft_x)
        sidebar_layout.addWidget(self.btn_auto_fft_x)
        
        # Controles de Ventana X
        sidebar_layout.addSpacing(5)
        x_range_label = QLabel("Ventana X (muestras):")
        sidebar_layout.addWidget(x_range_label)
        
        x_range_layout = QHBoxLayout()
        self.spin_x_min = QSpinBox()
        self.spin_x_min.setRange(0, 1024)
        self.spin_x_min.setValue(0)
        self.spin_x_min.valueChanged.connect(self.on_x_range_changed)
        x_range_layout.addWidget(self.spin_x_min)
        
        x_range_layout.addWidget(QLabel("to"))
        
        self.spin_x_max = QSpinBox()
        self.spin_x_max.setRange(10, 1024)
        self.spin_x_max.setValue(1024)
        self.spin_x_max.valueChanged.connect(self.on_x_range_changed)
        x_range_layout.addWidget(self.spin_x_max)
        sidebar_layout.addLayout(x_range_layout)
        
        self.btn_auto_x = QPushButton("Auto-Ajustar X")
        self.btn_auto_x.clicked.connect(self.auto_adjust_x)
        sidebar_layout.addWidget(self.btn_auto_x)
        
        # Audio Out Toggle
        self.check_audio_out = QCheckBox("Salida de Audio (Hardware)")
        self.check_audio_out.toggled.connect(self.orchestrator.toggle_audio_output)
        sidebar_layout.addWidget(self.check_audio_out)
        
        # Export CSV Button
        sidebar_layout.addSpacing(10)
        self.btn_export_csv = QPushButton("Exportar Datos a CSV")
        self.btn_export_csv.clicked.connect(self.export_to_csv)
        sidebar_layout.addWidget(self.btn_export_csv)
        
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(QLabel("<b>Gestión de Plugins</b>"))
        self.btn_load = QPushButton("Cargar Plugin (.py)")
        self.btn_load.clicked.connect(self.on_load_plugin_clicked)
        sidebar_layout.addWidget(self.btn_load)
        
        self.btn_open_plugin_panel = QPushButton("Abrir Panel del Plugin")
        self.btn_open_plugin_panel.clicked.connect(self._toggle_plugin_window)
        self.btn_open_plugin_panel.setEnabled(False)
        sidebar_layout.addWidget(self.btn_open_plugin_panel)
        
        sidebar_layout.addStretch()

        # Agregar al splitter
        self.splitter.addWidget(graph_container)
        self.splitter.addWidget(self.sidebar)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 1)
        
        # Ensure correct initial state for source
        self.on_source_changed(self.combo_source.currentIndex())
        self.open_channel_config_window()

    def on_source_changed(self, index):
        sources = ['serial', 'generator', 'audio']
        source = sources[index]
        
        # Siempre detener worker de adquisición anterior antes de cambiar
        if "acquisition" in self.orchestrator.workers:
            self.orchestrator._stop_worker("acquisition")
        
        # Si había una conexión serial activa, desconectar
        if self.orchestrator.serial_in.ser:
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
        if "RAW" in text:
            mode = "raw"
        elif "XY" in text:
            mode = "xy_colon"
        else:
            mode = "csv"
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
                self.btn_connect.setText("Desconectar")
                self.statusBar().showMessage(f"Serial conectado: {port}")
            else:
                self.btn_connect.setChecked(False)
                self.statusBar().showMessage("Error: No se pudo conectar al puerto serial")
        else:
            # Desconectar
            self.orchestrator.serial_in.stop()
            self.btn_connect.setText("Conectar")
            self.btn_connect.setChecked(False)
            self.statusBar().showMessage("Serial desconectado")

    def open_raw_format_dialog(self):
        from core.raw_format_dialog import RawFormatDialog
        dialog = RawFormatDialog(
            current_data_type=self.serial_data_type,
            current_hex_sep=self.serial_hex_sep,
            current_num_channels=self.serial_num_channels,
            parent=self
        )
        dialog.config_applied.connect(self.on_raw_format_applied)
        dialog.exec()

    def open_channel_config_window(self):
        if not hasattr(self, 'channel_config_window') or self.channel_config_window is None:
            from core.channel_config_window import ChannelConfigWindow
            self.channel_config_window = ChannelConfigWindow(
                current_num_channels=self.current_detected_channels,
                current_configs=self.channel_configs,
                parent=self
            )
            self.channels_detected.connect(self.channel_config_window.update_channel_rows)
            self.channel_config_window.config_changed.connect(self.on_channel_config_changed)
            
        self.channel_config_window.show()
        self.channel_config_window.raise_()
        
    def on_raw_format_applied(self, data_type, hex_sep, num_channels):
        self.serial_data_type = data_type
        self.serial_hex_sep = hex_sep
        self.serial_num_channels = num_channels
        
        self.orchestrator.update_serial_params(
            data_type=self.serial_data_type, 
            hex_separator=self.serial_hex_sep,
            num_channels=self.serial_num_channels
        )

    def on_channel_config_changed(self, configs):
        self.channel_configs = configs

    def _connect_signals(self):
        self.orchestrator.data_acquired.connect(self.update_input_plot)
        self.orchestrator.data_processed.connect(self.update_output_plot)
        self.orchestrator.error_occurred.connect(self.show_error)
        
        # Conectar zoom/pan de los plots
        plots = [self.input_plot, self.output_plot, self.combined_plot, self.fft_time_plot]
        for p in plots:
            p.getViewBox().sigRangeChanged.connect(self.on_plot_range_changed)
            
        self.fft_freq_plot.getViewBox().sigRangeChanged.connect(self.on_fft_plot_range_changed)
        
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

    
    def on_y_range_changed(self, *args):
        """Actualiza el rango Y de los gráficos de tiempo."""
        self._apply_y_range_to_all()
    
    def on_x_range_changed(self, *args):
        """Actualiza la cantidad de muestras visibles en X."""
        self._apply_x_range_to_all()
        
    def on_fft_y_range_changed(self, *args):
        """Actualiza el rango Y del gráfico FFT."""
        self._apply_fft_y_range()
        
    def on_fft_x_range_changed(self, *args):
        """Actualiza el rango X del gráfico FFT."""
        self._apply_fft_x_range()
        
    def _set_plot_signals_blocked(self, block):
        plots = [self.input_plot, self.output_plot, self.combined_plot, self.fft_time_plot, self.fft_freq_plot]
        for p in plots:
            p.getViewBox().blockSignals(block)

    def on_plot_range_changed(self, view_box, range_obj):
        x_range, y_range = range_obj
        
        self.spin_x_min.blockSignals(True)
        self.spin_x_max.blockSignals(True)
        self.spin_y_min.blockSignals(True)
        self.spin_y_max.blockSignals(True)
        
        self.spin_x_min.setValue(int(x_range[0]))
        self.spin_x_max.setValue(int(x_range[1]))
        self.spin_y_min.setValue(float(y_range[0]))
        self.spin_y_max.setValue(float(y_range[1]))
        
        self.spin_x_min.blockSignals(False)
        self.spin_x_max.blockSignals(False)
        self.spin_y_min.blockSignals(False)
        self.spin_y_max.blockSignals(False)
        
        self._apply_x_range_to_all()
        self._apply_y_range_to_all()

    def on_fft_plot_range_changed(self, view_box, range_obj):
        x_range, y_range = range_obj
        self.fft_spin_x_min.blockSignals(True)
        self.fft_spin_x_max.blockSignals(True)
        self.fft_spin_y_min.blockSignals(True)
        self.fft_spin_y_max.blockSignals(True)
        self.fft_spin_x_min.setValue(float(x_range[0]))
        self.fft_spin_x_max.setValue(float(x_range[1]))
        self.fft_spin_y_min.setValue(float(y_range[0]))
        self.fft_spin_y_max.setValue(float(y_range[1]))
        self.fft_spin_x_min.blockSignals(False)
        self.fft_spin_x_max.blockSignals(False)
        self.fft_spin_y_min.blockSignals(False)
        self.fft_spin_y_max.blockSignals(False)
        self._apply_fft_x_range()
        self._apply_fft_y_range()

    def _apply_y_range_to_all(self):
        y_min = self.spin_y_min.value()
        y_max = self.spin_y_max.value()
        if y_min >= y_max:
            return
        
        self._set_plot_signals_blocked(True)
        # Actualizar todos los gráficos de tiempo
        self.input_plot.setYRange(y_min, y_max)
        self.output_plot.setYRange(y_min, y_max)
        self.combined_plot.setYRange(y_min, y_max)
        self.fft_time_plot.setYRange(y_min, y_max)
        self._set_plot_signals_blocked(False)
        
    def _apply_fft_y_range(self):
        y_min = self.fft_spin_y_min.value()
        y_max = self.fft_spin_y_max.value()
        if y_min >= y_max:
            return
        self.fft_freq_plot.getViewBox().blockSignals(True)
        self.fft_freq_plot.setYRange(y_min, y_max)
        self.fft_freq_plot.getViewBox().blockSignals(False)

    def _apply_fft_x_range(self):
        x_min = self.fft_spin_x_min.value()
        x_max = self.fft_spin_x_max.value()
        if x_min >= x_max:
            return
        self.fft_freq_plot.getViewBox().blockSignals(True)
        self.fft_freq_plot.setXRange(x_min, x_max)
        self.fft_freq_plot.getViewBox().blockSignals(False)
        
    def _apply_x_range_to_all(self):
        x_min = self.spin_x_min.value()
        x_max = self.spin_x_max.value()
        if x_min >= x_max:
            return
            
        self.display_size = x_max
        self._set_plot_signals_blocked(True)
        # Actualizar el rango del eje X
        self.input_plot.setXRange(x_min, x_max)
        self.output_plot.setXRange(x_min, x_max)
        self.combined_plot.setXRange(x_min, x_max)
        self.fft_time_plot.setXRange(x_min, x_max)
        self._set_plot_signals_blocked(False)
        
    def auto_adjust_y(self):
        try:
            in_data = self.input_buffer[-self.display_size:] if len(self.input_buffer) > 0 else []
            out_data = self.output_buffer[-self.display_size:] if len(self.output_buffer) > 0 else []
            all_data = np.concatenate([d for d in (in_data, out_data) if len(d) > 0])
            
            if len(all_data) == 0:
                return
                
            min_y = float(np.min(all_data))
            max_y = float(np.max(all_data))
            
            if min_y == max_y:
                min_y -= 1.0
                max_y += 1.0
                
            margin = (max_y - min_y) * 0.1
            self.spin_y_min.blockSignals(True)
            self.spin_y_max.blockSignals(True)
            self.spin_y_min.setValue(min_y - margin)
            self.spin_y_max.setValue(max_y + margin)
            self.spin_y_min.blockSignals(False)
            self.spin_y_max.blockSignals(False)
            self._apply_y_range_to_all()
        except Exception as e:
            print(f"Error en auto_adjust_y: {e}")

    def auto_adjust_fft_y(self):
        try:
            max_y = -1e9
            min_y = 1e9
            has_data = False
            for curve in self.fft_freq_curves:
                if curve.isVisible() and curve.yData is not None and len(curve.yData) > 0:
                    c_max = float(np.max(curve.yData))
                    c_min = float(np.min(curve.yData))
                    if c_max > max_y: max_y = c_max
                    if c_min < min_y: min_y = c_min
                    has_data = True
            
            if not has_data:
                return
                
            if min_y == max_y:
                max_y += 1.0
                
            margin = (max_y - min_y) * 0.1
            if margin == 0:
                margin = 0.1
            
            self.fft_spin_y_min.blockSignals(True)
            self.fft_spin_y_max.blockSignals(True)
            self.fft_spin_y_min.setValue(min_y - margin)
            self.fft_spin_y_max.setValue(max_y + margin)
            self.fft_spin_y_min.blockSignals(False)
            self.fft_spin_y_max.blockSignals(False)
            self._apply_fft_y_range()
        except Exception as e:
            print(f"Error en auto_adjust_fft_y: {e}")

    def auto_adjust_fft_x(self):
        try:
            max_x = -1e9
            min_x = 1e9
            has_data = False
            for curve in self.fft_freq_curves:
                if curve.isVisible() and curve.xData is not None and len(curve.xData) > 0:
                    c_max = float(np.max(curve.xData))
                    c_min = float(np.min(curve.xData))
                    if c_max > max_x: max_x = c_max
                    if c_min < min_x: min_x = c_min
                    has_data = True
            
            if not has_data:
                return
                
            if min_x == max_x:
                max_x += 1.0
                
            margin = (max_x - min_x) * 0.05
            if margin == 0:
                margin = 0.1
            
            self.fft_spin_x_min.blockSignals(True)
            self.fft_spin_x_max.blockSignals(True)
            self.fft_spin_x_min.setValue(min_x - margin)
            self.fft_spin_x_max.setValue(max_x + margin)
            self.fft_spin_x_min.blockSignals(False)
            self.fft_spin_x_max.blockSignals(False)
            self._apply_fft_x_range()
        except Exception as e:
            print(f"Error en auto_adjust_fft_x: {e}")
            
    def auto_adjust_x(self):
        self.spin_x_min.blockSignals(True)
        self.spin_x_max.blockSignals(True)
        self.spin_x_min.setValue(0)
        self.spin_x_max.setValue(self.display_size)
        self.spin_x_min.blockSignals(False)
        self.spin_x_max.blockSignals(False)
        self._apply_x_range_to_all()


    def _update_buffer(self, buffer, data):
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        channels = data.shape[1]
        
        if buffer.shape[1] != channels:
            buffer = np.zeros((self.buffer_size, channels))
            
        if len(data) >= self.buffer_size:
            buffer[:] = data[-self.buffer_size:]
        else:
            buffer[:-len(data)] = buffer[len(data):].copy()
            buffer[-len(data):] = data
        return buffer

    def _plot_multi_channel(self, display_data, curves_list, combined_curves_list, plot_widget, combined_plot_widget, base_pen, name_prefix):
        if display_data.ndim == 1:
            display_data = display_data.reshape(-1, 1)
            
        num_channels = min(display_data.shape[1], self.max_channels)
        is_xy_mode = (self.orchestrator.current_source == 'serial' and self.orchestrator.serial_in.mode == 'xy_colon')

        if is_xy_mode:
            # Ocultar curvas adicionales
            for i in range(1, self.max_channels):
                curves_list[i].setData([], [])
                combined_curves_list[i].setData([], [])
                curves_list[i].setVisible(False)
                combined_curves_list[i].setVisible(False)
                
            i = 0
            color = base_pen.color()
            pen = pg.mkPen(color=color, width=base_pen.width())
            curves_list[i].setPen(pen)
            combined_curves_list[i].setPen(pen)
            curves_list[i].setVisible(True)
            combined_curves_list[i].setVisible(True)
                
            if num_channels >= 2:
                sort_idx = np.argsort(display_data[:, 0])
                curves_list[i].setData(x=display_data[sort_idx, 0], y=display_data[sort_idx, 1])
                combined_curves_list[i].setData(x=display_data[sort_idx, 0], y=display_data[sort_idx, 1])
            return

        for i in range(self.max_channels):
            if i >= num_channels:
                curves_list[i].setVisible(False)
                combined_curves_list[i].setVisible(False)
                continue
                
            # Check visibility from configs, default to True if missing
            visible = True
            if i in self.channel_configs:
                visible = self.channel_configs[i].get('visible', True)
                
            curves_list[i].setVisible(visible)
            combined_curves_list[i].setVisible(visible)
            
            if not visible:
                continue
                
            if i in self.channel_configs and 'color' in self.channel_configs[i]:
                color = self.channel_configs[i]['color']
            else:
                color = base_pen.color().lighter(100 + i * 20)
                
            pen = pg.mkPen(color=color, width=base_pen.width())
            curves_list[i].setPen(pen)
            combined_curves_list[i].setPen(pen)
                
            curves_list[i].setData(display_data[:, i])
            combined_curves_list[i].setData(display_data[:, i])

    def _plot_fft_tab(self, display_data):
        if display_data.ndim == 1:
            display_data = display_data.reshape(-1, 1)
            
        num_channels = min(display_data.shape[1], self.max_channels)
        
        # Plot Time Data
        for i in range(self.max_channels):
            if i >= num_channels:
                self.fft_time_curves[i].setVisible(False)
                continue

            visible = True
            if i in self.channel_configs:
                visible = self.channel_configs[i].get('visible', True)
            self.fft_time_curves[i].setVisible(visible)
            if not visible:
                continue
                
            if i in self.channel_configs and 'color' in self.channel_configs[i]:
                color = self.channel_configs[i]['color']
            else:
                color = self.pen_input.color().lighter(100 + i * 20)
                
            pen = pg.mkPen(color=color, width=self.pen_input.width())
            self.fft_time_curves[i].setPen(pen)
            self.fft_time_curves[i].setData(display_data[:, i])
            
        # Plot Frequency Data
        n = display_data.shape[0]
        fs = getattr(self.orchestrator, 'sample_rate', 44100)
        
        if n > 0:
            freqs = np.fft.rfftfreq(n, d=1.0/fs)
            # Handle 0 Hz for log scale
            if len(freqs) > 1:
                freqs[0] = freqs[1] / 10.0
            else:
                freqs[0] = 1e-3
                
            for i in range(self.max_channels):
                if i >= num_channels:
                    self.fft_freq_curves[i].setVisible(False)
                    continue

                visible = True
                if i in self.channel_configs:
                    visible = self.channel_configs[i].get('visible', True)
                self.fft_freq_curves[i].setVisible(visible)
                if not visible:
                    continue
                    
                if i in self.channel_configs and 'color' in self.channel_configs[i]:
                    color = self.channel_configs[i]['color']
                else:
                    color = self.pen_input.color().lighter(100 + i * 20)
                    
                pen = pg.mkPen(color=color, width=self.pen_input.width())
                self.fft_freq_curves[i].setPen(pen)
                
                # Compute FFT explicitly
                fft_mag = np.abs(np.fft.rfft(display_data[:, i])) / n
                
                self.fft_freq_curves[i].setData(x=freqs, y=fft_mag)

    @pyqtSlot(object)
    def update_input_plot(self, data):
        if data.ndim == 1:
            data = data.reshape(-1, 1)
        num_channels = data.shape[1]
        if num_channels > self.current_detected_channels:
            self.current_detected_channels = num_channels
            self.channels_detected.emit(num_channels)
            
        self.input_buffer = self._update_buffer(self.input_buffer, data)
        display_data = self.input_buffer[-self.display_size:]
        self._plot_multi_channel(display_data, self.input_curves, self.combined_input_curves, self.input_plot, self.combined_plot, self.pen_input, '<span style="color: #f0e68c;">●</span> Entrada')
        self._plot_fft_tab(display_data)

    @pyqtSlot(object)
    def update_output_plot(self, data):
        self.output_buffer = self._update_buffer(self.output_buffer, data)
        display_data = self.output_buffer[-self.display_size:]
        self._plot_multi_channel(display_data, self.output_curves, self.combined_output_curves, self.output_plot, self.combined_plot, self.pen_output, '<span style="color: #00d9ff;">●</span> Salida')

    def on_load_plugin_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Plugin", "plugins", "Python Files (*.py)"
        )
        if file_path:
            self.load_plugin_file(file_path)

    def load_plugin_file(self, path):
        # Cerrar ventana anterior si existe
        if self.plugin_window is not None:
            self.plugin_window.close()
            self.plugin_window = None
            
        # Cargar nuevo plugin vía orquestador
        plugin_ui = self.orchestrator.load_plugin(path)
        if plugin_ui:
            self._plugin_ui = plugin_ui
            self.current_plugin_name = os.path.basename(path)
            self.btn_open_plugin_panel.setEnabled(True)
            self.open_plugin_window(plugin_ui)
            self.statusBar().showMessage(f"Plugin cargado: {os.path.basename(path)}")
        else:
            self.show_error(f"No se pudo cargar el plugin: {os.path.basename(path)}")

    def show_error(self, message):
        """Muestra un diálogo de error y actualiza la barra de estado."""
        self.statusBar().showMessage(f"ERROR: {message}")
        QMessageBox.critical(self, "Error de Pipeline", message)

    def closeEvent(self, event):
        self.orchestrator.stop_pipeline()
        if self.plugin_window is not None:
            self.plugin_window.close()
        event.accept()

    def open_plugin_window(self, plugin_ui: QWidget):
        """Abre la UI del plugin en una ventana separada."""
        if self.plugin_window is not None:
            self.plugin_window.close()
            self.plugin_window = None
        
        self.plugin_window = QDialog(self)
        self.plugin_window.setWindowTitle(f"Plugin: {self.current_plugin_name}")
        self.plugin_window.setMinimumSize(400, 300)
        self.plugin_window.setModal(False)
        self.plugin_window.finished.connect(self._on_plugin_window_closed)
        
        layout = QVBoxLayout(self.plugin_window)
        layout.addWidget(plugin_ui)
        
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.plugin_window.close)
        layout.addWidget(close_btn)
        
        self.plugin_window.show()

    def _toggle_plugin_window(self):
        """Abre o cierra la ventana del plugin según su estado."""
        if self.plugin_window is None or not self.plugin_window.isVisible():
            if self._plugin_ui:
                self.open_plugin_window(self._plugin_ui)
        else:
            self.plugin_window.close()

    def _on_plugin_window_closed(self, result):
        """Limpia la referencia cuando se cierra la ventana del plugin."""
        self.plugin_window = None

    def export_to_csv(self):
        """Exporta los datos actuales del plot a un archivo CSV."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Datos como CSV", "export_data.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return
            
        try:
            # Obtener datos mostrados
            is_xy_mode = (self.orchestrator.current_source == 'serial' and self.orchestrator.serial_in.mode == 'xy_colon')
            
            if is_xy_mode:
                data = self.input_buffer[-self.display_size:]
                if data.shape[1] >= 2:
                    header = "X,Y"
                else:
                    header = "Data"
            else:
                data = self.output_buffer[-self.display_size:]
                header = ",".join([f"Channel_{i}" for i in range(data.shape[1])])
                
            np.savetxt(file_path, data, delimiter=",", header=header, comments="")
            self.statusBar().showMessage(f"Datos guardados exitosamente en {os.path.basename(file_path)}")
            
        except Exception as e:
            self.show_error(f"Error al guardar CSV: {e}")
