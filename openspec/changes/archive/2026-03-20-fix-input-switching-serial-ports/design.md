# Design: Input Switching and Serial Configuration

## Technical Approach
We will ensure that switching input sources is a clean operation by stopping and restarting the `AcquisitionWorker` thread. This prevents race conditions and ensures hardware resources (Audio/Serial) are correctly released and re-initialized.

## Architecture Decisions

### Decision: Thread-based Source Switching
- **Choice**: Stop and restart the `AcquisitionWorker` thread in `Orchestrator.set_input_source`.
- **Alternatives**: Updating the `source_func` pointer in-place.
- **Rationale**: Re-starting the thread ensures that any state associated with the previous source (like timing or buffers) is cleared and the new source starts with a fresh loop.

### Decision: Static Port Discovery
- **Choice**: Implement a static method `SerialInput.get_available_ports()` using `pyserial`.
- **Rationale**: Keeps serial-related logic within the `SerialInput` class while making it accessible to the UI without instantiating the hardware.

## Data Flow
1. **User selects source** in `MainWindow`.
2. **MainWindow** calls `Orchestrator.set_input_source(source)`.
3. **Orchestrator**:
   - Stops current `acquisition` thread.
   - Starts/Stops hardware objects (`audio_in`, `serial_in`).
   - Re-creates and starts `AcquisitionWorker` with the new `source_func`.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `core/orchestrator.py` | Modify | Implement graceful stop/restart for input switching. |
| `core/inputs/serial_in.py` | Modify | Add port discovery and dynamic configuration. |
| `core/main_window.py` | Modify | Add Port/Baudrate dropdowns and Refresh button. |
| `tests/test_pipeline.py` | Modify | Add integration tests for source switching. |

## Interfaces / Contracts

```python
# core/inputs/serial_in.py
class SerialInput:
    @staticmethod
    def get_available_ports() -> list[str]: ...
    def update_config(self, port: str, baudrate: int): ...
```

## Testing Strategy
- **Integration**: `test_source_switching` will start the pipeline, capture data, switch source, and verify that the data stream remains active and changes content.
- **Unit**: Verify `SerialInput.get_available_ports()` returns a list of strings.
