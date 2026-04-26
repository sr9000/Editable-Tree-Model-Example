# Phase 5.5 — Search / filter bar

## Goal

A debounced, recursive substring filter above each tab's tree, with
ancestors of matching rows kept visible.

## Entry criteria

- Phase 5.1, 5.2 merged (raw `EditRole` and stable dialog edits make
  proxy filtering safe).

## Exit criteria

- Each `JsonTab` has a `QLineEdit` above its tree view; Ctrl+F focuses
  it. Typing filters the tree by name **or** value substring (case
  insensitive). Ancestors of matches stay visible.
- Filter recomputation is debounced at 150 ms.
- All delegates and tree-view actions still work when the proxy is
  active (i.e. `index.internalPointer()` is mapped to source first).

## Work items

### `TreeFilterProxy`
- [ ] [proxy] New module `tree_filter_proxy.py` with class
      `TreeFilterProxy(QSortFilterProxyModel)`:
      - `setRecursiveFilteringEnabled(True)`.
      - `setFilterCaseSensitivity(Qt.CaseInsensitive)`.
      - Override `filterAcceptsRow(self, src_row, src_parent)` to test
        substring against the source item's `name` and `value`
        (skip OBJECT/ARRAY values; show them via recursive flag only
        when a descendant matches).
      — `tree_filter_proxy.py` (new)
- [ ] [tests] Unit-test the proxy on a small handcrafted model:
      filter on a needle that matches only one leaf → assert the
      ancestors are visible and unrelated siblings hidden.

### Wire into `JsonTab`
- [ ] [tab] In `JsonTab.__init__`:
      - Construct `self.proxy = TreeFilterProxy(self)` with
        `setSourceModel(self.model)`.
      - `self.view.setModel(self.proxy)`.
      - Add `self.search_edit = QLineEdit(self)` with placeholder
        "Filter (Ctrl+F)".
      - `QTimer` debounce 150 ms → `self.proxy.setFilterFixedString`.
      - `QShortcut(QKeySequence.Find, self.view)` →
        `self.search_edit.setFocus()`.
      - Layout: search bar above the tree view in the existing
        `QVBoxLayout`.
      — `json_tab.py:JsonTab.__init__`
- [ ] [tab] Update every place that calls
      `self.view.selectionModel().currentIndex()` /
      `self.model.index(...)` to pass through the proxy when the
      view's model is the proxy. Helper:
      `def _proxy_to_source(self, index): return
       self.proxy.mapToSource(index) if isinstance(index.model(),
       QSortFilterProxyModel) else index`.
      Audit: `_index_path`, `_index_from_path`, `_qualified_name`,
      `_collect_expanded_paths`, every typed-command `redo/undo`.
- [ ] [tab] Inverse mapping: when typed commands resolve a path back
      to an index, they currently call `self.model.index(...)`. Switch
      to a helper `_view_index_from_path(path)` that maps the source
      index up to the proxy before calling
      `view.setCurrentIndex` / `view.edit`.

### Delegate / view audit
- [ ] [delegate] Update `ValueDelegate`, `JsonTypeDelegate`,
      `NameDelegate` so any direct `index.internalPointer()` access
      goes through a small `_source_index(index)` helper that calls
      `proxy.mapToSource` first when needed.
      — `delegate.py`
- [ ] [view] In `tree_view.py`, every helper that uses
      `index.internalPointer()` (`copy_selection`, `cut_selection`,
      `paste_from_clipboard`, `delete_selection`, `duplicate_selection`,
      `move_selection_*`, `sort_selection_keys`,
      `insert_sibling_*`, `insert_child_current`,
      `show_context_menu`) must map to source via the proxy. Add a
      single helper `_resolve(view) -> (model, source_index)` that all
      callers use.
      — `tree_view.py`
- [ ] [tests] Add a test that opens a tab, sets a filter, and runs
      cut/copy/paste/delete/duplicate/move/sort against a *visible
      filtered* row → all operate on the right source row.

## Risks / notes

- `QSortFilterProxyModel.setFilterFixedString` does substring matching
  out of the box but only consults `filterRole()` (default
  `DisplayRole`) on the model's `filterKeyColumn()`. Our recursive
  filter needs to look at *both* name (col 0) and value (col 2) — that
  has to live in our `filterAcceptsRow`, ignoring `filterKeyColumn`.
- `setRecursiveFilteringEnabled(True)` requires Qt ≥ 5.10 (we're on
  Qt 6, fine).
- Be careful with the parent argument of `setFilterRegularExpression`
  / `setFilterFixedString` — we want fixed strings to avoid
  accidentally interpreting user input as regex.
- Match-highlight delegate (`paint` override) is a stretch; defer to
  Phase 5.6 misc polish or a follow-up phase.
