# Stage 07 — Validation dock and schema-binding seam

Covers report scenarios **F2, F3**.

## Targets

| File                                 | Lines     | Probe                                                                    |
|--------------------------------------|-----------|--------------------------------------------------------------------------|
| `documents/tab_validation.py`        | 37        | `getattr(documents.tab, "schema_registry", DEFAULT_REGISTRY)`            |
| `app/validation_dock.py`             | 145       | `getattr(self._tab, sig_name)` where `sig_name ∈ {"validationChanged","schemaChanged"}` |
| `app/validation_dock.py`             | 146       | `getattr(self, f"_on_{name}")`                                           |
| `app/validation_dock.py`             | 189, 226  | `getattr(ref, "url", None)` / `getattr(self._tab.schema_ref, "url", None)` |

## Why this is an OOP violation

- `self._tab` is `JsonTab`, both signals exist on it by class declaration.
- `self._on_<name>` are slots defined on `ValidationDock` itself — there
  is no reason for a class to look up its own methods by string.
- `SchemaRef` is a project-owned, finite-variant type. Asking
  "does this ref have a URL?" should be a discriminated-union match,
  not a `getattr`.
- `documents.tab.schema_registry` is a module-attribute monkeypatch hook
  for tests; that should be replaced with a proper dependency-injection
  parameter.

## Target design

### 1. F3 — explicit signal / slot mapping (no reflection)

```python
_SIGNAL_SLOT_PAIRS: tuple[tuple[str, Callable[[ValidationDock], Callable]], ...] = (
    ("validationChanged", lambda self: self._on_validation_changed),
    ("schemaChanged",     lambda self: self._on_schema_changed),
)

def _disconnect_old_tab(self) -> None:
    if self._tab is None:
        return
    self._tab.validationChanged.disconnect(self._on_validation_changed)
    self._tab.schemaChanged.disconnect(self._on_schema_changed)
```

If the "loop over sig_name" form is preferred, keep an explicit static
list of `(Signal, Slot)` tuples — not name strings:

```python
pairs = [
    (self._tab.validationChanged, self._on_validation_changed),
    (self._tab.schemaChanged,     self._on_schema_changed),
]
for sig, slot in pairs:
    sig.disconnect(slot)
```

No `getattr` either way.

### 2. F3 — `SchemaRef.url` becomes a discriminated union

`validation.schema_source.SchemaRef` is finite:

- file-backed (`FileSchemaRef`)
- URL-backed (`UrlSchemaRef`)
- inline / unset

Use `match` (or `isinstance` if Py<3.10 must be supported):

```python
match ref:
    case UrlSchemaRef(url=url):
        ...
    case FileSchemaRef(path=p):
        ...
    case _:
        ...
```

`getattr(ref, "url", None)` is eliminated.

### 3. F2 — replace module-attribute monkeypatch hook with DI

`documents/tab_validation.py:37` looks up
`getattr(documents.tab, "schema_registry", DEFAULT_REGISTRY)` purely so
tests can monkeypatch `documents.tab.schema_registry`. Replace with
explicit constructor injection:

```python
class TabValidation:
    def __init__(self, ..., schema_registry: SchemaRegistry | None = None) -> None:
        self._schema_registry = schema_registry or DEFAULT_SCHEMA_REGISTRY
```

Tests pass a registry stub directly. The `documents.tab.schema_registry`
attribute is removed.

## Steps

1. Refactor `_disconnect_old_tab` / `_connect_new_tab` in
   `app/validation_dock.py` to use a static `(signal, slot)` list.
2. Promote `SchemaRef` to a discriminated union (or confirm it already
   is) and rewrite the `url` reads via `match` / `isinstance`.
3. Add `schema_registry` to `TabValidation.__init__` (constructor
   injection). Migrate call sites and tests.
4. Delete the `documents.tab.schema_registry` module attribute (or
   demote it to a private default).
5. `grep -n 'getattr\|hasattr' app/validation_dock.py documents/tab_validation.py`
   returns nothing.

## Acceptance criteria

- `app/validation_dock.py` and `documents/tab_validation.py` contain
  zero `getattr` / `hasattr`.
- Tests that previously monkeypatched `documents.tab.schema_registry`
  inject via constructor parameter instead.
- Validation-dock connect / disconnect on tab switch is verified by tests.
- Report inventory drops by **5** `getattr` expressions.
