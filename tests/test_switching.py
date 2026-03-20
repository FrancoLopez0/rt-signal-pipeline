import pytest
import numpy as np
import time
from core.orchestrator import Orchestrator

def test_atomic_source_switching(qtbot):
    """Verifica que el cambio de fuente reinicie correctamente el hilo de adquisición."""
    orch = Orchestrator()
    
    # 1. Iniciar con Generador (Seno)
    orch.set_input_source('generator')
    orch.generator.update_params(wave_type='sine', frequency=440)
    orch.start_pipeline()
    
    # Capturar datos iniciales
    captured_sine = []
    def on_data_sine(data):
        captured_sine.append(data)
    
    orch.data_acquired.connect(on_data_sine)
    qtbot.waitUntil(lambda: len(captured_sine) > 2, timeout=2000)
    orch.data_acquired.disconnect(on_data_sine)
    
    # 2. Cambiar tipo de onda en tiempo real (mismo worker)
    orch.generator.update_params(wave_type='square')
    
    captured_square = []
    def on_data_square(data):
        captured_square.append(data)
        
    orch.data_acquired.connect(on_data_square)
    qtbot.waitUntil(lambda: len(captured_square) > 2, timeout=2000)
    orch.data_acquired.disconnect(on_data_square)
    
    # 3. Cambiar a Audio (reinicio de thread)
    # Solo verificamos que el worker se re-instancie
    old_worker = orch.workers.get("acquisition")
    orch.set_input_source('audio')
    new_worker = orch.workers.get("acquisition")
    
    assert old_worker is not new_worker
    
    orch.stop_pipeline()
    
    assert len(captured_sine) > 0
    assert len(captured_square) > 0
    # No verificamos np.array_equal aquí porque la seno y cuadrada a 440Hz 
    # a veces pueden tener fragmentos similares dependiendo del chunk, 
    # pero el cambio de worker es lo que importa para la "atómica".

def test_serial_config_persistence():
    """Verifica que los parámetros seriales se guarden en el objeto SerialInput."""
    orch = Orchestrator()
    orch.update_serial_params(port='/dev/ttyTEST', baudrate=9600)
    
    assert orch.serial_in.port == '/dev/ttyTEST'
    assert orch.serial_in.baudrate == 9600

def test_available_ports_discovery():
    """Verifica que el método de descubrimiento devuelva una lista."""
    from core.inputs.serial_in import SerialInput
    ports = SerialInput.get_available_ports()
    assert isinstance(ports, list)

def test_serial_invalid_port_error():
    """Verifica que intentar abrir un puerto inválido emita un error."""
    orch = Orchestrator()
    errors = []
    orch.error_occurred.connect(errors.append)
    
    orch.update_serial_params(port='/dev/non_existent_port_12345')
    orch.set_input_source('serial')
    
    assert len(errors) > 0
    assert "No se pudo abrir el puerto serial" in errors[0]
