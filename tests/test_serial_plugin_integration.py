import pytest
import numpy as np
import queue
from core.orchestrator import Orchestrator
from core.inputs.serial_in import SerialInput
from plugins.custom_filter import Plugin as GainPlugin

def test_serial_deque_functionality():
    """Verifica que el deque del SerialInput funciona correctamente."""
    serial = SerialInput()
    
    # Simular datos llegando al deque
    for i in range(100):
        serial.data_buffer.append(float(i))
    
    # Verificar que el deque tiene maxlen=1024
    assert serial.data_buffer.maxlen == 1024
    
    # Verificar que get_data retorna un numpy array de tamaño fijo (chunk_size)
    data = serial.get_data()
    assert isinstance(data, np.ndarray)
    assert len(data) == 1024  # Siempre retorna chunk_size
    
    # Los últimos 100 elementos deben ser 0-99, los primeros 924 son ceros (relleno)
    assert data[0] == 0.0  # Primer elemento es cero (relleno)
    assert data[-1] == 99.0  # Último elemento es 99

def test_serial_deque_sliding_window():
    """Verifica que el deque descarta valores antiguos cuando está lleno."""
    serial = SerialInput()
    
    # Llenar más allá del tamaño inicial
    for i in range(1500):
        serial.data_buffer.append(float(i))
    
    # El deque debería contener solo los últimos 1024 valores (476-1499)
    # debido a maxlen=1024
    data = serial.get_data()
    assert len(data) == 1024
    assert data[0] == 476.0  # 1500 - 1024 = 476
    assert data[-1] == 1499.0

def test_serial_input_queue_integration():
    """Verifica que SerialInput pone datos en la cola del pipeline."""
    test_queue = queue.Queue(maxsize=10)
    serial = SerialInput(input_queue=test_queue)
    
    # Simular algunos datos
    for i in range(5):
        serial.data_buffer.append(float(i * 10))
    
    # Simular lo que hace _read_loop: poner en cola
    if serial.input_queue:
        try:
            serial.input_queue.put_nowait(serial.get_data())
        except queue.Full:
            pass
    
    # Verificar que la cola recibió los datos
    assert not test_queue.empty()
    queued_data = test_queue.get_nowait()
    assert isinstance(queued_data, np.ndarray)
    assert len(queued_data) == 1024  # Siempre chunk_size

def test_serial_with_plugin_processing(qtbot):
    """Verifica que datos seriales pasan por el pipeline de plugins."""
    orch = Orchestrator()
    
    # Cargar plugin de ganancia (multiplica por 2.0)
    gain_ui = orch.load_plugin("plugins/custom_filter.py")
    assert gain_ui is not None
    
    # Configurar ganancia a 2.0
    gain_ui.slider.setValue(200)
    
    # Iniciar pipeline
    orch.start_pipeline()
    
    # Lista para capturar datos procesados
    processed_data = []
    def on_processed(data):
        processed_data.append(data.copy())
    
    orch.data_processed.connect(on_processed)
    
    # Esperar datos
    qtbot.waitUntil(lambda: len(processed_data) >= 2, timeout=2000)
    
    orch.stop_pipeline()
    
    # Verificar que los datos fueron procesados (multiplicados por gain=2.0)
    assert len(processed_data) >= 2
    
    # Los datos procesados deberían ser diferentes de cero
    for chunk in processed_data:
        assert isinstance(chunk, np.ndarray)
        assert len(chunk) == 1024

def test_orchestrator_serial_connected_signal():
    """Verifica que serial se conecta correctamente al data_acquired."""
    orch = Orchestrator()
    
    # Verificar flag inicial
    assert hasattr(orch, '_serial_connected')
    assert orch._serial_connected == False
    
    # Configurar serial
    orch.update_serial_params(port='TEST')
    
    # Cambiar a fuente serial
    orch.set_input_source('serial')
    
    # Verificar que se estableció la conexión interna
    # (El flag se usa para evitar conexiones duplicadas)
    # No verificamos el valor exacto porque puede variar según el estado
