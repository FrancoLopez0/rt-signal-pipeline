Este proyecto es una aplicación de escritorio basada en PyQt diseñada para la adquisición, procesamiento y visualización de señales (audio, serial, USB) en tiempo real. Implementa una arquitectura altamente desacoplada que permite inyectar algoritmos de procesamiento dinámicamente ("hot-swapping") y modificar sus parámetros sin detener el flujo de datos ni congelar la interfaz gráfica.
## 🚀 Características Principales

* **Pipeline Definida:** `Input -> Graph 1 -> Process -> Graph 2 -> Audio Out` (con opción de bypass).
* **Patrón MVP (Model-View-Presenter):** Separación estricta entre la interfaz gráfica (Vista) y la lógica de enrutamiento (Orquestador/Presentador).
* **Procesamiento Dinámico:** Carga de módulos `.py` en tiempo de ejecución (`importlib`) proporcionados por el usuario.
* **Aislamiento de Hilos (Multithreading):** Arquitectura diseñada para evitar "Race Conditions" y bloqueos de la GUI en PyQt.
* **Gráficos de Alto Rendimiento:** Uso de `pyqtgraph` para renderizado fluido en el tiempo, FFT y formato |x,y|.
* **Testing Automatizado:** Suite de pruebas con `pytest` para validar la estabilidad matemática, condiciones de carrera y cumplimiento de contratos en los plugins.
* **Generador de Señales Integrado:** Herramienta interna para inyectar senoidales, cuadradas, diente de sierra y ruido blanco para calibración y pruebas.
## 🏗️ Arquitectura del Sistema

Para garantizar estabilidad en el procesamiento digital de señales (DSP) en tiempo real, el sistema divide sus tareas utilizando `QThread` y colas (`queue.Queue`) seguras para subprocesos.

### 1. El Orquestador (Presenter - Main Thread)
Es el núcleo lógico de la aplicación. Se ejecuta en el hilo principal y se encarga de:
* Instanciar la Vista (GUI principal).
* Arrancar y detener los hilos de trabajo (Workers).
* Cargar dinámicamente los plugins del usuario.
* Interceptar las señales (`pyqtSignal`) de la Vista y enrutarlas de forma segura hacia los hilos de procesamiento.

### 2. El Modelo de Hilos (Worker Threads)
La interfaz gráfica **nunca** toca los datos crudos. El flujo de datos ocurre en hilos separados:
* **Capa de Adquisición:** Lee de USB/Serial/Audio y alimenta una `Cola_Input`.
* **Capa de Procesamiento:** Consume la `Cola_Input`, aplica el algoritmo del usuario y envía el resultado a la `Cola_Output`.
* **Capa de Audio/Salida:** Consume la `Cola_Output` y escribe en los buffers del dispositivo.

### 3. La Vista (View - Main Thread)
Totalmente pasiva. Se limita a dibujar la ventana y renderizar los gráficos. Si el usuario interactúa con un control, la Vista simplemente emite una señal que el Orquestador captura.

## 🧩 Sistema de Plugins (El "Contrato")

Para que el usuario pueda proveer su propio algoritmo de procesamiento junto con su propia interfaz gráfica (sin violar las reglas de hilos de PyQt), el sistema define un contrato estricto mediante Clases Base Abstractas (`ABC`).

El usuario debe proveer un script en Python que exponga una clase heredada de `BasePlugin`. Este diseño garantiza que:
1. **La UI del plugin** (`BaseProcessUI`) sea extraída por el Orquestador y dibujada en el **Main Thread**.
2. **El algoritmo DSP** (`BaseProcessDSP`) sea enviado a ejecutarse infinitamente en el **Worker Thread**.

### Definición de la Interfaz (`plugin_interface.py`)

Cualquier módulo inyectado por el usuario debe implementar esta estructura:

```python
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
```

## 📂 Estructura del Proyecto

```text
proyecto_pipeline/
│
├── main.py                 # Punto de entrada de la aplicación.
├── plugin_interface.py     # Contrato ABC (BasePlugin, BaseProcessUI, BaseProcessDSP).
├── requirements.txt        # Dependencias del proyecto.
│
├── core/                   # Motor interno de la aplicación
│   ├── orchestrator.py     # Puente lógico entre UI, Threads y Plugins.
│   ├── threads.py          # Definición de QThreads y Queues.
│   ├── main_window.py      # Interfaz gráfica principal.
│   └── inputs/             
│       ├── serial_in.py    
│       ├── audio_in.py     
│       └── generator_in.py # Generador de señales de test (Senoidal, Ruido, etc.).
│
├── plugins/                # Directorio para los algoritmos del usuario
│   ├── bypass.py           # Plugin base (deja pasar la señal intacta).
│   └── custom_filter.py    # Ejemplo de DSP implementado por el usuario.
│
└── tests/                  # Suite de testing automatizado
    ├── test_plugins.py     # Valida que los .py cumplan el contrato BasePlugin.
    ├── test_pipeline.py    # Pruebas matemáticas headless (sin GUI).
    └── test_gui.py         # Pruebas de integración de PyQt.
````
## 🧩 Sistema de Plugins (API del Usuario)

Para inyectar código propio, el usuario debe crear un archivo `.py` en la carpeta `plugins/` que implemente la clase `BasePlugin` provista en `plugin_interface.py`.

El contrato obliga a separar la UI (que el Orquestador incrustará en el Main Thread) del algoritmo DSP (que el Orquestador enviará al Worker Thread).

```Python
# Ejemplo esquemático de un plugin de usuario
from plugin_interface import BaseProcessUI, BaseProcessDSP, BasePlugin

class MiFiltroUI(BaseProcessUI):
    # Definición de sliders y botones (Main Thread)
    ...

class MiFiltroDSP(BaseProcessDSP):
    # Procesamiento matemático de arrays NumPy (Worker Thread)
    def process(self, data):
        return data * self.parametro
    ...

class Plugin(BasePlugin):
    # Fábrica requerida por el Orquestador
    def get_ui(self): return MiFiltroUI()
    def get_dsp(self): return MiFiltroDSP()
```

## 🧪 Testing y Debugging

El proyecto incluye un entorno de validación robusto:

1. **Generador Interno:** Desde la GUI, selecciona "Test Generator" en el Input para inyectar formas de onda perfectas y analizar la respuesta de tus plugins.
2. **Pytest:** Ejecuta `pytest` en la raíz del proyecto antes de ejecutar la aplicación para asegurar que ningún plugin nuevo rompa la arquitectura o genere _Race Conditions_.

## 🛠️ Instalación

1. Clonar el repositorio y acceder a la carpeta:
    ```Bash
    git clone <URL_DEL_REPO>
    cd proyecto_pipeline
    ```
2. Crear y activar un entorno virtual:
    ```Bash
    # En Windows:
    python -m venv venv
    venv\Scripts\activate
    ```
3. Instalar las dependencias (requiere Python 3.9+):    
    ```Bash
    pip install -r requirements.txt
    ```
    _(Dependencias principales: PyQt6, pyqtgraph, numpy, scipy, sounddevice, pyserial, pytest, pytest-qt)_
4. Ejecutar la aplicación:
    ```Bash
    python main.py
    ```
