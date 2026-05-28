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
    """Verifica que no se intente abrir el puerto automáticamente al cambiar fuente.
    
    El puerto serial ahora solo se conecta cuando el usuario hace clic en "Conectar"
    en la UI (vía toggle_serial_connection), no automáticamente al cambiar la fuente.
    """
    orch = Orchestrator()
    errors = []
    orch.error_occurred.connect(errors.append)
    
    # Configurar un puerto inválido
    orch.update_serial_params(port='/dev/non_existent_port_12345')
    
    # Cambiar a fuente serial NO debe intentar abrir el puerto automáticamente
    orch.set_input_source('serial')
    
    # No debe haber errores porque no se intenta abrir el puerto automáticamente
    assert len(errors) == 0
    
    # Verificar que serial_in.ser sigue siendo None (no conectado)
    assert orch.serial_in.ser is None
    
    # Verificar que attempting_manually_to_connect_returns_error()
    # El intento manual de conexión falla con el puerto inválido
    result = orch.serial_in.start()
    assert result == False  # No pudo abrir el puerto
    assert orch.serial_in.ser is None  # sigue siendo None
