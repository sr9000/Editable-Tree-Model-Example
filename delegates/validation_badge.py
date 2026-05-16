"""Shared helper for drawing a wavy-underline severity indicator on cell text."""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem

from themes.spec import ThemeSpec

# Hard-coded fallbacks used when the theme palette has no explicit badge color.
_FALLBACK_ERROR = QColor("#d13438")
_FALLBACK_WARNING = QColor("#bf6900")

_WAVE_AMPLITUDE = 1.5   # px  half peak-to-trough
_WAVE_LENGTH = 6        # px  full period
_LINE_WIDTH = 1.5       # px  pen width


def draw_severity_badge(
    painter: QPainter,
    option: QStyleOptionViewItem,
    severity: str | None,
    theme: ThemeSpec,
) -> None:
    """Draw a wavy underline beneath the cell text for *severity*.

    Does nothing when *severity* is ``None`` or unrecognised.
    """
    if severity is None:
        return

    vs = theme.palette.validation
    if severity == "error":
        color = vs.error_badge or _FALLBACK_ERROR
    elif severity == "warning":
        color = vs.warning_badge or _FALLBACK_WARNING
    else:
        return

    # Use the style's text sub-rect so the wave sits under the text, not the whole cell.
    style = QApplication.style()
    text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, option.widget)
    if text_rect.isEmpty():
        text_rect = option.rect  # fallback to full cell

    baseline_y = float(text_rect.bottom()) - 2.0
    x_start = float(text_rect.left()) + 1.0
    x_end = float(text_rect.right()) - 1.0
    if x_end <= x_start:
        return

    path = QPainterPath()
    path.moveTo(x_start, baseline_y)
    x = x_start
    up = True
    while x < x_end:
        x_next = min(x + _WAVE_LENGTH / 2.0, x_end)
        x_mid = (x + x_next) / 2.0
        cy = baseline_y - (_WAVE_AMPLITUDE * 2.0 if up else _WAVE_AMPLITUDE * -2.0)
        path.quadTo(QPointF(x_mid, cy), QPointF(x_next, baseline_y))
        x = x_next
        up = not up

    pen = QPen(color)
    pen.setWidthF(_LINE_WIDTH)

    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(pen)
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawPath(path)
    finally:
        painter.restore()
