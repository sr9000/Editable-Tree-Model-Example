from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)


class LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):  # type: ignore[override]
        self._editor.line_number_area_paint_event(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._line_numbers_enabled = True

        self._lineNumberArea = LineNumberArea(self)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)

        self._update_line_number_area_width(0)

        # Better defaults for multi-line editing
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.setWordWrap(True)

    # Public API
    def setLineNumbersVisible(self, visible: bool) -> None:
        self._line_numbers_enabled = visible
        self._lineNumberArea.setVisible(visible)
        self._update_line_number_area_width(0)

    def setWordWrap(self, enabled: bool) -> None:
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if enabled else QPlainTextEdit.LineWrapMode.NoWrap)

    # Line number area plumbing
    def line_number_area_width(self) -> int:
        if not self._line_numbers_enabled:
            return 0
        digits = 1
        max_count = max(1, self.blockCount())
        while max_count >= 10:
            max_count //= 10
            digits += 1
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def _update_line_number_area_width(self, _newBlockCount: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._lineNumberArea.scroll(0, dy)
        else:
            self._lineNumberArea.update(0, rect.y(), self._lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def resizeEvent(self, event):  # type: ignore[override]
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint_event(self, event) -> None:
        if not self._line_numbers_enabled:
            return
        painter = QPainter(self._lineNumberArea)
        painter.fillRect(event.rect(), self.palette().alternateBase())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(self.palette().color(self.foregroundRole()))
                painter.drawText(
                    0,
                    int(top),
                    int(self._lineNumberArea.width()) - 5,
                    int(self.fontMetrics().height()),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1


class MultilineEditorDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, text: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Text")
        self.setModal(True)
        self.resize(700, 500)

        self.editor = CodeEditor(self)
        self.editor.setPlainText(text or "")

        # Controls row
        self.wrapCheck = QCheckBox("Word wrap")
        self.wrapCheck.setChecked(True)
        self.wrapCheck.toggled.connect(self.editor.setWordWrap)

        self.linesCheck = QCheckBox("Line numbers")
        self.linesCheck.setChecked(True)
        self.linesCheck.toggled.connect(self.editor.setLineNumbersVisible)

        controls = QHBoxLayout()
        controls.addWidget(self.wrapCheck)
        controls.addWidget(self.linesCheck)
        controls.addStretch(1)

        # Buttons
        self.buttonBox = QDialogButtonBox(self)
        ok = self.buttonBox.addButton(QDialogButtonBox.StandardButton.Ok)
        cancel = self.buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

        # Layout
        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.editor)
        layout.addWidget(self.buttonBox)

    def text(self) -> str:
        return self.editor.toPlainText()
