# Step 6 — Hot auto-rescan checkbox + dock toolbar

_Commit-sized: 5 source files + 3 test files; ~350 LOC._

## Scope

Add the dock's top toolbar with:

- **🔄 Rescan now** (`QPushButton`, always enabled when a schema is
  attached);
- **☑ Auto rescan** (`QCheckBox`, persisted globally in QSettings);
- **status label**: `"3 errors · 1 warning"` or `"Up to date"`;
- **🚫 Clear schema** (small button, only visible when a schema
  source is `inline`/`sibling`/`manual`).

When **Auto rescan** is checked, every model mutation triggers a
debounced (250 ms) revalidation. Unchecked → only the Rescan button
runs `tab.revalidate()`.

## Files touched (8)

```
app/validation_dock.py              # toolbar widgets + signal wiring
app/validation_dock_actions.py      # _AutoRescanController, _Debouncer
documents/tab.py                    # auto_rescan property, _on_model_mutation()
                                    # triggered by model.dataChanged /
                                    # rowsInserted / rowsRemoved / modelReset
                                    # via QTimer.singleShot debounce
state/validation_settings.py        # auto_rescan_enabled() / set_auto_rescan_enabled()
                                    # already stubbed in Step 2 — extend
documents/tab_status.py             # show "Validation: N errors" while issues > 0
tests/test_validation_autorescan.py
tests/test_validation_debounce.py
tests/test_validation_toolbar.py
```

## Public API

```python
# app/validation_dock_actions.py
class _Debouncer(QObject):
    """QTimer-based 250 ms trailing debounce; .schedule(callable)."""
    def schedule(self, fn: Callable[[], None]) -> None: ...
    def cancel(self) -> None: ...

# documents/tab.py
@property
def auto_rescan(self) -> bool: ...
def set_auto_rescan(self, enabled: bool) -> None:
    """Wire/unwire model.dataChanged etc. to the debouncer."""

# app/validation_dock.py
class ValidationDock(QDockWidget):
    rescanRequested = Signal()
    autoRescanToggled = Signal(bool)
    clearSchemaRequested = Signal()
    # ...
    def update_status(self, issue_index: IssueIndex) -> None: ...
```

## Implementation notes

- **Auto-rescan is a global toggle**, not per-tab, kept simple. Per-
  tab override is not in scope.
- **Mutation signals subscribed**:
  - `model.dataChanged` (any role);
  - `model.rowsInserted`;
  - `model.rowsRemoved`;
  - `model.rowsMoved`;
  - `model.modelReset`.
  All connected on first `set_auto_rescan(True)`, **disconnected**
  on `set_auto_rescan(False)` (or hidden behind a single bool gate
  in the slot to avoid Qt-disconnect quirks across PySide6 versions).
- Debouncer rules:
  - schedule resets the timer to 250 ms;
  - on timeout calls `tab.revalidate()`;
  - undo/redo bursts collapse into a single rescan.
- The Rescan button is **enabled iff schema is attached**;
  toolbar disables itself when `schema_ref.origin == "none"`.
- `tab_status` adds a permanent right-aligned label
  `"Validation: 3 errors"` when `len(issue_index) > 0`, hidden when 0.
- QSettings key: `validation/auto_rescan` (bool, default `False`).
- The Step-2 `_revalidate_on_open` no longer needs to be called
  manually when `auto_rescan=True`; we still call it once on tab
  construction so the dock has data on first show.

## Tests

- `test_validation_autorescan.py` (qtbot):
  - flip checkbox on → mutate a value → after ~300 ms the dock's
    issue count matches the new state;
  - flip off → mutate → count stays stale until Rescan-now clicked.
- `test_validation_debounce.py`:
  - 10 rapid mutations in a tight loop → exactly one
    `validationChanged` emission after the burst settles.
- `test_validation_toolbar.py`:
  - Clear schema button hidden when origin=="none";
  - rescan button disabled when schema absent;
  - status label text matches `"N errors · M warnings"`.

## Out of scope

- Schema picker UI (Step 7).
- Cross-tab debounce coordination — each tab owns its own
  `_Debouncer`, simpler.

## Commit message

```
feat(validation): hot auto-rescan + dock toolbar

- ValidationDock gains: Rescan now button, Auto rescan checkbox,
  status label, Clear schema button
- JsonTab.set_auto_rescan wires model mutation signals through a
  250 ms trailing debouncer to revalidate(); persists across
  sessions via QSettings
- Status bar shows 'Validation: N errors' while issues > 0
```
