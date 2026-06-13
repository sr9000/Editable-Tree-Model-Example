"""Raw numeric value object for unsupported numeric literals.

When a numeric literal cannot be represented as the application's normal numeric
type (``gmpy2.mpq``) because of overflow, underflow, a non-finite result, an
unsupported format, or parser rejection, the original raw text is preserved
verbatim inside a :class:`RawNumericValue`.  The value is treated as plain,
editable text so loading, rendering, editing, validation, and saving never
crash and never silently lose the original literal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Stable reason codes (kept as plain strings so they survive serialization and
# are easy to assert against in tests).
REASON_OVERFLOW = "overflow"
REASON_UNDERFLOW = "underflow"
REASON_NON_FINITE = "non-finite"
REASON_INVALID_FORMAT = "invalid-format"
REASON_PRECISION_LIMIT = "precision-limit"
REASON_PARSER_REJECTION = "parser-rejection"
REASON_UNKNOWN = "unknown"

_REASON_DESCRIPTIONS: dict[str, str] = {
    REASON_OVERFLOW: "the value magnitude is too large (overflow)",
    REASON_UNDERFLOW: "the value magnitude is too small (underflow)",
    REASON_NON_FINITE: "the value is not finite (infinity or NaN)",
    REASON_INVALID_FORMAT: "the value is not a valid number format",
    REASON_PRECISION_LIMIT: "the value has too many significant digits",
    REASON_PARSER_REJECTION: "the value was rejected by the numeric parser",
    REASON_UNKNOWN: "the value is unsupported as a regular number",
}


def describe_reason(reason: str) -> str:
    """Return a short human-readable explanation for a reason code."""
    return _REASON_DESCRIPTIONS.get(reason, _REASON_DESCRIPTIONS[REASON_UNKNOWN])


# Narrow recovery/edit grammar for raw numeric values. This is intentionally
# NOT a full float grammar: it only accepts the small set of shapes the app
# allows when a user edits an unsupported numeric literal. Exponent length is
# bounded so a fresh edit cannot reintroduce an unbounded-magnitude literal
# (the original raw text is always allowed unchanged regardless of this regex).
_RAW_NUMERIC_EDIT_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")

# Non-finite spellings the app is willing to preserve through a raw edit.
_RAW_NON_FINITE_SPELLINGS = frozenset(
    {
        "inf",
        "+inf",
        "-inf",
        "infinity",
        "+infinity",
        "-infinity",
        ".inf",
        "+.inf",
        "-.inf",
        "nan",
        "+nan",
        "-nan",
        ".nan",
    }
)


def raw_numeric_text_is_acceptable(text: str) -> bool:
    """Return True iff *text* matches the narrow raw-numeric edit grammar."""
    candidate = text.strip()
    if not candidate:
        return False
    if _RAW_NUMERIC_EDIT_RE.match(candidate):
        return True
    return candidate.lower() in _RAW_NON_FINITE_SPELLINGS


@dataclass(frozen=True, slots=True)
class RawNumericValue:
    """Raw numeric literal preserved as-is and edited as plain text.

    Attributes:
        raw: The exact original literal text, preserved byte-for-byte.
        reason: One of the ``REASON_*`` codes describing why the literal is
            unsupported as a regular number.
        source_syntax: Optional origin hint (for example ``"json"`` or
            ``"yaml"``) used when deciding cross-format save safety.
        detail: Optional extra context for diagnostics / tooltips.
    """

    raw: str
    reason: str = REASON_UNKNOWN
    source_syntax: str = ""
    detail: str = ""

    def __str__(self) -> str:
        return self.raw

    def describe(self) -> str:
        return describe_reason(self.reason)
