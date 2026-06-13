"""Inline editor for raw, unsupported numeric literals.

Editing happens as plain text guarded by a deliberately narrow validator
(:func:`core.raw_numeric.raw_numeric_text_is_acceptable`). The validator never
returns ``Invalid`` so the user can keep typing and can leave the original raw
value unchanged; the model's ``set_data`` makes the final keep / convert /
reject decision.
"""

from PySide6.QtGui import QValidator

from core.raw_numeric import raw_numeric_text_is_acceptable
from editors.inline.caps_safe_line import _CapsLockSafeLineEdit


class RawNumericValidator(QValidator):
    """Accept only the app's narrow raw-numeric recovery grammar."""

    def validate(self, s: str, pos: int):
        if s == "":
            return QValidator.State.Intermediate, s, pos
        if raw_numeric_text_is_acceptable(s):
            return QValidator.State.Acceptable, s, pos
        # Intermediate (never Invalid) so partial input and the unchanged
        # original literal are not blocked at the keystroke level.
        return QValidator.State.Intermediate, s, pos


class RawNumericLineEdit(_CapsLockSafeLineEdit):
    """Plain-text line editor used for ``JsonType.RAW_FLOAT`` values."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setValidator(RawNumericValidator(self))
