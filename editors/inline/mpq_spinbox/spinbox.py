from gmpy2 import mpq
from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import QAbstractSpinBox

from coalesce import nn
from core.safe_mpq import safe_mpq_from_text
from editors.inline.mpq_spinbox.validator import MpqValidator, _to_mpq
from mpq2py import mpq_serialization


class QMpqSpinBox(QAbstractSpinBox):
    """
    Big-rational spinbox built on gmpy2.mpq.

    - Uses exact rationals internally (mpq).
    - Optional min/max (None = unbounded).
    - Prefix/suffix, wrapping, commit on Enter/focus-out, identical stepping behavior.
    - Displays using mpq_serialization(value).
    """

    def __init__(
        self,
        parent=None,
        value=mpq(0),
        /,
        minimum: mpq = None,
        maximum: mpq = None,
        single_step: mpq = None,
        prefix: str = "",
        suffix: str = "",
    ):
        super().__init__(parent)

        if single_step is None:
            single_step = mpq_serialization(_to_mpq(value))[1] / 10

        self._minimum: mpq | None = minimum
        self._maximum: mpq | None = maximum
        self._value: mpq = _to_mpq(value)
        self._single_step: mpq = max(mpq(0), _to_mpq(single_step)) or mpq(1)

        self._prefix: str = prefix
        self._suffix: str = suffix

        self.lineEdit().setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._validator = MpqValidator(self)
        self.lineEdit().setValidator(self._validator)

        self.setValue(self._value)

    # Core value API
    def value(self) -> mpq:
        return self._value

    def setValue(self, expectedNewValue: mpq) -> None:
        new_value = self._clamp(_to_mpq(expectedNewValue))
        new_value_string = str(mpq_serialization(new_value)[0])

        # Always update text (matches C++ approach)
        self.lineEdit().setText(self._prefix + new_value_string + self._suffix)
        if self._value != new_value:
            self._value = new_value

    def cleanText(self) -> str:
        return str(mpq_serialization(self._value)[0])

    # Prefix/Suffix
    def prefix(self) -> str:
        return self._prefix

    def setPrefix(self, prefix: str):
        self._prefix = prefix
        self.setValue(self._value)

    def suffix(self) -> str:
        return self._suffix

    def setSuffix(self, suffix: str):
        self._suffix = suffix
        self.setValue(self._value)

    # Step
    def singleStep(self) -> mpq:
        return self._single_step

    def setSingleStep(self, step: mpq):
        self._single_step = max(mpq(0), _to_mpq(step)) or mpq(1)

    # Range (None = unbounded)
    def minimum(self) -> mpq | None:
        return self._minimum

    def setMinimum(self, minv: mpq | None):
        self._minimum = minv

        if self._maximum is not None:
            self._maximum = max(self._maximum, self._maximum or self._minimum)

        self.setValue(self._value)

    def maximum(self) -> mpq | None:
        return self._maximum

    def setMaximum(self, maxv: mpq | None):
        self._maximum = maxv

        if self._minimum is not None:
            self._minimum = min(self._minimum, self._minimum or self._maximum)

        self.setValue(self._value)

    def setRange(self, minv: mpq | None, maxv: mpq | None):
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

        if (self._prefix + str(mpq_serialization(self._value)[0]) + self._suffix) != self.lineEdit().text():
            self.lineEditEditingFinalize()

        newValue = self._value + mpq(steps) * self._single_step

        if self.wrapping() and self._minimum is not None and self._maximum is not None:
            # Emulate wrap nuances similar to your bigint version
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
    def _clamp(self, v: mpq) -> mpq:
        return min(nn[self._maximum, v], max(nn[self._minimum, v], v))

    def lineEditEditingFinalize(self):
        text = self.lineEdit().text()

        # 1) Try as plain number
        parsed = safe_mpq_from_text(text)
        if parsed is not None:
            self.setValue(parsed)
            return

        # 2) Try number with prefix/suffix
        if text.startswith(self._prefix) and text.endswith(self._suffix):
            number = text[(len(self._prefix)) : -len(self._suffix) or None]
            parsed = safe_mpq_from_text(number)
            if parsed is not None:
                self.setValue(parsed)
                return

        # 3) Revert
        self.setValue(self._value)

    def selectCleanText(self):
        le = self.lineEdit()
        extra_length = len(self._prefix) + len(self._suffix)
        length = max(0, len(le.text()) - extra_length)
        le.setSelection(len(self._prefix), length)
