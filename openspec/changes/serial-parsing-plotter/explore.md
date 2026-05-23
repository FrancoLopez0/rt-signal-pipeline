# Exploration Report: Serial Parsing Plotter

## Overview
The goal is to implement a new serial parsing strategy that reads incoming data in the format `"x:y"` (e.g., `"192:2"`) and plots these values as an X,Y graph.

## Current Architecture
The current serial acquisition system uses a strategy pattern:
- `core/inputs/serial_strategies.py` contains `SerialParsingStrategy` interface with `CsvStrategy` and `RawStrategy` implementations.
- `core/inputs/serial_in.py` handles reading the serial port, applying the strategy, chunking the data, and emitting it.
- `core/orchestrator.py` receives the emitted data and passes it to the UI and processing pipeline.
- `core/main_window.py` handles plotting via PyQtGraph, currently assuming an implicit X-axis (index/time) and plotting channels as Y-values.

## Proposed Integration Points

### 1. `core/inputs/serial_strategies.py`
Add a new strategy: `XYColonStrategy(SerialParsingStrategy)`.
- **Parsing logic**: Split raw bytes by newline, decode, and split each line by `:`.
- **Output**: Return a numpy array of shape `(N, 2)` representing X and Y coordinates.

### 2. `core/inputs/serial_in.py`
- Modify `update_config` to support a new mode (e.g., `'xy_colon'`).
- Ensure the chunking logic `_make_chunk` gracefully handles the `(N, 2)` array.

### 3. `core/main_window.py`
- **UI update**: Add the "XY Colon" option to the `combo_serial_mode` dropdown.
- **State update**: Modify `on_serial_mode_changed` to map the selection to the `'xy_colon'` mode.
- **Plotting logic**: Update `_plot_multi_channel` (or add a specialized method) to check if the current serial mode is `'xy_colon'`. If so, use the first column as X values and the second column as Y values (`curves_list[i].setData(x=display_data[:, 0], y=display_data[:, 1])`).
- **Buffering/Triggering**: Ensure that `_update_buffer` and `_apply_trigger` logic is compatible with explicit X-coordinates, or bypass triggering if in XY scatter mode.

## Risks & Considerations
- **Buffering vs Plotting X,Y**: Traditional time-series buffering (`input_buffer`) overwrites old data using indices. For X,Y plotting (especially scatter plots or Lissajous-like graphs), a circular buffer on the X-axis might not make sense in the same way. We might just need to pass the raw array points.
- **Permission issues**: We were unable to invoke `mem_save` via CLI due to permission timeouts. The state is instead saved in this file.
