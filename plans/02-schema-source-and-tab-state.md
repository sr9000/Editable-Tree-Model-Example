# Step 2 — Schema discovery + per-tab schema state

_Commit-sized: 5 source files + 3 test files; ~350 LOC._

## Scope

Give every `JsonTab` an attached schema (or `None`), a current list
of issues, and the signals other layers will subscribe to. No UI
yet — Step 3 builds the dock that consumes these signals.

## Files touched (8)

```
validation/schema_source.py            # discovery (inline $schema, sibling file, manual)
validation/index.py                    # IssueIndex keyed by model-path
documents/tab.py                       # +schema/schema_path/issues/issue_index, signals,
                                       # revalidate(), set_schema(), clear_schema()
documents/tab_setup.py                 # one-line: init validation state after model attach
state/validation_settings.py           # QSettings recall of per-file schema path (stub now,
                                       # consumed in Step 7)
tests/test_schema_source.py
tests/test_tab_schema_state.py
tests/test_validation_index.py
```

## Public API delta

```python
# validation/schema_source.py
@dataclass(frozen=True, slots=True)
class SchemaRef:
    path: Path | None                          # local file, or None for inline
    inline: Mapping[str, Any] | None           # already-parsed dict
    origin: Literal["inline", "sibling", "manual", "none"]

def discover_schema(doc_path: Path | None, data: Any) -> SchemaRef:
    """
    Resolution order:
      1. data['$schema'] is a *local file path* → load it;
      2. <doc_path>.schema.json sibling file → load it;
      3. otherwise SchemaRef(None, None, "none").
    Remote $schema URLs are *ignored* (kept as the schema's identifier
    only). Loader uses io_formats.load_file_with_format so YAML
    schemas work too.
    """

def load_schema(ref: SchemaRef) -> Mapping[str, Any] | None: ...

# validation/index.py
class IssueIndex:
    """O(1) lookup: model_path -> max severity, plus
    issues_for(path) -> list[ValidationIssue]."""

    def __init__(self, issues: Iterable[ValidationIssue], root_data: Any): ...
    def severity_at(self, model_path: tuple[int, ...]) -> str | None: ...
    def issues_for(self, model_path: tuple[int, ...]) -> list[ValidationIssue]: ...
    def ancestor_severity(self, model_path: tuple[int, ...]) -> str | None:
        """For container rows: highest severity in this subtree."""
    def __len__(self) -> int: ...

# documents/tab.py (additive)
class JsonTab(QWidget):
    schemaChanged = Signal(object)         # SchemaRef | None
    validationChanged = Signal(object)     # IssueIndex
    # ...
    @property
    def schema(self) -> Mapping[str, Any] | None: ...
    @property
    def schema_ref(self) -> SchemaRef: ...
    @property
    def issue_index(self) -> IssueIndex: ...

    def set_schema(self, ref: SchemaRef) -> None: ...
    def clear_schema(self) -> None: ...
    def revalidate(self) -> None: ...
```

## Implementation notes

- `JsonTab.__init__` calls `discover_schema(file_path, data)` once
  the model is loaded; emits `schemaChanged` and `validationChanged`
  even when the result is empty so the (Step-3) dock can clear
  itself.
- `revalidate()`:
  - serialises the live model to plain Python via `root_item.to_json()`;
  - delegates to `validation.validator.validate_document`;
  - replaces `self._issue_index = IssueIndex(issues, root_data)`;
  - emits `validationChanged`.
- `IssueIndex` builds two maps in `__init__`:
  - `_exact: dict[tuple[int, ...], list[ValidationIssue]]`;
  - `_ancestor: dict[tuple[int, ...], str]` (max severity along
    every ancestor of every issue) — pre-computed so the delegate
    paint path is O(1).
- `state/validation_settings.py` exposes only stubs in this step:
  `read_schema_path(doc_path)`, `write_schema_path(doc_path, schema_path)`.
  Step 7 wires them into the picker UI.
- No QTimer / debounce yet — every call site invokes `revalidate()`
  explicitly. The debounce belongs to Step 6.

## Tests

- `test_schema_source.py`: inline `$schema` (local path) wins over
  sibling; remote URL is ignored (origin == "none"); sibling-file
  variant; YAML schema loads via `io_formats.load_file_with_format`.
- `test_tab_schema_state.py`: tab constructed with `data=` and a
  valid schema → `validationChanged` fires once, `issue_index` empty;
  call `set_schema(bad_schema)` → `schemaChanged` fires, then
  `validationChanged` reports the bad-data issues. Uses `qtbot`.
- `test_validation_index.py`: `severity_at` exact match,
  `ancestor_severity` for containers, deletion-safe lookups, empty
  index degenerate path.

## Out of scope

- The dock that displays the issues (Step 3).
- Tree-row decoration (Step 5).
- Hot rescan on `dataChanged` (Step 6).

## Commit message

```
feat(validation): per-tab schema state + IssueIndex

- validation.schema_source: inline $schema / sibling-file discovery
- validation.index: O(1) lookup of severity per model path,
  plus ancestor-aggregated severity for container rows
- JsonTab gains schemaChanged / validationChanged signals,
  set_schema / clear_schema / revalidate(), and reads attached
  schema on construction
```
