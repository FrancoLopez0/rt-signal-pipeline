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
                    self.out_queue.put(data)
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
                    self.out_queue.put(processed_data)
                self.processed_ready.emit(processed_data)
                
            except queue.Empty:
                continue
            except Exception as e:
                self.error.emit(str(e))
                break
                
        self.finished.emit()

class OutputWorker(PipelineWorker):
    """Hilo de salida: Reproducción de audio y consumo final."""
    def __init__(self, in_queue, sample_rate=44100, chunk_size=1024):
        super().__init__()
        self.in_queue = in_queue
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.audio_out_enabled = False
        self.stream = None

    def toggle_audio(self, enabled):
        """Activa/Desactiva la salida de audio por hardware."""
        self.audio_out_enabled = enabled
        if enabled:
            import sounddevice as sd
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                channels=1,
                dtype='float32'
            )
            self.stream.start()
        elif self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def run(self):
        self._running = True
        while self._running:
            try:
                data = self.in_queue.get(timeout=0.05)
                # Si el audio está habilitado, escribir en el stream de hardware
                if self.audio_out_enabled and self.stream:
                    # Nos aseguramos de que el array tenga la forma correcta para sd.write
                    # sounddevice espera (frames, channels)
                    audio_data = data.reshape(-1, 1).astype(np.float32)
                    self.stream.write(audio_data)
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.error.emit(f"Error en Salida Audio: {str(e)}")
                break
                
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.finished.emit()
