from __future__ import annotations

from black.trans import Callable
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget


class LineNumberArea(QWidget):
    def __init__(self, editor: "MultilineEditor") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # type: ignore[override]
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):  # type: ignore[override]
        self._editor.line_number_area_paint_event(event)


class MultilineEditor(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._lineNumbersWidget = LineNumberArea(self)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)

        # Better defaults for multi-line editing
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance("9"))
        self.setWordWrap(True)
        self.setLineNumbersVisible(True)

    # Public API
    def setLineNumbersVisible(self, is_visible: bool) -> None:
        self._lineNumbersWidget.setVisible(is_visible)
        self._update_line_number_area_width()

    def setWordWrap(self, enabled: bool) -> None:
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if enabled else QPlainTextEdit.LineWrapMode.NoWrap)

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


class MultilineDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, text: str = "", callback: Callable[[str], None] = lambda _: None
    ) -> None:
        super().__init__(parent)
        self._callback = callback

        self.setWindowTitle("Edit Multiline Text")
        self.setModal(True)
        self.resize(600, 440)

        self.editor = MultilineEditor(self)
        self.editor.setPlainText(text or "")

        # Controls row
        self.wrapCheckBox = QCheckBox("Word wrap")
        self.wrapCheckBox.setChecked(True)
        self.wrapCheckBox.toggled.connect(self.editor.setWordWrap)

        self.lineNumbersCheckBox = QCheckBox("Line numbers")
        self.lineNumbersCheckBox.setChecked(True)
        self.lineNumbersCheckBox.toggled.connect(self.editor.setLineNumbersVisible)

        controls = QHBoxLayout()
        controls.addWidget(self.wrapCheckBox)
        controls.addWidget(self.lineNumbersCheckBox)
        controls.addStretch(1)

        # Buttons
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.addButton(QDialogButtonBox.StandardButton.Ok).clicked.connect(self.accept)
        self.buttonBox.addButton(QDialogButtonBox.StandardButton.Cancel).clicked.connect(self.reject)

        # Layout
        self._layout = QVBoxLayout(self)
        self._layout.addLayout(controls)
        self._layout.addWidget(self.editor)
        self._layout.addWidget(self.buttonBox)

        self.setLayout(self._layout)

    def text(self) -> str:
        return self.editor.toPlainText()

    def accept(self) -> None:
        super().accept()
        self._callback(self.text())
