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
from gmpy2 import mpq
from PySide6.QtCore import QModelIndex

from datetime_editor.enums import DateTimeCategory
from datetime_editor.regex import parse_datetime_text
from delegates.bytes_codec import decode_bytes, encode_bytes
from tree.item_coercion import coerce_value_for_type
from tree.model import JsonTreeModel
from tree.types import JsonType
from units.number_affix import AffixKind, NumberAffix, format_number_affix

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


def test_strict_datetime_keeps_entered_seconds_and_fractional_part():
    ok, result = coerce_value_for_type(JsonType.DATETIME, "2025-11-02T12:34:56.1234", strict=True)
    assert ok
    assert result == "2025-11-02T12:34:56.1234"


def test_strict_datetime_can_remove_seconds_back_to_minutes():
    ok, result = coerce_value_for_type(JsonType.DATETIME, "2025-11-02T12:34", strict=True)
    assert ok
    assert result == "2025-11-02T12:34"


def test_strict_time_keeps_entered_fractional_precision():
    ok, result = coerce_value_for_type(JsonType.TIME, "12:34:56.1", strict=True)
    assert ok
    assert result == "12:34:56.1"


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


def test_float_seconds_to_datetime_preserves_fractional_part():
    epoch_s = 1704067200.5  # 2024-01-01 00:00:00.5 UTC
    result = _coerce(JsonType.DATETIME, epoch_s)
    dt = datetime.datetime.fromisoformat(result)
    assert dt == datetime.datetime(2024, 1, 1, 0, 0, 0, 500000)


def test_mpq_epoch_seconds_to_date_works():
    epoch = mpq(1717200000)  # 2024-06-01 00:00:00 UTC
    result = _coerce(JsonType.DATE, epoch)
    assert result == "2024-06-01"


def test_numeric_seconds_to_time_works_for_non_int():
    result = _coerce(JsonType.TIME, mpq("3723.25"))
    parsed = datetime.time.fromisoformat(result)
    assert parsed == datetime.time(1, 2, 3, 250000)


def test_time_to_integer_out_of_range_uses_default_fallback():
    ok, result = coerce_value_for_type(JsonType.INTEGER, 90_000, strict=False, old_type=JsonType.TIME)
    assert ok
    assert isinstance(result, int)
    assert result != 90_000


def test_time_to_integer_out_of_range_strict_rejects():
    ok, result = coerce_value_for_type(JsonType.INTEGER, 90_000, strict=True, old_type=JsonType.TIME)
    assert ok is False
    assert result is None


def test_invalid_date_string_to_float_uses_default_fallback():
    ok, result = coerce_value_for_type(JsonType.FLOAT, "not-a-date", strict=False, old_type=JsonType.DATE)
    assert ok
    assert result in {
        mpq("3.14159265"),
        mpq("2.71828182"),
        mpq("1.61803398"),
        mpq("1.41421356"),
        mpq("6.62607015"),
        mpq("9.80665"),
    }


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


def test_datetime_string_to_integer_uses_unix_epoch():
    value = "2024-03-10T08:30:00"
    ok, result = coerce_value_for_type(JsonType.INTEGER, value, strict=False, old_type=JsonType.DATETIME)
    assert ok
    assert result == int(datetime.datetime(2024, 3, 10, 8, 30, 0, tzinfo=datetime.timezone.utc).timestamp())


def test_date_string_to_integer_uses_unix_epoch_midnight_utc():
    value = "2024-06-01"
    ok, result = coerce_value_for_type(JsonType.INTEGER, value, strict=False, old_type=JsonType.DATE)
    assert ok
    assert result == int(datetime.datetime(2024, 6, 1, 0, 0, 0, tzinfo=datetime.timezone.utc).timestamp())


def test_time_string_to_integer_uses_seconds_since_day_start():
    value = "01:02:03"
    ok, result = coerce_value_for_type(JsonType.INTEGER, value, strict=False, old_type=JsonType.TIME)
    assert ok
    assert result == 3723


def test_temporal_to_float_keeps_subsecond_precision():
    ok, result = coerce_value_for_type(JsonType.FLOAT, "12:34:56.5", strict=False, old_type=JsonType.TIME)
    assert ok
    assert (
        result
        == datetime.time(12, 34, 56, 500000).hour * 3600 + datetime.time(12, 34, 56, 500000).minute * 60 + 56 + 0.5
    )


def test_datetimezone_to_float_uses_unix_epoch_seconds():
    value = "2024-01-01T00:00:00+01:00"
    ok, result = coerce_value_for_type(JsonType.FLOAT, value, strict=False, old_type=JsonType.DATETIMEZONE)
    assert ok
    expected = datetime.datetime(2023, 12, 31, 23, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
    assert float(result) == expected


def _temporal_category(json_type: JsonType) -> DateTimeCategory:
    mapping = {
        JsonType.DATE: DateTimeCategory.Date,
        JsonType.TIME: DateTimeCategory.Time,
        JsonType.DATETIME: DateTimeCategory.DateTime,
        JsonType.DATETIMEZONE: DateTimeCategory.DateTimeWithTZ,
        JsonType.DATETIMEUTC: DateTimeCategory.DateTimeUTC,
    }
    return mapping[json_type]


def _assert_number_result(number_type: JsonType, result, expected_seconds: mpq) -> None:
    if number_type is JsonType.INTEGER:
        assert isinstance(result, int)
        assert result == int(expected_seconds)
    else:
        assert isinstance(result, mpq)
        assert result == expected_seconds


def _temporal_epoch_seconds(temporal_type: JsonType) -> mpq:
    match temporal_type:
        case JsonType.DATE:
            dt = datetime.datetime(2024, 1, 2, tzinfo=datetime.timezone.utc)
            return mpq(int(dt.timestamp()))
        case JsonType.TIME:
            return mpq("3723.5")
        case JsonType.DATETIME:
            dt = datetime.datetime(2024, 1, 2, 3, 4, 5, 500000, tzinfo=datetime.timezone.utc)
            return mpq(int(dt.timestamp() * 1_000_000), 1_000_000)
        case JsonType.DATETIMEZONE:
            dt = datetime.datetime(2024, 1, 2, 3, 4, 5, 500000, tzinfo=datetime.timezone(datetime.timedelta(hours=1)))
            return mpq(int(dt.timestamp() * 1_000_000), 1_000_000)
        case JsonType.DATETIMEUTC:
            dt = datetime.datetime(2024, 1, 2, 3, 4, 5, 500000, tzinfo=datetime.timezone.utc)
            return mpq(int(dt.timestamp() * 1_000_000), 1_000_000)
    raise AssertionError(f"unsupported temporal type: {temporal_type}")


def _temporal_text_and_object(temporal_type: JsonType):
    match temporal_type:
        case JsonType.DATE:
            return "2024-01-02", datetime.date(2024, 1, 2)
        case JsonType.TIME:
            return "01:02:03.5", datetime.time(1, 2, 3, 500000)
        case JsonType.DATETIME:
            return "2024-01-02T03:04:05.5", datetime.datetime(2024, 1, 2, 3, 4, 5, 500000)
        case JsonType.DATETIMEZONE:
            return "2024-01-02T03:04:05.5+01:00", datetime.datetime(
                2024, 1, 2, 3, 4, 5, 500000, tzinfo=datetime.timezone(datetime.timedelta(hours=1))
            )
        case JsonType.DATETIMEUTC:
            return "2024-01-02T03:04:05.5Z", datetime.datetime(
                2024, 1, 2, 3, 4, 5, 500000, tzinfo=datetime.timezone.utc
            )
    raise AssertionError(f"unsupported temporal type: {temporal_type}")


_FALLBACK_FLOATS = {
    mpq("3.14159265"),
    mpq("2.71828182"),
    mpq("1.61803398"),
    mpq("1.41421356"),
    mpq("6.62607015"),
    mpq("9.80665"),
}
_FALLBACK_INTS = {42, 1337, 65535, 8086, 420, 9001, 73, 777, 299792458}


@pytest.mark.parametrize("number_type", [JsonType.INTEGER, JsonType.FLOAT], ids=["integer", "float"])
@pytest.mark.parametrize(
    "temporal_type",
    [JsonType.DATE, JsonType.TIME, JsonType.DATETIME, JsonType.DATETIMEZONE, JsonType.DATETIMEUTC],
    ids=["date", "time", "datetime", "dtz", "dtutc"],
)
@pytest.mark.parametrize(
    "case_kind",
    [
        "text_to_number",
        "object_to_number",
        "number_to_temporal_int",
        "number_to_temporal_fraction",
        "invalid_temporal_to_number",
    ],
)
def test_number_time_matrix(number_type: JsonType, temporal_type: JsonType, case_kind: str):
    temporal_text, temporal_obj = _temporal_text_and_object(temporal_type)
    expected_seconds = _temporal_epoch_seconds(temporal_type)

    if case_kind == "text_to_number":
        ok, result = coerce_value_for_type(number_type, temporal_text, strict=False, old_type=temporal_type)
        assert ok
        _assert_number_result(number_type, result, expected_seconds)
        return

    if case_kind == "object_to_number":
        ok, result = coerce_value_for_type(number_type, temporal_obj, strict=False, old_type=temporal_type)
        assert ok
        _assert_number_result(number_type, result, expected_seconds)
        return

    if case_kind == "number_to_temporal_int":
        epoch = int(expected_seconds)
        ok, result = coerce_value_for_type(temporal_type, epoch, strict=False, old_type=number_type)
        assert ok
        parsed = parse_datetime_text(result, _temporal_category(temporal_type))
        assert parsed is not None
        return

    if case_kind == "number_to_temporal_fraction":
        if temporal_type is JsonType.TIME:
            numeric = float(expected_seconds)
        else:
            numeric = float(expected_seconds) + 0.25
        ok, result = coerce_value_for_type(temporal_type, numeric, strict=False, old_type=number_type)
        assert ok
        parsed = parse_datetime_text(result, _temporal_category(temporal_type))
        assert parsed is not None
        return

    ok, result = coerce_value_for_type(number_type, "not-a-temporal", strict=False, old_type=temporal_type)
    assert ok
    if number_type is JsonType.INTEGER:
        assert result in _FALLBACK_INTS
    else:
        assert result in _FALLBACK_FLOATS


@pytest.mark.parametrize("number_type", [JsonType.INTEGER, JsonType.FLOAT], ids=["integer", "float"])
@pytest.mark.parametrize("case_kind", ["string_to_number", "number_to_string", "invalid_string_to_number"])
def test_string_number_matrix(number_type: JsonType, case_kind: str):
    if case_kind == "string_to_number":
        value = "12345" if number_type is JsonType.INTEGER else "12345.25"
        ok, result = coerce_value_for_type(number_type, value, strict=False, old_type=JsonType.STRING)
        assert ok
        if number_type is JsonType.INTEGER:
            assert result == 12345
        else:
            assert result == mpq("12345.25")
        return

    if case_kind == "number_to_string":
        value = 12345 if number_type is JsonType.INTEGER else mpq("12345.25")
        ok, result = coerce_value_for_type(JsonType.STRING, value, strict=False, old_type=number_type)
        assert ok
        assert isinstance(result, str)
        assert result
        return

    ok, result = coerce_value_for_type(number_type, "not-a-number", strict=False, old_type=JsonType.STRING)
    assert ok
    if number_type is JsonType.INTEGER:
        assert result in _FALLBACK_INTS
    else:
        assert result in _FALLBACK_FLOATS


@pytest.mark.parametrize(
    "temporal_type,value_text,value_obj",
    [
        (JsonType.DATE, "2024-01-02", datetime.date(2024, 1, 2)),
        (JsonType.TIME, "01:02:03", datetime.time(1, 2, 3)),
        (JsonType.DATETIME, "2024-01-02T03:04", datetime.datetime(2024, 1, 2, 3, 4)),
        (JsonType.DATETIME, "2024-01-02T03:04:05", datetime.datetime(2024, 1, 2, 3, 4, 5)),
        (
            JsonType.DATETIMEZONE,
            "2024-01-02T03:04:05+01:00",
            datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone(datetime.timedelta(hours=1))),
        ),
        (
            JsonType.DATETIMEUTC,
            "2024-01-02T03:04:05Z",
            datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc),
        ),
    ],
)
@pytest.mark.parametrize("direction", ["string_to_temporal", "temporal_to_string"])
def test_string_time_matrix(temporal_type: JsonType, value_text: str, value_obj, direction: str):
    if direction == "string_to_temporal":
        ok, result = coerce_value_for_type(temporal_type, value_text, strict=False, old_type=JsonType.STRING)
        assert ok
        parsed = parse_datetime_text(result, _temporal_category(temporal_type))
        assert parsed is not None
        return

    ok, result = coerce_value_for_type(JsonType.STRING, value_obj, strict=False, old_type=temporal_type)
    assert ok
    assert result == str(value_obj)


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


def test_none_to_bytes_gives_stub_payload():
    """None → BYTES/ZLIB/GZIP yields a friendly placeholder payload (saint coercion)."""
    for kind in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):
        result = _coerce(kind, None)
        assert isinstance(result, str)
        assert result, f"{kind} stub must not be empty"
        # Must round-trip back to bytes through its own codec.
        assert decode_bytes(result, kind)  # raises on failure


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
# Bug fix: BYTES/ZLIB/GZIP → STRING surfaces underlying printable text
# ---------------------------------------------------------------------------


def test_bytes_to_string_decodes_printable_text():
    """A BYTES value that holds UTF-8 text must surface as that text in STRING,
    not as the base64 representation."""
    raw = b"hello world"
    bytes_b64 = encode_bytes(raw, JsonType.BYTES)
    result = _coerce(JsonType.STRING, bytes_b64, old_type=JsonType.BYTES)
    assert result == "hello world"


def test_zlib_to_string_decodes_printable_text():
    raw = "Привет, мир!".encode("utf-8")  # non-ASCII printable UTF-8
    zlib_b64 = encode_bytes(raw, JsonType.ZLIB)
    result = _coerce(JsonType.UNICODE, zlib_b64, old_type=JsonType.ZLIB)
    assert result == "Привет, мир!"


def test_gzip_to_string_decodes_printable_text():
    raw = b"some readable text"
    gzip_b64 = encode_bytes(raw, JsonType.GZIP)
    result = _coerce(JsonType.STRING, gzip_b64, old_type=JsonType.GZIP)
    assert result == "some readable text"


def test_bytes_to_string_keeps_base64_when_non_printable():
    """Non-printable bytes (e.g. PNG header) must NOT be silently mangled —
    we keep the base64 encoded form so the user sees something useful."""
    raw = b"\x89PNG\r\n\x1a\n\x00\x01\x02\x03"  # PNG magic + binary
    bytes_b64 = encode_bytes(raw, JsonType.BYTES)
    result = _coerce(JsonType.STRING, bytes_b64, old_type=JsonType.BYTES)
    assert result == bytes_b64


def test_bytes_to_string_full_round_trip_through_item(qtbot):
    """End-to-end: switching BYTES→STRING in a tab surfaces decoded text."""
    from documents.tab import JsonTab

    raw = b"the answer is 42"
    bytes_b64 = encode_bytes(raw, JsonType.BYTES)
    tab = JsonTab(lambda *_: None, data={"blob": bytes_b64})
    qtbot.addWidget(tab)

    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.BYTES

    type_idx = tab.data_store.model.index(0, 1, QModelIndex())
    assert tab.push_change_type(type_idx, JsonType.STRING)

    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.STRING
    assert item.value == "the answer is 42"


# ---------------------------------------------------------------------------
# Saint coercion: friendly stubs for unrecoverable transitions
# ---------------------------------------------------------------------------


def test_unparseable_string_to_integer_yields_fun_stub():
    """A plain English word can't become an int; instead of 0 we return a
    famous integer."""
    result = _coerce(JsonType.INTEGER, "not a number")
    assert isinstance(result, int)
    assert result != 0, "Phase-3 fallback must avoid the boring 0 placeholder"


def test_unparseable_string_to_float_yields_fun_stub():
    from gmpy2 import mpq

    result = _coerce(JsonType.FLOAT, "definitely not a float")
    assert isinstance(result, mpq)
    assert result != mpq(0), "Float fallback must avoid mpq(0)"


def test_unparseable_string_to_percent_yields_in_range_stub():
    from gmpy2 import mpq

    result = _coerce(JsonType.PERCENT, "150%")
    assert isinstance(result, mpq)
    assert 0 <= result <= 1
    assert result != mpq(0)


def test_none_to_string_yields_fun_stub():
    result = _coerce(JsonType.STRING, None)
    assert isinstance(result, str)
    assert result, "None → STRING fallback must not be empty"


def test_none_to_multiline_yields_lorem_ipsum():
    result = _coerce(JsonType.MULTILINE, None)
    assert isinstance(result, str)
    assert "\n" in result, "MULTILINE stub should contain newlines"


def test_int_via_float_string_truncates():
    """'3.14' is not a valid int literal but is a sensible float we can truncate."""
    result = _coerce(JsonType.INTEGER, "3.14")
    assert result == 3


def test_float_affix_to_integer_truncates_fractional_part():
    value = NumberAffix(AffixKind.CURRENCY, "$", False, mpq("7/2"))
    result = _coerce(JsonType.INTEGER, value)
    assert result == 3


def test_float_affix_to_integer_affix_truncates_fractional_part():
    value = NumberAffix(AffixKind.UNITS, "kg", True, mpq("7/2"))
    result = _coerce(JsonType.INTEGER_UNITS, value)
    assert result == NumberAffix(AffixKind.UNITS, "kg", True, 3)


def test_affix_to_string_uses_formatted_text():
    value = NumberAffix(AffixKind.CURRENCY, "$", True, mpq("7/2"))
    ok, result = coerce_value_for_type(JsonType.STRING, value, strict=False, old_type=JsonType.FLOAT_CURRENCY)
    assert ok
    assert result == format_number_affix(value)


def test_number_to_affix_type_uses_mru_default_affix(qtbot):
    from documents.tab import JsonTab

    tab = JsonTab(
        lambda *_: None,
        data={
            "known": NumberAffix(AffixKind.CURRENCY, "$", False, 10),
            "plain": 5,
        },
    )
    qtbot.addWidget(tab)

    type_idx = tab.data_store.model.index(1, 1, QModelIndex())
    assert tab.push_change_type(type_idx, JsonType.INTEGER_CURRENCY)

    item = tab.data_store.model.get_item(tab.data_store.model.index(1, 0, QModelIndex()))
    assert isinstance(item.value, NumberAffix)
    assert item.value.affix == "$"


def test_affix_to_string_to_affix_undo_redo_round_trip(qtbot):
    from documents.tab import JsonTab

    original = NumberAffix(AffixKind.CURRENCY, "$", False, 10)
    tab = JsonTab(lambda *_: None, data={"v": original})
    qtbot.addWidget(tab)

    type_idx = tab.data_store.model.index(0, 1, QModelIndex())

    assert tab.push_change_type(type_idx, JsonType.STRING)
    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.STRING
    assert item.value == "$10"

    assert tab.push_change_type(type_idx, JsonType.INTEGER_UNITS)
    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.INTEGER_UNITS
    assert item.value == NumberAffix(AffixKind.UNITS, "$", False, 10)

    tab.data_store.undo_stack.undo()
    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.STRING
    assert item.value == "$10"

    tab.data_store.undo_stack.undo()
    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.INTEGER_CURRENCY
    assert item.value == original

    tab.data_store.undo_stack.redo()
    tab.data_store.undo_stack.redo()
    item = tab.data_store.model.get_item(tab.data_store.model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.INTEGER_UNITS
    assert item.value == NumberAffix(AffixKind.UNITS, "$", False, 10)


def test_bytes_to_integer_returns_decoded_length():
    """Switching from a bytes-family kind to INTEGER returns the underlying
    byte length, which is meaningful (file/blob size)."""
    raw = b"hello"  # 5 bytes
    bytes_b64 = encode_bytes(raw, JsonType.BYTES)
    result = _coerce(JsonType.INTEGER, bytes_b64, old_type=JsonType.BYTES)
    assert result == 5


def test_strict_mode_still_rejects_bad_input():
    """Strict mode (column-2 value editing) must keep returning failure for
    invalid input, even with stubs available."""
    from tree.item_coercion import coerce_value_for_type

    ok, _ = coerce_value_for_type(JsonType.INTEGER, "not a number", strict=True)
    assert ok is False
    ok, _ = coerce_value_for_type(JsonType.FLOAT, "abc", strict=True)
    assert ok is False
    ok, _ = coerce_value_for_type(JsonType.PERCENT, "200%", strict=True)
    assert ok is False


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
