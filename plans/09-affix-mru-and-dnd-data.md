# Stage 09 — Affix MRU bootstrap and DnD data shapes

Covers report scenarios **E2, E3, E4**.

## Targets

| File                       | Lines      | Probe                                                |
|----------------------------|------------|------------------------------------------------------|
| `state/affix_mru.py`       | 12         | `getattr(settings, "NUMBER_AFFIX_MRU_SIZE", default)` |
| `state/affix_mru.py`       | 40         | `hasattr(node, "value")`                             |
| `state/affix_mru.py`       | 40, 41     | `getattr(node, "value")`                             |
| `state/affix_mru.py`       | 43         | `hasattr(node, "child_items")`                       |
| `state/affix_mru.py`       | 44         | `getattr(node, "child_items")`                       |
| `tree_actions/dnd.py`      | 65         | `hasattr(mime, "text")`                              |
| `tree_actions/dnd.py`      | 119        | `hasattr(view, "mark_drag_handled_internally")`     |

## Why this is an OOP violation

`affix_mru.py` walks a heterogeneous graph (`NumberAffix`,
`JsonTreeItem`, `dict`, `list`). All four candidates are project-owned
or built-in. `isinstance` is the right discriminator, not `hasattr`.

For DnD:

- `QMimeData.text()` is a hard Qt API — always present.
- `JsonTreeView.mark_drag_handled_internally` is a method on a
  project-owned class.

## Target design

### 1. Affix-MRU root walk via `isinstance` dispatch

```python
def _walk(node: object) -> Iterator[NumberAffix]:
    if isinstance(node, NumberAffix):
        yield node
    elif isinstance(node, JsonTreeItem):
        if isinstance(node.value, NumberAffix):
            yield node.value
        for child in node.child_items:
            yield from _walk(child)
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)
    # otherwise: nothing to do
```

No `hasattr` / `getattr`. `JsonTreeItem` already declares `.value` and
`.child_items` typed in `tree/item.py`.

### 2. Settings access via attribute, not reflection

The defaulted `getattr(settings, "NUMBER_AFFIX_MRU_SIZE", default)` is
covering a missing-attribute case. Pick one of:

- give `settings.py` an unconditional `NUMBER_AFFIX_MRU_SIZE = N` (then
  `settings.NUMBER_AFFIX_MRU_SIZE`), or
- expose `settings.number_affix_mru_size() -> int` with the default
  baked in, or
- inject the value into `AffixMRU.__init__(size: int)` from the
  controller that creates it.

Preferred: constructor injection (`AffixMRU(size=settings.NUMBER_AFFIX_MRU_SIZE)`)
so `affix_mru.py` does not import settings at all.

### 3. DnD mime + view checks

- Replace `hasattr(mime, "text")` with `isinstance(mime, QMimeData)`
  and call `mime.text()` directly — Qt guarantees the method.
- Replace `hasattr(view, "mark_drag_handled_internally")` with
  `isinstance(view, JsonTreeView)` and a direct call. If a non-project
  view is ever possible, the parameter type itself should be
  `JsonTreeView` (assertion at the entry point).

## Steps

1. Rewrite `_walk` in `state/affix_mru.py` using `isinstance`.
2. Move `NUMBER_AFFIX_MRU_SIZE` to constructor injection; remove the
   `getattr(settings, ...)` line.
3. Update `tree_actions/dnd.py` to `isinstance(mime, QMimeData)` and
   `isinstance(view, JsonTreeView)` branches.
4. `grep -n 'getattr\|hasattr' state/affix_mru.py tree_actions/dnd.py`
   returns nothing (note: stage 01 already cleared `dnd.py`'s other
   probes, this stage finishes the file).

## Acceptance criteria

- `state/affix_mru.py` contains zero `getattr` / `hasattr`.
- `tree_actions/dnd.py` contains zero `getattr` / `hasattr` (combined
  with stage 01).
- Affix MRU recovery from nested tree / dict / list payloads is
  covered by tests.
- DnD text-fallback drop and internal-move marker paths are exercised
  by tests.
- Report inventory drops by **7** expressions across these files.
