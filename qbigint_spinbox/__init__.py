from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QValidator
from PySide6.QtWidgets import QAbstractSpinBox


def in_range(low: int | None, value: int, high: int | None) -> bool:
    return (low is None or value >= low) and (high is None or value <= high)


class BigIntValidator(QValidator):
    """
    Validator for QBigIntSpinBox using arbitrary-precision Python ints.

    Behavior:
     - Produces only QValidator.State.Acceptable or QValidator.State.Invalid (no Intermediate).
     - Empty input -> Acceptable; returned text is prefix+suffix and cursor advances by len(prefix).
     - Plain integer without prefix/suffix -> Acceptable iff it is within [minimum, maximum] (each bound may be None);
       on success, returned text is prefix+number+suffix and cursor advances by len(prefix).
     - Input with correct prefix/suffix -> Acceptable iff the inner number is empty or within the same bounds;
       text and cursor are left unchanged.
     - Otherwise -> Invalid.

    Both minimum and maximum, when set, are enforced.
    """

    def __init__(self, spinbox: "QBigIntSpinBox"):
        super().__init__(spinbox)
        self._sb = spinbox

    def validate(self, s: str, pos: int):
        prefix = self._sb.prefix()
        suffix = self._sb.suffix()

        # 0. given value are empty
        if s == "":
            return QValidator.State.Acceptable, prefix + suffix, pos + len(prefix)

        maxv = self._sb.maximum()  # int|None
        minv = self._sb.minimum()

        # 1. plain number (no prefix/suffix)
        try:
            if in_range(minv, int(s), maxv):
                return (
                    QValidator.State.Acceptable,
                    prefix + s + suffix,
                    pos + len(prefix),
                )
        except ValueError:
            pass

        # 2. with prefix/suffix
        if prefix and not s.startswith(prefix):
            return QValidator.State.Invalid, s, pos

        if suffix and not s.endswith(suffix):
            return QValidator.State.Invalid, s, pos

        number = s[len(prefix) : -len(suffix)]

        # 2a. value is empty
        if number == "":
            return QValidator.State.Acceptable, s, pos

        # 2b. value is a number
        try:
            if in_range(minv, int(number), maxv):
                return QValidator.State.Acceptable, s, pos
        except ValueError:
            pass

        # 3. validation did not pass
        return QValidator.State.Invalid, s, pos


class QBigIntSpinBox(QAbstractSpinBox):
    """
    Simplified big-int spinbox:
    - Uses Python's arbitrary-precision int.
    - Optional min/max (None = unbounded).
    - Prefix/suffix, wrapping, commit on Enter/focus-out, identical stepping behavior.
    """

    def __init__(
        self,
        parent=None,
        value=0,
        /,
        minimum=None,
        maximum=None,
        single_step=1,
        prefix="",
        suffix="",
    ):
        super().__init__(parent)
        self._minimum: int | None = minimum
        self._maximum: int | None = maximum
        self._value: int = value
        self._single_step: int = single_step
        self._prefix: str = prefix
        self._suffix: str = suffix

        self.lineEdit().setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._validator = BigIntValidator(self)
        self.lineEdit().setValidator(self._validator)

        self.setValue(self._value)

    # Core value API
    def value(self) -> int:
        return self._value

    def setValue(self, expectedNewValue: int):
        newValue = self._clamp(int(expectedNewValue))
        newValueString = str(newValue)

        # Always update text (matches C++ approach)
        self.lineEdit().setText(self._prefix + newValueString + self._suffix)
        if self._value != newValue:
            self._value = newValue

    def cleanText(self) -> str:
        return str(self._value)

    # Prefix/Suffix
    def prefix(self) -> str:
        return self._prefix

    def setPrefix(self, prefix: str):
        self._prefix = prefix or ""
        self.setValue(self._value)

    def suffix(self) -> str:
        return self._suffix

    def setSuffix(self, suffix: str):
        self._suffix = suffix or ""
        self.setValue(self._value)

    # Step
    def singleStep(self) -> int:
        return self._single_step

    def setSingleStep(self, step: int):
        self._single_step = max(1, int(step))

    # Range (None = unbounded)
    def minimum(self) -> int | None:
        return self._minimum

    def setMinimum(self, minv: int | None):
        self._minimum = minv

        if self._maximum is not None:
            self._maximum = max(self._maximum, self._maximum or self._minimum)

        self.setValue(self._value)

    def maximum(self) -> int | None:
        return self._maximum

    def setMaximum(self, maxv: int | None):
        self._maximum = maxv

        if self._minimum is not None:
            self._minimum = min(self._minimum, self._minimum or self._maximum)

        self.setValue(self._value)

    def setRange(self, minv: int | None, maxv: int | None):
        # Handle None bounds; if both ints and min > max, swap
        if minv is not None and maxv is not None and minv > maxv:
            minv, maxv = maxv, minv

        self._minimum = minv
        self._maximum = maxv

        self.setValue(self._value)

    # Events/behavior
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.selectCleanText()
            self.lineEditEditingFinalize()
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent):
        self.lineEditEditingFinalize()
        super().focusOutEvent(event)

    def stepEnabled(self):
        if self.isReadOnly():
            return QAbstractSpinBox.StepEnabledFlag(0)

        Flags = QAbstractSpinBox.StepEnabledFlag
        se = Flags(0)
        if self.wrapping() or (self._maximum is None or self._value < self._maximum):
            se |= Flags.StepUpEnabled
        if self.wrapping() or (self._minimum is None or self._value > self._minimum):
            se |= Flags.StepDownEnabled
        return se

    def stepBy(self, steps: int):
        if self.isReadOnly():
            return

        if (self._prefix + str(self._value) + self._suffix) != self.lineEdit().text():
            self.lineEditEditingFinalize()

        newValue = self._value + steps * self._single_step

        if self.wrapping() and self._minimum is not None and self._maximum is not None:
            # Emulate the same wrap nuances as the C++ code
            if newValue > self._maximum:
                if self._value == self._maximum:
                    newValue = self._minimum
                else:
                    newValue = self._maximum
            elif newValue < self._minimum:
                if self._value == self._minimum:
                    newValue = self._maximum
                else:
                    newValue = self._minimum
        else:
            newValue = self._clamp(newValue)

        self.setValue(newValue)
        self.selectCleanText()

    # Helpers
    def _clamp(self, v: int) -> int:
        return min(self._maximum or v, max(self._minimum or v, v))

    def lineEditEditingFinalize(self):
        text = self.lineEdit().text()

        # 1) Try as plain number
        try:
            self.setValue(int(text))
            return
        except ValueError:
            pass

        # 2) Try number with prefix/suffix
        if text.startswith(self._prefix) and text.endswith(self._suffix):
            number = text[(len(self._prefix)) : -len(self._suffix)]
            try:
                self.setValue(int(number))
                return
            except ValueError:
                pass

        # 3) Revert
        self.setValue(self._value)

    def selectCleanText(self):
        le = self.lineEdit()
        extra_length = len(self._prefix) + len(self._suffix)
        length = max(0, len(le.text()) - extra_length)
        le.setSelection(len(self._prefix), length)
