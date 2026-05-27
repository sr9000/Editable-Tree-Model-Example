# Stage 01 — `tree_actions/*` ↔ `JsonTab` discovery and consumption

Covers report scenarios **B1, B2, B3**.

## Targets

| File                                | Lines (from report) | Probe                                                                       |
|-------------------------------------|---------------------|-----------------------------------------------------------------------------|
| `tree_actions/paste.py`             | 22                  | `hasattr(parent, "push_insert_rows")`                                       |
| `tree_actions/structure.py`         | 25                  | `hasattr(parent, "push_insert_rows")`                                       |
| `tree_actions/structure.py`         | 217, 223            | `getattr(tab, "_status_message_callback", None)`                            |
| `tree_actions/structure.py`         | 337, 424            | `getattr(tab, "_last_move_placed", None)`                                   |
| `tree_actions/dnd.py`               | 12                  | `hasattr(parent, "push_move_rows")`                                         |
| `tree_actions/dnd.py`               | 89                  | `getattr(tab, "_status_message_callback", None)`                            |
| `tree_actions/context_menu.py`      | 58, 60              | parent-chain walk via `hasattr(cursor, "edit_name_or_value_from_enter")` etc. |
| `tree_actions/context_menu.py`      | 88                  | `getattr(tab, "edit_name_or_value_from_enter")`                             |
| `tree_actions/context_menu.py`      | 134                 | `getattr(tab, "_status_message_callback", None)`                            |
| `tree_actions/context_menu.py`      | 143, 167            | `getattr(tab, "search_edit", None)`                                         |
| `tree_actions/context_menu.py`      | 173                 | `getattr(tab, "_apply_filter", None)`                                       |
| `tree_actions/context_menu.py`      | 259                 | `hasattr(tab, "commit_set_data")` (stale; actual call is `tab.mutations.commit_set_data`) |

## Why this is an OOP violation

All probes here target `documents.tab.JsonTab` (a concrete, project-owned
class). The reflection exists only because the action modules receive a
generic `QTreeView` / `QWidget` and walk parents to find the owning tab.

## Target design

### 1. One typed discovery helper

Add `documents/tab_lookup.py` (or extend `documents/tab.py`):

```python
def find_owning_tab(widget: QWidget | None) -> JsonTab | None:
    node = widget
    while node is not None:
        if isinstance(node, JsonTab):
            return node
        node = node.parent() if isinstance(node, QObject) else None
    return None
```

`isinstance(JsonTab)` replaces every `hasattr(cursor, "edit_name_or_value_from_enter")`
/ `hasattr(parent, "push_insert_rows")` / `hasattr(parent, "push_move_rows")`
parent walk. Action modules import `find_owning_tab` and receive a
`JsonTab | None`.

### 2. Promote private callbacks to typed accessors

On `JsonTab`, expose typed methods so callers stop reaching into private
fields:

- `tab.show_status(message: str, *, timeout_ms: int = ...) -> None`
  wraps the existing `_status_message_callback` (and is a no-op if none).
  Replaces every `cb = getattr(tab, "_status_message_callback", None); if cb: cb(...)`.
- `tab.last_move_placed -> int | None` as a typed `@property`
  (and a setter where structure.py currently writes it).
- `tab.search_edit` and `tab.apply_filter()` already exist conceptually;
  expose them as public typed members (rename or alias the existing
  `_apply_filter`) so callers stop using `getattr`.

### 3. Drop the stale `commit_set_data` capability check

`tree_actions/context_menu.py:259` checks `hasattr(tab, "commit_set_data")`
but the real path is `tab.mutations.commit_set_data(...)`. Replace the
guarded branch with a direct, typed call to
`tab.mutations.commit_set_data(...)` — `JsonTab` always has `.mutations`.

### 4. Action entry points become typed

Each action function signature changes from "anything with the right
method" to `tab: JsonTab` (resolved by the caller via `find_owning_tab`
once at the entry point):

```python
def paste_rows(tab: JsonTab, ...): ...
def insert_rows(tab: JsonTab, ...): ...
def move_rows(tab: JsonTab, ...): ...
def open_context_menu(tab: JsonTab, view: JsonTreeView, ...): ...
```

If a callsite genuinely cannot resolve a `JsonTab` (e.g. action triggered
from a non-tab widget), it must return early instead of falling through
reflection.

## Steps

1. Add `find_owning_tab` (typed, `isinstance`-based).
2. Add `JsonTab.show_status`, `JsonTab.last_move_placed`,
   public `search_edit` / `apply_filter` accessors.
3. Update each of the 4 action modules:
   - replace `hasattr(...)` discovery with `find_owning_tab(...)`,
   - replace `getattr(tab, "_xxx", None)` with the new typed accessors,
   - delete the `commit_set_data` fallback branch.
4. Delete the now-unused `_status_message_callback` reads (the field can
   stay private on `JsonTab`, only its accessor is public).
5. Run tests; verify `grep -RIn 'getattr\|hasattr' tree_actions/` returns
   nothing.

## Acceptance criteria

- `tree_actions/paste.py`, `structure.py`, `dnd.py`, `context_menu.py`
  contain zero `getattr` / `hasattr` calls.
- All action functions take `JsonTab` (or `JsonTab | None`) parameters,
  not `QWidget`-typed proxies.
- Existing paste / move / context-menu / DnD tests pass unchanged.
- Report inventory drops by **15** expressions (5 `hasattr`, 10 `getattr`).
