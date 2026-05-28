import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

data = np.random.randn(1024, 3) # 1024 samples, 3 channels
sos = butter(4, 0.2, output='sos')
zi_base = sosfilt_zi(sos)

# The shape we created: (n_sections, 2, channels)
zi = np.repeat(zi_base[:, :, np.newaxis], 3, axis=2)

try:
    filtered, new_zi = sosfilt(sos, data, axis=0, zi=zi)
    print(f"Success! filtered shape: {filtered.shape}, new_zi shape: {new_zi.shape}")
except Exception as e:
    print(f"Failed with shape {zi.shape}: {e}")

# What if we used the user's suggested shape: (sections, channels, 2)?
zi2 = np.repeat(zi_base[:, np.newaxis, :], 3, axis=1)
try:
    filtered, new_zi = sosfilt(sos, data, axis=0, zi=zi2)
    print(f"Success with user shape! filtered shape: {filtered.shape}, new_zi shape: {new_zi.shape}")
except Exception as e:
    print(f"Failed with user shape {zi2.shape}: {e}")
