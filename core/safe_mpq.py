from __future__ import annotations

from decimal import Context, Decimal, Inexact, InvalidOperation, Overflow, Underflow
from typing import Any

from gmpy2 import mpq

from settings import MPQ_SAFE_MAX_ABS_EXPONENT, MPQ_SAFE_MAX_SIG_DIGITS


def _normalize_numeric_text(text: str) -> str:
    return text.replace("_", "").strip()


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


def safe_mpq_from_text(
    text: str,
    *,
    max_abs_exponent: int = MPQ_SAFE_MAX_ABS_EXPONENT,
    max_sig_digits: int = MPQ_SAFE_MAX_SIG_DIGITS,
) -> mpq | None:
    candidate = _normalize_numeric_text(text)
    if not candidate:
        return None

    if "/" in candidate:
        numerator_text, sep, denominator_text = candidate.partition("/")
        if sep != "/" or "/" in denominator_text:
            return None
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
            return None
        try:
            return mpq(numerator, denominator)
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    parsed = safe_decimal_from_text(
        candidate,
        max_abs_exponent=max_abs_exponent,
        max_sig_digits=max_sig_digits,
    )
    if parsed is None:
        return None

    numerator, denominator = parsed.as_integer_ratio()
    try:
        return mpq(numerator, denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def safe_mpq_from_any(value: Any) -> mpq | None:
    if isinstance(value, mpq):
        return value
    if value is None or isinstance(value, bool):
        return None
    return safe_mpq_from_text(str(value))
