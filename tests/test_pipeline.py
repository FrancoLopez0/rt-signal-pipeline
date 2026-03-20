import pytest
import time
import numpy as np
from core.orchestrator import Orchestrator
from plugins.bypass import Plugin

def test_pipeline_data_flow(qtbot):
    """Prueba que los datos fluyan desde el generador hasta el final del pipeline."""
    orch = Orchestrator()
    
    # Cargar plugin de bypass explícitamente para el test
    orch.load_plugin("plugins/bypass.py")
    
    # Lista para capturar los datos procesados
    captured_data = []
    
    def on_data(data):
        captured_data.append(data)
        
    orch.data_processed.connect(on_data)
    
    # Arrancar pipeline
    orch.start_pipeline()
    
    # Esperar a que se procesen al menos 3 bloques de datos
    # Usamos qtbot.waitUntil con un timeout razonable
    qtbot.waitUntil(lambda: len(captured_data) >= 3, timeout=2000)
    
    # Detener pipeline
    orch.stop_pipeline()
    
    # Verificaciones
    assert len(captured_data) >= 3
    for chunk in captured_data:
        assert isinstance(chunk, np.ndarray)
        assert len(chunk) == 1024 # Tamaño de chunk por defecto
        # En bypass, los datos no deberían ser todo ceros (vienen del generador)
        assert np.any(chunk != 0)

def test_plugin_hot_swapping(qtbot):
    """Prueba que se pueda cambiar el plugin mientras el pipeline está corriendo."""
    orch = Orchestrator()
    orch.start_pipeline()
    
    # 1. Cargar bypass
    ui = orch.load_plugin("plugins/bypass.py")
    assert ui is not None
    assert orch.current_plugin_name == "bypass"
    
    # 2. Capturar datos procesados por bypass
    last_chunk_bypass = None
    def capture_bypass(data):
        nonlocal last_chunk_bypass
        last_chunk_bypass = data
    
    orch.data_processed.connect(capture_bypass)
    qtbot.waitUntil(lambda: last_chunk_bypass is not None, timeout=1000)
    orch.data_processed.disconnect(capture_bypass)
    
    # 3. Simular carga de otro plugin (mismo archivo para simplificar, o uno nuevo)
    # Si cargamos el mismo, debería funcionar igual
    ui_new = orch.load_plugin("plugins/bypass.py")
    assert ui_new is not None
    
    orch.stop_pipeline()
