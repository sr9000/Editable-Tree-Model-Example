# Step 1 — `SchemaSource` + `SchemaRegistry` core (no UI, no wiring)

_Commit-sized: 3 source files + 1 test file; ~250 LOC._

## Scope

Pure-logic foundation. Adds the registry singleton and the
`SchemaSource` value object. Does **not** touch `JsonTab`,
`MainWindow`, or the dock — those land in Steps 2–3. The existing
`SchemaRef`-based signal contract stays intact.

## Files touched (4)

```
validation/schema_registry.py        # new: SchemaSource, SchemaEntry, SchemaRegistry
validation/__init__.py               # re-export schema_registry singleton
validation/schema_source.py          # +SchemaSource.from_ref helper (no behaviour change)
tests/test_schema_registry.py        # new
```

## Public API

```python
# validation/schema_registry.py
@dataclass(frozen=True, slots=True)
class SchemaSource:
    kind: Literal["file", "url"]
    key: str          # resolved abs path (file) or normalised URL (url)
    display: str      # what to show in menus (basename for file, host+tail for url)

    @classmethod
    def for_file(cls, path: Path) -> "SchemaSource": ...
    @classmethod
    def for_url(cls, url: str) -> "SchemaSource": ...

@dataclass
class SchemaEntry:
    source: SchemaSource
    inline: Mapping[str, Any]    # the loaded dict (shared, never mutated)
    mtime_ns: int | None         # populated for kind == "file"
    ref_count: int               # number of bound tabs
    # bound_tabs kept as WeakSet[JsonTab] but typed as object to avoid the
    # documents.tab import cycle.

class SchemaRegistry(QObject):
    schemaReloaded = Signal(object)   # SchemaSource

    def acquire(self, source: SchemaSource, tab: object) -> SchemaEntry | None: ...
    def release(self, source: SchemaSource, tab: object) -> None: ...
    def reload(self, source: SchemaSource) -> SchemaEntry | None: ...
    def lookup(self, source: SchemaSource) -> SchemaEntry | None: ...
    def all_entries(self) -> list[SchemaEntry]: ...

schema_registry: SchemaRegistry  # module-level singleton
```

## Implementation notes

- `acquire()` is idempotent for the same `(source, tab)` pair: ref-
  count is incremented only on the first call for that pair, tracked
  via a `dict[SchemaSource, WeakSet[object]]`.
- Loading routes through `validation.schema_source.load_schema` so
  YAML / JSON / URL fetching reuses the proven code path. On failure
  `acquire` returns `None` (caller decides how to surface the error).
- `mtime_ns` is captured immediately after a successful file read;
  Step 4's watcher uses it to dedupe spurious `fileChanged` bursts.
- No threading: `acquire` / `reload` are synchronous. URL fetches
  reuse the existing 10 s timeout in `load_schema_from_url`.

## Tests

`tests/test_schema_registry.py`:
- two `acquire(same_source)` calls return the same `SchemaEntry`
  (identity), `ref_count == 2`, single underlying load
  (monkeypatched counter on `load_schema`);
- `release` decrements; reaching zero drops the entry;
- `reload` replaces `inline` and emits `schemaReloaded`;
- `SchemaSource.for_file(Path("~/x.json"))` resolves `~`;
- URL normalisation collapses trailing slash and lower-cases scheme.

## Out of scope

- `JsonTab` integration (Step 2).
- `QFileSystemWatcher` (Step 4).
- Recents persistence (Step 5).

## Commit message

```
feat(validation): SchemaSource + SchemaRegistry core

- frozen SchemaSource(kind, key, display) with for_file / for_url
- SchemaRegistry singleton: acquire/release/reload, refcount,
  shared inline dict, schemaReloaded signal
- registry routes loads through existing load_schema for JSON/YAML/URL
- no UI / no MainWindow / no JsonTab changes yet
```
