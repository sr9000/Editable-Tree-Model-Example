import re
from decimal import Decimal
from typing import Tuple

from gmpy2 import mpq
from PySide6.QtGui import QValidator

from coalesce import nn

PARTIAL_FLOAT = re.compile(r"[-+]?\d*\.?\d*e?[-+]?\d*", re.IGNORECASE)


def in_range(low: mpq | None, value: mpq, high: mpq | None) -> bool:
    return (nn[low, value] <= value) and (value <= nn[high, value])


def _to_mpq(x) -> mpq:
    if isinstance(x, mpq):
        return x
    if isinstance(x, Decimal):
        return mpq(str(x))  # avoid binary float artifacts

    return mpq(x)


class MpqValidator(QValidator):
    """
    Validator for QMpqSpinBox.

    Behavior:
     - Produces Acceptable, Intermediate, or Invalid.
     - Empty/partial inputs (e.g. "", "-", ".", "1.", "12/", "12/-", "1e", "1e+") -> Intermediate.
     - Plain number (int/decimal/scientific) or "a/b" (int over int):
       * in range -> Acceptable (text becomes prefix+number+suffix, cursor advances by len(prefix))
       * out of range -> Intermediate
     - With correct prefix/suffix:
       * inner empty or partial -> Intermediate
       * inner parses to mpq in range -> Acceptable (text/cursor unchanged)
       * inner parses to mpq out of range -> Intermediate
     - Otherwise -> Invalid.
    """

    def __init__(self, spinbox: "QMpqSpinBox"):
        super().__init__(spinbox)
        self._sb = spinbox

    def validate(self, s: str, pos: int) -> Tuple[QValidator.State, str, int]:
        prefix = self._sb.prefix()
        suffix = self._sb.suffix()

        maxv = self._sb.maximum()  # mpq|None
        minv = self._sb.minimum()

        if PARTIAL_FLOAT.fullmatch(s):
            try:
                float(s)
            except ValueError:
                return QValidator.State.Intermediate, s, pos

            # 1) Try as plain number (no requirement to already contain prefix/suffix)
            try:
                n = mpq(s)
                if in_range(minv, n, maxv):
                    return (
                        QValidator.State.Acceptable,
                        prefix + s + suffix,
                        pos + len(prefix),
                    )
                else:
                    return QValidator.State.Intermediate, s, pos
            except ValueError:
                pass

        # 2) With prefix/suffix
        if prefix and not s.startswith(prefix):
            return QValidator.State.Invalid, s, pos
        if suffix and not s.endswith(suffix):
            return QValidator.State.Invalid, s, pos

        number = s[len(prefix) : -len(suffix) or None]

        if PARTIAL_FLOAT.fullmatch(number):
            try:
                float(number)
            except ValueError:
                return QValidator.State.Intermediate, s, pos

            try:
                n = mpq(number)
                if in_range(minv, n, maxv):
                    return QValidator.State.Acceptable, s, pos
                else:
                    return QValidator.State.Intermediate, s, pos
            except ValueError:
                pass

        return QValidator.State.Invalid, s, pos
