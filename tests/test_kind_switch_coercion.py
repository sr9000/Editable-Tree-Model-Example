"""Tests for Phase-3 type-switch coercion fixes.

Coverage:
  3.1  bool → string produces lowercase "true"/"false"
  3.2  switching to DATE/TIME/DATETIME/DATETIMEZONE from an unparseable value
       falls back to "now" (not the 1970 epoch zero)
  3.3  int (seconds / milliseconds) ↔ DATETIME round-trip
  3.4  switching to BYTES/ZLIB/GZIP encodes the current value; cross-format
       re-encoding is lossless when `old_type` is known
  3.5  ARRAY↔OBJECT morph preserves children with correct names / order
"""

import base64
import datetime
import gzip
import zlib

import pytest
from PySide6.QtCore import QModelIndex

from delegates.bytes_codec import decode_bytes, encode_bytes
from tree.item_coercion import coerce_value_for_type
from tree.model import JsonTreeModel
from tree.types import JsonType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce(new_type, value, old_type=None):
    ok, result = coerce_value_for_type(new_type, value, strict=False, old_type=old_type)
    assert ok, f"coerce_value_for_type returned failure for {new_type!r}, {value!r}"
    return result


# ---------------------------------------------------------------------------
# 3.1  bool → string  (lowercase)
# ---------------------------------------------------------------------------


def test_bool_to_string_is_lowercase():
    assert _coerce(JsonType.STRING, True) == "true"
    assert _coerce(JsonType.STRING, False) == "false"
    assert _coerce(JsonType.UNICODE, True) == "true"
    assert _coerce(JsonType.MULTILINE, False) == "false"
    assert _coerce(JsonType.TEXT, True) == "true"


def test_int_to_string_not_affected_by_bool_check():
    # Plain int must still stringify normally
    assert _coerce(JsonType.STRING, 42) == "42"
    assert _coerce(JsonType.STRING, 0) == "0"


# ---------------------------------------------------------------------------
# 3.2  DATE/TIME/DATETIME/DATETIMEZONE → falls back to "now"
# ---------------------------------------------------------------------------


def test_string_to_date_falls_back_to_today_when_unparseable():
    before = datetime.date.today()
    result = _coerce(JsonType.DATE, "not-a-date")
    after = datetime.date.today()
    parsed = datetime.date.fromisoformat(result)
    assert before <= parsed <= after


def test_string_to_time_falls_back_to_now_when_unparseable():
    result = _coerce(JsonType.TIME, "garbage")
    # Just check it's a valid HH:MM string
    h, m = result.split(":")
    assert 0 <= int(h) <= 23
    assert 0 <= int(m) <= 59


def test_none_to_datetime_falls_back_to_now_not_epoch():
    result = _coerce(JsonType.DATETIME, None)
    assert not result.startswith("1970"), f"Expected 'now', got epoch: {result!r}"
    # Must parse back as a datetime
    dt = datetime.datetime.fromisoformat(result)
    assert dt.year >= 2020


def test_none_to_datetimezone_falls_back_to_now_not_epoch():
    result = _coerce(JsonType.DATETIMEZONE, None)
    assert not result.startswith("1970"), f"Expected 'now', got epoch: {result!r}"


# ---------------------------------------------------------------------------
# 3.3  int epoch seconds / milliseconds ↔ DATETIME round-trip
# ---------------------------------------------------------------------------


def test_int_seconds_to_datetime():
    # 2024-01-15 12:00:00 UTC as seconds
    epoch_s = int(datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    result = _coerce(JsonType.DATETIME, epoch_s)
    dt = datetime.datetime.fromisoformat(result)
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.day == 15


def test_int_milliseconds_to_datetime():
    # Epoch ≥ 10^12 is treated as milliseconds
    epoch_ms = int(datetime.datetime(2024, 6, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    assert epoch_ms >= 10**12
    result = _coerce(JsonType.DATETIME, epoch_ms)
    dt = datetime.datetime.fromisoformat(result)
    assert dt.year == 2024
    assert dt.month == 6


def test_datetime_to_integer_round_trip():
    """DATETIME string → INTEGER yields epoch; that epoch re-coerces to same date."""
    dt_str = "2024-03-10T08:30"
    # First coerce STRING→DATETIME
    _, as_date = coerce_value_for_type(JsonType.DATETIME, dt_str, strict=False)
    # The stored value is a string; coerce to INTEGER via the item path (old_type=DATETIME)
    # We directly test with a Python datetime object
    dt_obj = datetime.datetime(2024, 3, 10, 8, 30)
    ok, epoch = coerce_value_for_type(JsonType.INTEGER, dt_obj, strict=False)
    assert ok
    assert isinstance(epoch, int)
    # Round-trip back to DATETIME
    result = _coerce(JsonType.DATETIME, epoch)
    rt_dt = datetime.datetime.fromisoformat(result)
    assert rt_dt.year == 2024
    assert rt_dt.month == 3
    assert rt_dt.day == 10


# ---------------------------------------------------------------------------
# 3.4  BYTES/ZLIB/GZIP encode-on-switch
# ---------------------------------------------------------------------------


def test_string_to_bytes_encodes_utf8():
    result = _coerce(JsonType.BYTES, "hello")
    raw = base64.b64decode(result)
    assert raw == b"hello"


def test_string_to_zlib_compresses_utf8():
    result = _coerce(JsonType.ZLIB, "hello world")
    raw_b64 = base64.b64decode(result)
    assert zlib.decompress(raw_b64) == b"hello world"


def test_string_to_gzip_compresses_utf8():
    result = _coerce(JsonType.GZIP, "hello world")
    raw_b64 = base64.b64decode(result)
    assert gzip.decompress(raw_b64) == b"hello world"


def test_none_to_bytes_gives_empty():
    assert _coerce(JsonType.BYTES, None) == ""
    assert _coerce(JsonType.ZLIB, None) == ""
    assert _coerce(JsonType.GZIP, None) == ""


def test_bytes_to_zlib_recompresses():
    """BYTES → ZLIB must decode the raw bytes, then re-compress, not encode the b64 string."""
    raw = b"some binary data"
    bytes_b64 = encode_bytes(raw, JsonType.BYTES)

    # Cross-format re-encode: old_type=BYTES, new_type=ZLIB
    result = _coerce(JsonType.ZLIB, bytes_b64, old_type=JsonType.BYTES)
    recovered = decode_bytes(result, JsonType.ZLIB)
    assert recovered == raw, "BYTES→ZLIB must preserve the underlying raw bytes"


def test_zlib_to_gzip_recompresses():
    raw = b"compress me"
    zlib_b64 = encode_bytes(raw, JsonType.ZLIB)
    result = _coerce(JsonType.GZIP, zlib_b64, old_type=JsonType.ZLIB)
    recovered = decode_bytes(result, JsonType.GZIP)
    assert recovered == raw


def test_bytes_already_valid_kept_unchanged():
    raw = b"unchanged"
    bytes_b64 = encode_bytes(raw, JsonType.BYTES)
    result = _coerce(JsonType.BYTES, bytes_b64)
    assert result == bytes_b64


# ---------------------------------------------------------------------------
# 3.5  ARRAY↔OBJECT container morph preserves children
# ---------------------------------------------------------------------------


def test_array_to_object_preserves_values_with_item_n_names():
    # Wrap array as a child so we can address its type column via the model.
    model = JsonTreeModel({"arr": [10, 20, 30]})
    type_idx = model.index(0, 1, QModelIndex())  # type col of "arr" (ARRAY)

    assert model.setData(type_idx, JsonType.OBJECT)

    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.OBJECT
    assert item.child_count() == 3
    names = [child.name for child in item.child_items]
    assert names == ["item1", "item2", "item3"]
    values = [child.value for child in item.child_items]
    assert values == [10, 20, 30]


def test_object_to_array_preserves_value_order_drops_names():
    model = JsonTreeModel({"obj": {"a": 1, "b": 2, "c": 3}})
    type_idx = model.index(0, 1, QModelIndex())  # type col of "obj" (OBJECT)

    assert model.setData(type_idx, JsonType.ARRAY)

    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.ARRAY
    assert item.child_count() == 3
    assert all(child.name is None for child in item.child_items)
    assert [child.value for child in item.child_items] == [1, 2, 3]


def test_array_to_object_and_back_round_trips():
    model = JsonTreeModel({"arr": [True, "hello", 99]})
    type_idx = model.index(0, 1, QModelIndex())  # type col of "arr"

    # ARRAY → OBJECT
    assert model.setData(type_idx, JsonType.OBJECT)
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.OBJECT
    assert item.child_count() == 3

    # OBJECT → ARRAY
    assert model.setData(type_idx, JsonType.ARRAY)
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.ARRAY
    assert item.child_count() == 3
    assert all(child.name is None for child in item.child_items)


def test_array_to_object_morph_no_children_is_ok():
    model = JsonTreeModel({"arr": []})
    type_idx = model.index(0, 1, QModelIndex())  # type col of "arr" (empty ARRAY)
    assert model.setData(type_idx, JsonType.OBJECT)
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.OBJECT
    assert item.child_count() == 0
