from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QHeaderView, QLineEdit


class HeaderViewEditorMixin:
    def __init__(self, header: QHeaderView):
        self.header = header

        # This block sets up the edit line by making setting the parent
        # to the Headers Viewport.
        self.line = QLineEdit(parent=self.header.viewport())  # Create
        self.line.setAlignment(Qt.AlignmentFlag.AlignTop)  # Set the Alignmnet
        self.line.setHidden(True)  # Hide it till its needed

        # This is needed because I am having a werid issue that I believe has
        # to do with it losing focus after editing is done.
        self.line.blockSignals(True)
        self.sectionedit = 0

        # Connects to double-click
        self.header.sectionDoubleClicked.connect(self.edit_header)
        self.line.editingFinished.connect(self.done_editing)

    def done_editing(self):
        # This block signals needs to happen first otherwise I have lost focus
        # problems again when there are no rows
        self.line.blockSignals(True)
        self.line.setHidden(True)

        # oldname = self.model().headerData(self.sectionedit, Qt.Orientation.Horizontal)
        newname = str(self.line.text())

        self.header.model().setHeaderData(
            self.sectionedit, Qt.Orientation.Horizontal, newname
        )
        self.line.setText("")
        self.header.setCurrentIndex(QModelIndex())

    def edit_header(self, section):
        self.sectionedit = section

        # This block sets up the geometry for the line edit
        edit_geometry = self.line.geometry()
        edit_geometry.setWidth(self.header.sectionSize(section))
        edit_geometry.moveLeft(self.header.sectionViewportPosition(section))
        self.line.setGeometry(edit_geometry)

        self.line.setText(
            self.header.model().headerData(self.sectionedit, Qt.Orientation.Horizontal)
        )
        self.line.setHidden(False)  # Make it visiable
        self.line.blockSignals(False)  # Let it send signals
        self.line.setFocus()
        self.line.selectAll()
