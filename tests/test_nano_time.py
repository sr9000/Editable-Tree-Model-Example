"""Unit tests for the NanoTime dataclass."""

import pytest

from core.datetime_parsing.nano_time import NanoTime


class TestNanoTimeConstruction:
    def test_default_values(self):
        nt = NanoTime()
        assert nt.hour == 0
        assert nt.minute == 0
        assert nt.second == 0
        assert nt.nanosecond == 0

    def test_full_construction(self):
        nt = NanoTime(23, 59, 59, 999999999)
        assert nt.hour == 23
        assert nt.minute == 59
        assert nt.second == 59
        assert nt.nanosecond == 999999999

    def test_invalid_hour(self):
        with pytest.raises(ValueError, match="hour"):
            NanoTime(24, 0, 0)

    def test_invalid_minute(self):
        with pytest.raises(ValueError, match="minute"):
            NanoTime(0, 60, 0)

    def test_invalid_second(self):
        with pytest.raises(ValueError, match="second"):
            NanoTime(0, 0, 60)

    def test_invalid_nanosecond(self):
        with pytest.raises(ValueError, match="nanosecond"):
            NanoTime(0, 0, 0, 1_000_000_000)

    def test_frozen(self):
        nt = NanoTime(12, 30, 0)
        with pytest.raises(AttributeError):  # allow: testing frozen dataclass immutability
            nt.hour = 13  # type: ignore[misc]


class TestNanoTimeIsoformat:
    def test_auto_no_fraction(self):
        assert NanoTime(12, 34, 56).isoformat() == "12:34:56"

    def test_auto_with_fraction(self):
        assert NanoTime(12, 34, 56, 123000000).isoformat() == "12:34:56.123"

    def test_auto_with_microsecond_precision(self):
        assert NanoTime(12, 34, 56, 123456000).isoformat() == "12:34:56.123456"

    def test_auto_with_nanosecond_precision(self):
        assert NanoTime(12, 34, 56, 123456789).isoformat() == "12:34:56.123456789"

    def test_auto_trailing_zeros_stripped(self):
        assert NanoTime(12, 34, 56, 100000000).isoformat() == "12:34:56.1"

    def test_timespec_hours(self):
        assert NanoTime(12, 34, 56).isoformat(timespec="hours") == "12:34"

    def test_timespec_minutes(self):
        assert NanoTime(12, 34, 56).isoformat(timespec="minutes") == "12:34"

    def test_timespec_seconds(self):
        assert NanoTime(12, 34, 56).isoformat(timespec="seconds") == "12:34:56"

    def test_timespec_milliseconds(self):
        assert NanoTime(12, 34, 56, 123456789).isoformat(timespec="milliseconds") == "12:34:56.123"

    def test_timespec_microseconds(self):
        assert NanoTime(12, 34, 56, 123456789).isoformat(timespec="microseconds") == "12:34:56.123456"

    def test_timespec_nanoseconds(self):
        assert NanoTime(12, 34, 56, 123456789).isoformat(timespec="nanoseconds") == "12:34:56.123456789"


class TestNanoTimeFromisoformat:
    def test_hh_mm(self):
        assert NanoTime.fromisoformat("12:34") == NanoTime(12, 34, 0, 0)

    def test_hh_mm_ss(self):
        assert NanoTime.fromisoformat("12:34:56") == NanoTime(12, 34, 56, 0)

    def test_hh_mm_ss_fff_6digit(self):
        assert NanoTime.fromisoformat("12:34:56.123456") == NanoTime(12, 34, 56, 123456000)

    def test_hh_mm_ss_fff_9digit(self):
        assert NanoTime.fromisoformat("12:34:56.123456789") == NanoTime(12, 34, 56, 123456789)

    def test_hh_mm_ss_fff_1digit(self):
        assert NanoTime.fromisoformat("12:34:56.1") == NanoTime(12, 34, 56, 100000000)

    def test_invalid_string(self):
        with pytest.raises(ValueError, match="Invalid"):
            NanoTime.fromisoformat("not-a-time")


class TestNanoTimeRoundTrip:
    @pytest.mark.parametrize(
        "text",
        [
            "12:34:56",
            "12:34:56.1",
            "12:34:56.123",
            "12:34:56.123456",
            "12:34:56.123456789",
        ],
    )
    def test_isoformat_round_trip(self, text: str):
        nt = NanoTime.fromisoformat(text)
        assert nt.isoformat() == text

    def test_hh_mm_round_trip(self):
        """'12:34' parses to NanoTime(12,34,0,0) which formats as '12:34:00'."""
        nt = NanoTime.fromisoformat("12:34")
        assert nt == NanoTime(12, 34, 0, 0)
        assert nt.isoformat() == "12:34:00"


class TestNanoTimeReplace:
    def test_replace_hour(self):
        nt = NanoTime(12, 34, 56, 123456789)
        replaced = nt.replace(hour=23)
        assert replaced == NanoTime(23, 34, 56, 123456789)

    def test_replace_nanosecond(self):
        nt = NanoTime(12, 34, 56, 123456789)
        replaced = nt.replace(nanosecond=0)
        assert replaced == NanoTime(12, 34, 56, 0)


class TestNanoTimeStr:
    def test_str_matches_isoformat(self):
        nt = NanoTime(12, 34, 56, 123000000)
        assert str(nt) == nt.isoformat()
