import base64
import functools
import gzip
import zlib
from typing import Callable

import gmpy2
from PySide6.QtCore import QPersistentModelIndex, Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView, QTreeView, QVBoxLayout, QWidget

from delegate import JsonTypeDelegate, ValueDelegate
from enums import JsonType
from tree_model import JsonTreeModel
from tree_view import show_context_menu

# JSON types whose "editor" is actually a modal dialog opened from
# ValueDelegate.createEditor as a side effect (it returns None). Calling
# view.edit() for these would only trigger a redundant Qt warning.
_MODAL_EDITOR_TYPES = frozenset({JsonType.MULTILINE, JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP})


def _uses_modal_editor(json_type: JsonType) -> bool:
    return json_type in _MODAL_EDITOR_TYPES


class JsonTab(QWidget):
    def __init__(
        self,
        update_actions_callback,
        status_message_callback: Callable[[str, int], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self._status_message_callback = status_message_callback

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
                "time": "12:34",
                "datetime": "2024-06-01 12:34:56",
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
        self.model.typeChanged.connect(self._on_type_changed)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(functools.partial(show_context_menu, self.view))

        self.file_path = None

    def _on_type_changed(self, item_index, lossy: bool) -> None:
        value_index = self.model.index(item_index.row(), 2, item_index.parent())
        self.view.closePersistentEditor(value_index)

        # Only re-open the editor for value cells that are actually editable.
        # NULL / ARRAY / OBJECT have no editable value, and dialog-based types
        # (MULTILINE / BYTES / ZLIB / GZIP) drive their own modal editors;
        # calling `view.edit()` for any of these makes Qt log
        # "edit: editing failed" and is otherwise a no-op.
        flags = self.model.flags(value_index)
        new_type = self.model.get_item(item_index).json_type
        if not (flags & Qt.ItemFlag.ItemIsEditable) or _uses_modal_editor(new_type):
            if lossy and self._status_message_callback is not None:
                self._status_message_callback("Type change dropped existing child nodes", 3000)
            return

        # Defer the edit() call to the next event-loop iteration so that the
        # synchronous chain that committed the type-combo finishes first.
        # If a previous value editor for this index is still alive, Qt will
        # reuse it — that is OK because ``ValueDelegate.setEditorData`` /
        # ``setModelData`` dispatch on the editor's *widget class*, so a
        # stale editor still operates correctly without triggering Qt
        # warnings.
        persistent = QPersistentModelIndex(value_index)

        def _start_value_edit():
            if not persistent.isValid():
                return
            idx = self.model.index(persistent.row(), persistent.column(), persistent.parent())
            if self.model.flags(idx) & Qt.ItemFlag.ItemIsEditable:
                self.view.edit(idx)

        QTimer.singleShot(0, _start_value_edit)

        if lossy and self._status_message_callback is not None:
            self._status_message_callback("Type change dropped existing child nodes", 3000)
