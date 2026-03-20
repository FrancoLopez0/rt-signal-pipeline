import sounddevice as sd
import numpy as np

class AudioInput:
    """Adquisición de audio desde el hardware del sistema."""
    def __init__(self, sample_rate=44100, chunk_size=1024, channels=1):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.buffer = np.zeros(0, dtype=np.float32)

    def start(self):
        """Inicia el stream de audio."""
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.chunk_size,
            channels=self.channels,
            callback=self._callback
        )
        self.stream.start()

    def stop(self):
        """Detiene el stream de audio."""
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()

    def _callback(self, indata, frames, time, status):
        """Callback llamado por sounddevice cada vez que hay datos."""
        if status:
            print(f"Audio Input Status: {status}")
        # Guardamos en un buffer interno plano
        self.buffer = np.append(self.buffer, indata.flatten())

    def get_chunk(self, chunk_size: int) -> np.ndarray:
        """Extrae un bloque de datos del buffer acumulado."""
        if len(self.buffer) < chunk_size:
            # Si no hay suficientes datos, rellenamos con silencio
            # Esto evita que el pipeline se bloquee
            return np.zeros(chunk_size, dtype=np.float32)
        
        chunk = self.buffer[:chunk_size]
        self.buffer = self.buffer[chunk_size:]
        return chunk.astype(np.float32)
