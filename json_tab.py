import functools

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QAbstractItemView

from delegate import JsonTypeDelegate, ValueDelegate
from header_view_editor import HeaderViewEditorMixin
from tree_model import JsonTreeModel
from tree_view import show_context_menu


class JsonTab(QWidget):
    def __init__(self, update_actions_callback, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)

        self.view = QTreeView(self)
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setAnimated(False)
        self.view.setAllColumnsShowFocus(True)

        self.layout.addWidget(self.view)

        # option to edit headers is not needed
        # self.header_editor = HeaderViewEditorMixin(self.view.header())

        self.model = JsonTreeModel(
            {
                "question": "The Ultimate Question of Life, the Universe, and Everything.",
                "answer": 42,
            },
            self.view,
        )

        self.view.setModel(self.model)

        self.type_delegate = JsonTypeDelegate()
        self.value_delegate = ValueDelegate()

        self.view.setItemDelegateForColumn(1, self.type_delegate)
        self.view.setItemDelegateForColumn(2, self.value_delegate)

        self.view.selectionModel().selectionChanged.connect(update_actions_callback)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(
            functools.partial(show_context_menu, self.view)
        )

        self.file_path = None
