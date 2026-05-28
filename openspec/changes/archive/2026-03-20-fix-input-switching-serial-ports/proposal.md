# Proposal: Fix Input Switching and Add Serial Port Selection

## Intent
Solve the issue where input source selection fails to transition correctly (staying stuck in Sine/Generator) and provide a way for users to select specific serial ports/baudrates from the UI.

## Scope

### In Scope
- **Fix Input Switching**: Ensure `Orchestrator` correctly restarts/updates `AcquisitionWorker` when changing sources.
- **Serial Port Discovery**: Implement automatic discovery of available COM/USB ports.
- **UI Enhancements**: Add port and baudrate selectors to the sidebar.
- **Integration Tests**: Verify that changing sources actually changes the data flow.

### Out of Scope
- Auto-detection of baudrate (user must select it).
- Support for multiple simultaneous input sources.

## Approach
1. **Orchestrator**: Refactor `set_input_source` to signal the `AcquisitionWorker` to reload its source or recreate the worker thread for a clean transition.
2. **Serial Input**: Integrate `serial.tools.list_ports` to fetch available ports.
3. **MainWindow**: Update the serial control group to include dynamic port listing and a "Refresh" button.
4. **Testing**: Add a test case that captures the waveform before and after a source switch.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `core/orchestrator.py` | Modified | Improved source switching logic. |
| `core/main_window.py` | Modified | New UI controls for serial ports. |
| `core/inputs/serial_in.py` | Modified | Support for dynamic port/baudrate assignment. |
| `tests/test_pipeline.py` | Modified | New integration tests for source switching. |

## Risks
- **Race Conditions**: Switching sources too fast might cause buffer overflows or thread crashes.
- **Hardware Access**: Serial ports might be locked by other applications.

## Rollback Plan
Revert to the last stable commit using `git checkout`.

## Success Criteria
- [ ] Switching between Generator types (Sine -> Square) works instantly.
- [ ] Switching from Generator to Audio shows microphone data.
- [ ] Serial port list is populated and selectable.
- [ ] Automated tests confirm data flow changes upon source switch.
