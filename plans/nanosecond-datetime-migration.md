# Plan: Replace `datetime` with `pandas.Timestamp` for Nanosecond Precision

**Date:** 2026-06-01  
**Status:** Draft  
**Scope:** All datetime storage, parsing, editing, coercion, formatting, serialization, and validation

---

## 1. Motivation

Python's `datetime.datetime` stores sub-second precision as a **microsecond** (`0–999999`, 6 digits).  
Many data formats (Parquet, Arrow, high-frequency trading logs, scientific timestamps) require **nanosecond**
precision (9 fractional digits). `pandas.Timestamp` wraps a 64-bit integer nanosecond count and supports the full
ISO-8601 fractional-second range up to 9 digits.

**Goal:** Replace all internal datetime representation from `datetime.date` / `datetime.time` / `datetime.datetime` to
`pandas.Timestamp` (for datetimes) / `pandas.Timestamp.date()` (for dates) / `pandas.Timedelta` (for time-of-day),
gaining nanosecond precision while preserving the existing `DateTimeCategory` taxonomy and UI behavior.

---

## 2. Key Design Decisions

### 2.1 Storage Type Mapping

| Current Type                   | New Type                                                                   | Rationale                                                                                         |
|--------------------------------|----------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| `datetime.datetime` (naive)    | `pandas.Timestamp` (naive)                                                 | Native ns precision, drop-in for most APIs                                                        |
| `datetime.datetime` (tz-aware) | `pandas.Timestamp` (tz-aware)                                              | `pd.Timestamp` supports `tzinfo` via `pytz`/`zoneinfo`                                            |
| `datetime.date`                | `pandas.Timestamp` (normalized to midnight)                                | `pd.Timestamp` can represent dates; `.date()` extracts `datetime.date` when needed for ISO format |
| `datetime.time`                | `pandas.Timestamp` (anchored to `1970-01-01`) or custom `NanoTime` wrapper | `pd.Timestamp` always has a date component; for pure-time we need a thin wrapper or convention    |
| `datetime.timedelta`           | `pandas.Timedelta`                                                         | ns-resolution deltas                                                                              |
| `datetime.timezone`            | `datetime.timezone` / `zoneinfo.ZoneInfo`                                  | Timezone objects remain stdlib; `pd.Timestamp` accepts them                                       |

### 2.2 The `datetime.time` Problem

`pandas.Timestamp` cannot represent a standalone time-of-day without a date component. Options:

- **Option A: Custom `NanoTime` dataclass** — stores `(hour, minute, second, nanosecond)` as pure integers. Lightweight,
  no pandas dependency for the time-only path. Requires custom `isoformat()` / `fromisoformat()`.
- **Option B: Anchor to epoch** — store time-of-day as `pd.Timestamp("1970-01-01") + offset`. The date is always
  `1970-01-01`; formatting strips it. Simpler but semantically misleading.
- **Option C: Keep `datetime.time` for TIME category only** — minimal change, but creates a split representation (some
  types use `pd.Timestamp`, one uses `datetime.time`). Loses nanosecond precision for TIME.

**Recommendation:** **Option A** (`NanoTime` dataclass). It's clean, preserves nanosecond precision for all categories,
and avoids the "phantom date" problem. Place it in `core/datetime_parsing/nano_time.py`.

### 2.3 The `datetime.date` Problem

`pandas.Timestamp` always has a time component (defaulting to midnight). For the `Date` category:

- **Option A: Use `pd.Timestamp` with convention** — always normalize to midnight; `isoformat()` outputs `YYYY-MM-DD`
  only. Simple but `str(ts)` includes time.
- **Option B: Custom `NanoDate` dataclass** — stores `(year, month, day)`. Overkill since dates don't need ns precision.
- **Option C: Keep `datetime.date` for DATE category** — simple, no precision gain needed for dates.

**Recommendation:** **Option C** — keep `datetime.date` for the `Date` category. Dates don't benefit from nanosecond
precision, and `datetime.date` is the natural Python representation. Only `datetime` and `time` categories gain
nanosecond precision.

### 2.4 Revised Storage Type Mapping

| Category         | Current             | New                               |
|------------------|---------------------|-----------------------------------|
| `Date`           | `datetime.date`     | `datetime.date` (unchanged)       |
| `Time`           | `datetime.time`     | `NanoTime` (custom, ns-precision) |
| `DateTime`       | `datetime.datetime` | `pandas.Timestamp` (naive)        |
| `DateTimeWithTZ` | `datetime.datetime` | `pandas.Timestamp` (tz-aware)     |
| `DateTimeUTC`    | `datetime.datetime` | `pandas.Timestamp` (tz=UTC)       |

---

## 3. Affected Files & Changes

### 3.1 New Files

| File                                 | Purpose                                                                                                                                                                                                                                                          |
|--------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `core/datetime_parsing/nano_time.py` | `NanoTime` dataclass: hour, minute, second, nanosecond. Methods: `isoformat()`, `fromisoformat()`, `replace()`.                                                                                                                                                  |
| `core/datetime_parsing/compat.py`    | Thin adapter layer: `to_timestamp(value)`, `to_nanotime(value)`, `to_date(value)`, `isoformat(value, category)`, `from_iso(text, category)`. Centralizes the `pd.Timestamp` / `NanoTime` / `datetime.date` construction so callers don't import pandas directly. |

### 3.2 Core Parsing Layer

#### `core/datetime_parsing/enums.py`

- **No changes.** `DateTimeCategory` enum is category-only; no type references.

#### `core/datetime_parsing/regex.py`

- **Change:** `parse_datetime_text()` return type changes from `date | time | datetime` to
  `date | NanoTime | pd.Timestamp`.
- Replace `date.fromisoformat()` → keep (DATE category still returns `datetime.date`).
- Replace `time.fromisoformat()` → `NanoTime.fromisoformat()`.
- Replace `isoparse()` → `pd.Timestamp()` for datetime categories.
- Update `PARTIAL_DATETIME_RE` to allow up to 9 fractional digits (currently `\d{1,6}` → `\d{1,9}`).
- Update `DATETIME_RE` to allow up to 9 fractional digits (`\.\d{1,6}` → `\.\d{1,9}`).

#### `core/datetime_parsing/__init__.py`

- Re-export `NanoTime` from `nano_time.py`.

### 3.3 Tree Data Model

#### `tree/types.py`

- **Change:** `parse_json_type()` pattern matching on `datetime(tzinfo=None)` → `pd.Timestamp` check.
- `isinstance(value, datetime)` checks → `isinstance(value, pd.Timestamp)`.
- `isinstance(value, date)` → keep `datetime.date` check (DATE unchanged).
- `isinstance(value, time)` → `isinstance(value, NanoTime)`.
- **Import changes:** Add `import pandas as pd`; add `NanoTime` import; remove `from datetime import time`.

#### `tree/types_datetime.py`

- **Change:** `convert_datetime()` must handle `pd.Timestamp` and `NanoTime` instead of `datetime.datetime` and
  `datetime.time`.
- `isinstance(value, date)` / `isinstance(value, datetime)` / `isinstance(value, time)` checks → updated type checks.
- Construction of new values uses `pd.Timestamp()` / `NanoTime()` / `datetime.date`.
- **Import changes:** Replace `from datetime import ...` with `import pandas as pd` + `NanoTime` import.

#### `tree/item.py`

- **Change:** `_convert_datetime_text()` uses `pd.Timestamp.isoformat()` / `NanoTime.isoformat()` instead of
  `datetime.datetime.isoformat()`.
- `isinstance(converted, datetime.date)` / `datetime.time` / `datetime.datetime` checks → updated.
- **Import changes:** `import datetime` → `import pandas as pd` + `NanoTime` import.

#### `tree/item_coercion.py`

- **Change:** All `datetime.datetime`, `datetime.time`, `datetime.date` construction and `isinstance` checks.
- `_now_for_type()` → use `pd.Timestamp.now()` for datetime types.
- `_epoch_seconds_from_temporal()` → handle `pd.Timestamp` and `NanoTime`.
- `_try_parse_temporal()` → return ISO strings constructed from `pd.Timestamp` / `NanoTime`.
- `_timespec_for_clock()` → extend for nanosecond precision (`"nanoseconds"` timespec).
- `microsecond` references → `nanosecond` where appropriate.
- **Import changes:** `import datetime` → `import pandas as pd` + `NanoTime` import.

### 3.4 Editor Widgets

#### `editors/inline/datetime/__init__.py` (old `DateTimeEditor`)

- **Change:** `get_category()` uses `isinstance(value, pd.Timestamp)` and `isinstance(value, NanoTime)`.
- `setValue()` / `value()` handle `pd.Timestamp` and `NanoTime`.
- **Import changes:** Replace `from datetime import ...` with `import pandas as pd` + `NanoTime`.

#### `editors/inline/datetime/better_dt_editor.py`

- **Change:** `BetterDateTimeBuffer`:
    - `_value` type: `ValueType = Union[date, NanoTime, pd.Timestamp, None]`.
    - `_format_value()` → format `pd.Timestamp` with up to 9 fractional digits; format `NanoTime` with ns.
    - `_as_datetime()` → convert to `pd.Timestamp` (not `datetime.datetime`).
    - `_restore_type()` → construct `pd.Timestamp` / `NanoTime` / `datetime.date`.
    - `_apply_delta_to_segment()` → `microsecond` segment becomes `nanosecond`; step size adjusted.
    - `_format_microsecond()` → `_format_nanosecond()` (9-digit support).
    - `_apply_microsecond_delta()` → `_apply_nanosecond_delta()`.
- **Change:** `BetterDateTimeEditor`:
    - `setValue()` / `value()` / `setCategory()` — same API, different internal types.
- **Import changes:** Replace `from datetime import ...` with `import pandas as pd` + `NanoTime`.

#### `editors/inline/datetime/validator.py`

- **Change:** `microsecond` validation range: `0–999999` → `0–999999999`.
- `PARTIAL_DATETIME_RE` group name `microsecond` → consider renaming to `subsecond` or keep as `microsecond` for regex
  compat but validate up to 9 digits.
- **Minimal change:** Just widen the digit count and range check.

### 3.5 Delegates / Formatting

#### `delegates/formatting/value_formatting.py`

- **Change:** `datetime.fromisoformat()` → `pd.Timestamp()` for DATETIMEUTC formatting.
- `dt.microsecond` → `dt.nanosecond` (or `dt.value % 1_000_000_000` for ns component).
- `timespec="microseconds"` → custom ns formatting.
- **Import changes:** `from datetime import datetime, timezone` → `import pandas as pd` +
  `from datetime import timezone`.

### 3.6 Validation

#### `validation/_sanitize.py`

- **Change:** `isinstance(value, datetime)` → `isinstance(value, pd.Timestamp)`.
- `isinstance(value, time)` → `isinstance(value, NanoTime)`.
- `value.isoformat()` → works for both `pd.Timestamp` and `NanoTime` (ensure `NanoTime.isoformat()` exists).
- **Import changes:** Replace `from datetime import date, datetime, time` with `import pandas as pd` + `NanoTime`.

### 3.7 Qt Bridge

#### `qt2py/__init__.py`

- **Change:** `qtdatetime()` accepts `pd.Timestamp` instead of `datetime.datetime`.
- `pydatetime()` returns `pd.Timestamp` instead of `datetime.datetime`.
- `pd.Timestamp` has `.timestamp()` and `.tzinfo`, so the logic is nearly identical.
- **Import changes:** `from datetime import datetime` → `import pandas as pd`.

#### `app/runtime_compat.py`

- **Change:** `tz_name()` accepts `pd.Timestamp` (has `.tzinfo` attribute, same API).
- **Import changes:** `from datetime import datetime` → `import pandas as pd`.

### 3.8 Documents / Commands

#### `documents/states/editing/command_dispatcher.py`

- **Change:** `datetime.now()` → `pd.Timestamp.now()`.
- **Import changes:** `from datetime import datetime` → `import pandas as pd`.

### 3.9 I/O Serialization

#### `io_formats/dump.py`

- **No direct changes.** Datetime values are stored as **strings** in the tree (ISO format). The `mpq_json_default` and
  YAML dumpers already handle strings. However, if any `pd.Timestamp` or `NanoTime` objects leak into the serialization
  path, they need custom handlers.

#### `mpq2py/__init__.py`

- **Change:** Add `pd.Timestamp` and `NanoTime` handlers to `mpq_json_default()`:
  ```python
  if isinstance(obj, pd.Timestamp):
      return obj.isoformat()
  if isinstance(obj, NanoTime):
      return obj.isoformat()
  ```
- Add YAML representers for `pd.Timestamp` and `NanoTime` in `MpqSafeDumper`.

#### `io_formats/load.py`

- **No direct changes.** Loaded data is strings/numbers; `parse_json_type()` + `parse_datetime_text()` do the
  conversion.

### 3.10 Tests

| Test File                              | Changes                                                                                                              |
|----------------------------------------|----------------------------------------------------------------------------------------------------------------------|
| `tests/test_datetime_editor.py`        | Update expected types: `datetime(...)` → `pd.Timestamp(...)`, `time(...)` → `NanoTime(...)`.                         |
| `tests/test_better_datetime_buffer.py` | Update all `datetime.fromisoformat()` → `pd.Timestamp()`, `date.fromisoformat()` stays. Add ns-precision test cases. |
| `tests/test_convert_datetime.py`       | Update `datetime(...)` → `pd.Timestamp(...)`, `time(...)` → `NanoTime(...)`. Add ns round-trip tests.                |
| `tests/test_kind_switch_coercion.py`   | Update `datetime.date.fromisoformat()` / `datetime.datetime.fromisoformat()` calls.                                  |
| `tests/test_partial_regex.py`          | Add test cases for 7–9 digit fractional seconds.                                                                     |
| New: `tests/test_nano_time.py`         | Unit tests for `NanoTime` dataclass.                                                                                 |
| New: `tests/test_ns_precision.py`      | End-to-end tests: load ns-precision JSON → edit → save → reload.                                                     |

---

## 4. Regex Changes (Critical)

### `DATETIME_RE` (in `core/datetime_parsing/regex.py`)

Current:

```python
r"\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?"  # Time
r"\d{2}:\d{2}(:\d{2}(\.\d{1,6})?)?"  # DateTime time part
```

New:

```python
r"\d{2}:\d{2}(:\d{2}(\.\d{1,9})?)?"  # Time — up to 9 fractional digits
r"\d{2}:\d{2}(:\d{2}(\.\d{1,9})?)?"  # DateTime time part — up to 9 fractional digits
```

### `PARTIAL_DATETIME_RE`

Current:

```python
r"(?:\.(?P<microsecond>\d*))?"
```

New (keep group name `microsecond` for backward compat, or rename to `subsecond`):

```python
r"(?:\.(?P<subsecond>\d{0,9}))?"  # up to 9 digits
```

If renaming: update all references in `validator.py`, `better_dt_editor.py`, and `regex.py`.

---

## 5. `NanoTime` Dataclass Design

```python
# core/datetime_parsing/nano_time.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NanoTime:
    """Time-of-day with nanosecond precision (replaces datetime.time for the TIME category)."""
    hour: int = 0
    minute: int = 0
    second: int = 0
    nanosecond: int = 0  # 0–999_999_999

    def isoformat(self, timespec: str = "auto") -> str:
        base = f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}"
        if timespec == "nanoseconds" or (timespec == "auto" and self.nanosecond):
            ns_str = f"{self.nanosecond:09d}".rstrip("0") or "0"
            return f"{base}.{ns_str}"
        if timespec == "microseconds" or (timespec == "auto" and self.nanosecond % 1000):
            us = self.nanosecond // 1000
            us_str = f"{us:06d}".rstrip("0") or "0"
            return f"{base}.{us_str}"
        if timespec in ("seconds", "auto"):
            return base
        if timespec == "minutes":
            return f"{self.hour:02d}:{self.minute:02d}"
        return base

    @classmethod
    def fromisoformat(cls, text: str) -> NanoTime:
        # Parse "hh:mm[:ss[.nnnnnnnnn]]"
        ...

    def replace(self, **kwargs) -> NanoTime:
        ...

    def __str__(self) -> str:
        return self.isoformat()
```

---

## 6. Dependency Changes

### `requirements.txt`

Add:

```
pandas>=2.0.0
```

`pandas` pulls in `numpy`, `python-dateutil`, `pytz`. The project already depends on `python-dateutil`. The `pandas`
wheel is ~12 MB.

### Packaging Impact

- **PyInstaller:** `pandas` must be included in the bundle. Update `EditableTreeModel.spec` if it has explicit hidden
  imports.
- **Cold-start time:** `import pandas` adds ~0.5–1.0s. Consider lazy import: `import pandas as pd` only in
  `core/datetime_parsing/compat.py` and re-export what's needed.

---

## 7. Migration Phases

### Phase 1: Foundation (no behavior change)

1. Create `NanoTime` dataclass in `core/datetime_parsing/nano_time.py`.
2. Create `core/datetime_parsing/compat.py` adapter layer.
3. Widen regex to accept 1–9 fractional digits.
4. Add `pandas` to `requirements.txt`.
5. Add tests for `NanoTime` and widened regex.

### Phase 2: Core type swap

1. Change `parse_datetime_text()` return types: `datetime` → `pd.Timestamp`, `time` → `NanoTime`.
2. Update `tree/types.py` `parse_json_type()` isinstance checks.
3. Update `tree/types_datetime.py` `convert_datetime()`.
4. Update `tree/item.py` `_convert_datetime_text()`.
5. Update `tree/item_coercion.py` all temporal helpers.
6. Run existing tests; fix failures.

### Phase 3: Editor & UI

1. Update `BetterDateTimeBuffer` and `BetterDateTimeEditor` for `pd.Timestamp` / `NanoTime`.
2. Update `DateTimeValidator` for 9-digit subsecond.
3. Update `delegates/formatting/value_formatting.py`.
4. Update `editors/factory.py` `set_value_editor_data()` / `set_value_model_data()`.

### Phase 4: Periphery

1. Update `validation/_sanitize.py`.
2. Update `qt2py/__init__.py`.
3. Update `app/runtime_compat.py`.
4. Update `documents/states/editing/command_dispatcher.py`.
5. Update `mpq2py/__init__.py` serialization handlers.

### Phase 5: Test updates & new coverage

1. Update all test files to use `pd.Timestamp` / `NanoTime`.
2. Add nanosecond-precision round-trip tests.
3. Add edge-case tests (9-digit fractional, leap second boundaries, etc.).
4. Run `make gate` (lint → reflection → isolation → tests).

---

## 8. Risk Assessment

| Risk                                                                             | Mitigation                                                                                                                                                                                                 |
|----------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `pd.Timestamp` is not a drop-in for `datetime.datetime` in all APIs              | `compat.py` adapter layer centralizes construction; type-check all call sites                                                                                                                              |
| `pandas` import time slows app startup                                           | Lazy import in `compat.py`; only load when datetime values are first encountered                                                                                                                           |
| `NanoTime` diverges from `datetime.time` API                                     | Keep `NanoTime` API minimal; mirror `datetime.time` methods that are actually used                                                                                                                         |
| Regex widening may accept previously-invalid inputs                              | Validator still enforces category-specific digit limits; add explicit 9-digit test cases                                                                                                                   |
| JSON/YAML round-trip: ns-precision strings may not parse on reload               | `parse_datetime_text()` handles up to 9 digits; `pd.Timestamp.isoformat()` outputs up to 9                                                                                                                 |
| `isinstance(value, datetime.datetime)` catches `pd.Timestamp` (it's a subclass!) | **Critical:** `pd.Timestamp` IS a subclass of `datetime.datetime`. All `isinstance(x, datetime.datetime)` checks will still match. Must use `isinstance(x, pd.Timestamp)` FIRST, or use exact type checks. |
| Tree isolation rule: `tree/` must not import from `app/`, `editors/`, etc.       | `pandas` is an external package — allowed. `NanoTime` lives in `core/` — allowed per tree-isolation rules.                                                                                                 |

### Critical: `pd.Timestamp` subclass issue

`pandas.Timestamp` inherits from `datetime.datetime`. This means:

- `isinstance(pd.Timestamp("2025-01-01"), datetime.datetime)` → `True`
- `isinstance(pd.Timestamp("2025-01-01"), datetime.date)` → `True`

All `isinstance` checks must test `pd.Timestamp` **before** `datetime.datetime` and `datetime.date`, or use exact type
checks (`type(x) is datetime.date`). This is the single most dangerous migration pitfall.

---

## 9. Alternatives Considered

| Alternative                                          | Pros                                                                                         | Cons                                                                            |
|------------------------------------------------------|----------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| Keep `datetime.datetime`, store ns as separate field | No new dependency                                                                            | Complex; every API must handle the extra field; serialization is ad-hoc         |
| Use `numpy.datetime64`                               | Lightweight; no pandas                                                                       | Awkward API; no `.isoformat()`; no `.tzinfo`; requires manual string formatting |
| Use `arrow.Arrow`                                    | Rich API; ns support                                                                         | Another heavy dependency; different API surface                                 |
| Store as integer nanoseconds since epoch             | Zero dependencies                                                                            | Loses ISO formatting convenience; timezone handling is manual                   |
| **`pandas.Timestamp`** (chosen)                      | Subclass of `datetime.datetime`; familiar API; ns precision; built-in ISO format; tz support | Heavy dependency (~12 MB); slow import; subclass trap                           |

---

## 10. Open Questions

1. **Lazy pandas import?** Should `compat.py` defer `import pandas` until first use to avoid startup penalty? Likely
   yes.
2. **`NanoTime` or keep `datetime.time`?** If TIME category nanosecond precision is not needed, we could keep
   `datetime.time` and only migrate datetime types. This simplifies the migration significantly.
3. **Segment naming in `PARTIAL_DATETIME_RE`:** Rename `microsecond` group to `subsecond`? This is a large rename across
   validator, buffer, and editor. Worth it for clarity but increases diff size.
4. **Backward compatibility:** Files saved with 6-digit microseconds should load identically. Files saved with 9-digit
   nanoseconds should load on older versions (they'd truncate to 6 digits). Is this acceptable?
