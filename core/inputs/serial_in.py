import serial
import serial.tools.list_ports
import numpy as np
import threading
from collections import deque
from PyQt6.QtCore import QObject, pyqtSignal

class SerialInput(QObject):
    """Adquisición de datos desde puerto serial (Arduino, ESP32, etc.)."""
    data_updated = pyqtSignal(np.ndarray)  # Señal emitida cuando llega un dato
    
    def __init__(self, port=None, baudrate=115200, mode='raw'):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.mode = mode # 'raw' para audio, 'fft' para x,y
        self.ser = None
        self.running = False
        self.data_buffer = deque(maxlen=1024)  # Ventana deslizante de 1024 valores
        self.thread = None

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
                        
                        # Agregar al buffer (descarte automático de antiguos)
                        self.data_buffer.append(value)
                        
                        # Emitir señal con buffer completo para graficar
                        self.data_updated.emit(self.get_data())
                        
                    except ValueError:
                        continue
            except Exception as e:
                print(f"Error en lectura serial: {e}")
                break

    def get_data(self) -> np.ndarray:
        """Retorna el buffer actual como array numpy."""
        return np.array(self.data_buffer, dtype=np.float32)
