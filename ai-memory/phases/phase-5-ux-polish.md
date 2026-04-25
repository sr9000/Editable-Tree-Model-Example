# Phase 5 — UX Polish

## Goal

Make the editor pleasant to use day-to-day: human-friendly value
display, persistent layout, status-bar feedback, and a search/filter bar.

## Entry criteria

- Phase 4 complete: files open, save, dirty state works.

## Exit criteria

- Long values are elided in the table; full text is in a tooltip.
- Percentages display as `50%`, mpq fractions as their decimal form,
  datetimes in ISO-8601 with timezone where present.
- Status bar shows current path "Object > items > 3 > name" plus type
  and size hints.
- Column widths and tree expansion state are persisted per file path
  via `QSettings`.
- A search/filter bar above each tree filters by name and value
  substring.

## Work items

### Display formatting
- [ ] [ux] Implement `ValueDelegate.displayText(value, locale)`:
      - PERCENT → `f"{value*100:g}%"`
      - mpq FLOAT → `mpq_serialization(value)[0]`
      - long STRING / MULTILINE → first 80 chars + ellipsis
      - BYTES / ZLIB / GZIP → `f"<{units.format_bytes(len(raw))}>"`
      — `delegate.py:ValueDelegate`
- [ ] [ux] Implement `JsonTreeModel.data` for `Qt.ToolTipRole` to return
      the full value (capped at e.g. 4 KB) for long cells.
      — `tree_model.py:JsonTreeModel.data`
- [ ] [ux] Render the Type column with an icon per `JsonType` (optional
      stretch; can be deferred).

### Status bar
- [ ] [ux] When selection changes, write a breadcrumb to
      `MainWindow.statusBar()`: `Path: a > b > 3 (string, 24 chars)`.
- [ ] [ux] When a long-running action runs (load/save/sort), show a
      transient status message.

### Persisted view state
- [ ] [ux] On tab close / app close, persist per-file:
      - column widths
      - expansion state (set of tree paths)
      - last selected path
      Use `QSettings("EditableTreeModel", "view_state").setValue(path, ...)`.
- [ ] [ux] On open, restore the same. Fall back to defaults
      (`expandAll`, `resizeColumnToContents`) when unknown.

### Search / filter
- [ ] [ux] Add a `QLineEdit` above the tree in `JsonTab` (Ctrl+F to
      focus). Filter rows whose name or value substring-matches; keep
      ancestors visible.
- [ ] [ux] Use a `QSortFilterProxyModel` subclass that overrides
      `filterAcceptsRow` with recursive include-ancestor logic.
- [ ] [ux] Highlight matched substrings via a custom delegate
      (`paint` override) — optional stretch.

### Misc polish
- [ ] [ux] Resize columns to contents on `currentChanged`
      (tab switch) and `model.modelReset`.
- [ ] [ux] Add zoom in / out (Ctrl++/Ctrl+-) for tree font.
- [ ] [ux] Provide "Collapse All" / "Expand All" entries in context
      menu and View menu.

## Risks / notes

- A custom proxy model interacts with the `internalPointer()`
  contract: selection delegates must call
  `proxy.mapToSource(index).internalPointer()`. Audit `ValueDelegate`
  and `JsonTypeDelegate` accordingly.
- Persisted view state keyed by file path needs migration logic if
  the path changes (Save As). Drop or copy the entry on save-as.
- Search performance on a 100k-row document needs a one-pass index
  rather than re-walking on every keystroke; introduce a debounce.
