from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHeaderView, QLineEdit, QWidget


class EscapableLineEdit(QLineEdit):
    class Filter(QObject):
        def __init__(self, finishable_line_edit: QLineEdit):
            super().__init__()
            self.edit = finishable_line_edit

        def eventFilter(self, watched, event, /) -> bool:
            if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
                if event.key() == Qt.Key.Key_Escape:
                    self.edit.setText("")
                    self.edit.editingFinished.emit()
                    return True

                if event.key() in (
                    Qt.Key.Key_Up,
                    Qt.Key.Key_Down,
                    Qt.Key.Key_PageUp,
                    Qt.Key.Key_PageDown,
                ):
                    return True  # dirty hack -- disable up/down keys to prevent moving in parent

            return False

    def __init__(self, parent: QWidget = None, **kwargs):
        super().__init__(parent, **kwargs)

        self.filter = self.Filter(self)
        self.installEventFilter(self.filter)


class HeaderViewEditorMixin:
    def __init__(self, header: QHeaderView):
        self.header = header

        # This block sets up the edit line by making setting the parent
        # to the Headers Viewport.
        self.line = EscapableLineEdit(parent=self.header.viewport())  # Create
        self.line.setAlignment(Qt.AlignmentFlag.AlignTop)  # Set the Alignmnet
        self.line.setHidden(True)  # Hide it till its needed

        # This is needed because I am having a werid issue that I believe has
        # to do with it losing focus after editing is done.
        self.line.blockSignals(True)

        self.section = 0

        # Connects to double-click
        self.header.sectionDoubleClicked.connect(self.edit_header)
        self.line.editingFinished.connect(self.done_editing)

    def done_editing(self):
        # This block signals needs to happen first otherwise I have lost focus
        # problems again when there are no rows
        self.line.blockSignals(True)
        self.line.setHidden(True)

        if new_data := str(self.line.text()):
            self.header.model().setHeaderData(self.section, Qt.Orientation.Horizontal, new_data)
        self.line.setText("")

    def edit_header(self, section):
        self.section = section

        # This block sets up the geometry for the line edit
        edit_geometry = self.line.geometry()
        edit_geometry.setWidth(self.header.sectionSize(section))
        edit_geometry.moveLeft(self.header.sectionViewportPosition(section))
        self.line.setGeometry(edit_geometry)

        self.line.setText(self.header.model().headerData(self.section, Qt.Orientation.Horizontal))
        self.line.setHidden(False)  # Make it visiable
        self.line.blockSignals(False)  # Let it send signals
        self.line.setFocus()
        self.line.selectAll()
