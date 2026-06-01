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
        assert nt.frac_digits == 0

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

    def test_frac_digits_none(self):
        nt = NanoTime(12, 34, 0, 0, _frac_digits=None)
        assert nt.frac_digits is None

    def test_frac_digits_explicit(self):
        nt = NanoTime(12, 34, 56, 123000000, _frac_digits=3)
        assert nt.frac_digits == 3

    def test_invalid_frac_digits(self):
        with pytest.raises(ValueError, match="frac_digits"):
            NanoTime(12, 34, 56, 0, _frac_digits=10)


class TestNanoTimeIsoformat:
    def test_auto_no_fraction(self):
        assert NanoTime(12, 34, 56).isoformat() == "12:34:56"

    def test_auto_with_fraction(self):
        assert NanoTime(12, 34, 56, 123000000, _frac_digits=3).isoformat() == "12:34:56.123"

    def test_auto_with_microsecond_precision(self):
        assert NanoTime(12, 34, 56, 123456000, _frac_digits=6).isoformat() == "12:34:56.123456"

    def test_auto_with_nanosecond_precision(self):
        assert NanoTime(12, 34, 56, 123456789, _frac_digits=9).isoformat() == "12:34:56.123456789"

    def test_auto_trailing_zeros_stripped(self):
        assert NanoTime(12, 34, 56, 100000000, _frac_digits=1).isoformat() == "12:34:56.1"

    def test_auto_hh_mm_format(self):
        assert NanoTime(12, 34, 0, 0, _frac_digits=None).isoformat() == "12:34"

    def test_auto_hh_mm_ss_format(self):
        assert NanoTime(12, 34, 56, 0, _frac_digits=0).isoformat() == "12:34:56"

    def test_auto_hh_mm_ss_frac_format(self):
        assert NanoTime(12, 34, 56, 100000000, _frac_digits=1).isoformat() == "12:34:56.1"

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
        nt = NanoTime.fromisoformat("12:34")
        assert nt == NanoTime(12, 34, 0, 0)
        assert nt.frac_digits is None

    def test_hh_mm_ss(self):
        nt = NanoTime.fromisoformat("12:34:56")
        assert nt == NanoTime(12, 34, 56, 0)
        assert nt.frac_digits == 0

    def test_hh_mm_ss_fff_6digit(self):
        nt = NanoTime.fromisoformat("12:34:56.123456")
        assert nt == NanoTime(12, 34, 56, 123456000)
        assert nt.frac_digits == 6

    def test_hh_mm_ss_fff_9digit(self):
        nt = NanoTime.fromisoformat("12:34:56.123456789")
        assert nt == NanoTime(12, 34, 56, 123456789)
        assert nt.frac_digits == 9

    def test_hh_mm_ss_fff_1digit(self):
        nt = NanoTime.fromisoformat("12:34:56.1")
        assert nt == NanoTime(12, 34, 56, 100000000)
        assert nt.frac_digits == 1

    def test_invalid_string(self):
        with pytest.raises(ValueError, match="Invalid"):
            NanoTime.fromisoformat("not-a-time")


class TestNanoTimeRoundTrip:
    @pytest.mark.parametrize(
        "text",
        [
            "12:34",
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


class TestNanoTimeReplace:
    def test_replace_hour(self):
        nt = NanoTime(12, 34, 56, 123456789, _frac_digits=9)
        replaced = nt.replace(hour=23)
        assert replaced == NanoTime(23, 34, 56, 123456789)
        assert replaced.frac_digits == 9

    def test_replace_nanosecond(self):
        nt = NanoTime(12, 34, 56, 123456789, _frac_digits=9)
        replaced = nt.replace(nanosecond=0)
        assert replaced == NanoTime(12, 34, 56, 0)
        assert replaced.frac_digits == 9

    def test_replace_preserves_frac_digits(self):
        nt = NanoTime.fromisoformat("12:34")
        replaced = nt.replace(hour=23)
        assert replaced.frac_digits is None
        assert replaced.isoformat() == "23:34"

    def test_replace_frac_digits(self):
        nt = NanoTime(12, 34, 56, 0)
        replaced = nt.replace(frac_digits=None)
        assert replaced.frac_digits is None
        assert replaced.isoformat() == "12:34"


class TestNanoTimeStr:
    def test_str_matches_isoformat(self):
        nt = NanoTime(12, 34, 56, 123000000, _frac_digits=3)
        assert str(nt) == nt.isoformat()


class TestNanoTimeEquality:
    def test_equal_ignores_frac_digits(self):
        a = NanoTime(12, 34, 0, 0, _frac_digits=None)
        b = NanoTime(12, 34, 0, 0, _frac_digits=0)
        assert a == b

    def test_hash_ignores_frac_digits(self):
        a = NanoTime(12, 34, 0, 0, _frac_digits=None)
        b = NanoTime(12, 34, 0, 0, _frac_digits=0)
        assert hash(a) == hash(b)
