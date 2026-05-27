# Stage 05 — `model_actions.py` model-like protocol

Covers report scenario **D1**.

## Targets

| File                 | Lines           | Probe                                      |
|----------------------|-----------------|--------------------------------------------|
| `model_actions.py`   | 16, 59, 85      | `hasattr(model, "get_item")`               |
| `model_actions.py`   | 115, 144        | `hasattr(model, "move_row")`               |
| `model_actions.py`   | 128, 157        | `hasattr(model, "root_item")`              |
| `model_actions.py`   | 173             | `hasattr(model, "sort_keys")`              |
| `model_actions.py`   | 175             | `getattr(model, "show_root", False)`       |

## Why this is an OOP violation

`model_actions.py` is the project's helper layer for `tree.model.JsonTreeModel`.
Today it treats the model as "anything with `get_item`/`move_row`/…",
but in practice the only object passed in is `JsonTreeModel`. The
`hasattr`-driven branches are dead alternatives.

If there is a genuine need for headless / reduced model support (e.g.
tests), that is a `Protocol` job, not a reflection job.

## Target design

### 1. Declare a `TreeModelLike` protocol

In `tree/model_protocol.py` (new) or inside `tree/model.py`:

```python
class TreeModelLike(Protocol):
    show_root: bool
    def get_item(self, index: QModelIndex) -> JsonTreeItem: ...
    def move_row(self, src_parent: QModelIndex, src_row: int,
                 dst_parent: QModelIndex, dst_row: int) -> bool: ...
    @property
    def root_item(self) -> JsonTreeItem: ...
    def sort_keys(self, parent: QModelIndex, *, ascending: bool) -> None: ...
```

`JsonTreeModel` already implements this; any test double must too.

### 2. Replace probes with typed calls

- All `hasattr(model, "get_item")` / `move_row` / `root_item` / `sort_keys`
  branches collapse — the parameter is `TreeModelLike`, the method
  exists by contract.
- `getattr(model, "show_root", False)` → `model.show_root`. Make
  `show_root` an attribute / property on the protocol with a documented
  default of `False`.

### 3. Reject genuinely incompatible models loudly

`model_actions.py` currently silently no-ops if a probe fails. After the
migration, callers must pass a `TreeModelLike`; a malformed test double
should raise an `AttributeError` / `TypeError` instead of being silently
ignored.

## Steps

1. Add `TreeModelLike` protocol next to `JsonTreeModel`.
2. Verify `JsonTreeModel` satisfies it (run `mypy --strict` on the file
   or write a `_: TreeModelLike = JsonTreeModel(...)` assertion).
3. Annotate every `model_actions.py` function with `model: TreeModelLike`.
4. Delete every `hasattr(...)` branch — call the method directly.
5. Replace `getattr(model, "show_root", False)` with `model.show_root`.
6. Audit `tests/` for ad-hoc model doubles; convert them into proper
   stubs that implement the protocol.
7. `grep -n 'getattr\|hasattr' model_actions.py` returns nothing.

## Acceptance criteria

- `model_actions.py` contains zero `getattr` / `hasattr`.
- `TreeModelLike` protocol declared and used in every signature.
- All move / insert / sort / show-root tests pass unchanged.
- Report inventory drops by **9** expressions (8 `hasattr`, 1 `getattr`).
