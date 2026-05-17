# Step 4 — Jump-to-problem on click

_Commit-sized: 4 source files + 2 test files; ~200 LOC._

## Scope

Wire `ValidationDock.issueActivated` (emitted on `QListView.clicked`
*and* `activated`) to the active tab so the corresponding tree row
gets selected, scrolled into view, and made current. Single-click =
select+scroll; double-click / Enter = also start editing the value
column when the leaf is editable.

## Files touched (6)

```
app/validation_dock.py              # connect QListView clicked/activated
app/main_window.py                  # ValidationDock.issueActivated →
                                    # active_tab.goto_validation_issue(issue)
documents/tab.py                    # goto_validation_issue(issue, *, edit=False)
documents/tab_paths.py              # ensure index_from_path tolerates Nones
tests/test_validation_navigation.py
tests/test_validation_navigation_edit.py
```

## Public API

```python
# documents/tab.py
def goto_validation_issue(
    self,
    issue: ValidationIssue,
    *,
    edit: bool = False,
) -> bool:
    """
    Resolve issue.instance_path → model path → proxy QModelIndex,
    set current index on the view, scrollTo it, and select the row.
    If edit=True and the resolved row's value column is editable,
    additionally call view.edit(value_index).
    Returns True on success, False when the path no longer exists
    (the schema referred to a row the user has since deleted).
    """
```

## Implementation notes

- Resolution chain:
  1. `validation.json_pointer.instance_path_to_model_path(
        self.root_data, issue.instance_path)` → `(int, ...)` or `None`;
  2. on `None`, push a transient status message
     `"Validation issue path no longer exists"` and return `False`;
  3. otherwise `documents.tab_paths.index_from_path(
        self.model, model_path)` → source index;
  4. map source → proxy via `tab_paths.source_to_view`;
  5. `view.setCurrentIndex(idx)`, `view.scrollTo(idx,
        PositionAtCenter)`,
     `view.selectionModel().select(row_idx,
        ClearAndSelect | Rows)`.
- `MainWindow` connects on the active dock once, in `__init__`,
  using a single lambda that grabs `currentWidget()` at signal time
  (so tab switches don't leak stale closures).
- The connection survives `attach_tab(None)` — when there is no
  active tab the dock simply has nothing to emit.

## Tests

- `test_validation_navigation.py`:
  - schema demands `$.a.b` is integer, document has string →
    activate the issue → `view.currentIndex()` lands on the offending
    row; status bar shows the breadcrumb path.
  - deleted-row case: delete `$.a.b`, activate the stale issue → no
    crash, `currentIndex()` unchanged, transient status message
    matches.
- `test_validation_navigation_edit.py`:
  - `edit=True` opens the value editor on the offending leaf;
  - container rows (OBJECT/ARRAY) ignore `edit=True` cleanly.

## Out of scope

- Highlighting the row beyond the normal selection highlight
  (Step 5 covers persistent badges).
- Filter-aware navigation when the row is currently filtered out
  (acceptable: navigation succeeds but the row is invisible until
  filter is cleared; could be polished post-plan).

## Commit message

```
feat(validation): jump to problem on issue click

- ValidationDock emits issueActivated on click+activate
- JsonTab.goto_validation_issue maps instance_path → tree index,
  selects + centres, optionally starts the value editor
- MainWindow wires dock → active tab once at startup
```
