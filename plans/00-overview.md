# Drag-and-Drop Multi-Selection — Overview

End goal: native drag-and-drop reorder/move of fields across the file,
backed by multi-selection (Shift / Ctrl), keyboard moves, and round-trip
undo, with collapse/expand state preserved.

## Step map

| #   | File                                | Theme                                                   | Touches                                                                          | Test gate                                |
| --- | ----------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------- | ---------------------------------------- |
| 1   | `01-multiselect-foundation.md`      | Audit + harden multi-selection in clipboard/structure   | `tree_actions/selection.py`, tests                                               | `tests/test_multiselect_foundation.py`   |
| 2   | `02-mime-payload-helpers.md`        | Extract reusable MIME (de)serializer for multi-select   | `tree_actions/clipboard.py`, `tree_actions/paste.py`, tests                      | `tests/test_mime_payload.py`             |
| 3   | `03-multi-row-move-undo.md`         | Atomic `push_move_rows` macro on the undo stack         | `documents/tab.py`, `undo/commands.py`                                           | `tests/test_undo_multimove.py`           |
| 4   | `04-keyboard-multimove.md`          | Alt+Up/Down on multi-selection + bubble-out at boundary | `tree_actions/structure.py`, `documents/tab_setup.py`                            | `tests/test_keyboard_multimove.py`       |
| 5   | `05-preserve-collapse-state.md`     | Snapshot/restore expansion + selection across moves     | `documents/tab.py`, `state/view_state.py` (helper)                               | `tests/test_move_preserves_expansion.py` |
| 6   | `06-drag-drop-internal.md`          | Native QTreeView drag-and-drop wired to move helpers    | `documents/tab_setup.py`, `tree/model.py`, `tree_actions/dnd.py` (new)           | `tests/test_drag_drop_internal.py`       |
| 7   | `07-drop-policies-visuals.md`       | Self-into-descendant guard, primitive fallback, cursors | `tree_actions/dnd.py`, `tree/model.py`                                           | `tests/test_drop_policies.py`            |
| 8   | `08-shortcuts-menu-docs.md`         | Shortcuts, context menu labels, repo-map refresh        | `documents/tab_setup.py`, `tree_actions/context_menu.py`, `ai-memory/repo-map.md`| `tests/test_shortcuts_and_menu.py`       |

## Acceptance criteria for the whole feature

- Mouse left-click + drag inside the tree moves the selection, including
  multi-selection built up via Shift+Click (contiguous) or Ctrl+Click
  (disjoint).
- `Ctrl+C` / `Ctrl+X` / `Ctrl+V` work on the selection, regardless of
  whether the selected rows share a parent. Cross-parent multi copy
  serialises into a list payload; same-parent named copy under an OBJECT
  produces a dict payload (existing behaviour, now under test).
- `Alt+Up` / `Alt+Down` move the whole selection by one row. At a parent
  boundary the selection is promoted/demoted across the parent (looks
  like a continuous row reorder).
- A single undo step reverses a multi-row move or drag-and-drop.
- Expansion state of every moved subtree is preserved at the destination,
  current index and selection follow the moved rows.
- All steps land in a green test suite (`pytest -q`) on the same Qt
  platform matrix as today (offscreen-only failures listed in
  `ai-memory/todo-n-fixme.md` remain the only allowed reds).

## Conventions

- Each step file ships a single commit ≤ 500 changed lines, ≤ 10 files.
- DoD is verified by `pytest tests/<file>.py` plus the listed manual
  CLI smoke (`python main.py <fixture.yaml>` where given).
- Tests must be headless (`QT_QPA_PLATFORM=offscreen`) — drag-drop tests
  exercise the MIME pipeline through `model.mimeData` /
  `model.dropMimeData` directly, not synthetic mouse events.
