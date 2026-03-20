import queue
import importlib.util
import os
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from core.threads import AcquisitionWorker, ProcessingWorker, OutputWorker
from core.inputs.generator_in import SignalGenerator
from core.inputs.audio_in import AudioInput
from core.inputs.serial_in import SerialInput

class Orchestrator(QObject):
    """
    Presenter/Orquestador: El cerebro que conecta la UI con los Workers.
    Gestiona la carga dinámica de plugins y el ciclo de vida de los hilos.
    """
    data_acquired = pyqtSignal(object)  # Datos originales (Input)
    data_processed = pyqtSignal(object) # Datos procesados (Output)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        
        # Parámetros base
        self.sample_rate = 44100
        self.chunk_size = 1024
        
        # Colas seguras para intercambio de datos entre hilos
        self.input_queue = queue.Queue(maxsize=10)
        self.output_queue = queue.Queue(maxsize=10)
        
        # Instancias de Input
        self.generator = SignalGenerator(self.sample_rate)
        self.audio_in = AudioInput(self.sample_rate, self.chunk_size)
        self.serial_in = SerialInput()
        
        self.current_source = 'generator'
        
        # Referencias a workers y threads
        self.workers = {}
        self.threads = {}
        
        # Plugin actual
        self.current_plugin = None
        self.current_plugin_name = None

    def set_input_source(self, source_type: str):
        """Cambia la fuente de entrada: 'generator', 'audio', 'serial'."""
        self.current_source = source_type
        
        # Detener fuentes previas si es necesario
        self.audio_in.stop()
        self.serial_in.stop()
        
        source_func = None
        if source_type == 'generator':
            source_func = self.generator.generate_chunk
        elif source_type == 'audio':
            self.audio_in.start()
            source_func = self.audio_in.get_chunk
        elif source_type == 'serial':
            self.serial_in.start()
            source_func = self.serial_in.get_chunk
            
        # Actualizar el worker de adquisición si está corriendo
        if "acquisition" in self.workers and source_func:
            self.workers["acquisition"].source_func = source_func

    def toggle_audio_output(self, enabled: bool):
        """Activa o desactiva la salida de audio por hardware."""
        if "output" in self.workers:
            self.workers["output"].toggle_audio(enabled)

    def load_plugin(self, plugin_path: str):
        """Carga dinámicamente un plugin desde su ruta de archivo."""
        try:
            module_name = os.path.basename(plugin_path).replace(".py", "")
            spec = importlib.util.spec_from_file_location(module_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Instanciar el plugin a través de su clase 'Plugin'
            self.current_plugin = module.Plugin()
            self.current_plugin_name = module_name
            
            # Obtener UI y DSP
            ui = self.current_plugin.get_ui()
            dsp = self.current_plugin.get_dsp()
            
            # Conectar señales de la UI al DSP para actualización de parámetros
            ui.parameter_changed.connect(lambda name, val: dsp.update_parameter(name, val))
            
            # Actualizar el Worker de procesamiento si está activo
            if "processing" in self.workers:
                self.workers["processing"].set_plugin_dsp(dsp)
                
            return ui
            
        except Exception as e:
            self.error_occurred.emit(f"Error cargando plugin: {str(e)}")
            return None

    def start_pipeline(self):
        """Arranca todos los hilos del pipeline."""
        # 1. Acquisition Thread
        self.set_input_source(self.current_source)
        source_func = None
        if self.current_source == 'generator': source_func = self.generator.generate_chunk
        elif self.current_source == 'audio': source_func = self.audio_in.get_chunk
        elif self.current_source == 'serial': source_func = self.serial_in.get_chunk

        self.workers["acquisition"] = AcquisitionWorker(source_func, self.sample_rate, self.chunk_size)
        self.workers["acquisition"].out_queue = self.input_queue
        
        # 2. Processing Thread
        self.workers["processing"] = ProcessingWorker(self.input_queue, self.output_queue)
        if self.current_plugin:
            self.workers["processing"].set_plugin_dsp(self.current_plugin.get_dsp())
            
        # 3. Output/Consumer Thread
        self.workers["output"] = OutputWorker(self.output_queue, self.sample_rate, self.chunk_size)
        
        # Setup signals and start threads
        for name, worker in self.workers.items():
            self.threads[name] = QThread()
            worker.moveToThread(self.threads[name])
            
            # Conexión de inicio/parada
            self.threads[name].started.connect(worker.run)
            worker.finished.connect(self.threads[name].quit)
            worker.error.connect(self.error_occurred)
            
            # Conectar señales de datos a la UI (vía Orquestador)
            if name == "acquisition":
                worker.data_ready.connect(self.data_acquired)
            elif name == "processing":
                worker.processed_ready.connect(self.data_processed)
                
            self.threads[name].start()

    def stop_pipeline(self):
        """Detiene de forma segura todos los hilos."""
        # 1. Señalizar a los workers que deben parar
        for name, worker in self.workers.items():
            worker.stop()
            
        # 2. Esperar a que los hilos terminen grácilmente
        for name, thread in self.threads.items():
            if thread.isRunning():
                thread.quit()
                if not thread.wait(2000): # Esperar hasta 2s
                    print(f"Warning: Thread {name} did not stop gracefully, terminating.")
                    thread.terminate()
                    thread.wait()
                
        self.workers.clear()
        self.threads.clear()
        
        # 3. Limpiar colas para evitar que datos antiguos queden atrapados
        try:
            while not self.input_queue.empty(): self.input_queue.get_nowait()
            while not self.output_queue.empty(): self.output_queue.get_nowait()
        except Exception:
            pass
