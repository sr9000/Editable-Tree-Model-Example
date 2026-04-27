from __future__ import annotations

from PySide6.QtGui import QColor


def _to_linear(channel: int) -> float:
    value = channel / 255.0
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(color: QColor) -> float:
    return 0.2126 * _to_linear(color.red()) + 0.7152 * _to_linear(color.green()) + 0.0722 * _to_linear(color.blue())


def contrast_ratio(a: QColor, b: QColor) -> float:
    l1 = relative_luminance(a)
    l2 = relative_luminance(b)
    bright, dark = (l1, l2) if l1 >= l2 else (l2, l1)
    return (bright + 0.05) / (dark + 0.05)
