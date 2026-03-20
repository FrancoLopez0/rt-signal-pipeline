import pytest
from plugins.bypass import Plugin, BypassUI, BypassDSP
from plugin_interface import BasePlugin, BaseProcessUI, BaseProcessDSP
import numpy as np

def test_bypass_plugin_contract(qtbot):
    plugin = Plugin()
    assert isinstance(plugin, BasePlugin)
    
    ui = plugin.get_ui()
    qtbot.addWidget(ui) # Register widget with qtbot
    assert isinstance(ui, BaseProcessUI)
    
    dsp = plugin.get_dsp()
    assert isinstance(dsp, BaseProcessDSP)

def test_bypass_dsp_processing():
    dsp = Plugin().get_dsp()
    input_data = np.array([1, 2, 3, 4], dtype=np.float32)
    output_data = dsp.process(input_data)
    
    assert np.array_equal(input_data, output_data)
