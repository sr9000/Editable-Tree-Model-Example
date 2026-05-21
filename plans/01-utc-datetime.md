# Plan 01 — UTC DateTime (Zulu / `Z` suffix) with smart conversions

## Goal

Add a first-class **UTC datetime** value kind that is serialized with a trailing
`Z` (e.g. `2026-05-21T14:33:09Z`, `2026-05-21T14:33:09.123456Z`) and a smart
conversion lattice between every existing date/time variant:

- `DATE` ↔ `TIME` ↔ naive `DATETIME` ↔ `DATETIMEZONE` ↔ **`DATETIMEUTC`**
- Switching `DATETIMEZONE → DATETIMEUTC` performs **a real timezone shift**
  (i.e. local-with-offset is normalized to UTC instant), not a flag flip.
- Switching `DATETIMEUTC → DATETIMEZONE` attaches `+00:00`.
- Switching naive `DATETIME ↔ DATETIMEUTC` preserves wall-clock components and
  only adds/strips `Z` (no implicit local-tz assumption).
- Round-trip through a known offset is lossless when going UTC → +tz → UTC.

DST / "skipped or repeated wall-clock" edge cases are surfaced via
`tzinfo`-aware arithmetic only; we never attach a named IANA zone, only fixed
offsets (matches the existing `DATETIMEZONE` model).

## Design notes

- New enum value `JsonType.DATETIMEUTC = "dt+utc"` in `tree/types.py`.
- New regex / parser branch accepting the `...Z` suffix (with and without
  fractional seconds, both `T` and space separators, mirroring existing
  variants).
- Parser pseudo-code (in `datetime_editor/regex.py`):
  - `...Z`         → `datetime(..., tzinfo=timezone.utc)`
  - `...+HH:MM`    → existing `DATETIMEZONE`
  - bare           → naive `DATETIME`
- `parse_json_type` returns `DATETIMEUTC` when `datetime.tzinfo == timezone.utc`
  **and** the source string ended in `Z` (we keep `+00:00` as `DATETIMEZONE` to
  preserve the user's chosen rendering).
- Smart conversion lives in a single helper, e.g.
  `tree/types_datetime.py::convert_datetime(value, src: JsonType, dst: JsonType) -> Any`,
  used by the type-change action and tested in isolation.
- Editor (`datetime_editor/better_dt_editor.py`) gains a UTC category that
  forces `tzinfo=utc` and renders with `Z`.

---

## Commits

Each commit is **one logical file**. Tests live in `tests/` and may be added
alongside their target commit (counted as same commit) when they exclusively
test that file.

### Commit 1 — `datetime_editor/enums.py`

Add `DateTimeCategory.DateTimeUTC`.

**DoD**

- New enum member exists.
- `from datetime_editor.enums import DateTimeCategory` still imports cleanly.
- `grep -R "DateTimeCategory\." | wc -l` shows no broken match-case (every
  existing `match` over the enum either handles the new member or has a
  default branch — verified manually, no runtime fallthrough).

### Commit 2 — `datetime_editor/regex.py`

Extend `parse_datetime_text` to accept trailing `Z`:

- New regex branch `...Z` with and without `.ffffff`, `T` or space separator.
- Returns `datetime(..., tzinfo=timezone.utc)`.
- `category=DateTimeCategory.DateTimeUTC` rejects non-UTC strings.

**DoD**

- Unit tests in `tests/test_datetime_regex_utc.py` pass:
  - `"2026-05-21T14:33:09Z"` → aware UTC datetime.
  - `"2026-05-21 14:33:09.5Z"` → microsecond=500000, aware UTC.
  - `"2026-05-21T14:33:09+00:00"` still parses (still `DATETIMEZONE` from
    caller's POV — parser stays format-faithful).
  - Invalid (`"...+05:00"` with `category=DateTimeUTC`) raises.
- No regressions in existing `tests/test_datetime*` (all green).

### Commit 3 — `tree/types.py`

- Add `JsonType.DATETIMEUTC = "dt+utc"`.
- Update `parse_json_type` to map a UTC-aware datetime whose source string
  ended in `Z` to `DATETIMEUTC`. (Implementation: parser returns a sentinel /
  the caller checks the original string.)
- Add `DATETIME_FAMILY` frozenset (`DATE, TIME, DATETIME, DATETIMEZONE,
  DATETIMEUTC`) for downstream gating.

**DoD**

- `parse_json_type("2026-01-01T00:00:00Z") == JsonType.DATETIMEUTC`.
- `parse_json_type("2026-01-01T00:00:00+00:00") == JsonType.DATETIMEZONE`
  (unchanged).
- `parse_json_type("2026-01-01T00:00:00") == JsonType.DATETIME` (unchanged).
- All existing tests touching `JsonType` still green.

### Commit 4 — `tree/types_datetime.py` (new)

Single-purpose conversion module:

```python
def convert_datetime(value: Any, src: JsonType, dst: JsonType) -> Any: ...
```

Conversion matrix (only inside `DATETIME_FAMILY`):

| from \\ to       | DATE | TIME | DATETIME      | DATETIMEZONE   | DATETIMEUTC          |
|-----------------|------|------|---------------|----------------|----------------------|
| DATE            | =    | err  | midnight      | midnight+00:00 | midnight Z           |
| TIME            | err  | =    | today+T       | today+T+00:00  | today+T Z            |
| DATETIME        | .date()| .time()| =          | attach +00:00  | attach Z (no shift)  |
| DATETIMEZONE    | .date()| .time()| drop tz     | =              | **astimezone(utc)**  |
| DATETIMEUTC     | .date()| .time()| drop tz     | astimezone(+00:00)= | =              |

`err` raises `ValueError` (UI gates these via `type_delegate.py`).

**DoD**

- `tests/test_convert_datetime.py` covers all 25 cells, including the DST-ish
  shift `(2026-05-21T10:00:00+05:00 → DATETIMEUTC)` → `2026-05-21T05:00:00Z`.
- Round-trip property test: for every UTC dt and every offset in
  `[-12:00 .. +14:00]`, `utc → tz → utc` is identity.
- Module has no imports from Qt / GUI layers (pure stdlib + `JsonType`).

### Commit 5 — `datetime_editor/better_dt_editor.py`

Wire `DateTimeCategory.DateTimeUTC` through the editor:

- New rendering: always `Z` suffix, always `tzinfo=utc`.
- Spinner / partial-edit logic mirrors `DateTimeWithTZ` minus the offset
  controls.
- Reject manual offset edits when category is UTC.

**DoD**

- Manual smoke test (documented in commit body): editor opens, types
  `2026-05-21T14:33:09Z`, commits → tree shows `DATETIMEUTC`.
- Switching from `DATETIMEZONE` to `DATETIMEUTC` via the type delegate calls
  `convert_datetime` and the displayed wall-clock changes when offset ≠ 0.
- No new pylint/flake errors over baseline in this file.

### Commit 6 — `delegates/type_delegate.py` + `delegates/value_formatting.py`

- Allow `DATETIMEUTC` in the type drop-down (within `DATETIME_FAMILY`).
- Format `DATETIMEUTC` values with `strftime` + `Z`, fractional seconds only
  when nonzero (consistent with existing datetime formatting).

**DoD**

- The type drop-down on a datetime cell lists `dt+utc`.
- Selecting it triggers `convert_datetime`, the cell text gains `Z`.
- Save → reload preserves the kind (round-trip via `io_formats`).

### Commit 7 — `io_formats/dump.py` + `io_formats/load.py`

- On dump: `DATETIMEUTC` → string with `Z`. (Already the canonical render, so
  this commit mostly verifies and locks behavior with tests.)
- On load: a `Z`-suffixed string survives the load → `parse_json_type` →
  `DATETIMEUTC` pipeline.

**DoD**

- `tests/test_io_datetime_utc.py`: dump→load is identity for a tree containing
  every member of `DATETIME_FAMILY`.
- JSON output of `DATETIMEUTC` is exactly the `Z` form (snapshot test).
- YAML round-trip likewise (uses the same string representation).

### Commit 8 — Docs

Update `ai-memory/repo-map.md` and `README.md`:

- New kind documented.
- Conversion matrix linked.
- `plan.txt` line 6 ("date/time type (various formats)") gets a sub-bullet
  noting UTC support.

**DoD**

- `repo-map.md` mentions `DATETIMEUTC` and `tree/types_datetime.py`.
- README's supported-types list is updated.
- No code changes in this commit.
