# Tasks: Serial Parsing Plotter

## Phase 1: Parsing Strategy

- [x] 1.1 In `core/inputs/serial_strategies.py`, create `XYColonStrategy` class inheriting from `SerialParsingStrategy`. Implement `parse` to decode utf-8, split lines by `\n`, split valid lines by `:`, parse as floats, and return `(N, 2)` float32 numpy array and leftover bytes.

## Phase 2: Input Configuration

- [x] 2.1 In `core/inputs/serial_in.py`, import `XYColonStrategy`. Update `update_config` to instantiate `XYColonStrategy` when `self.mode == 'xy_colon'`.

## Phase 3: UI and Plotting Integration

- [x] 3.1 In `core/main_window.py`, update `_init_ui` to add `"XY Colon"` to `self.combo_serial_mode`.
- [x] 3.2 In `core/main_window.py`, update `on_serial_mode_changed` to map `"XY Colon"` text to `"xy_colon"` internal mode.
- [x] 3.3 In `core/main_window.py`, update plotting logic (e.g., `_plot_multi_channel`) to check if mode is `"xy_colon"`. If so, use `setData(x=display_data[:, 0], y=display_data[:, 1])` for the first curve and clear/hide additional curves.
