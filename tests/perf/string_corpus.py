"""Adversarial string generators for parsing vulnerability measurement.

Each generator accepts ``size: int`` and returns ``(family_label: str, text: str)``.
The module imports only Python standard-library modules and ``settings`` for Plan 1
limit constants when available.
"""

from __future__ import annotations

import itertools
from typing import Callable

# Try to import Plan 1 limit constants; fall back to defaults if not yet defined.
try:
    from settings import NUMBER_AFFIX_MAX_LEN as _AFFIX_LIMIT
except ImportError:
    _AFFIX_LIMIT = 20


# ---------------------------------------------------------------------------
# Family generators
# ---------------------------------------------------------------------------


def plain_ascii(size: int) -> tuple[str, str]:
    """Return ``size`` ASCII 'a' characters."""
    return ("plain_ascii", "a" * size)


def whitespace(size: int) -> tuple[str, str]:
    """Return ``size`` whitespace characters including at least one newline."""
    if size < 3:
        # Ensure we have space for at least one newline
        text = " \n"[:size] if size > 0 else ""
    else:
        # Mix spaces, tabs, and newlines; ensure at least one newline
        cycle = itertools.cycle([" ", " ", "\t", " ", "\n", " "])
        text = "".join(itertools.islice(cycle, size))
    return ("whitespace", text)


def digits(size: int) -> tuple[str, str]:
    """Return ``size`` digit '9' characters."""
    return ("digits", "9" * size)


def base64_like(size: int) -> tuple[str, str]:
    """Return ``size`` base64-like characters, padded to a multiple of 4."""
    # Use 'A' which is valid base64 (decodes to 0x00 bytes)
    text = "A" * size
    # Pad to multiple of 4
    remainder = len(text) % 4
    if remainder:
        text += "=" * (4 - remainder)
    return ("base64_like", text)


def near_datetime(size: int) -> tuple[str, str]:
    """Return a string that starts with a date-like prefix but does not parse as datetime.

    Shape: date-like prefix + long digit run + invalid suffix.
    """
    prefix = "2026-06-13"
    if size <= len(prefix):
        # Just return the prefix truncated/padded
        text = prefix[:size] if size > 0 else ""
    else:
        # Add a long digit run and invalid suffix to prevent datetime parsing
        remaining = size - len(prefix)
        if remaining > 10:
            digit_run = "9" * (remaining - 3)
            suffix = "XYZ"  # Invalid suffix that prevents datetime parsing
            text = prefix + digit_run + suffix
        else:
            # For small sizes, just add digits and an invalid char
            text = prefix + "9" * (remaining - 1) + "X"
    return ("near_datetime", text)


def near_affix(size: int) -> tuple[str, str]:
    """Return a string with a currency/unit prefix plus a digit run exceeding the affix limit.

    The digit run is longer than ``NUMBER_AFFIX_MAX_LEN`` to stress the affix parser.
    """
    # Use a currency prefix that would be valid if the number were shorter
    prefix = "$"
    # Create a digit run that exceeds the affix limit
    digit_len = max(size - len(prefix), _AFFIX_LIMIT + 10)
    if size > len(prefix) + digit_len:
        # Pad with spaces if needed
        text = prefix + "9" * digit_len + " " * (size - len(prefix) - digit_len)
    else:
        text = prefix + "9" * digit_len
    # Truncate or pad to exact size
    if len(text) > size:
        text = text[:size]
    elif len(text) < size:
        text = text + " " * (size - len(text))
    return ("near_affix", text)


def near_color(size: int) -> tuple[str, str]:
    """Return a string that starts with '#' followed by hex characters.

    For stress sizes (size > 9), this exceeds valid color length.
    """
    if size < 1:
        return ("near_color", "")
    if size == 1:
        return ("near_color", "#")
    # '#' + 'f' * (size - 1)
    text = "#" + "f" * (size - 1)
    return ("near_color", text)


def unicode_bulk(size: int) -> tuple[str, str]:
    """Return ``size`` repetitions of a non-ASCII code point."""
    # Use 'é' (U+00E9) which has ord > 127
    return ("unicode_bulk", "é" * size)


def pathological_repetition(size: int) -> tuple[str, str]:
    """Return repeated regex-sensitive motifs such as 'ab' and '#fff'.

    The generated length is within one motif of ``size``.
    """
    if size < 1:
        return ("pathological_repetition", "")
    # Alternate between regex-sensitive motifs
    motifs = ["ab", "#fff", "9.9", "2026-"]
    motif_cycle = itertools.cycle(motifs)
    parts = []
    current_len = 0
    while current_len < size:
        motif = next(motif_cycle)
        if current_len + len(motif) <= size + len(motifs[-1]):  # Allow within one motif
            parts.append(motif)
            current_len += len(motif)
        else:
            break
    text = "".join(parts)
    # Truncate to exact size if we overshot
    if len(text) > size:
        text = text[:size]
    return ("pathological_repetition", text)


def mixed_interleaved(size: int) -> tuple[str, str]:
    """Return newline-separated chunks from at least three other families.

    The chunks are interleaved with newlines to stress multi-line parsing paths.
    """
    if size < 10:
        # For very small sizes, just combine a few short chunks
        chunks = [
            plain_ascii(max(1, size // 4))[1],
            digits(max(1, size // 4))[1],
            unicode_bulk(max(1, size // 4))[1],
        ]
        text = "\n".join(chunks)[:size]
        return ("mixed_interleaved", text)

    # Distribute size across at least 3 families plus newlines
    num_families = min(5, max(3, size // 100 + 3))  # 3-5 families based on size
    chunk_size = (size - num_families + 1) // num_families  # Account for newlines

    families_to_use = [
        plain_ascii,
        digits,
        unicode_bulk,
        base64_like,
        near_color,
    ][:num_families]

    chunks = []
    remaining = size
    for i, factory in enumerate(families_to_use):
        if i == len(families_to_use) - 1:
            # Last chunk gets remaining size minus newlines
            this_size = remaining - (len(families_to_use) - 1 - i)
        else:
            this_size = chunk_size
        this_size = max(1, min(this_size, remaining - (len(families_to_use) - 1 - i)))
        _, chunk_text = factory(this_size)
        chunks.append(chunk_text)
        remaining -= len(chunk_text) + 1  # +1 for newline

    text = "\n".join(chunks)
    # Ensure exact size
    if len(text) > size:
        text = text[:size]
    elif len(text) < size:
        text = text + " " * (size - len(text))
    return ("mixed_interleaved", text)


# ---------------------------------------------------------------------------
# Registry of all families
# ---------------------------------------------------------------------------

FAMILY_REGISTRY: dict[str, Callable[[int], tuple[str, str]]] = {
    "plain_ascii": plain_ascii,
    "whitespace": whitespace,
    "digits": digits,
    "base64_like": base64_like,
    "near_datetime": near_datetime,
    "near_affix": near_affix,
    "near_color": near_color,
    "unicode_bulk": unicode_bulk,
    "pathological_repetition": pathological_repetition,
    "mixed_interleaved": mixed_interleaved,
}

# Default sizes for normal local runs
DEFAULT_SIZES: tuple[int, ...] = (1024, 4096, 16384, 65536)

# Extended sizes for milestone reports
EXTENDED_SIZES: tuple[int, ...] = (262144, 1048576, 10485760)
