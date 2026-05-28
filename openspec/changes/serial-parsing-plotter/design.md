# Technical Design: Serial Parsing Plotter

## 1. Intent
Implement the `xy_colon` parsing strategy to allow real-time coordinate-based (X vs Y) plotting from serial data, addressing the limitation of the current time-series-only plotting system.

## 2. Architecture & Data Flow

The solution involves three main layers:
1.  **Parsing Layer (`serial_strategies.py`)**: A new `XYColonStrategy` class that decodes raw byte streams, splits lines on newline characters, and then splits each line by a colon (`:`) to extract X and Y floating-point values. It returns an `(N, 2)` numpy array.
2.  **Input Layer (`serial_in.py`)**: Update the configuration logic to instantiate and use `XYColonStrategy` when the `xy_colon` mode is selected.
3.  **Presentation Layer (`main_window.py`)**: 
    - Update the UI to include the "XY Colon" mode.
    - Adapt the plotting logic in `_plot_multi_channel` to conditionally map the first column to the X-axis and the second column to the Y-axis when operating in `xy_colon` mode.

## 3. Implementation Details

### 3.1. `core/inputs/serial_strategies.py`
Add a new class `XYColonStrategy` that inherits from `SerialParsingStrategy`:
- Decode bytes to UTF-8.
- Split by `\n`, handling incomplete lines via `leftover_bytes`.
- For each complete line, strip whitespace and split by `:`.
- If exactly two tokens are found, attempt to parse them as `float`.
- Return the resulting array `(N, 2)` of dtype `float32`. Invalid lines are silently ignored (similar to `CsvStrategy`).

### 3.2. `core/inputs/serial_in.py`
Modify `update_config` to handle the new mode string:
```python
        if self.mode == 'csv':
            self.strategy = CsvStrategy()
        elif self.mode == 'xy_colon':
            self.strategy = XYColonStrategy()
        else:
            self.strategy = RawStrategy(data_type=self.data_type, hex_separator=self.hex_separator)
```
Ensure `self.mode` can persist the `'xy_colon'` state properly.

### 3.3. `core/main_window.py`
- Add `"XY Colon"` to `self.combo_serial_mode` in `_init_ui`.
- Update `on_serial_mode_changed` to map the `"XY Colon"` selection to the `xy_colon` internal string.
- In `_plot_multi_channel` (or related plotting methods), check if the current serial mode is `xy_colon` (accessible via `self.orchestrator.serial_in.mode`).
  - **If `xy_colon`**:
    - Update the first curve using `setData(x=display_data[:, 0], y=display_data[:, 1])`.
    - Clear or hide any additional curves (e.g., `curves_list[1].setData([], [])`).
  - **If not `xy_colon`**:
    - Preserve the existing behavior (mapping each column to a separate Y-series curve against an implicit index-based X-axis).

## 4. Edge Cases & Risks
- **Incomplete/Malformed Strings**: Managed by `try/except ValueError` in `XYColonStrategy`.
- **Triggering Interference**: The UI's zero-crossing trigger logic in `_apply_trigger` operates on channel 0 (which becomes the X value). If trigger is enabled, it might slice the buffer based on the X values. The user might need to turn off the trigger for purely spatial XY plots, but it will not crash.
- **Plot Auto-Ranging**: `setData(x=..., y=...)` works seamlessly with PyQtGraph's limits and ranges.

## 5. Next Steps
Move to `sdd-tasks` phase to break this design down into actionable code changes.
