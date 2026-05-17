# Step 5 — Recent schemas persistence

_Commit-sized: 3 source files + 1 test file; ~150 LOC._

## Scope

Global "recent schemas" list, modelled on `app/recent_files.py`
(8 entries, `QSettings` key `recent_files`, verified). Storage
key lives under the validation settings group so it is grouped
with `recent_schemas`, `auto_rescan`, and the per-document
bindings already there.

## Files touched (4)

```
state/recent_schemas.py            # new — push/list/clear, cap 12
validation/schema_registry.py      # +push on every successful acquire / reload
state/validation_settings.py       # +const _RECENT_SCHEMAS_KEY for sharing
tests/test_recent_schemas.py       # new
```

## Public API

```python
# state/recent_schemas.py
RECENT_SCHEMAS_CAP = 12

def push_recent_schema(source: SchemaSource) -> None:
    """Move *source* to the front of the recents list (cap 12)."""

def recent_schemas() -> list[SchemaSource]:
    """Most-recent-first list of persisted SchemaSources.

    Drops entries whose serialised form is malformed; never raises.
    """

def clear_recent_schemas() -> None: ...
```

## Storage format

`QSettings(APPLICATION_ID, "validation")` key `recent_schemas`:
list of strings, each `"file:<resolved abs path>"` or
`"url:<normalised url>"`. Strings, not pickled objects — keeps
`QSettings` IO simple and inspectable in the on-disk INI/plist.

Deserialisation drops any entry whose kind prefix is unknown or whose
payload is empty.

## Implementation notes

- `SchemaRegistry.acquire(...)` calls `push_recent_schema(source)`
  only on successful load (entry is non-`None`). Step 1's tests
  already injected a counter on `load_schema` — extend the same
  tests to assert no push on failure.
- `push_recent_schema` is duplicate-safe (move-to-front behaviour
  identical to `app/recent_files.push_recent`).
- No UI yet — Step 6 builds the picker.

## Tests

`tests/test_recent_schemas.py`:
- `push_recent_schema(file_source)` × 3 distinct sources →
  `recent_schemas()` returns them most-recent-first;
- pushing the same source twice deduplicates and floats to front;
- exceeding the cap drops the oldest entry;
- malformed `QSettings` payload (e.g. `["garbage"]`) is filtered out;
- `clear_recent_schemas()` empties the list.

## Out of scope

- UI plumbing (Step 6).
- Per-document bindings — those already exist in
  `state/validation_settings.py` and remain unchanged.

## Commit message

```
feat(state): persist a global "recent schemas" list

- state.recent_schemas: push / list / clear, cap 12, serialised as
  "file:<path>" / "url:<url>" under QSettings(validation)/recent_schemas
- SchemaRegistry.acquire pushes on every successful load
- malformed persisted entries silently dropped on read
```
