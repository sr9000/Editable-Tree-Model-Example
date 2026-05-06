# Phase 3 — Type-switch coercion overhaul

**Risk:** medium · **Files:** `tree/item_coercion.py`, `tree/item.py`,
`tree/types.py` (helpers), `delegates/bytes_codec.py` ·
**Tests:** `tests/test_type_editing.py` (extend), new
`tests/test_kind_switch_coercion.py`

This is the largest functional change in the batch. Five distinct
issues all live in the kind-switch path
(`JsonTreeItem.set_data(column=1, ...)` →
`coerce_value_for_type(new_type, old_value, strict=False)`).

## Issues addressed

- [ ] Switching to `BYTES` / `ZLIB` / `GZIP` should **encode** the
      current text/binary value, not try to *decode* it as base64.
      Switching back should round-trip.
- [ ] Switching `BOOLEAN` → `STRING` produces "True" / "False"
      (Python `str(bool)` capitalisation). It should produce
      lowercase `"true"` / `"false"` to match the rendered text.
- [ ] Switching to `DATE` / `TIME` / `DATETIME` /
      `DATETIMEZONE` from a non-parseable value should fall back to
      **"now"** instead of `1970-01-01...` epoch zero.
- [ ] Switching to `DATE/TIME/DATETIME/DATETIMEZONE` from an integer
      should be interpreted as **epoch seconds** (heuristic: ≥ 10^12
      → milliseconds) and parsed accordingly. Switching the other
      direction (`DATETIME` → `INTEGER`) should yield the matching
      epoch number, not a `ValueError`.
- [ ] Switching `OBJECT` ↔ `ARRAY` must **preserve nested children**.
      Going `array → object`, give children placeholder names
      `item1, item2, …`. Going `object → array`, drop the names but
      keep order.

## Current behaviour (problem cases)

`tree/item_coercion.py`:

- `JsonType.STRING / UNICODE / MULTILINE / TEXT` paths use
  `str(value)` → `"True"` for booleans.
- `JsonType.BYTES | ZLIB | GZIP` path requires `value` to already be
  base64; otherwise it returns `(False, None)` (strict) or
  `(True, "")` (non-strict). It never *encodes* the current text.
- `JsonType.DATE / TIME / DATETIME / DATETIMEZONE` paths return the
  epoch placeholder when `value is None` and otherwise blindly
  `str(value)`.
- `JsonType.ARRAY` requires `isinstance(value, list)`; `OBJECT`
  requires `isinstance(value, dict)`. The current top-level dispatch
  only sees `value = item.to_json()` for ARRAY/OBJECT, and goes
  through `_apply_typed_value` which **rebuilds** children from the
  primitive. So OBJECT→ARRAY drops names but the values do round-trip
  through `to_json` so children survive. ARRAY→OBJECT, however, goes
  via `[…]` → not a dict → coercion returns `{}` (non-strict),
  destroying children.

## Plan

### 3.1 Bool stringification (smallest)

In `coerce_value_for_type`, the STRING/UNICODE/MULTILINE/TEXT branches
become:

```python
case JsonType.STRING | JsonType.UNICODE | JsonType.MULTILINE | JsonType.TEXT:
    if value is None:
        return True, ""
    if isinstance(value, bool):
        return True, "true" if value else "false"
    return True, str(value)
```

(Booleans must be checked before `int`, since `bool` ⊂ `int` in Python.)

### 3.2 Date / time / datetime placeholder = now

Replace the hard-coded epoch placeholders with a helper:

```python
def _now_for_type(json_type) -> str:
    now = datetime.datetime.now(tz=datetime.timezone.utc).astimezone()
    match json_type:
        case JsonType.DATE: return now.date().isoformat()
        case JsonType.TIME: return now.time().replace(microsecond=0).isoformat(timespec="minutes")
        case JsonType.DATETIME: return now.replace(microsecond=0, tzinfo=None).isoformat(timespec="minutes")
        case JsonType.DATETIMEZONE: return now.replace(microsecond=0).isoformat(timespec="seconds")
```

The branches now:

```python
case JsonType.DATE | JsonType.TIME | JsonType.DATETIME | JsonType.DATETIMEZONE:
    parsed = _try_parse_temporal(json_type, value)
    if parsed is not None:
        return True, parsed
    return True, _now_for_type(json_type)
```

`_try_parse_temporal` covers:
- existing string round-trips (just `str(value)` if it's a valid
  string in the right shape — reuse `datetime_editor` regex / parser
  helpers if cheap, otherwise simple `datetime.fromisoformat`),
- **integer epoch seconds / ms** (≥ 10^12 → ms),
- existing `datetime.date` / `datetime.time` / `datetime.datetime`
  Python objects.

`tree/types.py` already has parsing helpers used by `parse_json_type`;
extract a shared `try_parse_temporal(json_type, value)` so detection
and coercion stay in lock-step.

### 3.3 Datetime → integer (round-trip)

In `JsonType.INTEGER` branch, before `int(value)` raises, detect
`datetime.date / time / datetime` instances and emit
`int(dt.timestamp())` (seconds) — round-tripping with 3.2 above.

This keeps the user's flow: switch INTEGER ↔ DATETIME without losing
information.

### 3.4 Bytes / zlib / gzip encode-on-switch

Centralise encode/decode in `delegates/bytes_codec.py` (already
exists). The coercion path becomes:

```python
case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
    # 1) value already a valid base64 string of the right kind → keep.
    if isinstance(value, str) and _looks_valid_for(json_type, value):
        return True, value
    # 2) raw bytes → encode (zlib/gzip → compress first).
    if isinstance(value, (bytes, bytearray, memoryview)):
        return True, encode_bytes(bytes(value), json_type)
    # 3) fallback: encode str(value).encode("utf-8") — round-trips
    #    text-like values into the new representation.
    if value is None:
        return True, ""
    return True, encode_bytes(str(value).encode("utf-8"), json_type)
```

`_looks_valid_for(json_type, b64)` uses `decode_bytes(...)` inside a
`try/except` block. This is the same predicate
`compute_editable` uses; refactor to share.

Switching **between** the three (`BYTES → ZLIB`, etc.) must
**re-encode**: decode old representation to raw bytes, then encode
into the new one. Today's strict `(False, None)` path silently
preserves the base64 string, which is wrong because the same
characters mean different bytes in BYTES vs ZLIB.

### 3.5 Object ↔ array preserves children

This change lives in `tree/item.py:set_data` (column 1), not in
`coerce_value_for_type`, because it has to manipulate
`self.child_items` directly rather than go through
`_apply_typed_value` (which rebuilds from a primitive).

```python
if column == 1 and new_type in (JsonType.ARRAY, JsonType.OBJECT) \
        and self.json_type in (JsonType.ARRAY, JsonType.OBJECT) \
        and new_type is not self.json_type:
    return self._morph_container(new_type)
```

`_morph_container(new_type)`:
- ARRAY → OBJECT: for each child, if `child.name is None`, assign
  `child.name = unique_child_name(siblings, base="item")` (yielding
  `item1, item2, …`).
- OBJECT → ARRAY: drop `child.name` (set to `None`); preserve order.
- update `self.json_type`, `self.explicit_type = True`,
  `self.value = [] / {}`, `self.editable = False`,
  `self._children_dirty = True`.
- emit the same surgical signals via the existing
  `JsonTreeModel.change_type` → `DiffApplier` path; in practice the
  `_ChangeTypeCmd` already snapshots the parent subtree before/after
  via `to_json`, so making `to_json` correct (it already is for both
  shapes) plus rebuilding children with new names is enough.

> Note on naming: `unique_child_name(used, base="item")` already
> generates `item`, `item_2`, … For the first child we want `item1`
> (with the `1` suffix) per the user's spec, so we add a small
> override: when the parent is freshly morphed and **no** children
> have names yet, generate `item1, item2, …` deterministically by
> row index.

### Tests

`tests/test_kind_switch_coercion.py` (new):

- `bool_to_string_is_lowercase`
- `string_to_bytes_encodes_utf8`
- `bytes_to_zlib_recompresses` (decode+encode round-trip)
- `string_to_date_falls_back_to_today_when_unparseable`
- `int_seconds_to_datetime_round_trip`
- `int_milliseconds_to_datetime_round_trip` (≥ 10^12 heuristic)
- `array_to_object_preserves_values_with_item_n_names`
- `object_to_array_preserves_value_order_drops_names`

Plus extend `test_type_editing.py` to assert undo/redo of each new
path (because `_ChangeTypeCmd` snapshots the affected subtree, this
should "just work", but we still need a regression line).

## Acceptance

- Suite green.
- Manual: switching kinds in the type combobox feels lossless and
  intuitive across all listed pairs.
