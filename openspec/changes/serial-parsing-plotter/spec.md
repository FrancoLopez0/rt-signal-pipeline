# Specification: Serial Parsing Plotter

## 1. Intent
Implement the `serial-parsing-plotter` feature to parse serial data in the format "x:y", map it into an `(N, 2)` array, and natively plot X versus Y using PyQtGraph, as defined in the proposal.

## 2. Technical Specifications

### 2.1 `core/inputs/serial_strategies.py`
- **Class `XYColonStrategy`**: Create a new class inheriting from `SerialParsingStrategy`.
- **`parse(raw_data: bytes)`**: 
  - Decode `raw_data` to a UTF-8 string (ignore errors).
  - Split the string by `\n` to process lines.
  - Handle incomplete lines (no trailing `\n`) by returning them as leftover bytes.
  - For each complete line, split by `:` into exactly two tokens.
  - Parse both tokens as floats. Discard lines that fail to parse or don't have exactly two tokens.
  - Return a 2D NumPy array of shape `(N, 2)` containing the valid `[x, y]` pairs, and the `leftover_bytes`.

### 2.2 `core/inputs/serial_in.py`
- **`update_config` method**: Add support for `mode == 'xy_colon'`. When selected, set `self.strategy = XYColonStrategy()`.
- **Chunking logic**: The existing chunking logic `_make_chunk` in `SerialInput` currently pads or slices up to `num_channels`. If `XYColonStrategy` returns `(N, 2)`, it will be treated as 2 channels. This is acceptable, but ensure that `self.chunk_array` properly resizes to `(self.chunk_size, 2)` without errors.

### 2.3 `core/main_window.py`
- **UI Update**: Modify `self.combo_serial_mode.addItems(["CSV", "RAW Binary"])` to include `"XY Colon"`.
- **`on_serial_mode_changed(self, text)`**: Update the mode resolution:
  - If `"XY"` in `text`, set `mode = "xy_colon"`.
  - Elif `"RAW"` in `text`, set `mode = "raw"`.
  - Else set `mode = "csv"`.
- **Plotting Logic**:
  - `update_input_plot` and `update_output_plot`:
    - Add a check `is_xy_mode = (self.orchestrator.current_source == 'serial' and self.orchestrator.serial_in.mode == 'xy_colon')`.
    - If `is_xy_mode`, we should bypass the standard trigger (`_apply_trigger`) if it relies on time-series zero crossing.
    - Instead of `setData(display_data[:, i])` which plots channel against an implicit sample index (time), we must set explicitly `x` and `y` data.
  - Modify `_plot_multi_channel` (or create a variant/conditional branch):
    - If `is_xy_mode` is True:
      - We expect `display_data.shape[1] == 2`.
      - Use `curves_list[0].setData(x=display_data[:, 0], y=display_data[:, 1])`.
      - Hide or clear the second curve since `y` is now the value of the second channel and not plotted as a separate line vs time.
      - Apply the same `x` vs `y` logic for `combined_curves_list[0]`.

## 3. Data Flow
1. **Serial Port**: Emits bytes `... \n 1.0:5.5 \n 2.0:10.1 \n ...`
2. **`XYColonStrategy`**: Converts to `np.array([[1.0, 5.5], [2.0, 10.1]])`
3. **`SerialInput` buffer**: Accumulates into a 2D deque and emits chunks of size `chunk_size` with shape `(1024, 2)`.
4. **`update_input_plot`**: Detects XY mode, slices X from column 0, Y from column 1, and plots `X vs Y`.

## 4. Edge Cases & Handling
- **Malformed string**: (e.g., `10.5:` or `abc:def`) - `XYColonStrategy` safely ignores the line inside a `try...except ValueError` block.
- **Single column or >= 3 columns**: Only process lines that yield exactly 2 elements when split by `:`.
- **Plotting modes**: In XY mode, standard time-domain visualization (where X is sample index) no longer applies. `x_range` might not bound the data correctly if the X values exceed the window length. Consider enabling auto-range for X in XY mode, or documenting that the UI's X/Y range controls apply directly to the Cartesian plane.

## 5. Security & Privacy
- No security or privacy implications. All data processing is strictly local.

## 6. Testing Strategy
- Start pipeline with serial input in "XY Colon" mode.
- Use a mock serial input or Python script to write `x:y\n` strings.
- Verify that a scatter or line plot explicitly maps the first coordinate to the horizontal axis and the second to the vertical axis.
- Confirm it recovers gracefully when random non-conforming strings are interspersed.
