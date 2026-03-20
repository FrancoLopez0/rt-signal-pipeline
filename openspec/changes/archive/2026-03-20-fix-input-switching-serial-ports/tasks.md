# Tasks: Fix Input Switching and Serial Configuration

## Phase 1: Foundation (Serial Input Enhancements)

- [x] 1.1 Add `get_available_ports` static method to `SerialInput` in `core/inputs/serial_in.py` using `serial.tools.list_ports`.
- [x] 1.2 Update `SerialInput` to support dynamic `port` and `baudrate` updates via an `update_config` method.

## Phase 2: Core (Orchestrator Refactoring)

- [x] 2.1 Refactor `Orchestrator.set_input_source` in `core/orchestrator.py` to stop the current `acquisition` thread before re-creating it with the new source.
- [x] 2.2 Add `update_serial_params` to `Orchestrator` to pass UI configuration down to the `SerialInput` instance.

## Phase 3: UI Integration (MainWindow)

- [x] 3.1 Update `MainWindow._init_ui` in `core/main_window.py` to add a `QComboBox` for Port selection and a "Refresh" button in the `group_serial` frame.
- [x] 3.2 Implement `MainWindow.refresh_serial_ports` to populate the port dropdown on initialization and on button click.
- [x] 3.3 Connect Serial UI signals (Port/Baudrate changes) to `Orchestrator.update_serial_params`.

## Phase 4: Testing & Verification

- [x] 4.1 Create `tests/test_switching.py` to verify that switching from Generator to a mock source correctly updates the data stream.
- [x] 4.2 Verify that changing Wave Type in the Generator UI correctly updates the `AcquisitionWorker` output in real-time.
- [x] 4.3 Test edge case: attempting to start Serial on an invalid port shows a `QMessageBox` error.
