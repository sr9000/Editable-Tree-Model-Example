# Stage 06 — Validation error adapter boundary

Covers report scenario **F1**.

## Targets

| File                          | Lines       | Probe                                                  |
|-------------------------------|-------------|--------------------------------------------------------|
| `validation/validator.py`     | 119         | `getattr(err, "kind"/"validator"/"keyword"/"rule", …)` |
| `validation/validator.py`     | 134         | `getattr(err, "validator", …)`, `getattr(err, "context", …)` |
| `validation/validator.py`     | 144         | `getattr(err, "schema_path", …)`                       |
| `validation/validator.py`     | 192, 193    | `getattr(err, "path", …)`, `getattr(err, "schema_path", …)` |
| `validation/validator.py`     | 231, 232    | same                                                   |
| `validation/validator.py`     | 242, 244    | `getattr(err, "instance_path", …)`, `getattr(err, "path", …)` |
| `validation/validator.py`     | 246         | `getattr(err, "message", "")`                          |
| `validation/validator.py`     | 248         | `getattr(err, "schema_path", …)`                       |

## Why this is a *partial* exception

These probes target foreign objects (`jsonschema.exceptions.ValidationError`
and shaped-alike error objects). That is a legitimate adapter boundary —
but the boundary should be **crossed exactly once**, at the edge,
producing a frozen normalized object. The rest of `validator.py` must
not be reflection-driven.

## Target design

### 1. Define `NormalizedValidationError`

```python
@dataclass(frozen=True, slots=True)
class NormalizedValidationError:
    kind: str
    validator: str | None
    keyword: str | None
    rule: str | None
    message: str
    instance_path: tuple[str | int, ...]
    schema_path: tuple[str | int, ...]
    context: tuple["NormalizedValidationError", ...] = ()
```

### 2. Single adapter function — the only place reflection is allowed

```python
def normalize_validation_error(err: object) -> NormalizedValidationError:
    # The ONE place where getattr is permitted in this file.
    return NormalizedValidationError(
        kind=getattr(err, "kind", None) or _derive_kind(err),
        validator=getattr(err, "validator", None),
        keyword=getattr(err, "keyword", None),
        rule=getattr(err, "rule", None),
        message=getattr(err, "message", ""),
        instance_path=tuple(getattr(err, "instance_path", None)
                            or getattr(err, "path", ())),
        schema_path=tuple(getattr(err, "schema_path", ())),
        context=tuple(normalize_validation_error(c)
                      for c in getattr(err, "context", ()) or ()),
    )
```

This function (and only this function) is added to the allowlist for the
pre-commit hook — see stage 10.

### 3. Rewrite the rest of `validator.py` against the dataclass

Every other site (scoring specificity, combinator unwrapping, building
schema paths, message extraction) consumes `NormalizedValidationError`
fields directly. No further `getattr` in this file.

### 4. Move the adapter to its own module (optional but recommended)

Put `normalize_validation_error` in `validation/error_adapter.py`. That
way the allowlist only needs to whitelist a single file dedicated to
foreign-object normalization, mirroring how stage 10 whitelists
`jsontream/__init__.py`.

## Steps

1. Add `NormalizedValidationError` dataclass.
2. Add `normalize_validation_error(err)` (the single allowed reflection
   site) in `validation/error_adapter.py`.
3. Refactor the rest of `validation/validator.py` to consume the
   normalized type. Every former `getattr(err, ...)` call site reads a
   dataclass field instead.
4. Add a unit test that feeds a real `jsonschema.ValidationError` and a
   minimal duck-typed stand-in through the adapter and asserts they
   normalize identically.
5. `grep -n 'getattr\|hasattr' validation/validator.py` returns nothing.
6. `grep -n 'getattr' validation/error_adapter.py` is the only remaining
   occurrence in `validation/`.

## Acceptance criteria

- `validation/validator.py` contains zero `getattr` / `hasattr`.
- All reflection on foreign error objects is concentrated in
  `validation/error_adapter.py`.
- Validation-engine round-trip tests (combinator unwrapping, oneOf /
  anyOf specificity scoring, path rebuilding) pass unchanged.
- Report inventory drops by **15** `getattr` expressions inside
  `validator.py`; **1** site remains in `error_adapter.py` and is
  allowlisted in stage 10.
