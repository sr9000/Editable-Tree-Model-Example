from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from gmpy2 import mpq

from core.safe_mpq import safe_mpq_from_text
from settings import INFERENCE_MAX_AFFIX_CHARS

_AFFIX_FORBIDDEN_TOUCH_CHARS = set("+-.")
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

    m = _CURRENCY_RE.fullmatch(s)
    if m is not None:
        affix = m.group("affix")
        if not _is_valid_affix(affix, kind=AffixKind.CURRENCY, max_affix_len=max_affix_len):
            return None
        try:
            number = _parse_number(m.group("num"))
        except ValueError:
            return None
        return NumberAffix(
            kind=AffixKind.CURRENCY,
            affix=affix,
            space=(m.group("sp") == " "),
            number=number,
        )

    m = _UNITS_RE.fullmatch(s)
    if m is not None:
        affix = m.group("affix")
        if not _is_valid_affix(affix, kind=AffixKind.UNITS, max_affix_len=max_affix_len):
            return None
        try:
            number = _parse_number(m.group("num"))
        except ValueError:
            return None
        return NumberAffix(
            kind=AffixKind.UNITS,
            affix=affix,
            space=(m.group("sp") == " "),
            number=number,
        )

    return None


def format_number_affix(na: NumberAffix) -> str:
    if not _is_valid_affix(na.affix, kind=na.kind, max_affix_len=len(na.affix)):
        raise ValueError("Invalid affix")

    number_text = str(na.number) if isinstance(na.number, int) else _format_mpq_decimal(na.number)
    gap = " " if na.space else ""

    if na.kind is AffixKind.CURRENCY:
        return f"{na.affix}{gap}{number_text}"
    return f"{number_text}{gap}{na.affix}"


def is_integer_core(na: NumberAffix) -> bool:
    return isinstance(na.number, int)
