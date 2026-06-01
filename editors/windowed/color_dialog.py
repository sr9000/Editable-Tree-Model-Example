from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QWidget


class ColorPickerDialog(QColorDialog):
    """Thin, app-agnostic ``QColorDialog`` wrapper.

    The host supplies the initial colour, whether alpha is editable, a
    window title, and a callback invoked with the selected ``QColor``.
    Encoding/committing the picked colour stays with the host.
    """

    def __init__(
        self,
        parent: QWidget,
        *,
        initial: QColor,
        with_alpha: bool,
        title: str,
        callback: Callable[[QColor], None],
    ) -> None:
        super().__init__(parent, currentColor=initial)
        if with_alpha:
            self.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        self.setWindowTitle(title)
        self.colorSelected.connect(callback)
