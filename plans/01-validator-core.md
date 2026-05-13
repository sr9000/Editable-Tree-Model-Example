# Step 1 — Validator core + pointer mapping

_Commit-sized: 6 source files + 3 test files; ~300 LOC._

## Scope

1. Pin `jsonschema-rs` in `requirements.txt`.
2. Introduce a new `validation/` package independent of Qt and of the
   tree model — pure functions over Python primitives, so it stays
   trivially testable.
3. Build the bridge between `jsonschema-rs`' `instance_path`
   (tuple of `str | int`) and the tree's existing
   path-of-`int`-rows used by `documents/tab_paths.index_from_path`.

This step ships **no UI** and **does not touch `JsonTab`**. The next
step wires the result into the tab. Doing the engine in isolation
keeps the diff small and gives us a clean unit-test surface.

## Files touched (8)

```
requirements.txt                       # +jsonschema-rs==<latest stable>
validation/__init__.py                 # re-exports
validation/issue.py                    # ValidationIssue dataclass
validation/validator.py                # validate_document(data, schema)
validation/json_pointer.py             # instance_path ↔ model path
validation/_engine.py                  # thin jsonschema_rs wrapper
tests/test_validation_validator.py     # happy paths, draft detection
tests/test_validation_pointer.py       # instance_path mapping matrix
```

## Public API (frozen by end of step)

```python
# validation/issue.py
@dataclass(frozen=True, slots=True)
class ValidationIssue:
    severity: Literal["error", "warning"]
    message: str
    instance_path: tuple[str | int, ...]      # from jsonschema-rs
    schema_path: tuple[str | int, ...]
    kind: str                                  # validator name, e.g. "required"

# validation/validator.py
def validate_document(
    data: Any,
    schema: Mapping[str, Any],
    *,
    max_issues: int = 500,
) -> list[ValidationIssue]: ...

def is_schema_valid(schema: Mapping[str, Any]) -> tuple[bool, str | None]:
    """Cheap meta-validation; returns (ok, error_message)."""

# validation/json_pointer.py
def instance_path_to_model_path(
    root_data: Any,                            # the live Python tree
    instance_path: Sequence[str | int],
) -> tuple[int, ...] | None:
    """
    Translate jsonschema-rs' (str-for-objects, int-for-arrays) path
    into the (row, row, ...) tuple the JsonTreeModel + tab_paths
    understand. Returns None when the path no longer exists
    (e.g. user deleted the row between validation and click).
    """

def model_path_to_instance_path(
    root_data: Any,
    model_path: Sequence[int],
) -> tuple[str | int, ...]:
    """Reverse direction — used later by the in-tree indicator."""
```

## Implementation notes

- `validation/_engine.py` lazily imports `jsonschema_rs` and exposes
  `compile(schema_dict) -> _Compiled` with a `.iter_errors(instance)`
  shim. This keeps `from validation import ...` cheap and lets us
  monkey-patch the engine in tests.
- `jsonschema_rs.validator_for(schema)` is preferred over the
  deprecated `JSONSchema`; fall back to `JSONSchema(schema)` if the
  installed wheel is older. Branch on `hasattr(jsonschema_rs, "validator_for")`.
- `instance_path` items can be `str` (object key) or `int` (array
  index). When `root_data` is an `OBJECT`, look up by name in
  *insertion order* against `JsonTreeItem.child_items` semantics —
  i.e. simulate the same dict-iteration that produced the tree.
- Cap issue collection at `max_issues=500` to keep the dock model
  responsive on pathological schemas.
- No Qt imports in this package — adding `from PySide6...` should
  fail review.

## Tests

`tests/test_validation_validator.py`:
- valid document → empty list;
- missing required key → one `kind == "required"` issue;
- type mismatch → `kind == "type"`;
- `max_issues` truncation;
- `is_schema_valid` rejects a syntactically broken schema.

`tests/test_validation_pointer.py`:
- root pointer (`()`) → `()`;
- nested `("a", 0, "b")` → matching `(row_a, 0, row_b)`;
- non-existent key → `None`;
- mpq values pass through unaffected.

## Out of scope

- YAML loading (Step 7).
- `$ref` resolution against external files (Step 7 may add a local
  resolver; for now `jsonschema-rs` handles inline `$defs`).
- Tab/UI wiring (Step 2).

## Commit message

```
feat(validation): add jsonschema-rs core wrapper

- pin jsonschema-rs in requirements.txt
- new validation/ package: ValidationIssue, validate_document,
  json-pointer ↔ model-path mapping
- 38 new unit tests, zero Qt dependency
```
