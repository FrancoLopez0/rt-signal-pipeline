import time
import queue
import numpy as np
from PyQt6.QtCore import QObject, QThread, pyqtSignal

class PipelineWorker(QObject):
    """Clase base para workers del pipeline."""
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._running = False

    def stop(self):
        self._running = False

class AcquisitionWorker(PipelineWorker):
    """Hilo de adquisición de datos (Input)."""
    data_ready = pyqtSignal(np.ndarray)

    def __init__(self, source_func, sample_rate=44100, chunk_size=1024):
        super().__init__()
        self.source_func = source_func
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.out_queue = None

    def run(self):
        self._running = True
        interval = self.chunk_size / self.sample_rate
        
        while self._running:
            start_time = time.perf_counter()
            try:
                data = self.source_func(self.chunk_size)
                if self.out_queue:
                    try:
                        self.out_queue.put_nowait(data)
                    except queue.Full:
                        pass
                self.data_ready.emit(data)
            except Exception as e:
                self.error.emit(str(e))
                break
                
            elapsed = time.perf_counter() - start_time
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)
            
        self.finished.emit()

class ProcessingWorker(PipelineWorker):
    """Hilo de procesamiento DSP (Plugin)."""
    processed_ready = pyqtSignal(np.ndarray)

    def __init__(self, in_queue, out_queue):
        super().__init__()
        self.in_queue = in_queue
        self.out_queue = out_queue
        self.plugin_dsp = None

    def set_plugin_dsp(self, dsp):
        self.plugin_dsp = dsp

    def run(self):
        self._running = True
        while self._running:
            try:
                # Timeout pequeño para responder rápido a señales de parada
                data = self.in_queue.get(timeout=0.05)
                
                if self.plugin_dsp:
                    processed_data = self.plugin_dsp.process(data)
                else:
                    processed_data = data 
                
                if self.out_queue:
                    try:
                        self.out_queue.put_nowait(processed_data)
                    except queue.Full:
                        pass
                self.processed_ready.emit(processed_data)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.error.emit(str(e))
                break
                
        self.finished.emit()

class OutputWorker(PipelineWorker):
    """Hilo de salida: Reproducción de audio basada en callback de hardware."""
    def __init__(self, in_queue, sample_rate=44100, chunk_size=1024):
        super().__init__()
        self.in_queue = in_queue
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_out_enabled = False
        self.stream = None
        # Pequeño buffer circular interno para suavizar el jitter de las colas
        self.playback_buffer = np.zeros(0, dtype=np.float32)

    def toggle_audio(self, enabled):
        """Activa/Desactiva la salida de audio por hardware."""
        self.audio_out_enabled = enabled
        if enabled:
            import sounddevice as sd
            # Usamos un callback para que el hardware pida datos cuando esté listo
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                channels=1,
                dtype='float32',
                callback=self._audio_callback
            )
            self.stream.start()
        elif self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def _audio_callback(self, outdata, frames, time, status):
        """Callback del hardware de sonido. Se ejecuta en un hilo de alta prioridad."""
        if status:
            print(f"Audio Output Status: {status}")
            
        # Intentamos obtener datos de nuestro buffer interno o de la cola
        try:
            # Si el buffer interno está vacío, intentamos llenarlo de la cola
            while len(self.playback_buffer) < frames:
                chunk = self.in_queue.get_nowait()
                self.playback_buffer = np.append(self.playback_buffer, chunk)
        except queue.Empty:
            pass

        # Llenar outdata
        if len(self.playback_buffer) >= frames:
            outdata[:frames, 0] = self.playback_buffer[:frames]
            self.playback_buffer = self.playback_buffer[frames:]
        else:
            # Underflow: Rellenar con silencio si no hay datos suficientes
            outdata.fill(0)

    def run(self):
        """Bucle de control. Mantiene el pipeline fluido consumiendo la cola."""
        self._running = True
        while self._running:
            if not self.audio_out_enabled:
                try:
                    # Si el audio está apagado, vaciamos la cola para que no se bloquee el pipeline
                    self.in_queue.get(timeout=0.05)
                except queue.Empty:
                    pass
            else:
                # Si el audio está encendido, el callback se encarga de vaciar la cola
                time.sleep(0.1)
                
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.finished.emit()
