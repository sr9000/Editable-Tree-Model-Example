"""Shared helper for drawing validation severity with QTextCharFormat."""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import (QColor, QFontMetrics, QPainter, QPalette,
                           QTextCharFormat, QTextLayout, QTextOption)
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionViewItem

from themes.spec import ThemeSpec

# Hard-coded fallbacks used when the theme palette has no explicit badge color.
_FALLBACK_ERROR = QColor("#d13438")
_FALLBACK_WARNING = QColor("#bf6900")


def draw_severity_badge(
    painter: QPainter,
    option: QStyleOptionViewItem,
    severity: str | None,
    theme: ThemeSpec,
) -> None:
    """Draw the item text with a severity-coloured wave underline.

    Does nothing when *severity* is ``None`` or unrecognised.

    Call this instead of ``super().paint(...)`` for severity-marked rows. It
    lets the style paint the item background/decoration with an empty text,
    then paints the text once via ``QTextLayout`` using ``QTextCharFormat``.
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

    style = option.widget.style() if option.widget is not None else QApplication.style()

    text = option.text
    background_option = QStyleOptionViewItem(option)
    background_option.text = ""
    style.drawControl(QStyle.ControlElement.CE_ItemViewItem, background_option, painter, option.widget)
    if not text:
        return

    # Use the style's text sub-rect so the wave sits under the text, not the whole cell.
    text_rect = style.subElementRect(QStyle.SubElement.SE_ItemViewItemText, option, option.widget)
    if text_rect.isEmpty():
        text_rect = option.rect  # fallback to full cell
    if text_rect.width() <= 0 or text_rect.height() <= 0:
        return

    metrics = QFontMetrics(option.font)
    elided = metrics.elidedText(text, option.textElideMode, text_rect.width())

    fmt = QTextCharFormat()
    fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
    fmt.setUnderlineColor(color)
    fg_role = (
        QPalette.ColorRole.HighlightedText
        if option.state & QStyle.StateFlag.State_Selected
        else QPalette.ColorRole.Text
    )
    fmt.setForeground(option.palette.brush(fg_role))

    fmt_range = QTextLayout.FormatRange()
    fmt_range.start = 0
    fmt_range.length = len(elided)
    fmt_range.format = fmt

    text_option = QTextOption()
    text_option.setWrapMode(QTextOption.WrapMode.NoWrap)
    text_option.setAlignment(option.displayAlignment or Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

    layout = QTextLayout(elided, option.font)
    layout.setTextOption(text_option)
    layout.setFormats([fmt_range])
    layout.beginLayout()
    line = layout.createLine()
    line.setLineWidth(text_rect.width())
    line.setPosition(QPointF(0, 0))
    layout.endLayout()

    y = text_rect.top() + (text_rect.height() - line.height()) / 2.0

    painter.save()
    try:
        painter.setClipRect(text_rect)
        layout.draw(painter, QPointF(text_rect.left(), y))
    finally:
        painter.restore()
