# Stage 02 — `JsonTab` self-probes and view-state restore

Covers report scenarios **B4, B5**.

## Targets

| File                       | Lines       | Probe                                            |
|----------------------------|-------------|--------------------------------------------------|
| `state/view_state.py`      | 72, 94      | `getattr(tab, "file_path", None)`                |
| `state/view_state.py`      | 84          | `getattr(tab, "_font_pt", None)`                 |
| `state/view_state.py`      | 116         | `hasattr(tab, "_set_font_pt")`                   |
| `state/view_state.py`      | 126         | `hasattr(tab, "_user_sized_columns")`            |
| `documents/tab.py`         | 135         | `getattr(self, "view", None)` during init        |
| `documents/tab.py`         | 485         | `getattr(self, "_font_pt", <default>)`           |
| `documents/tab.py`         | 615         | `getattr(self.type_delegate, "_interactive", False)` |

## Why this is an OOP violation

`state/view_state.py` works exclusively with `JsonTab` — there is no
other "tab-like" implementation. The defensive `getattr`/`hasattr` exists
only because `JsonTab` lifecycle leaves some attributes optional.
`documents/tab.py` is probing its **own** instance, which is the clearest
violation — `self` always has a known declared shape.

## Target design

### 1. Make `JsonTab` declare its fields up front

In `JsonTab.__init__`, initialize every attribute that any caller ever
reads — even with `None` placeholders — so attribute access cannot raise
`AttributeError`:

```python
self.view: JsonTreeView | None = None
self.file_path: Path | None = None
self._font_pt: float = DEFAULT_FONT_PT
self._user_sized_columns: set[int] = set()
```

After that, `getattr(tab, "file_path", None)` → `tab.file_path`, and the
`hasattr(...)` guards in `view_state.py` collapse to `is not None`
checks where needed.

### 2. Public typed API for font + user-sized columns

Expose:

- `JsonTab.font_pt: float` (property + setter, replaces `_font_pt`
  read + `_set_font_pt` capability check).
- `JsonTab.user_sized_columns: Iterable[int]` (read-only view) plus a
  `restore_user_sized_columns(cols: Iterable[int]) -> None` method.

`view_state.py` consumes these typed members directly.

### 3. `JsonTypeDelegate.interactive` becomes a public flag

`documents/tab.py:615` reads `self.type_delegate._interactive`. Promote
it to a public `interactive` (bool) attribute or `is_interactive()` method
on `JsonTypeDelegate`. Stage 03 also touches this delegate, so coordinate
naming with that stage.

### 4. Self-probes inside `JsonTab` are deleted

- `getattr(self, "view", None)` in event-filter setup → guarantee
  `self.view` is assigned to `None` before any event filter is
  installed; then use `if self.view is None: return`.
- `getattr(self, "_font_pt", DEFAULT_FONT_PT)` → just `self._font_pt`
  (initialized in `__init__`).

## Steps

1. Audit `JsonTab.__init__` and add explicit defaults for every field
   probed in B4/B5.
2. Add `font_pt` / `user_sized_columns` / `restore_user_sized_columns`
   typed API. Keep the underscored fields private storage.
3. Add `JsonTypeDelegate.interactive` (or `is_interactive()`).
4. Rewrite `state/view_state.py` to take `tab: JsonTab` and use direct
   attribute access; replace `hasattr` with `is not None` only where the
   value is genuinely optional (`file_path`).
5. Remove the three `getattr` calls in `documents/tab.py`.
6. `grep -RIn 'getattr\|hasattr' state/view_state.py documents/tab.py`
   must return nothing.

## Acceptance criteria

- `JsonTab.__init__` initializes every attribute consumed by `view_state`
  and internal lifecycle paths.
- `state/view_state.py` parameters are typed `JsonTab`, no reflection.
- `documents/tab.py` contains zero `getattr` / `hasattr`.
- Window-state save/restore tests pass (zoom restore, column-width
  restore, file-path matching).
- Report inventory drops by **7** expressions (2 `hasattr`, 5 `getattr`).
