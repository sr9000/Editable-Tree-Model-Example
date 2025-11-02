import base64
import functools
import gzip
import zlib

import gmpy2
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTreeView, QVBoxLayout, QWidget

from delegate import JsonTypeDelegate, ValueDelegate
from tree_model import JsonTreeModel
from tree_view import show_context_menu


class JsonTab(QWidget):
    def __init__(self, update_actions_callback, parent=None):
        super().__init__(parent)

        self.layout = QVBoxLayout(self)

        self.view = QTreeView(self)
        self.view.setUniformRowHeights(True)
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
                "integer": 9223372036854775808,
                "float": gmpy2.mpq("3.14"),
                "percent": gmpy2.mpq("50/100"),
                "single-line": "Hello, world!" * 100,
                "multi-line": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6",
                "bytes": base64.b64encode(b"hello " * 10).decode(),
                "zlib": base64.b64encode(zlib.compress(b"hello " * 10)).decode(),
                "gzip": base64.b64encode(gzip.compress(b"hello " * 10)).decode(),
                "date": "2024-06-01",
                "date-time": "2024-06-01 12:34:56",
                "dt+timezone": "2024-06-01T12:34:56.9999+00:00",
                "boolean": True,
                "object": {"key": "value"},
                "array": [1, 2, 3],
                "null": None,
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
