from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal
import numpy as np

class BaseProcessUI(QWidget):
    """Se ejecuta en el Main Thread. Emite: (nombre_param, valor)"""
    parameter_changed = pyqtSignal(str, object)

class BaseProcessDSP(ABC):
    """Se ejecuta en el Worker Thread."""
    @abstractmethod
    def process(self, data: np.ndarray) -> np.ndarray:
        pass

    @abstractmethod
    def update_parameter(self, name: str, value: object):
        pass

class BasePlugin(ABC):
    """Fábrica que el Orquestador carga vía importlib."""
    @abstractmethod
    def get_ui(self) -> BaseProcessUI:
        pass

    @abstractmethod
    def get_dsp(self) -> BaseProcessDSP:
        pass
