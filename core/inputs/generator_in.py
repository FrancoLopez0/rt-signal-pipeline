import numpy as np

class SignalGenerator:
    """Generador de señales sintéticas para pruebas (Seno, Cuadrada, Sawtooth, Ruido)."""
    def __init__(self, sample_rate=44100, frequency=440.0, amplitude=0.5):
        self.sample_rate = sample_rate
        self.frequency = frequency
        self.amplitude = amplitude
        self.phase = 0.0
        self.noise_level = 0.0
        self.wave_type = 'sine' # 'sine', 'square', 'sawtooth', 'noise'

    def generate_chunk(self, chunk_size: int) -> np.ndarray:
        """Genera un bloque de datos NumPy."""
        t = np.linspace(0, chunk_size / self.sample_rate, chunk_size, endpoint=False)
        
        # Generación base según el tipo de onda
        if self.wave_type == 'sine':
            signal = self.amplitude * np.sin(2 * np.pi * self.frequency * t + self.phase)
        elif self.wave_type == 'square':
            from scipy import signal as sp_signal
            signal = self.amplitude * sp_signal.square(2 * np.pi * self.frequency * t + self.phase)
        elif self.wave_type == 'sawtooth':
            from scipy import signal as sp_signal
            signal = self.amplitude * sp_signal.sawtooth(2 * np.pi * self.frequency * t + self.phase)
        elif self.wave_type == 'noise':
            signal = np.random.normal(0, self.amplitude, chunk_size)
        else:
            signal = np.zeros(chunk_size)
            
        # Sumar ruido blanco adicional si está activado
        if self.noise_level > 0 and self.wave_type != 'noise':
            noise = np.random.normal(0, self.noise_level, chunk_size)
            signal += noise
            
        # Actualizar fase para continuidad
        self.phase += 2 * np.pi * self.frequency * chunk_size / self.sample_rate
        self.phase %= 2 * np.pi
        
        return signal.astype(np.float32)

    def update_params(self, frequency=None, amplitude=None, noise_level=None, wave_type=None):
        if frequency is not None: self.frequency = frequency
        if amplitude is not None: self.amplitude = amplitude
        if noise_level is not None: self.noise_level = noise_level
        if wave_type is not None: self.wave_type = wave_type
