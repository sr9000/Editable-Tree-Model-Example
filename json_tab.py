import base64
import functools
import gzip
import zlib
from typing import Callable

import gmpy2
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QAbstractItemView, QTreeView, QVBoxLayout, QWidget

from delegate import JsonTypeDelegate, ValueDelegate
from tree_model import JsonTreeModel
from tree_view import (
    copy_selection,
    cut_selection,
    delete_selection,
    duplicate_selection,
    move_selection_down,
    move_selection_up,
    paste_from_clipboard,
    show_context_menu,
    sort_selection_keys,
)


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

        # Keep keyboard shortcuts at the tab level so they work regardless of focused column.
        self._copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.view)
        self._copy_shortcut.activated.connect(lambda: self._run_tree_action("Copied selection", copy_only=True))

        self._cut_shortcut = QShortcut(QKeySequence.StandardKey.Cut, self.view)
        self._cut_shortcut.activated.connect(lambda: self._run_tree_action("Cut selection", cut=True))

        self._paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self.view)
        self._paste_shortcut.activated.connect(lambda: self._run_tree_action("Pasted JSON", paste=True))

        self._delete_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Delete), self.view)
        self._delete_shortcut.activated.connect(lambda: self._run_tree_action("Deleted selection", delete=True))

        self._duplicate_shortcut = QShortcut(QKeySequence("Ctrl+D"), self.view)
        self._duplicate_shortcut.activated.connect(lambda: self._run_tree_action("Duplicated selection", duplicate=True))

        self._move_up_shortcut = QShortcut(QKeySequence("Alt+Up"), self.view)
        self._move_up_shortcut.activated.connect(lambda: self._run_tree_action("Moved up", move_up=True))

        self._move_down_shortcut = QShortcut(QKeySequence("Alt+Down"), self.view)
        self._move_down_shortcut.activated.connect(lambda: self._run_tree_action("Moved down", move_down=True))

        self._sort_shortcut = QShortcut(QKeySequence("Ctrl+Alt+S"), self.view)
        self._sort_shortcut.activated.connect(lambda: self._run_tree_action("Sorted keys", sort_keys=True))

        self.file_path = None

    def _on_type_changed(self, item_index, lossy: bool) -> None:
        # ``change_type`` already emits ``dataChanged`` for the row, which
        # triggers the view to refresh and to close any inline editor that
        # might have been open on the value cell. We deliberately do NOT
        # call ``view.edit(value_index)`` here:
        #
        # * In programmatic / offscreen contexts (tests, scripted edits)
        #   ``view.edit()`` logs a spurious "edit: editing failed" warning
        #   because the view has no focus / no real editor host.
        # * In interactive contexts the user just dismissed the type combo;
        #   they can click or press F2 on the value cell when ready.
        #
        # The "reopen value editor" UX nicety is deferred to a later phase
        # where it can be wired through a single source of editor state
        # (e.g. an undo-stack-backed action).
        value_index = self.model.index(item_index.row(), 2, item_index.parent())
        self.view.closePersistentEditor(value_index)

        if lossy and self._status_message_callback is not None:
            self._status_message_callback("Type change dropped existing child nodes", 3000)

    def _run_tree_action(
        self,
        success_message: str,
        *,
        copy_only: bool = False,
        cut: bool = False,
        paste: bool = False,
        delete: bool = False,
        duplicate: bool = False,
        move_up: bool = False,
        move_down: bool = False,
        sort_keys: bool = False,
    ) -> None:
        changed = False
        if copy_only:
            changed = copy_selection(self.view)
        elif cut:
            changed = cut_selection(self.view)
        elif paste:
            changed = paste_from_clipboard(self.view)
        elif delete:
            changed = delete_selection(self.view)
        elif duplicate:
            changed = duplicate_selection(self.view)
        elif move_up:
            changed = move_selection_up(self.view)
        elif move_down:
            changed = move_selection_down(self.view)
        elif sort_keys:
            changed = sort_selection_keys(self.view, recursive=False)

        if changed and self._status_message_callback is not None:
            self._status_message_callback(success_message, 1500)
