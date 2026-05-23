import serial
import serial.tools.list_ports
import numpy as np
import threading
import queue
import time
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal
from core.inputs.serial_strategies import CsvStrategy, RawStrategy

class SerialInput(QObject):
    """Adquisición de datos desde puerto serial (Arduino, ESP32, etc.)."""
    data_updated = pyqtSignal(np.ndarray)  # Señal emitida cuando llega un dato
    
    def __init__(self, port=None, baudrate=115200, input_queue=None, chunk_size=1024, emit_interval=0.05):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.running = False
        self.chunk_size = chunk_size  # Tamaño fijo de chunk para consistencia
        self.emit_interval = emit_interval  # Intervalo mínimo entre emisiones (segundos)
        self.data_buffer = deque(maxlen=chunk_size)  # Ventana deslizante de chunk_size
        self.chunk_array = None # Pre-allocado dinámicamente según canales
        self.thread = None
        self.input_queue = input_queue  # queue.Queue for plugin pipeline
        self._last_emit_time = 0  # Para throttling
        
        # Estrategia por defecto
        self.strategy = CsvStrategy()
        self.mode = 'csv' # 'csv' o 'raw'
        self.data_type = 'int16'
        self.hex_separator = ''

    def set_queue(self, queue):
        """Set the input queue for plugin pipeline integration."""
        self.input_queue = queue

    @staticmethod
    def get_available_ports():
        """Lista los puertos seriales disponibles en el sistema."""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def update_config(self, port=None, baudrate=None, mode=None, data_type=None, hex_separator=None):
        """Actualiza los parámetros de conexión y la estrategia."""
        if port is not None: self.port = port
        if baudrate is not None: self.baudrate = int(baudrate)
        if mode is not None: self.mode = mode
        if data_type is not None: self.data_type = data_type
        if hex_separator is not None: self.hex_separator = hex_separator

        if self.mode == 'csv':
            self.strategy = CsvStrategy()
        else:
            self.strategy = RawStrategy(data_type=self.data_type, hex_separator=self.hex_separator)

    def start(self):
        """Inicia el hilo de lectura serial."""
        if not self.port:
            print("Error: No se ha especificado un puerto serial.")
            return False
            
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.running = True
            self.data_buffer.clear()
            self.chunk_array = None
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            print(f"Puerto Serial {self.port} abierto a {self.baudrate} bps.")
            return True
        except Exception as e:
            print(f"Error abriendo puerto serial {self.port}: {e}")
            return False

    def stop(self):
        """Detiene la lectura serial."""
        self.running = False
        if self.thread:
            self.thread.join(1.0)
        if self.ser:
            self.ser.close()
            self.ser = None

    def _read_loop(self):
        """Bucle de lectura que alimenta el buffer y emite señales."""
        leftover = b''
        while self.running:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    raw_data = self.ser.read(self.ser.in_waiting)
                    if not raw_data:
                        continue
                    
                    data_to_parse = leftover + raw_data
                    parsed_data, leftover = self.strategy.parse(data_to_parse)
                    
                    if parsed_data.size > 0:
                        # parsed_data is (num_samples, num_channels)
                        for row in parsed_data:
                            self.data_buffer.append(row)
                        
                        # Throttling: solo emitir cada emit_interval segundos
                        current_time = time.perf_counter()
                        if current_time - self._last_emit_time >= self.emit_interval:
                            self._last_emit_time = current_time
                            
                            # Crear y emitir chunk
                            chunk = self._make_chunk()
                            
                            # Emitir para graficar
                            self.data_updated.emit(chunk)
                            
                            # Put into pipeline queue for plugin processing
                            if self.input_queue:
                                try:
                                    self.input_queue.put_nowait(chunk)
                                except queue.Full:
                                    pass

            except Exception as e:
                print(f"Error en lectura serial: {e}")
                break

    def _make_chunk(self) -> np.ndarray:
        """Crea un chunk de tamaño fijo usando los datos del buffer (optimizado)."""
        buffer_len = len(self.data_buffer)
        
        if buffer_len == 0:
            if self.chunk_array is not None:
                return self.chunk_array
            return np.zeros((self.chunk_size, 1), dtype=np.float32)
            
        num_channels = max(len(row) for row in self.data_buffer)
        
        if self.chunk_array is None or self.chunk_array.shape[1] != num_channels:
            self.chunk_array = np.zeros((self.chunk_size, num_channels), dtype=np.float32)
            
        # Limpiar array
        self.chunk_array.fill(0)
        
        padded_list = []
        for row in self.data_buffer:
            if len(row) < num_channels:
                padded_list.append(np.pad(row, (0, num_channels - len(row)), constant_values=np.nan))
            else:
                padded_list.append(row[:num_channels])
        
        if buffer_len >= self.chunk_size:
            start_idx = buffer_len - self.chunk_size
            self.chunk_array[:] = padded_list[start_idx:]
        else:
            start_idx = self.chunk_size - buffer_len
            self.chunk_array[start_idx:] = padded_list
            
        return self.chunk_array

    def get_data(self) -> np.ndarray:
        """Retorna el buffer actual como array numpy de tamaño fijo."""
        return self._make_chunk()
