# Stage 03 — Delegates, editor factory, and type delegate

Covers report scenarios **C1, C2, C3**.

## Targets

| File                             | Lines    | Probe                                                              |
|----------------------------------|----------|--------------------------------------------------------------------|
| `documents/tab_setup.py`         | 44       | `getattr(self._tab, "_status_message_callback", None)`             |
| `documents/tab_setup.py`         | 53       | `getattr(self._tab, "_icon_provider", None)`                       |
| `documents/tab_setup.py`         | 56       | `getattr(self._tab, "affix_mru", None)`                            |
| `delegates/editor_factory.py`    | 195      | `hasattr(mru, "items")`                                            |
| `delegates/editor_factory.py`    | 198      | `hasattr(provider, "for_key")`                                     |
| `delegates/editor_factory.py`    | 434      | `hasattr(mru, "push")`                                             |
| `delegates/type_delegate.py`     | 131      | `hasattr(host_view, "iconSize")`                                   |

## Why this is an OOP violation

- `tab_setup.py` reads `JsonTab` private attributes via `getattr`. The
  delegate setup runs inside `JsonTab`'s construction graph — there is
  exactly one possible `_tab` type.
- `editor_factory.py` probes `AffixMRU` and the icon provider by method
  name, even though both are project-owned types with stable interfaces.
- `type_delegate.py` probes `QAbstractItemView` for `iconSize`, a method
  that is part of the Qt API contract.

## Target design

### 1. Inject typed collaborators into the delegate context

After stage 02, `JsonTab` exposes typed public accessors:

- `JsonTab.show_status(...)`
- `JsonTab.icon_provider: IconProvider` (typed)
- `JsonTab.affix_mru: AffixMRU`

`tab_setup.py` then constructs the delegate edit context by reading these
typed members directly — no `getattr` needed. If a collaborator is
genuinely optional (e.g. no MRU configured), the type should be
`AffixMRU | None` and callers branch on `is None`.

### 2. Declare `Protocol`s for editor-factory collaborators

In `delegates/editor_factory.py` (or a new
`delegates/protocols.py`):

```python
class AffixMRULike(Protocol):
    def items(self, key: AffixKey) -> Sequence[NumberAffix]: ...
    def push(self, key: AffixKey, value: NumberAffix) -> None: ...

class IconProviderLike(Protocol):
    def for_key(self, key: str) -> QIcon | None: ...
```

The concrete classes `state.affix_mru.AffixMRU`,
`themes.icon_provider.FileIconProvider`, `themes.icon_provider.StubIconProvider`
already satisfy these. Then:

- The factory parameter types become `mru: AffixMRULike | None`,
  `provider: IconProviderLike | None`.
- `hasattr(mru, "items")` / `hasattr(mru, "push")` /
  `hasattr(provider, "for_key")` collapse to `if mru is not None:` /
  `if provider is not None:`.

The protocols are documentation; runtime checks are simple `None` tests.

### 3. Qt host-view `iconSize` is a hard contract

`QAbstractItemView.iconSize()` is part of the public Qt API on every
binding the project supports. Replace
`hasattr(host_view, "iconSize")` with an `isinstance(host_view, QAbstractItemView)`
check (this is the real precondition — the option widget might be `None`
or a non-view widget in some paths). Inside the `isinstance` branch call
`host_view.iconSize()` directly.

## Steps

1. Land stage 02's public `JsonTab` accessors first.
2. Add `delegates/protocols.py` with `AffixMRULike`, `IconProviderLike`
   (or define inside `editor_factory.py`).
3. Update `documents/tab_setup.py` to read typed `JsonTab` properties
   directly; drop all three `getattr` calls.
4. Update `delegates/editor_factory.py`:
   - parameter types `mru: AffixMRULike | None`, `provider: IconProviderLike | None`,
   - replace each `hasattr` with `is not None`.
5. Update `delegates/type_delegate.py`:
   - replace `hasattr(host_view, "iconSize")` with
     `isinstance(host_view, QAbstractItemView)`.
6. `grep -RIn 'getattr\|hasattr' delegates/ documents/tab_setup.py` must
   return nothing.

## Acceptance criteria

- `documents/tab_setup.py` contains zero `getattr` / `hasattr`.
- `delegates/editor_factory.py` and `delegates/type_delegate.py` contain
  zero `getattr` / `hasattr`.
- Two `Protocol`s (`AffixMRULike`, `IconProviderLike`) exist and are used
  in factory signatures.
- Existing editor-open / affix-MRU / icon tests pass unchanged.
- Report inventory drops by **7** expressions (4 `hasattr`, 3 `getattr`).
