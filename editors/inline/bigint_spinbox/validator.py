from PySide6.QtGui import QValidator

from coalesce import nn


def in_range(low: int | None, value: int, high: int | None) -> bool:
    return (nn[low, value] <= value) and (value <= nn[high, value])


class BigIntValidator(QValidator):
    """
    Validator for QBigIntSpinBox using arbitrary-precision Python ints.

    Behavior:
     - Produces Acceptable, Intermediate, or Invalid.
     - Empty input -> Intermediate.
     - Plain integer without prefix/suffix:
       * in range -> Acceptable (text becomes prefix+number+suffix, cursor advances by len(prefix))
       * out of range -> Intermediate
       * "-" only -> Intermediate
     - With correct prefix/suffix:
       * inner empty or "-" -> Intermediate
       * inner number in range -> Acceptable (text/cursor unchanged)
       * inner number out of range -> Intermediate
     - Otherwise -> Invalid.

    Both minimum and maximum, when set, are enforced.
    """

    def __init__(self, spinbox: "QBigIntSpinBox"):
        super().__init__(spinbox)
        self._sb = spinbox

    def validate(self, s: str, pos: int):
        prefix = self._sb.prefix()
        suffix = self._sb.suffix()

        # empty input is a valid partial
        if s.strip() in ("", "-"):
            return QValidator.State.Intermediate, s, pos

        maxv = self._sb.maximum()  # int|None
        minv = self._sb.minimum()

        # 1) plain number (no prefix/suffix present in the string)
        try:
            n = int(s)
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

        # 2) with prefix/suffix
        if prefix and not s.startswith(prefix):
            return QValidator.State.Invalid, s, pos
        if suffix and not s.endswith(suffix):
            return QValidator.State.Invalid, s, pos

        number = s[(len(prefix)) : -len(suffix) or None]

        # 2a) inner value empty or just '-' -> partial
        if number.strip() in ("", "-"):
            return QValidator.State.Intermediate, s, pos

        # 2b) inner value is a number
        try:
            n = int(number)
            if in_range(minv, n, maxv):
                return QValidator.State.Acceptable, s, pos
            else:
                return QValidator.State.Intermediate, s, pos
        except ValueError:
            pass

        return QValidator.State.Invalid, s, pos
