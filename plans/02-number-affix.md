# Plan 02 — Numbers with prefix XOR suffix (structured storage)

## Decisions (locked after Q&A round 1)

- **Strict XOR.** A value has *either* a prefix *or* a suffix, never both,
  never neither (a bare number stays `INTEGER` / `FLOAT` / `PERCENT` with
  the existing editors). Orientation is encoded in the `JsonType`.
- **Four new `JsonType` members** (mirrors the `DATETIME*` split):
  - `INTEGER_CURRENCY = "int currency"`
  - `INTEGER_UNITS = "int units"`
  - `FLOAT_CURRENCY   = "float currency"`
  - `FLOAT_UNITS   = "float units"`
- **Storage shape: structured.** Cell value is a frozen
  `NumberAffix(kind, affix, space, number)` dataclass with
  `number: int | gmpy2.mpq`. JSON / YAML I/O serialises to a string and
  parses it back on load.
- **Bare numbers untouched.** `INTEGER` / `FLOAT` / `PERCENT` keep their
  current spinbox editors. `PERCENT` is **not** absorbed.
- **Composite editor: exactly three widgets, tight pack, shrink-to-content.**
  - CURRENCY variants:  `[combo (bank_line icon) + inline space-button]`,
                      `[QBigIntSpinBox / QMpqSpinBox]`.
  - UNITS variants:  `[QBigIntSpinBox / QMpqSpinBox]`,
                      `[combo (ruler_line icon) + inline space-button]`.
  - The space-button is a small checkable `QToolButton` (icon-only,
    tooltip "Space between affix and number") embedded on the inner edge
    of the combo (edge facing the number).
  - Orientation switch (prefix↔suffix) is done by changing the `JsonType`
    via the type delegate — there is no in-editor flip.
- **Combo dropdown source: per-document MRU.** Two MRU lists per
  document/tab (prefix, suffix). Each successful commit pushes the affix
  to the front; cap from settings.
- **Icons via theme.** Add logical keys `affix_prefix` → `bank_line` and
  `affix_suffix` → `ruler_line`. Resolved by `themes/icon_provider.py`
  via a new `for_key(key)` helper (does not touch the per-`JsonType` map).
- **Space semantics: strict preserve.** Checkbox ⇔ exactly one ASCII
  space between affix and number. On load, the parser observes the source
  spacing and sets the flag; arbitrary multi-space input is rejected by
  the parser (treated as `STRING`).
- **Affix constraints**:
  - non-empty;
  - the char touching the number (last char of prefix / first char of
    suffix) is non-digit, non-sign, non-whitespace, non-`.`;
  - max length from `settings.NUMBER_AFFIX_MAX_LEN` (default 16);
  - no internal/edge whitespace in the affix; the inter-token space is
    represented by the *space flag*, never embedded in the affix string.

## Module layout

```
units/number_affix.py                 # dataclass + parser + serialiser (pure)
delegates/number_affix_delegate.py    # composite editor + paint hook
tree/types.py                         # +4 enum members, parse hooks, NUMBER_FAMILY
themes/icon_provider.py               # +for_key()
themes/spec.py                        # +affix_prefix / affix_suffix logical keys
state/affix_mru.py                    # per-document MRU lists
io_formats/dump.py & load.py          # NumberAffix <-> str
settings.py                           # NUMBER_AFFIX_MAX_LEN, NUMBER_AFFIX_MRU_SIZE
tests/test_number_affix.py
tests/test_number_affix_delegate.py
tests/test_io_number_affix.py
```

---

## Commits

### Commit 1 — `units/number_affix.py` (new, pure)

`NumberAffix` dataclass + parser + serialiser. No Qt, no app deps.

```python
class AffixKind(StrEnum):
    CURRENCY = "prefix"
    UNITS = "suffix"

@dataclass(frozen=True, slots=True)
class NumberAffix:
    kind: AffixKind
    affix: str               # non-empty, validated
    space: bool              # single ASCII space between affix and number
    number: int | gmpy2.mpq  # caller's chosen numeric type

def parse_number_affix(s: str, *, max_affix_len: int = 16) -> NumberAffix | None: ...
def format_number_affix(na: NumberAffix) -> str: ...
def is_integer_core(na: NumberAffix) -> bool: ...
```

Anchored regexes (only ASCII `\u0020` as separator):

```
CURRENCY_RE = r"^(?P<affix>[^\d\s+\-.][^\s]*?)(?P<sp> ?)(?P<num>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)$"
UNITS_RE = r"^(?P<num>...)(?P<sp> ?)(?P<affix>[^\d\s+\-.eE](?:[^\s]*[^\s])?)$"
```

**DoD**
- `tests/test_number_affix.py` parametrized:
  - `"$1234"` → `NumberAffix(CURRENCY, "$", False, 1234)`.
  - `"$ 1234"` → same but `space=True`.
  - `"99.95%"` → `NumberAffix(UNITS, "%", False, mpq(1999, 20))`.
  - `"-3.14e2 m/s"` → `NumberAffix(UNITS, "m/s", True, mpq(-157, 50))` —
    or equivalent rational; round-trip is what matters.
  - `"$1234 USD"`, `"1234"`, `""`, `" 1234"`, `"$\t1234"`, `"$  1234"`
    → all `None`.
  - Affix longer than `max_affix_len` → `None`.
  - Round-trip: `format_number_affix(parse_number_affix(s)) == s` for
    every accepted `s` in a frozen sample list.
- Imports: stdlib + `re` + `dataclasses` + `gmpy2` only.

### Commit 2 — `tree/types.py` (enum + classification)

- Add the 4 enum members above.
- Add `NUMBER_FAMILY` frozenset:
  `{INTEGER, FLOAT, PERCENT, INTEGER_CURRENCY, INTEGER_UNITS, FLOAT_CURRENCY, FLOAT_UNITS}`.
- Extend `parse_json_type`:
  - New `match` arm for `NumberAffix` values → maps
    `(kind, isinstance(number, int))` to the four enum members.
  - Inside the `str` arm, after color/datetime and **before** base64, call
    `parse_number_affix(s)`. On success, return the matching enum (do not
    coerce model value here — see Commit 3).

**DoD**
- `parse_json_type(NumberAffix(CURRENCY, "$", False, 1234)) == JsonType.INTEGER_CURRENCY`.
- `parse_json_type("$1234") == JsonType.INTEGER_CURRENCY`.
- `parse_json_type("3.14 rad") == JsonType.FLOAT_UNITS`.
- `parse_json_type("1234") == JsonType.INTEGER` (unchanged).
- `parse_json_type("hello world") == JsonType.STRING` (unchanged).
- Existing `tests/test_types*` green.

### Commit 3 — `io_formats/load.py` + `io_formats/dump.py`

- **Load:** inbound strings that parse as `NumberAffix` are replaced with
  the dataclass instance in the in-memory tree (preserves the invariant
  "cell value matches `JsonType`'s native shape").
- **Dump:** serialise `NumberAffix` cells via `format_number_affix`
  (string output; neither JSON nor YAML has a native form).
- Idempotency: dump → load → dump byte-equal.

**DoD**
- `tests/test_io_number_affix.py`:
  - Round-trips a fixture tree with the six canonical samples
    (prefix/suffix × space on/off × int/float).
  - JSON and YAML byte-equal after one and two round-trips.
  - A loaded `"$1234"` cell has `item.value: NumberAffix` and
    `parse_json_type(item.value) == INTEGER_CURRENCY`.
  - Bare numbers (`1234`, `3.14`) remain `int` / `mpq`.

### Commit 4 — `state/affix_mru.py` + document hook

- New module: `AffixMRU` with two `OrderedDict[str, None]` (prefix,
  suffix). API: `push(kind, affix)`, `items(kind) -> list[str]`,
  `bootstrap_from_tree(root)`.
- Wire it into per-tab state (likely `documents/tab.py`; confirm at
  implementation time). On document open, walk the tree to seed both
  lists. On successful delegate commit, push the affix.
- Size capped by `settings.NUMBER_AFFIX_MRU_SIZE` (default 32).

**DoD**
- Unit test: `bootstrap_from_tree` deduplicates and preserves recency.
- `push` evicts oldest beyond the cap.
- Prefix and suffix MRUs are independent.

### Commit 5 — `themes/icon_provider.py` + theme spec

- Add `for_key(self, key: str) -> QIcon` to `IconProvider` Protocol and
  both implementations.
- Register `affix_prefix` → `bank_line`, `affix_suffix` → `ruler_line` in
  the default theme spec; the SVGs already ship under
  `themes/builtin/mingcute*/`.
- Share cache with `for_type`; flat string namespace.

**DoD**
- `provider.for_key("affix_prefix").isNull() is False` for every shipped
  theme.
- Existing icon tests green.

### Commit 6 — `settings.py`

Add:
- `NUMBER_AFFIX_MAX_LEN: int = 20`
- `NUMBER_AFFIX_MRU_SIZE: int = 50`

**DoD**
- Module-level constants matching the existing pattern.
- App code (`tree/types.py`, `io_formats/load.py`, delegate) passes
  `NUMBER_AFFIX_MAX_LEN` to `parse_number_affix`; the pure parser stays
  config-free.

### Commit 7 — `delegates/number_affix_delegate.py` (new)

Composite `QStyledItemDelegate`:

- `createEditor` returns `_AffixCompositeEditor(QWidget)` with
  `QHBoxLayout(spacing=0, contentsMargins=(0,0,0,0))`. Children depend on
  the cell's `JsonType`:
  - **CURRENCY:** `_AffixCombo(kind=CURRENCY, mru=…, icon=affix_prefix)`,
    then `QBigIntSpinBox` / `QMpqSpinBox`.
  - **UNITS:** number widget, then
    `_AffixCombo(kind=UNITS, mru=…, icon=affix_suffix)`.
- `_AffixCombo` is `QComboBox(editable=True)`:
  - leading icon (`bank_line` / `ruler_line`) installed on the `QLineEdit`
    via `addAction(icon, leading_or_trailing)` so it sits inside the
    combo's clickable area;
  - a small checkable `QToolButton` (16×16, `autoRaise`, icon-only,
    tooltip "Space between affix and number") placed on the inner edge
    via an action; falls back to a sibling `QToolButton` in the outer
    layout if action-placement can't yield a clean hit target. In the
    fallback the user-visible widget count is still three (combo,
    number, button) — note in PR.
- Size policies: number widget `Preferred`; combos `Minimum` +
  `setMinimumContentsLength(1)`; outer editor `Preferred, Fixed`.
- `setEditorData` unpacks the `NumberAffix` into the controls.
- `setModelData` builds a candidate `NumberAffix` and validates via
  `parse_number_affix(format_number_affix(candidate))`; on failure flips
  `property("invalid", True)` + repolish (red border) and refuses commit.
- On successful commit, the delegate pushes the affix into the tab's
  `AffixMRU`.

**DoD**
- `pytest-qt` headless: create editor for a CURRENCY cell, set `"$"`,
  number `1234`, space on, commit → model receives
  `NumberAffix(CURRENCY, "$", True, 1234)`.
- Same for UNITS with `"%"` and `mpq(1999, 20)`.
- Invalid affix (empty, digit at boundary, too long) → red border state,
  refuses commit; Esc reverts cleanly.
- Screenshot in commit body showing shrink-to-content tight pack for
  both orientations.

### Commit 8 — `delegates/value_formatting.py` + view paint

- Render the four affix `JsonType`s as `format_number_affix(value)`.
- Style: number portion right-aligned monospace like other numbers; affix
  in a muted `affix_text` theme colour (add this attribute to the theme
  spec with sensible defaults per built-in theme).

**DoD**
- Unit test on the formatter: for each of the 4 enum members the rendered
  text equals `format_number_affix`.
- Manual: sample tree shows `$1234` with `$` muted, `1234` regular.

### Commit 9 — `delegates/type_delegate.py` (type switching)

Wire the four new types into the dropdown when the cell is in
`NUMBER_FAMILY`. Conversion matrix (everything stays inside
`NUMBER_FAMILY`):

| from \ to        | INT  | FLOAT | PCT | INT_CURR | INT_UNITS | FLT_CURR | FLT_UNITS |
|------------------|------|-------|-----|----------|-----------|----------|-----------|
| INTEGER          | =    | float | %   | apply A  | apply A   | flt+A    | flt+A     |
| FLOAT            | int* | =     | %   | int*+A   | int*+A    | apply A  | apply A   |
| PERCENT          | n/a  | float | =   | n/a      | n/a       | apply A  | apply A   |
| INTEGER_CURRENCY | drop | float | n/a | =        | flip      | float    | flt+flip  |
| INTEGER_UNITS    | drop | float | n/a | flip     | =         | flt+flip | float     |
| FLOAT_CURRENCY   | int* | drop  | n/a | int*     | int*+f    | =        | flip      |
| FLOAT_UNITS      | int* | drop  | n/a | int*+f   | int*      | flip     | =         |

- `int*` requires exact integer value of the float core; disabled
  otherwise (greyed in dropdown).
- `apply A` = pull most-recent affix from doc MRU for the target kind
  (empty if MRU empty; user edits next).
- `flip` = keep affix + space + number, swap `kind`.
- `drop` = strip affix, retain numeric core.
- Per-cell "last affix" stored in `Qt.UserRole + N` so switching out and
  back into an affix variant restores the affix.

**DoD**
- INTEGER(1234) → INTEGER_CURRENCY → cell becomes
  `NumberAffix(CURRENCY, mru_top_or_"", False, 1234)`.
- FLOAT_CURRENCY("$3.5") → INTEGER_CURRENCY → disabled.
- FLOAT_CURRENCY("$3.0") → INTEGER_CURRENCY → succeeds, value
  `NumberAffix(CURRENCY, "$", False, 3)`.
- INTEGER_CURRENCY → INTEGER_UNITS preserves affix + space + number.
- Undo/redo of every transition restores prior state exactly.

### Commit 10 — Docs + repo-map

Update `README.md` and `ai-memory/repo-map.md`:

- New `JsonType` members with one-line examples.
- Reference `units/number_affix.py`, `delegates/number_affix_delegate.py`,
  `state/affix_mru.py`.
- Document the composite-editor layout (3 widgets, tight pack, inline
  space toggle, theme-driven icons).
- Note that PERCENT stays separate.

**DoD**
- `ai-memory/repo-map.md` lists every new module and the four enum
  members.
- `README.md`'s "supported types" gains the four affix examples.
- `plans/README.md` marks plan 02 as done.

---

## Notes / risks / follow-ups

- Inline `QToolButton` inside a `QComboBox`'s `QLineEdit` must not
  overlap the dropdown arrow. Fall-back placement (sibling button in the
  outer layout) is acceptable per Commit 7's DoD.
- `gmpy2.mpq` round-trip through string is lossless for finite decimals
  and exponent notation; non-terminating fractions cannot be typed via
  the spinbox so this is a non-issue. Documented in the parser docstring.
- "Both prefix and suffix" is explicitly out of scope. If requested
  later, it would be a separate pair (`*_AFFIX_BOTH`) with a 4-widget
  editor.
