# Phase 5.6 — Misc polish

## Goal

Ship the small touches that round out Phase 5: column-resize hooks,
expand/collapse-all, and confirm zoom integrates with persisted state.

## Entry criteria

- Phases 5.1 – 5.5 merged.

## Exit criteria

- Switching tabs or resetting the model resizes the first two columns
  to contents.
- View menu and tree context menu both expose `Expand All` and
  `Collapse All`.
- Zoom in/out (already added in 5.4) reflows columns correctly.
- Optional: type icons rendered in column 1 (deferred to a follow-up
  phase if SVG plumbing is not in place).

## Work items

### Resize on tab switch / model reset
- [ ] [shell] In `MainWindow._on_tab_changed`, after `_bind_undo_signals`
      call `tab.view.resizeColumnToContents(0)` and `(1)` (skip 2 to
      keep the value column flexible).
      — `ui.py:MainWindow._on_tab_changed`
- [ ] [tab] Connect `model.modelReset` (or proxy's) to a method that
      runs the same two `resizeColumnToContents` calls.
      — `json_tab.py:JsonTab.__init__`

### Expand / Collapse all
- [ ] [view] Add `expand_all(view)` and `collapse_all(view)` thin
      wrappers in `tree_view.py` (already exposed by `QTreeView` —
      wrappers exist for context-menu wiring uniformity).
      — `tree_view.py`
- [ ] [view] Add `Expand All` and `Collapse All` actions to the
      context menu in `show_context_menu`. Place under a separator
      after the structural actions.
      — `tree_view.py:show_context_menu`
- [ ] [shell] Add a `View` menu in `mainwindow.ui` (regen
      `mainwindow.py`) with:
      - `Expand All`  (no shortcut)
      - `Collapse All`  (no shortcut)
      - separator
      - `Zoom In`  (`Ctrl++`)
      - `Zoom Out` (`Ctrl+-`)
      - `Reset Zoom` (`Ctrl+0`)
      — `mainwindow.ui`, `ui.py:MainWindow.setup_connections`
- [ ] [tests] Smoke test that triggering the View menu actions on a
      populated tab toggles `view.isExpanded(top_index)` correctly.

### Match-highlight delegate (stretch)
- [ ] [delegate] Optional: override `ValueDelegate.paint` to draw a
      yellow background span over substring matches when a filter is
      active. Skip if effort exceeds budget; defer to a follow-up.

### Type icons (stretch)
- [ ] [delegate] Optional: register `:/icons/<type>.svg` resources and
      return them from `JsonTreeModel.data(..., DecorationRole)` for
      column 1. Defer to follow-up if SVG plumbing isn't wired.

## Risks / notes

- Aggressive `resizeColumnToContents` on every `dataChanged` is
  expensive; only do it on tab switch / model reset.
- `mainwindow.ui` regeneration must keep object names stable —
  existing connections in `ui.py` rely on `actionsMenu`,
  `fileMenu`, etc.
