# Step 2 — Route `JsonTab` through the registry

_Commit-sized: 4 source files + 2 test files; ~200 LOC (mostly delete)._

## Scope

Replace `JsonTab`'s private `_schema = dict(loaded)` with a registry
handle. Keep `schemaChanged` emitting `SchemaRef` for backward
compatibility — the dock and tests still listen on it.

## Files touched (6)

```
documents/tab.py                 # set_schema / clear_schema / _init_validation_state
                                 # acquire-release lifecycle in closeEvent
documents/tab_setup.py           # init_validation_state passes resolved doc path,
                                 # leaves registry call to JsonTab itself
validation/schema_registry.py    # +SchemaRegistry.acquire_ref(SchemaRef) convenience
validation/__init__.py           # re-export
tests/test_tab_schema_state.py   # adapt: assert single registry load across two tabs
tests/test_schema_registry_tab.py  # new: two tabs share one entry, release on close
```

## Current state being replaced

`documents/tab.py` L207–298 (verified):

```python
self._schema_ref = SchemaRef(path=None, inline=None, origin="none")
self._schema: dict[str, Any] | None = None
# ...
def set_schema(self, ref: SchemaRef) -> None:
    self._schema_ref = ref
    loaded = load_schema(ref)
    self._schema = dict(loaded) if loaded is not None else None
    self.schemaChanged.emit(self._schema_ref)
    self.revalidate()
```

## After Step 2

```python
def set_schema(self, ref: SchemaRef) -> None:
    new_source = SchemaSource.from_ref(ref)
    self._swap_source(new_source, ref)

def set_schema_from_source(self, source: SchemaSource) -> None:
    self._swap_source(source, source.as_ref())

def clear_schema(self) -> None:
    self._swap_source(None, SchemaRef(path=None, inline=None, origin="none"))

def _swap_source(self, source: SchemaSource | None, ref: SchemaRef) -> None:
    if self._schema_source is not None:
        schema_registry.release(self._schema_source, self)
    entry = schema_registry.acquire(source, self) if source else None
    self._schema_source = source
    self._schema_ref = ref
    self._schema = entry.inline if entry else None
    self.schemaChanged.emit(self._schema_ref)
    self.revalidate()
```

- Inline schemas (no path, no URL) bypass the registry — `source is None`
  but `self._schema = dict(ref.inline)` keeps current behaviour.
- `JsonTab.closeEvent` (or `deleteLater`-time cleanup hook in
  `tab_setup`) calls `schema_registry.release(self._schema_source, self)`.
- `self._schema` becomes a **shared reference** to the entry's
  `inline` dict, not a private copy. The schema dict is treated as
  read-only by `validation.validator` already — confirmed by reading
  `validation/validator.py` (only `Draft202012Validator(schema).iter_errors(data)`).

## Tests

- `tests/test_schema_registry_tab.py` (new):
  - construct two tabs with `set_schema(SchemaRef(path=tmp_path, ...))`;
  - assert `tab_a.schema is tab_b.schema` (same dict object);
  - assert one `load_schema` call (monkeypatched counter);
  - close tab A → entry still alive; close tab B → entry dropped.
- `tests/test_tab_schema_state.py`:
  - retain existing `schemaChanged` assertions;
  - add assertion that `tab.schema_source.kind == "file"` after
    setting a path-backed `SchemaRef`.

## Out of scope

- MainWindow handlers / dialog (Step 3).
- File watcher (Step 4).
- Recents (Step 5).

## Commit message

```
refactor(validation): JsonTab acquires schemas via SchemaRegistry

- _schema becomes a shared reference into a SchemaRegistry entry,
  not a per-tab dict copy
- set_schema / clear_schema / set_schema_from_source go through
  _swap_source with strict acquire/release pairing
- inline-only SchemaRefs (no path, no URL) keep their current
  per-tab semantics; they bypass the registry
- closeEvent releases the entry; entries drop on ref_count == 0
```
