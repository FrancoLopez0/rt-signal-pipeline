import serial
import serial.tools.list_ports
import numpy as np
import threading
import queue
import time
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal

class SerialInput(QObject):
    """Adquisición de datos desde puerto serial (Arduino, ESP32, etc.)."""
    data_updated = pyqtSignal(np.ndarray)  # Señal emitida cuando llega un dato
    
    def __init__(self, port=None, baudrate=115200, mode='raw', input_queue=None, chunk_size=1024, emit_interval=0.05):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.mode = mode  # 'raw' para audio, 'fft' para x,y
        self.ser = None
        self.running = False
        self.chunk_size = chunk_size  # Tamaño fijo de chunk para consistencia
        self.emit_interval = emit_interval  # Intervalo mínimo entre emisiones (segundos)
        self.data_buffer = deque(maxlen=chunk_size)  # Ventana deslizante de chunk_size
        self.chunk_array = np.zeros(chunk_size, dtype=np.float32)  # Pre-allocado para eficiencia
        self.thread = None
        self.input_queue = input_queue  # queue.Queue for plugin pipeline
        self._last_emit_time = 0  # Para throttling

    def set_queue(self, queue):
        """Set the input queue for plugin pipeline integration."""
        self.input_queue = queue

    @staticmethod
    def get_available_ports():
        """Lista los puertos seriales disponibles en el sistema."""
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def update_config(self, port=None, baudrate=None):
        """Actualiza los parámetros de conexión."""
        if port is not None: self.port = port
        if baudrate is not None: self.baudrate = int(baudrate)

    def start(self):
        """Inicia el hilo de lectura serial."""
        if not self.port:
            print("Error: No se ha especificado un puerto serial.")
            return False
            
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.running = True
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
        while self.running:
            try:
                if self.ser and self.ser.in_waiting > 0:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    
                    try:
                        # Parsear valor del CSV
                        value = float(line)
                        print(f"[Serial] Dato: {value}")
                        
                        # Agregar al buffer (descarte automático de antiguos cuando lleno)
                        self.data_buffer.append(value)
                        
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

                    except ValueError:
                        continue
            except Exception as e:
                print(f"Error en lectura serial: {e}")
                break

    def _make_chunk(self) -> np.ndarray:
        """Crea un chunk de tamaño fijo usando los datos del buffer (optimizado)."""
        buffer_len = len(self.data_buffer)
        
        if buffer_len == 0:
            return self.chunk_array  # Retornar array de ceros pre-allocado
        
        # Limpiar array y copiar datos directamente
        self.chunk_array.fill(0)
        
        if buffer_len >= self.chunk_size:
            # Buffer tiene suficientes datos - copiar últimos chunk_size elementos
            # Usar iterador para eficiencia
            start_idx = buffer_len - self.chunk_size
            for i, val in enumerate(list(self.data_buffer)[start_idx:]):
                self.chunk_array[i] = val
        else:
            # Buffer tiene menos datos, centrar en el chunk
            start_idx = self.chunk_size - buffer_len
            for i, val in enumerate(self.data_buffer):
                self.chunk_array[start_idx + i] = val
        
        return self.chunk_array

    def get_data(self) -> np.ndarray:
        """Retorna el buffer actual como array numpy de tamaño fijo."""
        return self._make_chunk()
