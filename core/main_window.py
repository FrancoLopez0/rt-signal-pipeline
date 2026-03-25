import os
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QFileDialog, QLabel, QFrame, QSplitter, 
                             QMessageBox, QComboBox, QCheckBox, QSlider)
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
        
        # Buffer para suavizado espectral (Persistancia)
        self.fft_smoothed = None
        self.fft_alpha = 0.15 # Factor de suavizado (0.0 a 1.0)
        
        self._init_ui()
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
        
        # --- PANEL DE GRÁFICOS ---
        graph_container = QWidget()
        graph_layout = QVBoxLayout(graph_container)
        
        # Configuración de pyqtgraph
        pg.setConfigOptions(antialias=True)
        
        # Gráficos de Tiempo
        self.input_plot = pg.PlotWidget(title="Entrada (Tiempo) - Trigger: Zero Crossing")
        self.input_curve = self.input_plot.plot(pen='y')
        self.input_plot.setYRange(-1.1, 1.1)
        self.input_plot.showGrid(x=True, y=True)
        graph_layout.addWidget(self.input_plot)
        
        self.output_plot = pg.PlotWidget(title="Procesada (Tiempo)")
        self.output_curve = self.output_plot.plot(pen='c')
        self.output_plot.setYRange(-1.1, 1.1)
        self.output_plot.showGrid(x=True, y=True)
        graph_layout.addWidget(self.output_plot)
        
        # Gráfico de Frecuencia (FFT)
        self.fft_plot = pg.PlotWidget(title="Espectro de Frecuencia (FFT / x,y)")
        self.fft_curve = self.fft_plot.plot(pen='m')
        self.fft_plot.setLogMode(x=True, y=False)
        self.fft_plot.showGrid(x=True, y=True)
        graph_layout.addWidget(self.fft_plot)
        
        # --- PANEL DE CONTROL (SIDEBAR) ---
        self.sidebar = QFrame()
        self.sidebar.setFrameShape(QFrame.Shape.StyledPanel)
        self.sidebar.setMinimumWidth(300)
        sidebar_layout = QVBoxLayout(self.sidebar)
        
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

    def toggle_trigger(self):
        self.trigger_enabled = self.btn_trigger.isChecked()
        self.btn_trigger.setText(f"Trigger: {'ON' if self.trigger_enabled else 'OFF'}")

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
        self.input_buffer = np.roll(self.input_buffer, -len(data))
        self.input_buffer[-len(data):] = data
        
        display_data = self._apply_trigger(self.input_buffer)
        self.input_curve.setData(display_data)

    @pyqtSlot(np.ndarray)
    def update_serial_plot(self, data):
        """Actualiza el gráfico de entrada con datos del serial (deque)."""
        self.input_curve.setData(data)
        # También actualizar el buffer interno para mantener sincronía
        self.input_buffer = np.roll(self.input_buffer, -len(data))
        self.input_buffer[-len(data):] = data

    @pyqtSlot(object)
    def update_output_plot(self, data):
        # Actualizar buffer de tiempo
        self.output_buffer = np.roll(self.output_buffer, -len(data))
        self.output_buffer[-len(data):] = data
        
        # Graficar tiempo con trigger
        display_data = self._apply_trigger(self.output_buffer)
        self.output_curve.setData(display_data)
        
        # Graficar FFT (si no estamos en modo serial FFT x,y)
        if self.orchestrator.current_source != 'serial' or self.orchestrator.serial_in.mode == 'raw':
            self.update_fft(display_data)
        else:
            # En modo serial FFT, los datos 'data' ya son x,y
            # Extraer x,y de los objetos recibidos
            x = []
            y = []
            if isinstance(data, np.ndarray):
                for d in data:
                    if isinstance(d, tuple) and len(d) >= 2:
                        x.append(d[0])
                        y.append(d[1])
            if x: self.fft_curve.setData(x, y)

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
            
            # 6. Fijar rango Y para estabilidad visual
            self.fft_plot.setYRange(-60, 40)
            
        except Exception as e:
            print(f"Error en FFT: {e}")

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
