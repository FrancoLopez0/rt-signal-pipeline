# Delta for Input Pipeline & Serial Configuration

## ADDED Requirements (core/inputs/serial)

### Requirement: Available Port Discovery
The system SHALL provide a mechanism to scan and list all available serial (COM/USB) ports currently connected to the OS.

#### Scenario: Scan ports on startup
- GIVEN the application is initializing
- WHEN the UI is constructed
- THEN the system MUST scan for available ports
- AND populate the Serial Port dropdown with the results.

### Requirement: Dynamic Serial Parameter Update
The system MUST allow updating the `port` and `baudrate` of the `SerialInput` before starting the acquisition.

#### Scenario: Update port before starting
- GIVEN a SerialInput instance is stopped
- WHEN the user selects a new port in the UI
- THEN the SerialInput MUST be updated with the new port string.

## MODIFIED Requirements (core/orchestrator)

### Requirement: Robust Input Source Switching
(Previously: updated the `source_func` pointer in place)
The Orchestrator MUST ensure that switching input sources is atomic. It SHALL stop the current acquisition source before starting the new one and updating the Worker's function pointer.

#### Scenario: Switch from Generator to Audio
- GIVEN the pipeline is running with 'generator'
- WHEN `set_input_source('audio')` is called
- THEN the system MUST stop any running input hardware
- AND start the `audio_in` stream
- AND update the `AcquisitionWorker` to use `audio_in.get_chunk`.

## ADDED Requirements (ui/main_window)

### Requirement: Serial Port UI Controls
The UI MUST include a dropdown for Port selection and a dropdown/input for Baudrate in the Serial settings group.

#### Scenario: Change port and baudrate
- GIVEN the Serial input is selected
- WHEN the user changes the Port or Baudrate
- THEN the Orchestrator MUST be notified of the change.
