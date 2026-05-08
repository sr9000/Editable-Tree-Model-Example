"""Friendly stub values for unrecoverable type coercions.

When a value can't be sensibly coerced into the target type (and we're not
in strict-rejection mode), instead of falling back to a soulless ``0`` /
``""`` we pick a small, fun placeholder.  These are picked at random so the
user gets a hint that the value is a placeholder rather than something
they actually entered.

Strict-mode coercion (the column-2 value editor) still rejects bad input;
stubs are only used when the system is morphing a value across an
incompatible type boundary at the user's request.
"""

import random

from gmpy2 import mpq

# ----- Numbers ------------------------------------------------------------

_FAMOUS_INTEGERS = (
    42,  # answer
    1337,  # leet
    65535,  # 2^16 - 1
    8086,  # i8086
    420,  # blaze
    9001,  # over 9000
    73,  # Sheldon's favourite prime
    777,  # lucky
    299792458,  # c (m/s) — hilariously big
)

_FAMOUS_FLOATS = (
    "3.14159265",  # π
    "2.71828182",  # e
    "1.61803398",  # φ (golden ratio)
    "1.41421356",  # √2
    "6.62607015",  # h (Planck) (×10⁻³⁴ omitted for taste)
    "9.80665",  # g
)

# Keep percents in [0, 1] so they pass the PERCENT range guard.
_FAMOUS_PERCENTS = (
    "1/2",
    "1/3",
    "2/3",
    "1/4",
    "3/4",
    "1/7",
    "0.01",
    "0.618",  # 1/φ
    "0.999",
)

# ----- Strings ------------------------------------------------------------

_FAMOUS_PHRASES = (
    "Hello, world!",
    "The quick brown fox jumps over the lazy dog.",
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
    "To be, or not to be, that is the question.",
    "All your base are belong to us.",
    "I think, therefore I am.",
    "May the Force be with you.",
    "So long, and thanks for all the fish.",
    "Curiouser and curiouser!",
    "Houston, we have a problem.",
    "Veni, vidi, vici.",
    "Cogito, ergo sum.",
    "E pluribus unum.",
    "Carpe diem.",
)

_LOREM_IPSUM_MULTILINE = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n"
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.\n"
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris\n"
    "nisi ut aliquip ex ea commodo consequat."
)

# Funny printable bytes payloads (raw bytes — encoder/compressor handles the rest).
_FUN_BYTES = (
    b"GIF89a",  # GIF magic
    b"\x89PNG\r\n\x1a\n",  # PNG magic
    b"PK\x03\x04",  # zip magic
    b"%PDF-1.4",  # PDF magic
    b"#!/bin/sh\n",  # shebang
    b"<!DOCTYPE html>\n",
    b"deadbeef",
    b"cafebabe",
)


# ----- Picker -------------------------------------------------------------


def stub_integer() -> int:
    return random.choice(_FAMOUS_INTEGERS)


def stub_float() -> "mpq":
    return mpq(random.choice(_FAMOUS_FLOATS))


def stub_percent() -> "mpq":
    return mpq(random.choice(_FAMOUS_PERCENTS))


def stub_string() -> str:
    return random.choice(_FAMOUS_PHRASES)


def stub_multiline() -> str:
    return _LOREM_IPSUM_MULTILINE


def stub_bytes_raw() -> bytes:
    return random.choice(_FUN_BYTES)
