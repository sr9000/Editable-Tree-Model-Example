import functools

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTreeView, QAbstractItemView

from delegate import JsonTypeDelegate, ComboBoxDelegate
from header_view_editor import HeaderViewEditorMixin
from tree_model import JsonTreeModel
from tree_view import show_context_menu


class JsonTab(QWidget):
    def __init__(self, update_actions_callback, parent=None):
        super().__init__(parent)

        self.my_layout = QVBoxLayout(self)

        self.my_view = QTreeView(self)
        self.my_view.setAlternatingRowColors(True)
        self.my_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.my_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        self.my_view.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.my_view.setAnimated(False)
        self.my_view.setAllColumnsShowFocus(True)

        self.my_layout.addWidget(self.my_view)

        self.my_header_editor = HeaderViewEditorMixin(self.my_view.header())

        self.my_model = JsonTreeModel(
            {
                "question": "The Ultimate Question of Life, the Universe, and Everything.",
                "answer": 42,
            },
            self.my_view,
        )

        self.my_view.setModel(self.my_model)

        self.type_delegate = JsonTypeDelegate()
        self.value_delegate = ComboBoxDelegate()

        self.my_view.setItemDelegateForColumn(1, self.type_delegate)
        self.my_view.setItemDelegateForColumn(2, self.value_delegate)

        self.my_view.selectionModel().selectionChanged.connect(update_actions_callback)
        self.my_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # self.my_view.customContextMenuRequested.connect(
        #     functools.partial(show_context_menu, self.my_view)
        # )

        self.my_file_path = None
