# Proposal: Serial Parsing Plotter

## Intent

Implement a new parsing strategy to process incoming serial data formatted as "x:y" and plot it as X,Y coordinates. This satisfies the user need for plotting coordinate-based telemetry data rather than implicitly time-based data.

## Scope

### In Scope
- Create `XYColonStrategy` in `core/inputs/serial_strategies.py`.
- Update `core/inputs/serial_in.py` to support `'xy_colon'` mode.
- Add UI option for "XY Colon" in `core/main_window.py`.
- Update PyQtGraph plotting logic to explicitly use X and Y coordinates.

### Out of Scope
- Support for other coordinate formats (e.g., "x,y,z").
- Significant refactoring of the buffering system beyond what is required for X,Y plotting.
- Additional plot types (e.g., polar plots).

## Approach

Implement an `XYColonStrategy` that decodes and splits raw bytes by `:` to form an `(N, 2)` numpy array. Integrate this into the existing `SerialParsingStrategy` interface. Update `serial_in.py` to handle chunking for 2D arrays. Modify the main window's plotting logic to recognize the `'xy_colon'` mode and apply `setData(x=display_data[:, 0], y=display_data[:, 1])`, bypassing standard time-series triggering/buffering if necessary.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `core/inputs/serial_strategies.py` | Modified | Add `XYColonStrategy` |
| `core/inputs/serial_in.py` | Modified | Support new mode and 2D chunks |
| `core/main_window.py` | Modified | Update UI dropdown and plotting logic |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Buffer incompatibility | Med | Bypass or adapt circular buffer for X,Y data |
| Malformed data crashes | Low | Add robust error handling during string split and float parsing |

## Rollback Plan

Revert the commits modifying `serial_strategies.py`, `serial_in.py`, and `main_window.py`. The previous strategies and time-series plotting will function normally.

## Dependencies

- None (uses existing PyQtGraph and NumPy).

## Success Criteria

- [ ] "XY Colon" option is visible and selectable in the UI.
- [ ] Serial strings like "192:2" are successfully parsed into floats.
- [ ] Data is plotted correctly with explicit X and Y coordinates without crashing.
