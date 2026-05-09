from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontDatabase, QPainter
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class LineNumberArea(QWidget):
    def __init__(self, editor: "QMultilineEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):  # type: ignore[override]
        self._editor.line_number_area_paint_event(event)


class QMultilineEditor(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._lineNumbersWidget = LineNumberArea(self)
        self._defaultFont = QFont(self.font())
        self._monospacedFont = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._isMonospaced = False

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

    # Line number area plumbing
    def line_number_area_width(self, new_block_count: int = 0) -> int:
        if not self._lineNumbersWidget.isVisible():
            return 0

        max_count = max(1, new_block_count or self.blockCount())
        digits = 1 + max(1, len(str(max_count)))
        space = digits * self.fontMetrics().horizontalAdvance("9")
        return space

    def _update_line_number_area_width(self, new_block_count: int = 0) -> None:
        self.setViewportMargins(self.line_number_area_width(new_block_count), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._lineNumbersWidget.scroll(0, dy)
        else:
            self._lineNumbersWidget.update(0, rect.y(), self._lineNumbersWidget.width(), rect.height())

        if self._lineNumbersWidget.width() + 1 != self.viewport().x():
            self._update_line_number_area_width()

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._lineNumbersWidget.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

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
