import struct
from abc import ABC, abstractmethod
import numpy as np
import binascii

class SerialParsingStrategy(ABC):
    @abstractmethod
    def parse(self, raw_data: bytes) -> tuple[np.ndarray, bytes]:
        """
        Parses raw serial bytes into a numpy array of values.
        Returns the parsed data and any leftover bytes.
        """
        pass

class CsvStrategy(SerialParsingStrategy):
    def parse(self, raw_data: bytes) -> tuple[np.ndarray, bytes]:
        """
        Parses comma-separated lines.
        Returns a 2D numpy array where columns represent channels.
        """
        text = raw_data.decode('utf-8', errors='ignore')
        lines = text.split('\n')
        
        parsed_data = []
        # Keep the last line if it's incomplete (doesn't end with \n)
        leftover_text = lines.pop() if not raw_data.endswith(b'\n') else ""
        leftover_bytes = leftover_text.encode('utf-8')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                values = [float(v.strip()) for v in line.split(',') if v.strip()]
                if values:
                    parsed_data.append(values)
            except ValueError:
                pass
                
        if not parsed_data:
            return np.array([]).reshape(0, 0), leftover_bytes
            
        # Make all rows the same length by padding with NaN
        max_len = max(len(row) for row in parsed_data)
        padded_data = [row + [np.nan] * (max_len - len(row)) for row in parsed_data]
        
        return np.array(padded_data, dtype=np.float32), leftover_bytes

class XYColonStrategy(SerialParsingStrategy):
    def parse(self, raw_data: bytes) -> tuple[np.ndarray, bytes]:
        """
        Parses 'x:y' formatted lines.
        Returns a (N, 2) numpy array.
        """
        text = raw_data.decode('utf-8', errors='ignore')
        lines = text.split('\n')
        
        parsed_data = []
        leftover_text = lines.pop() if not raw_data.endswith(b'\n') else ""
        leftover_bytes = leftover_text.encode('utf-8')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            parts = line.split(':')
            if len(parts) == 2:
                try:
                    x = float(parts[0].strip())
                    y = float(parts[1].strip())
                    parsed_data.append([x, y])
                except ValueError:
                    pass
                    
        if not parsed_data:
            return np.array([]).reshape(0, 2), leftover_bytes
            
        return np.array(parsed_data, dtype=np.float32), leftover_bytes

class RawStrategy(SerialParsingStrategy):
    def __init__(self, data_type: str = 'int16', hex_separator: str = '', num_channels: int = 1):
        self.data_type = data_type
        self.hex_separator = hex_separator
        self.num_channels = num_channels
        
        # Determine numpy dtype
        dtype_map = {
            'int8': np.int8, 'uint8': np.uint8,
            'int16': np.int16, 'uint16': np.uint16,
            'int32': np.int32, 'uint32': np.uint32,
            'float32': np.float32, 'float64': np.float64
        }
        self.dtype = dtype_map.get(data_type.lower(), np.int16)
        self.item_size = np.dtype(self.dtype).itemsize

    def parse(self, raw_data: bytes) -> tuple[np.ndarray, bytes]:
        """
        Parses raw binary data according to data_type.
        """
        if self.hex_separator:
            # If hex separator is used, we assume text representation of hex bytes (e.g. 'FF AA 00')
            text = raw_data.decode('utf-8', errors='ignore')
            tokens = [t for t in text.split(self.hex_separator) if t]
            
            valid_bytes = bytearray()
            leftover_text = ""
            for i, token in enumerate(tokens):
                # We need exact 2 chars for hex
                token = token.strip()
                if len(token) == 2:
                    try:
                        valid_bytes.append(int(token, 16))
                    except ValueError:
                        pass
                elif i == len(tokens) - 1:
                    leftover_text = token
                    
            raw_data = bytes(valid_bytes)
            leftover = leftover_text.encode('utf-8')
        else:
            leftover = b''
            
        frame_size = self.item_size * self.num_channels
        num_frames = len(raw_data) // frame_size
        if num_frames == 0:
            return np.array([]).reshape(0, self.num_channels), raw_data if not self.hex_separator else leftover
            
        valid_length = num_frames * frame_size
        data_to_parse = raw_data[:valid_length]
        
        if not self.hex_separator:
            leftover = raw_data[valid_length:]
            
        parsed_array = np.frombuffer(data_to_parse, dtype=self.dtype).astype(np.float32)
        return parsed_array.reshape(-1, self.num_channels), leftover
