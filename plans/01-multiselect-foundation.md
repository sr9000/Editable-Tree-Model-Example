# Step 1 — Multiselect foundation audit & hardening

## Why
`QTreeView` in `documents/tab_setup.py::init_layout` already uses
`ExtendedSelection`, so Shift+Click (contiguous) and Ctrl+Click
(disjoint) work for raw selection. But multi-row support across the
clipboard / structure helpers is implicit and untested. Before adding
drag-and-drop we need a documented, tested baseline.

## Scope (single commit)

### Files to touch
1. `tree_actions/selection.py` — promote `_selected_rows` /
   `_top_level_selected_rows` to public names (`selected_source_rows`,
   `top_level_source_rows`); keep underscore aliases for back-compat.
   Add `selection_spans_multiple_parents(rows) -> bool` helper.
2. `tree_actions/clipboard.py` — switch internal callers to the new
   public names. No behaviour change.
3. `tree_actions/structure.py` — same import update.
4. `tests/test_multiselect_foundation.py` (new).
5. `ai-memory/repo-map.md` — bump scan date and note the public helpers
   in §11.

### Helper additions (selection.py)
```python
def selected_source_rows(view) -> list[QModelIndex]: ...      # was _selected_rows
def top_level_source_rows(view) -> list[QModelIndex]: ...     # was _top_level_selected_rows
def selection_spans_multiple_parents(rows) -> bool: ...
```

`top_level_source_rows` must already prune indexes whose ancestor is also
selected — extend with an explicit unit test for nested ancestor pruning.

## Definition of Done
- [ ] `pytest tests/test_multiselect_foundation.py -q` passes with these
      cases:
    1. `ExtendedSelection` is set on a fresh `JsonTab`.
    2. Shift+selection across a contiguous block returns N rows from
       `top_level_source_rows`, ordered by `_index_path`.
    3. Ctrl+selection across two disjoint subtrees yields exactly those
       two top-level indexes; `selection_spans_multiple_parents` is
       `True`.
    4. Selecting parent **and** its child returns the parent only
       (ancestor pruning).
    5. `copy_selection` followed by `paste_from_clipboard` round-trips
       a 3-row disjoint selection into the same target without losing
       rows or names.
- [ ] `pytest -q` overall: no new reds vs. baseline (573 pass / 3
      offscreen-only fail).
- [ ] Grep shows zero remaining call sites of the underscore-prefixed
      legacy names outside `tree_actions/selection.py` (the aliases
      stay in place for one release).

## Manual smoke
```
QT_QPA_PLATFORM=offscreen pytest -q tests/test_multiselect_foundation.py
python main.py data.yaml   # Ctrl+Click two leaves → Ctrl+C → Ctrl+V into another container
```
