# Plan 02 — Numbers with prefix / suffix (stored as string)

## Goal

Allow integers and floats to carry a **textual prefix or suffix** (but never
both at once). The whole value is stored verbatim **as a string** so the
exact user input is preserved through save/load. Examples:

- `"$1234"`, `"$ 1234"`            ← prefix `$`
- `"1234 USD"`, `"1234USD"`        ← suffix `USD`
- `"99.95 %"`, `"-3.14e2 m/s"`     ← suffix on a float
- `"0x1F kB"`                      ← rejected (we don't combine number-base
  flags with units; covered by *Validation*, see below)

The number portion supports the same syntax as the existing `INTEGER` /
`FLOAT` editors (sign, decimal, optional exponent for floats). Whitespace
between affix and number is **optional** and preserved on round-trip.

Affixes are arbitrary user text but constrained:

- non-empty;
- contains no digit at the boundary touching the number (so a parser can
  unambiguously split);
- max length configurable (default 16 chars).

## Design notes

- Two new `JsonType` members:
  - `INTEGER_AFFIX = "integer+affix"`
  - `FLOAT_AFFIX = "float+affix"`
- Storage shape (in-memory tree): a `tuple[str, str, Affix]` is **not** used —
  values stay as plain Python `str`. Parsing is on demand. This keeps the
  existing model invariant ("editor value type matches `JsonType`'s native
  Python type or `str`").
- A small dataclass `NumberAffix(prefix: str | None, suffix: str | None,
  space: bool, number_text: str)` is the parsed projection used by
  delegates / validators.
- New module: `units/number_affix.py` (the `units/` folder already exists).
- Detection: in `parse_json_type`, after color/datetime/base64 checks and
  before the bare-number checks, try `parse_number_affix(s)`. If it splits
  and the numeric core parses as int → `INTEGER_AFFIX`; as float →
  `FLOAT_AFFIX`; otherwise fall through.
- Editing: a dedicated `delegates/number_affix_delegate.py` providing a
  composite editor (affix line edit + number spinbox / line edit). On commit
  it joins them according to the original space flag.
- Type-change conversions:
  - `INTEGER ↔ INTEGER_AFFIX`: drop or attach last-used affix (per cell,
    remembered in `Qt.UserRole`).
  - `INTEGER_AFFIX ↔ FLOAT_AFFIX`: parse number portion, retype, keep affix.
  - `FLOAT_AFFIX → INTEGER_AFFIX`: only if number is exactly representable as
    int.

## Commits

### Commit 1 — `units/number_affix.py` (new)

Pure parser/serializer:

```python
@dataclass(frozen=True)
class NumberAffix:
    prefix: str | None
    suffix: str | None
    space: bool          # True iff a single space separates affix and number
    number_text: str     # exactly what the user typed for the number

def parse_number_affix(s: str) -> NumberAffix | None: ...
def format_number_affix(na: NumberAffix) -> str: ...
def is_int_core(na: NumberAffix) -> bool: ...
def is_float_core(na: NumberAffix) -> bool: ...
```

Rules (regex-based):

- `^(?P<prefix>\D[^\d\s]*?)(?P<sp>\s?)(?P<num>[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)$`
- `^(?P<num>...)(?P<sp>\s?)(?P<suffix>[^\d\s].*?)$`
- Both prefix **and** suffix → returns `None` (caller must treat as plain
  string).

**DoD**

- `tests/test_number_affix.py` covers:
  - `"$1234"` → prefix `$`, no space, int core.
  - `"$ 1234"` → prefix `$`, space, int core.
  - `"99.95%"` / `"99.95 %"` → suffix `%`, float core.
  - `"-3.14e2 m/s"` → suffix `m/s`, float core.
  - `"$1234 USD"` → `None` (both affixes).
  - `"1234"` → `None` (no affix; bare number is not "affixed").
  - `format_number_affix(parse_number_affix(s)) == s` for every accepted `s`
    (round-trip property).
- No imports from Qt or other app modules. Pure stdlib + `re` + `dataclasses`.

### Commit 2 — `tree/types.py`

- Add `JsonType.INTEGER_AFFIX`, `JsonType.FLOAT_AFFIX`.
- Add `NUMBER_FAMILY` frozenset
  (`INTEGER, FLOAT, PERCENT, INTEGER_AFFIX, FLOAT_AFFIX`).
- Extend `parse_json_type(str(s))` branch: try `parse_number_affix(s)` after
  color and before base64, classify int vs float core.

**DoD**

- `parse_json_type("$1234") == JsonType.INTEGER_AFFIX`.
- `parse_json_type("3.14 rad") == JsonType.FLOAT_AFFIX`.
- `parse_json_type("1234") == JsonType.INTEGER` (unchanged — bare number is
  parsed by the upstream `int()` path; this branch only sees strings already
  not parseable as numbers).
- `parse_json_type("hello world")` unchanged → `STRING`.
- Existing `tests/test_types*` all green.

### Commit 3 — `delegates/value_formatting.py`

- Render `INTEGER_AFFIX` / `FLOAT_AFFIX` exactly as stored (no normalization).
- Color/style hint matching existing number kinds (right-align number,
  affix in muted color).

**DoD**

- Snapshot test or simple unit test asserting the formatted text equals the
  raw stored string.
- Manual run (documented): sample tree with `"$1234"` shows up right-aligned
  with `$` in the configured "affix" color.

### Commit 4 — `delegates/number_affix_delegate.py` (new)

Composite editor:

- `QLineEdit` for prefix (left), `QLineEdit`/spinbox for the number,
  `QLineEdit` for suffix (right). Empty side is hidden but toggleable via
  context menu.
- Live validation using `parse_number_affix` on a synthesized string;
  rejects "both prefix and suffix".
- Preserves `space` flag from the original string.

**DoD**

- Editor opens, accepts a value, commits string identical to a known input
  (verified with a Qt Test or manual smoke recorded in commit body).
- Trying to fill both prefix and suffix disables OK / shows red border.
- Empty number portion rejected.

### Commit 5 — `delegates/type_delegate.py`

Wire the new types into the dropdown for cells in `NUMBER_FAMILY`:

- Conversions implemented per the matrix in *Design notes*.
- Last-used affix per cell stored in a `Qt.UserRole + N` slot; reapplied on
  re-entering the affix variant.

**DoD**

- Switch `INTEGER (1234) → INTEGER_AFFIX` → cell becomes `"1234"` and the
  user can type a prefix/suffix in the editor.
- Switch back to `INTEGER` → cell becomes `1234` (int).
- Switching `FLOAT_AFFIX("3.5 m") → INTEGER_AFFIX` is rejected (3.5 ≠ int);
  switching `FLOAT_AFFIX("3 m") → INTEGER_AFFIX` succeeds.
- Undo/redo of a type switch restores prior text exactly.

### Commit 6 — `io_formats/dump.py` + `io_formats/load.py`

- Dump: emit the stored string verbatim.
- Load: `parse_json_type` already handles the inference; just verify nothing
  in load coerces affixed strings to numbers.

**DoD**

- `tests/test_io_number_affix.py` round-trips a tree containing all six
  sample affix strings (JSON and YAML).
- A loaded tree with `"$1234"` reports `JsonType.INTEGER_AFFIX` for that
  cell.

### Commit 7 — `settings.py`

- Add `NUMBER_AFFIX_MAX_LEN = 16` (default).
- Add optional `NUMBER_AFFIX_ALLOW_SPACE = True` (toggle to forbid
  with-space form).

**DoD**

- Settings exposed as plain module constants (matching existing pattern).
- Parser reads them at module level (or via an injected config) — verified
  by a unit test that mutates settings and re-parses.

### Commit 8 — Docs

Update `README.md` and `ai-memory/repo-map.md`:

- New kinds documented with examples.
- Reference `units/number_affix.py` and the conversion rules.

**DoD**

- repo-map mentions both new `JsonType` members and the new module.
- README's "supported types" gains the affix examples.
