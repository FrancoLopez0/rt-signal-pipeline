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

    def set_input_source(self, source_type: str, force_restart=False):
        """Cambia la fuente de entrada. Solo reinicia el worker si el tipo cambia o se fuerza."""
        is_same_type = self.current_source == source_type
        self.current_source = source_type
        
        # Si es el mismo tipo y no forzamos, no hacemos nada (el generador se actualiza solo)
        if is_same_type and not force_restart and "acquisition" in self.workers:
            return

        # 1. Detener el worker de adquisición actual si existe
        self._stop_worker("acquisition")

        # 2. Detener hardware previo
        self.audio_in.stop()
        self.serial_in.stop()
        
        source_func = None
        if source_type == 'generator':
            source_func = self.generator.generate_chunk
        elif source_type == 'audio':
            self.audio_in.start()
            source_func = self.audio_in.get_chunk
        elif source_type == 'serial':
            # No iniciar automáticamente - el botón "Conectar" lo maneja
            # Solo actualizar el flag interno
            self.current_source = 'serial'
            return

        # 3. Arrancar el worker si el pipeline está activo
        if source_func and "processing" in self.workers:
            self._start_acquisition_worker(source_func)

    def update_serial_params(self, port=None, baudrate=None):
        """Actualiza la configuración serial."""
        self.serial_in.update_config(port, baudrate)
        # Si ya estábamos en serial, reiniciamos para aplicar cambios
        if self.current_source == 'serial' and "acquisition" in self.workers:
            self.set_input_source('serial')

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
        self.stop_pipeline() # Asegurar estado limpio

        # 1. Processing Thread
        self.workers["processing"] = ProcessingWorker(self.input_queue, self.output_queue)
        if self.current_plugin:
            self.workers["processing"].set_plugin_dsp(self.current_plugin.get_dsp())
            
        # 2. Output/Consumer Thread
        self.workers["output"] = OutputWorker(self.output_queue, self.sample_rate, self.chunk_size)
        
        # Start core workers
        for name in ["processing", "output"]:
            worker = self.workers[name]
            self.threads[name] = QThread()
            worker.moveToThread(self.threads[name])
            self.threads[name].started.connect(worker.run)
            worker.finished.connect(self.threads[name].quit)
            worker.error.connect(self.error_occurred)
            if name == "processing":
                worker.processed_ready.connect(self.data_processed)
            self.threads[name].start()

        # 3. Acquisition Thread (via set_input_source logic)
        self.set_input_source(self.current_source)

    def _start_acquisition_worker(self, source_func):
        worker = AcquisitionWorker(source_func, self.sample_rate, self.chunk_size)
        worker.out_queue = self.input_queue
        thread = QThread()
        worker.moveToThread(thread)
        
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.error.connect(self.error_occurred)
        worker.data_ready.connect(self.data_acquired)
        
        self.workers["acquisition"] = worker
        self.threads["acquisition"] = thread
        thread.start()

    def _stop_worker(self, name):
        if name in self.workers:
            worker = self.workers[name]
            thread = self.threads[name]
            worker.stop()
            thread.quit()
            if not thread.wait(1000):
                thread.terminate()
                thread.wait()
            del self.workers[name]
            del self.threads[name]

    def stop_pipeline(self):
        """Detiene de forma segura todos los hilos."""
        for name in list(self.workers.keys()):
            self._stop_worker(name)
            
        self.audio_in.stop()
        self.serial_in.stop()
        
        # Limpiar colas
        try:
            while not self.input_queue.empty(): self.input_queue.get_nowait()
            while not self.output_queue.empty(): self.output_queue.get_nowait()
        except Exception:
            pass
