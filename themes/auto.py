from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from app.runtime_compat import system_color_scheme


def detect_system_mode(app: QGuiApplication) -> Literal["light", "dark"]:
    hints = app.styleHints()
    color_scheme = system_color_scheme(hints)
    if color_scheme == Qt.ColorScheme.Dark:
        return "dark"
    if color_scheme == Qt.ColorScheme.Light:
        return "light"

    window_color = app.palette().window().color()
    return "light" if window_color.lightness() >= 128 else "dark"
