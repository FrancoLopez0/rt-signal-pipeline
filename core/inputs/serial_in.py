import serial
import numpy as np
import threading
import queue

class SerialInput:
    """Adquisición de datos desde puerto serial (Arduino, ESP32, etc.)."""
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, mode='raw'):
        self.port = port
        self.baudrate = baudrate
        self.mode = mode # 'raw' para audio, 'fft' para x,y
        self.ser = None
        self.running = False
        self.data_queue = queue.Queue()
        self.thread = None

    def start(self):
        """Inicia el hilo de lectura serial."""
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            print(f"Puerto Serial {self.port} abierto correctamente.")
        except Exception as e:
            print(f"Error abriendo puerto serial: {e}")

    def stop(self):
        """Detiene la lectura serial."""
        self.running = False
        if self.thread:
            self.thread.join(1.0)
        if self.ser:
            self.ser.close()

    def _read_loop(self):
        """Bucle de lectura que alimenta la cola de datos."""
        while self.running:
            if self.ser and self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                
                try:
                    # Suponemos formato CSV: valor o x,y
                    values = [float(v) for v in line.split(',')]
                    if self.mode == 'fft' and len(values) >= 2:
                        # Guardamos par x,y (freq, amp)
                        self.data_queue.put(tuple(values[:2]))
                    else:
                        # Guardamos valor único (audio raw)
                        self.data_queue.put(values[0])
                except ValueError:
                    continue

    def get_chunk(self, chunk_size: int) -> np.ndarray:
        """Extrae un bloque de datos de la cola serial."""
        data = []
        for _ in range(chunk_size):
            try:
                # Si no hay datos, salimos para no bloquear
                val = self.data_queue.get_nowait()
                data.append(val)
            except queue.Empty:
                break
        
        if not data:
            return np.zeros(chunk_size, dtype=np.float32)
        
        # Si sobran datos, los dejamos; si faltan, rellenamos con ceros
        if len(data) < chunk_size:
            data.extend([0.0] * (chunk_size - len(data)))
            
        return np.array(data, dtype=np.float32 if self.mode == 'raw' else object)
