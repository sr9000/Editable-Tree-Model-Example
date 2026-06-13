from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    MAX_EMAX,
    MIN_EMIN,
    Context,
    Decimal,
    Inexact,
    InvalidOperation,
    Overflow,
    Underflow,
)
from typing import Any

from gmpy2 import mpq

from core.raw_numeric import (
    REASON_INVALID_FORMAT,
    REASON_NON_FINITE,
    REASON_OVERFLOW,
    REASON_PARSER_REJECTION,
    REASON_PRECISION_LIMIT,
    REASON_UNDERFLOW,
)
from settings import MPQ_SAFE_MAX_ABS_EXPONENT, MPQ_SAFE_MAX_SIG_DIGITS

# Special float spellings that are syntactically "numbers" but are not finite.
# These are classified as non-finite rather than overflow/format errors so the
# UI can explain the cause precisely.
_NON_FINITE_LITERALS = frozenset(
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
        "snan",
        "+snan",
        "-snan",
    }
)


@dataclass(frozen=True, slots=True)
class MpqParseResult:
    """Outcome of safe numeric parsing.

    ``value`` is a finite ``mpq`` on success and ``None`` on rejection. When
    ``value`` is ``None``, ``reason`` carries a ``core.raw_numeric.REASON_*``
    code explaining why the literal is unsupported as a regular number.
    """

    value: mpq | None
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.value is not None


def _normalize_numeric_text(text: str) -> str:
    return text.replace("_", "").strip()


def _is_non_finite_literal(candidate: str) -> bool:
    return candidate.lower() in _NON_FINITE_LITERALS


def _safe_decimal_context(
    *,
    max_abs_exponent: int,
    max_sig_digits: int,
) -> Context:
    ctx = Context(
        prec=max_sig_digits,
        Emax=max_abs_exponent,
        Emin=-max_abs_exponent,
    )
    ctx.traps[Overflow] = True
    ctx.traps[Underflow] = True
    ctx.traps[InvalidOperation] = True
    ctx.traps[Inexact] = True
    return ctx


def _classification_context(*, max_sig_digits: int) -> Context:
    """A trap-free context with the widest possible exponent range.

    Used only to classify a literal (format / non-finite / order of magnitude)
    before the strict, trapping context makes the final exact decision.
    """
    return Context(prec=max(1, max_sig_digits), Emax=MAX_EMAX, Emin=MIN_EMIN)


def safe_decimal_from_text(
    text: str,
    *,
    max_abs_exponent: int = MPQ_SAFE_MAX_ABS_EXPONENT,
    max_sig_digits: int = MPQ_SAFE_MAX_SIG_DIGITS,
) -> Decimal | None:
    candidate = _normalize_numeric_text(text)
    if not candidate:
        return None

    ctx = _safe_decimal_context(
        max_abs_exponent=max_abs_exponent,
        max_sig_digits=max_sig_digits,
    )
    try:
        parsed = ctx.create_decimal(candidate)
    except (InvalidOperation, Overflow, Underflow, Inexact):
        return None

    if not parsed.is_finite():
        return None
    return parsed


def _safe_int_from_text(
    text: str,
    *,
    max_abs_exponent: int = MPQ_SAFE_MAX_ABS_EXPONENT,
    max_sig_digits: int = MPQ_SAFE_MAX_SIG_DIGITS,
) -> int | None:
    candidate = _normalize_numeric_text(text)
    if not candidate:
        return None

    body = candidate.lstrip("+-")
    if not body or not body.isdigit():
        return None

    parsed = safe_decimal_from_text(
        candidate,
        max_abs_exponent=max_abs_exponent,
        max_sig_digits=max_sig_digits,
    )
    if parsed is None:
        return None

    numerator, denominator = parsed.as_integer_ratio()
    if denominator != 1:
        return None
    return numerator


def _parse_rational(
    candidate: str,
    *,
    max_abs_exponent: int,
    max_sig_digits: int,
) -> MpqParseResult:
    numerator_text, sep, denominator_text = candidate.partition("/")
    if sep != "/" or "/" in denominator_text:
        return MpqParseResult(None, REASON_INVALID_FORMAT)

    numerator = _safe_int_from_text(
        numerator_text,
        max_abs_exponent=max_abs_exponent,
        max_sig_digits=max_sig_digits,
    )
    denominator = _safe_int_from_text(
        denominator_text,
        max_abs_exponent=max_abs_exponent,
        max_sig_digits=max_sig_digits,
    )
    if numerator is None or denominator is None or denominator == 0:
        return MpqParseResult(None, REASON_INVALID_FORMAT)
    try:
        return MpqParseResult(mpq(numerator, denominator), None)
    except (TypeError, ValueError, ZeroDivisionError):
        return MpqParseResult(None, REASON_PARSER_REJECTION)


def _parse_decimal(
    candidate: str,
    *,
    max_abs_exponent: int,
    max_sig_digits: int,
) -> MpqParseResult:
    # 0) Non-finite spellings (including YAML forms such as ``.inf`` / ``.nan``
    #    that ``Decimal`` itself does not accept) are classified up-front.
    if _is_non_finite_literal(candidate):
        return MpqParseResult(None, REASON_NON_FINITE)

    # 1) Classification pass (no traps): identify format errors, non-finite
    #    values, and order of magnitude so overflow / underflow are reported
    #    precisely.
    probe_ctx = _classification_context(max_sig_digits=max_sig_digits)
    try:
        probe = probe_ctx.create_decimal(candidate)
    except InvalidOperation:
        return MpqParseResult(None, REASON_INVALID_FORMAT)
    except Overflow:  # pragma: no cover - traps are off; defensive only
        return MpqParseResult(None, REASON_OVERFLOW)

    if not probe.is_finite():
        if _is_non_finite_literal(candidate):
            return MpqParseResult(None, REASON_NON_FINITE)
        # Overflowed all the way to infinity during classification.
        return MpqParseResult(None, REASON_OVERFLOW)

    if probe != 0:
        adjusted = probe.adjusted()
        if adjusted > max_abs_exponent:
            return MpqParseResult(None, REASON_OVERFLOW)
        if adjusted < -max_abs_exponent:
            return MpqParseResult(None, REASON_UNDERFLOW)

    # 2) Strict pass (traps on): enforce exact precision within bounds.
    strict_ctx = _safe_decimal_context(
        max_abs_exponent=max_abs_exponent,
        max_sig_digits=max_sig_digits,
    )
    try:
        parsed = strict_ctx.create_decimal(candidate)
    except Overflow:
        return MpqParseResult(None, REASON_OVERFLOW)
    except Underflow:
        return MpqParseResult(None, REASON_UNDERFLOW)
    except Inexact:
        return MpqParseResult(None, REASON_PRECISION_LIMIT)
    except InvalidOperation:
        return MpqParseResult(None, REASON_INVALID_FORMAT)

    if not parsed.is_finite():
        return MpqParseResult(None, REASON_NON_FINITE)

    numerator, denominator = parsed.as_integer_ratio()
    try:
        return MpqParseResult(mpq(numerator, denominator), None)
    except (TypeError, ValueError, ZeroDivisionError):
        return MpqParseResult(None, REASON_PARSER_REJECTION)


def parse_mpq(
    text: str,
    *,
    max_abs_exponent: int = MPQ_SAFE_MAX_ABS_EXPONENT,
    max_sig_digits: int = MPQ_SAFE_MAX_SIG_DIGITS,
) -> MpqParseResult:
    """Parse *text* into a finite ``mpq``, preserving the rejection cause.

    Returns an :class:`MpqParseResult` whose ``value`` is an ``mpq`` on success
    or ``None`` with a ``reason`` code on rejection.
    """
    candidate = _normalize_numeric_text(text)
    if not candidate:
        return MpqParseResult(None, REASON_INVALID_FORMAT)

    if "/" in candidate:
        return _parse_rational(
            candidate,
            max_abs_exponent=max_abs_exponent,
            max_sig_digits=max_sig_digits,
        )

    return _parse_decimal(
        candidate,
        max_abs_exponent=max_abs_exponent,
        max_sig_digits=max_sig_digits,
    )


def safe_mpq_from_text(
    text: str,
    *,
    max_abs_exponent: int = MPQ_SAFE_MAX_ABS_EXPONENT,
    max_sig_digits: int = MPQ_SAFE_MAX_SIG_DIGITS,
) -> mpq | None:
    return parse_mpq(
        text,
        max_abs_exponent=max_abs_exponent,
        max_sig_digits=max_sig_digits,
    ).value


def mpq_literal_is_safe(
    text: str,
    *,
    max_abs_exponent: int = MPQ_SAFE_MAX_ABS_EXPONENT,
    max_sig_digits: int = MPQ_SAFE_MAX_SIG_DIGITS,
) -> bool:
    return (
        safe_mpq_from_text(
            text,
            max_abs_exponent=max_abs_exponent,
            max_sig_digits=max_sig_digits,
        )
        is not None
    )


def safe_mpq_from_any(value: Any) -> mpq | None:
    if isinstance(value, mpq):
        return value
    if value is None or isinstance(value, bool):
        return None
    return safe_mpq_from_text(str(value))
