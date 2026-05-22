from __future__ import annotations

import math

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics, QPainter
from PySide6.QtWidgets import QPlainTextEdit, QPushButton, QWidget


class LineNumberArea(QWidget):
    def __init__(self, editor: "QMultilineEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):  # type: ignore[override]
        self._editor.line_number_area_paint_event(event)


class _SensitiveCover(QWidget):
    """Opaque overlay that tiles a diagonal 'Hidden' label over secret content."""

    _HIDDEN_TEXT = "Hidden"
    _ROTATION_DEG = -30.0

    def __init__(self, editor: "QMultilineEditor") -> None:
        super().__init__(editor)
        self._editor = editor
        # Block interactions with the underlying viewport.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ForbiddenCursor)

    def paintEvent(self, event):  # type: ignore[override]
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().base())

        font = QFont(self._editor.font())
        font.setBold(True)
        metrics = QFontMetrics(font)
        painter.setFont(font)

        # Subtle, theme-aware color.
        pen_color = self.palette().mid().color()
        pen_color.setAlpha(180)
        painter.setPen(pen_color)

        text = self._HIDDEN_TEXT
        step_x = metrics.horizontalAdvance(text) + 24
        step_y = metrics.height() + 12

        diag = math.hypot(max(1, self.width()), max(1, self.height()))
        n_x = int(diag // step_x) + 2
        n_y = int(diag // step_y) + 2

        painter.translate(self.width() / 2.0, self.height() / 2.0)
        painter.rotate(self._ROTATION_DEG)

        for iy in range(-n_y, n_y + 1):
            for ix in range(-n_x, n_x + 1):
                painter.drawText(ix * step_x, iy * step_y, text)


class QMultilineEditor(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._lineNumbersWidget = LineNumberArea(self)
        self._defaultFont = QFont(self.font())
        self._monospacedFont = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._isMonospaced = False

        # Sensitive mode (off by default).
        self._sensitive: bool = False
        self._revealed: bool = False
        self._cover: _SensitiveCover | None = None
        self._reveal_button: QPushButton | None = None

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)

        # Better defaults for multi-line editing
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance("9"))
        self.setWordWrap(True)
        self.setLineNumbersVisible(True)

    # Public API
    def setLineNumbersVisible(self, is_visible: bool) -> None:
        self._lineNumbersWidget.setHidden(not is_visible)
        self._update_line_number_area_width()

    def lineNumbersVisible(self) -> bool:
        return not self._lineNumbersWidget.isHidden()

    def setWordWrap(self, enabled: bool) -> None:
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if enabled else QPlainTextEdit.LineWrapMode.NoWrap)

    def wordWrap(self) -> bool:
        return self.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth

    def setMonospaced(self, enabled: bool) -> None:
        self._isMonospaced = enabled
        self.setFont(self._monospacedFont if enabled else self._defaultFont)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance("9"))

    def setRegularFontFamily(self, family: str) -> None:
        if not family:
            return
        self._defaultFont.setFamily(str(family))
        if not self._isMonospaced:
            self.setFont(self._defaultFont)
            self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance("9"))

    def setMonospaceFontFamily(self, family: str) -> None:
        if not family:
            return
        self._monospacedFont.setFamily(str(family))
        self._monospacedFont.setStyleHint(QFont.StyleHint.Monospace)
        self._monospacedFont.setFixedPitch(True)
        if self._isMonospaced:
            self.setFont(self._monospacedFont)
            self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance("9"))

    def setEditorPointSize(self, point_size: int) -> None:
        size = max(6, int(point_size))
        self._defaultFont.setPointSize(size)
        self._monospacedFont.setPointSize(size)
        self.setFont(self._monospacedFont if self._isMonospaced else self._defaultFont)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance("9"))

    def isMonospaced(self) -> bool:
        return self._isMonospaced

    # Sensitive mode API
    def setSensitive(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._sensitive:
            return
        self._sensitive = enabled
        if enabled:
            if self._cover is None:
                self._cover = _SensitiveCover(self)
            if self._reveal_button is None:
                self._reveal_button = QPushButton(self)
                self._reveal_button.setCheckable(True)
                self._reveal_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                self._reveal_button.setAutoDefault(False)
                self._reveal_button.setDefault(False)
                self._reveal_button.toggled.connect(self._on_reveal_toggled)
            self._revealed = False
            self._reveal_button.blockSignals(True)
            self._reveal_button.setChecked(False)
            self._reveal_button.blockSignals(False)
            self._apply_sensitive_state()
        else:
            if self._cover is not None:
                self._cover.hide()
            if self._reveal_button is not None:
                self._reveal_button.hide()
            self.setReadOnly(False)
            self._revealed = True

    def isSensitive(self) -> bool:
        return self._sensitive

    def setSecretRevealed(self, revealed: bool) -> None:
        if not self._sensitive or self._reveal_button is None:
            return
        self._reveal_button.setChecked(bool(revealed))

    def secretRevealed(self) -> bool:
        return self._revealed if self._sensitive else True

    def _on_reveal_toggled(self, checked: bool) -> None:
        self._revealed = bool(checked)
        self._apply_sensitive_state()

    def _apply_sensitive_state(self) -> None:
        if not self._sensitive or self._cover is None or self._reveal_button is None:
            return
        label = "Reveal" if not self._revealed else "Hide"
        self._reveal_button.setText(label)
        self._reveal_button.setToolTip(
            "Click to reveal secret contents" if not self._revealed else "Click to hide secret contents"
        )
        self._update_button_width()
        self.setReadOnly(not self._revealed)
        self._update_sensitive_geometry()
        self._cover.setVisible(not self._revealed)
        self._reveal_button.show()
        if self._cover.isVisible():
            self._cover.raise_()
        self._reveal_button.raise_()
        self._update_button_width()

    def _update_button_width(self) -> None:
        if self._reveal_button is None:
            return
        metrics = QFontMetrics(self._reveal_button.font())
        width = max(metrics.horizontalAdvance("Reveal"), metrics.horizontalAdvance("Hide")) + 18
        self._reveal_button.setFixedWidth(width)

    def _update_sensitive_geometry(self) -> None:
        if not self._sensitive:
            return
        cr = self.contentsRect()
        if self._cover is not None:
            self._cover.setGeometry(cr)
        if self._reveal_button is not None:
            btn = self._reveal_button
            btn.adjustSize()
            margin = 6
            x = cr.right() - btn.width() - margin
            y = cr.top() + margin
            btn.move(max(cr.left() + margin, x), y)

    # Line number area plumbing
    def line_number_area_width(self, new_block_count: int = 0) -> int:
        if not self._lineNumbersWidget.isVisible():
            return 0

        max_count = max(1, new_block_count or self.blockCount())
        digits = 1 + max(1, len(str(max_count)))
        space = digits * self.fontMetrics().horizontalAdvance("9")
        return space

    def _update_line_number_area_width(self, new_block_count: int = 0) -> None:
        self._update_button_width()
        self.setViewportMargins(self.line_number_area_width(new_block_count), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        self._update_button_width()

        if dy:
            self._lineNumbersWidget.scroll(0, dy)
        else:
            self._lineNumbersWidget.update(0, rect.y(), self._lineNumbersWidget.width(), rect.height())

        if self._lineNumbersWidget.width() + 1 != self.viewport().x():
            self._update_line_number_area_width()

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        self._update_button_width()
        cr = self.contentsRect()
        self._lineNumbersWidget.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))
        self._update_sensitive_geometry()

    def line_number_area_paint_event(self, event) -> None:
        if not self._lineNumbersWidget.isVisible():
            return

        painter = QPainter(self._lineNumbersWidget)
        painter.fillRect(event.rect(), self.palette().alternateBase())
        painter.setPen(self.palette().accent().color())

        block = self.firstVisibleBlock()
        block_number = 1 + block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        width = int(self._lineNumbersWidget.width() - 0.5 * self.fontMetrics().horizontalAdvance("9"))
        height = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    int(top),
                    width,
                    height,
                    Qt.AlignmentFlag.AlignRight,
                    str(block_number),
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1
