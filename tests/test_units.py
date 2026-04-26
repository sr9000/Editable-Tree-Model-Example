from units import bits, counts, format_bytes


def test_bits_bytes():
    assert bits(0) == "0 byte"
    assert bits(1) == "1 byte"
    assert bits(512) == "512 byte"

    assert bits(1023) == "1.00 KiB"
    assert bits(1024) == "1.00 KiB"
    assert bits(1025) == "1.00 KiB"
    assert bits(1536) == "1.50 KiB"
    assert bits(10 * 1024) == "10.0 KiB"
    assert bits(998 * 1024) == "998 KiB"
    assert bits(998 * 1024 + 1) == "998 KiB"
    assert bits(998 * 1024 + 51) == "998 KiB"
    assert bits(998 * 1024 + 52) == "998 KiB"

    assert bits(999 * 1024) == "0.98 MiB"
    assert bits(999 * 1024 + 1) == "0.98 MiB"
    assert bits(1024 * 1024 - 5243) == "0.99 MiB"
    assert bits(1024 * 1024 - 5242) == "1.00 MiB"
    assert bits(1024 * 1024 - 1) == "1.00 MiB"
    assert bits(1024 * 1024) == "1.00 MiB"
    assert bits(5 * 1024 * 1024 + 250 * 1024) == "5.24 MiB"
    assert bits(10 * 1024 * 1024 + 900 * 1024) == "10.9 MiB"

    assert bits(1024**8) == "1.00 YiB"
    assert bits(1024**9) == "∞ byte"


def test_counts_units():
    assert counts(0) == "0"
    assert counts(1) == "1"
    assert counts(999) == "999"

    assert counts(1000) == "1.00K"
    assert counts(1555) == "1.55K"
    assert counts(10_000) == "10.0K"
    assert counts(15_555) == "15.6K"
    assert counts(1_000_000 - 1001) == "998K"

    assert counts(1_000_000 - 1000) == "1.00M"
    assert counts(1_000_000 - 999) == "1.00M"
    assert counts(1_000_000 - 1) == "1.00M"
    assert counts(1_000_000) == "1.00M"
    assert counts(1_500_000) == "1.50M"
    assert counts(10_000_000) == "10.0M"

    assert counts(1_000_000_000) == "1.00B"
    assert counts(10_000_000_000) == "10.0B"
    assert counts(998_900_000_000) == "998B"
    assert counts(998_999_999_999) == "998B"

    assert counts(999_000_000_000) == "∞"
    assert counts(999_000_000_001) == "∞"
    assert counts(10**100) == "∞"


def test_format_bytes_is_bits_alias():
    assert format_bytes(0) == bits(0)
    assert format_bytes(1536) == bits(1536)
    assert format_bytes(1024**8) == bits(1024**8)
