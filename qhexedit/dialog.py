from typing import Callable

from PySide6.QtWidgets import QDialog, QWidget


class QHexDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, data: bytes = b"", callback: Callable[[bytes], None] = lambda _: None
    ) -> None:
        super().__init__(parent)
        self._callback = callback
