from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from gmpy2 import mpq

from core.safe_mpq import safe_mpq_from_text
from settings import INFERENCE_MAX_AFFIX_CHARS

_AFFIX_FORBIDDEN_TOUCH_CHARS = set(".")
_NUMBER_RE = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"

_CURRENCY_RE = re.compile(rf"^(?P<affix>[^\d\s+\-.][^\s]*?)(?P<sp> ?)(?P<num>{_NUMBER_RE})$")
_UNITS_RE = re.compile(rf"^(?P<num>{_NUMBER_RE})(?P<sp> ?)(?P<affix>[^\d\s+\-.eE][^\s]*?)$")


class AffixKind(StrEnum):
    CURRENCY = "prefix"
    UNITS = "suffix"


@dataclass(frozen=True, slots=True)
class NumberAffix:
    kind: AffixKind
    affix: str
    space: bool
    number: int | mpq
    integral_digits: int = 0
    fractional_digits: int = -1
    explicit_plus: bool = False

    def __str__(self) -> str:
        try:
            return format_number_affix(self)
        except ValueError as e:
            return str(e)

    def __repr__(self) -> str:
        try:
            return format_number_affix(self)
        except ValueError as e:
            return str(e)


def _is_valid_affix(affix: str, *, kind: AffixKind, max_affix_len: int) -> bool:
    if not affix or len(affix) > max_affix_len:
        return False
    if any(ch.isspace() for ch in affix):
        return False

    touching = affix[-1] if kind is AffixKind.CURRENCY else affix[0]
    if touching.isdigit() or touching in _AFFIX_FORBIDDEN_TOUCH_CHARS or touching.isspace():
        return False
    return True


def _parse_number(num_text: str) -> int | mpq:
    if re.fullmatch(r"[+-]?\d+", num_text):
        return int(num_text)
    parsed = safe_mpq_from_text(num_text)
    if parsed is None:
        raise ValueError("Unsafe numeric literal")
    return parsed


def _resolve_currency_no_space_boundary(
    affix: str,
    num_text: str,
    *,
    has_space: bool,
    max_affix_len: int,
) -> tuple[str, str] | None:
    """Resolve ambiguous ``prefix-number`` boundaries for no-space currency text.

    Prefix currency syntax has an unavoidable ambiguity for strings like
    ``prod-200``: the ``-`` can be read either as part of the numeric sign or as
    the final character of the affix. This parser treats *spaced* negatives as
    the explicit negative form (``prod -200``) and, for *no-space* forms,
    prefers the affix boundary when that yields a valid currency affix.

    That keeps parsing structurally consistent for hyphenated affixes instead of
    relying on special cases such as zero-padded numbers only.
    """
    if has_space or not num_text.startswith("-"):
        return None

    # Keep single-symbol / punctuation-led currency prefixes on the historical
    # path: ``$-1`` should remain an invalid no-space negative currency form.
    # The ambiguity fix is for textual/hyphenatable affixes such as
    # ``prod-200`` where the dash naturally belongs to the affix token.
    if not affix[-1].isalnum():
        return None

    unsigned = num_text[1:]
    if not re.fullmatch(r"\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?", unsigned):
        return None

    shifted_affix = affix + "-"
    if not _is_valid_affix(shifted_affix, kind=AffixKind.CURRENCY, max_affix_len=max_affix_len):
        return None

    return shifted_affix, unsigned


def _format_mpq_decimal(value: mpq) -> str:
    # Inputs accepted by parse_number_affix are finite base-10 numerals,
    # so this exact decimal conversion is lossless.
    n = int(value.numerator)
    d = int(value.denominator)

    sign = "-" if n < 0 else ""
    n = abs(n)

    twos = 0
    fives = 0
    while d % 2 == 0:
        d //= 2
        twos += 1
    while d % 5 == 0:
        d //= 5
        fives += 1

    if d != 1:
        return str(value)

    scale = max(twos, fives)
    scaled = n * (2 ** (scale - twos)) * (5 ** (scale - fives))
    digits = str(scaled)
    if scale == 0:
        return sign + digits
    if len(digits) <= scale:
        digits = "0" * (scale - len(digits) + 1) + digits
    i = len(digits) - scale
    return f"{sign}{digits[:i]}.{digits[i:]}"


def parse_number_affix(s: str, *, max_affix_len: int = 16, allow_expensive: bool = False) -> NumberAffix | None:
    # Gate expensive regex work for oversized strings during automatic inference.
    # Explicit coercion passes allow_expensive=True to bypass this gate.
    if not allow_expensive and len(s) > INFERENCE_MAX_AFFIX_CHARS:
        return None

    for regex, kind in [(_CURRENCY_RE, AffixKind.CURRENCY), (_UNITS_RE, AffixKind.UNITS)]:
        m = regex.fullmatch(s)
        if m is not None:
            affix = m.group("affix")
            if not _is_valid_affix(affix, kind=kind, max_affix_len=max_affix_len):
                return None
            num_text = m.group("num")

            if kind == AffixKind.CURRENCY:
                resolved = _resolve_currency_no_space_boundary(
                    affix,
                    num_text,
                    has_space=(m.group("sp") == " "),
                    max_affix_len=max_affix_len,
                )
                if resolved is not None:
                    affix, num_text = resolved
                elif m.group("sp") == "" and num_text.startswith("-"):
                    return None

            if not _is_valid_affix(affix, kind=kind, max_affix_len=max_affix_len):
                return None

            try:
                number = _parse_number(num_text)
            except ValueError:
                return None

            digits_str = num_text.lstrip("+-")
            integral_digits = 0
            fractional_digits = -1

            if "." in digits_str or "e" in digits_str.lower():
                parts = digits_str.lower().split("e")[0].split(".")
                int_part = parts[0]
                if int_part.startswith("0") and len(int_part) > 1:
                    integral_digits = len(int_part)
                if len(parts) > 1:
                    frac_part = parts[1]
                    if frac_part.endswith("0"):
                        fractional_digits = len(frac_part)
            else:
                if digits_str.startswith("0") and len(digits_str) > 1:
                    integral_digits = len(digits_str)

            return NumberAffix(
                kind=kind,
                affix=affix,
                space=(m.group("sp") == " "),
                number=number,
                integral_digits=integral_digits,
                fractional_digits=fractional_digits,
                explicit_plus=num_text.startswith("+"),
            )

    return None


def format_number_affix(na: NumberAffix) -> str:
    if not _is_valid_affix(na.affix, kind=na.kind, max_affix_len=len(na.affix)):
        raise ValueError("Invalid affix")

    if isinstance(na.number, int):
        number_text = str(na.number)
        if na.integral_digits > 0:
            if na.number < 0:
                number_text = "-" + number_text[1:].zfill(na.integral_digits)
            else:
                number_text = number_text.zfill(na.integral_digits)
    else:
        number_text = _format_mpq_decimal(na.number)
        parts = number_text.split(".")
        int_part = parts[0]
        frac_part = parts[1] if len(parts) > 1 else ""

        if na.integral_digits > 0:
            sign = "-" if int_part.startswith("-") else ""
            digits = int_part.lstrip("+-")
            if len(digits) < na.integral_digits:
                int_part = sign + digits.zfill(na.integral_digits)

        if na.fractional_digits >= 0:
            if len(frac_part) < na.fractional_digits:
                frac_part = frac_part.ljust(na.fractional_digits, "0")

        if na.fractional_digits >= 0 or frac_part:
            if not frac_part and na.fractional_digits > 0:
                frac_part = "0" * na.fractional_digits
            if frac_part:
                number_text = f"{int_part}.{frac_part}"
            else:
                number_text = int_part
        else:
            number_text = int_part

    if na.explicit_plus and na.number >= 0 and not number_text.startswith(("+", "-")):
        number_text = "+" + number_text

    gap = " " if na.space else ""

    if na.kind is AffixKind.CURRENCY:
        return f"{na.affix}{gap}{number_text}"
    return f"{number_text}{gap}{na.affix}"


def is_integer_core(na: NumberAffix) -> bool:
    return isinstance(na.number, int)
