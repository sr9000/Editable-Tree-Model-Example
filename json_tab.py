import base64
import functools
import gzip
import zlib
from datetime import datetime
from typing import Any, Callable

import gmpy2
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QKeySequence, QShortcut, QUndoCommand, QUndoStack
from PySide6.QtWidgets import QAbstractItemView, QTreeView, QVBoxLayout, QWidget

from delegate import JsonTypeDelegate, ValueDelegate
from enums import JsonType
from tree_item import JsonTreeItem
from tree_model import JsonTreeModel
from tree_view import (
    copy_selection,
    cut_selection,
    delete_selection,
    duplicate_selection,
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
    move_selection_down,
    move_selection_up,
    paste_from_clipboard,
    show_context_menu,
    sort_selection_keys,
)


class _SnapshotCommand(QUndoCommand):
    def __init__(
        self,
        tab: "JsonTab",
        text: str,
        before: dict,
        after: dict,
        *,
        skip_first_redo: bool = False,
    ):
        super().__init__(text)
        self._tab = tab
        self._before = before
        self._after = after
        # ``QUndoStack.push()`` automatically invokes ``redo()``. The model
        # is already in the after-state right after the mutator ran, so
        # the implicit redo would only mean rebuilding the same state from
        # a snapshot. Skipping that first redo avoids one O(N) restore per
        # commit on large trees.
        self._skip_next_redo = skip_first_redo

    def undo(self):
        self._tab._restore_state(self._before)

    def redo(self):
        if self._skip_next_redo:
            self._skip_next_redo = False
            return
        self._tab._restore_state(self._after)


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
        self.undo_stack = QUndoStack(self)

        self.view.setModel(self.model)

        self.type_delegate = JsonTypeDelegate(self)
        self.value_delegate = ValueDelegate(self)

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
        self._duplicate_shortcut.activated.connect(
            lambda: self._run_tree_action("Duplicated selection", duplicate=True)
        )

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

    def _snapshot(self) -> Any:
        return self.model.root_item.to_json()

    @staticmethod
    def _ordered_repr(value: Any) -> Any:
        # Build a comparison key that preserves dict key order (Python dict
        # equality ignores order, which would mask object-member reorderings
        # like move-up / move-down on object children).
        if isinstance(value, dict):
            return ("__obj__", [(k, JsonTab._ordered_repr(v)) for k, v in value.items()])
        if isinstance(value, list):
            return ("__arr__", [JsonTab._ordered_repr(v) for v in value])
        return value

    @classmethod
    def _tree_equals_data(cls, item: JsonTreeItem, data: Any) -> bool:
        """Return True iff *item*'s subtree matches the python *data* snapshot.

        Single-pass, allocation-free, early-exit. Order-sensitive on dicts
        so reorderings of OBJECT members are detected as a real change.

        This replaces the deep ``_ordered_repr`` build+compare on the no-op
        detection path: we walk the live tree against the ``before`` data
        directly without materialising the after-state into Python data.
        """
        jt = item.json_type
        if jt is JsonType.OBJECT:
            if not isinstance(data, dict) or len(item.child_items) != len(data):
                return False
            for child, (k, v) in zip(item.child_items, data.items()):
                if child.name != k or not cls._tree_equals_data(child, v):
                    return False
            return True
        if jt is JsonType.ARRAY:
            if not isinstance(data, list) or len(item.child_items) != len(data):
                return False
            for child, v in zip(item.child_items, data):
                if not cls._tree_equals_data(child, v):
                    return False
            return True
        return item.value == data

    def _index_path(self, index: QModelIndex) -> tuple[int, ...]:
        path: list[int] = []
        cursor = index
        while cursor.isValid():
            path.append(cursor.row())
            cursor = cursor.parent()
        return tuple(reversed(path))

    def _index_from_path(self, path: tuple[int, ...]) -> QModelIndex:
        idx = QModelIndex()
        for row in path:
            nxt = self.model.index(row, 0, idx)
            if not nxt.isValid():
                return QModelIndex()
            idx = nxt
        return idx

    def _qualified_name(self, index: QModelIndex) -> str:
        """Return a JSON-style qualified path of *index* (e.g. ``$.foo.bar[2].baz``).

        Uses ``$`` as the document root. Returns ``$`` when the index is invalid.
        """
        if not index.isValid():
            return "$"

        # Walk up from the leaf collecting (parent_type, child_item) pairs.
        chain: list[tuple[JsonType | None, Any]] = []
        cursor = self.model.index(index.row(), 0, index.parent())
        while cursor.isValid():
            item = self.model.get_item(cursor)
            parent_item = item.parent() if item is not None else None
            parent_type = parent_item.json_type if parent_item is not None else None
            chain.append((parent_type, item))
            cursor = cursor.parent()

        chain.reverse()
        parts: list[str] = ["$"]
        for parent_type, item in chain:
            if parent_type is JsonType.ARRAY:
                parts.append(f"[{item.row()}]")
            else:
                name = item.name if isinstance(item.name, str) and item.name else "<no name>"
                parts.append(f".{name}")
        return "".join(parts)

    def _collect_expanded_paths(self) -> list[tuple[int, ...]]:
        paths: list[tuple[int, ...]] = []

        def visit(parent_index: QModelIndex) -> None:
            for r in range(self.model.rowCount(parent_index)):
                child = self.model.index(r, 0, parent_index)
                if not child.isValid():
                    continue
                if self.view.isExpanded(child):
                    paths.append(self._index_path(child))
                    visit(child)

        visit(QModelIndex())
        return paths

    def _capture_state(self) -> dict:
        current = self.view.currentIndex()
        return {
            "data": self._snapshot(),
            "expansion": self._collect_expanded_paths(),
            "current": self._index_path(current) if current.isValid() else None,
        }

    def _restore_state(self, state: dict) -> None:
        self.model.beginResetModel()
        self.model.root_item = JsonTreeItem(None, state["data"])
        self.model.endResetModel()

        for path in state.get("expansion", ()):
            idx = self._index_from_path(path)
            if idx.isValid():
                self.view.setExpanded(idx, True)

        current_path = state.get("current")
        if isinstance(current_path, tuple):
            idx = self._index_from_path(current_path)
            if idx.isValid():
                sel_model = self.view.selectionModel()
                if sel_model is not None:
                    self.view.setCurrentIndex(idx)

    def _restore_snapshot(self, data: Any) -> None:
        # Backward-compatible helper: restore data only (used by older callers / tests).
        self._restore_state({"data": data, "expansion": [], "current": None})

    def commit_mutation(
        self,
        text: str,
        mutator: Callable[[], bool],
        *,
        target_index: QModelIndex | None = None,
    ) -> bool:
        before = self._capture_state()
        # Capture the target path BEFORE the mutator runs: for delete/move/edit
        # this is the affected node; for insert/duplicate the path of the
        # parent / sibling that triggered the action is still informative.
        target = target_index if (target_index is not None and target_index.isValid()) else self.view.currentIndex()
        target_qname = self._qualified_name(target)
        if not bool(mutator()):
            return False

        # Single-pass walk against the ``before`` snapshot — early-exit, no
        # extra ``to_json`` build for the after-state.
        if self._tree_equals_data(self.model.root_item, before["data"]):
            # Mutation reported success but produced no visible change; skip undo entry.
            return False

        # Build ``after`` only when we know we will push.
        after = self._capture_state()

        timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
        label = f"[{timestamp}] {text} @ {target_qname}"
        # The model is already in the after-state, so tell the command to
        # skip the implicit redo Qt fires from ``push()``.
        self.undo_stack.push(_SnapshotCommand(self, label, before, after, skip_first_redo=True))
        return True

    def commit_set_data(self, index: QModelIndex, value: Any, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole) -> bool:
        def _apply() -> bool:
            return bool(self.model.setData(index, value, role))

        match index.column():
            case 0:
                text = "rename"
            case 1:
                text = "change type"
            case 2:
                text = "edit value"
            case _:
                text = "edit cell"
        return self.commit_mutation(text, _apply, target_index=index)

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

    def insert_sibling_before(self) -> bool:
        return insert_sibling_before(self.view)

    def insert_sibling_after(self) -> bool:
        return insert_sibling_after(self.view)

    def insert_child(self) -> bool:
        return insert_child_current(self.view)
