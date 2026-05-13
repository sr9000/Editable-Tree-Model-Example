# Step 3 — Validation dock panel (movable Left/Bottom/Right)

_Commit-sized: 5 source files + 2 test files; ~400 LOC._

## Scope

Build the `QDockWidget` that displays current-tab issues. The dock
is movable between **Left**, **Bottom** and **Right** dock areas
(no Top — top is reserved for the menu/toolbar), can be hidden via a
View-menu toggle, and persists its geometry/area via `QSettings`.

This step **only displays** issues. Step 4 wires click → jump.
Step 6 adds the auto-rescan toolbar.

## Files touched (7)

```
app/validation_dock.py              # ValidationDock(QDockWidget)
app/validation_panel_model.py       # IssueListModel(QAbstractListModel)
app/main_window.py                  # construct + addDockWidget + restore
                                    # geometry; track current-tab issues
app/main_window_actions.py          # +View → "Validation Panel" checkable QAction
mainwindow.ui                       # (optional) action stub; or done in code
tests/test_validation_dock.py       # qtbot: dock visibility, model rows
tests/test_validation_dock_geometry.py
```

## Public API

```python
# app/validation_dock.py
class ValidationDock(QDockWidget):
    issueActivated = Signal(object)         # ValidationIssue (used in Step 4)

    ALLOWED_AREAS = (
        Qt.DockWidgetArea.LeftDockWidgetArea
        | Qt.DockWidgetArea.BottomDockWidgetArea
        | Qt.DockWidgetArea.RightDockWidgetArea
    )

    def __init__(self, parent=None): ...
    def attach_tab(self, tab: JsonTab | None) -> None:
        """Subscribe to tab.validationChanged. Pass None to clear."""

# app/validation_panel_model.py
class IssueListModel(QAbstractListModel):
    """Columns-less list with rich DisplayRole:
       '[severity] $.path.to.node — message (kind)'."""

    def set_issues(self, issues: Sequence[ValidationIssue]) -> None: ...
    def issue_at(self, row: int) -> ValidationIssue | None: ...
```

## Implementation notes

- `QDockWidget`:
  - `setAllowedAreas(ALLOWED_AREAS)`;
  - `setFeatures(DockWidgetMovable | DockWidgetFloatable | DockWidgetClosable)`;
  - default area: `BottomDockWidgetArea`;
  - default visible: `True`, but **restored** from
    `QSettings("validation/dock_visible")`.
- Internal widget layout:
  ```
  ┌──────────────────────────────────────────────────────────┐
  │ <toolbar placeholder — populated in Step 6>              │
  │ ┌──────────────────────────────────────────────────────┐ │
  │ │ QListView bound to IssueListModel                    │ │
  │ │ ❌ $.users[0].age — must be number (type)            │ │
  │ │ ⚠️ $.users[1] — missing 'name' (required)            │ │
  │ └──────────────────────────────────────────────────────┘ │
  └──────────────────────────────────────────────────────────┘
  ```
- `MainWindow` switches the dock's `attach_tab(active_tab)` on
  `tabWidget.currentChanged` and on `close_tab`.
- View menu gains a `Validation Panel` checkable action wired to
  `dock.setVisible` and `dock.visibilityChanged`.
- Geometry persistence:
  - on `closeEvent` → `QSettings.setValue("validation/dock_state",
    saveState())`;
  - on `MainWindow.__init__` after `addDockWidget` →
    `restoreState(QByteArray)`.
- Severity rendering: `❌` (error) / `⚠️` (warning) prefix via
  `Qt.DecorationRole` (use bundled theme icons if available, else
  unicode glyph).
- `JsonPath` formatter reuses `documents.tab_paths.qualified_name`
  if a model path is resolvable, otherwise falls back to a
  `$.foo[0].bar` string built from `instance_path`.

## Tests

- `test_validation_dock.py` (qtbot):
  - dock attached to a tab with a failing schema → list shows N rows;
  - switching to a clean tab clears the list;
  - View → "Validation Panel" toggles visibility.
- `test_validation_dock_geometry.py`:
  - dock allows only `Left|Bottom|Right`;
  - `setFloating(True)` works, `Top` is rejected (assert via
    `isAreaAllowed`).

## Out of scope

- Click-to-jump (Step 4) — the dock just emits `issueActivated`,
  MainWindow ignores it for now (or connects to a no-op).
- Auto-rescan toolbar (Step 6).
- In-tree badges (Step 5).
- Per-issue context menu (later, not in this plan).

## Commit message

```
feat(validation): dockable validation panel (left/bottom/right)

- ValidationDock(QDockWidget) restricted to Left|Bottom|Right areas,
  movable + floatable + closable
- IssueListModel renders one row per ValidationIssue with severity
  icon, qualified $.path, message and validator kind
- MainWindow constructs the dock, restores its state from QSettings,
  switches its bound tab on currentChanged, and adds a View-menu
  toggle action
```
