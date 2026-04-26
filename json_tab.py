import base64
import gzip
import time
import zlib
from datetime import datetime
from typing import Any, Callable

import gmpy2
from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt, QTimer, Signal
from PySide6.QtWidgets import QWidget

from documents.tab_io import save as tab_save, save_as as tab_save_as, snapshot as tab_snapshot
from documents.tab_paths import index_from_path, index_path, proxy_to_source, qualified_name, source_to_view
from documents.tab_setup import init_delegates_and_connections, init_layout, init_model, init_search_filter, init_shortcuts
from documents.tab_status import on_current_changed, size_hint_for_item
from enums import TEXT_FAMILY, JsonType, parse_json_type, text_pseudotype_for
from tree_item import JsonTreeItem
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
    sort_selection_keys,
)
from undo.commands import (
    _ChangeTypeCmd,
    _EditValueCmd,
    _InsertRowsCmd,
    _MoveRowCmd,
    _RemoveRowsCmd,
    _RenameCmd,
    _SortKeysCmd,
)


def _make_label(text: str, target_qname: str) -> str:
    timestamp = datetime.now().astimezone().strftime("%H:%M:%S")
    return f"[{timestamp}] {text} @ {target_qname}"


_DEFAULT_DATA = object()

# QUndoCommand.id() values for typed commands that support mergeWith().
# Qt requires id() to fit in a signed 32-bit int (anything larger overflows
# the C++ ``int`` return type and raises ``SystemError`` from PySide).
_CMD_ID_RENAME = 0x0E71_0001
_CMD_ID_EDIT_VALUE = 0x0E71_0002

# Time window in seconds during which two consecutive same-path edits
# collapse into one undo entry. Tuned for keystroke-level typing.
_MERGE_WINDOW_SECONDS = 0.5


def _demo_data() -> dict[str, Any]:
    return {
        "question": "The Ultimate Question of Life, the Universe, and Everything.",
        "answer": 42,
        "integer": 9223372036854775808,
        "float": gmpy2.mpq("3.14"),
        "percent": gmpy2.mpq("50/100"),
        "single-line": "Hello, world!" * 100,
        "utf8-line": "caf\u00e9",
        "multi-line": "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6",
        "utf8-text": "Line 1\nLine 2\n\u03a9",
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
    }


class JsonTab(QWidget):
    dirtyChanged = Signal(bool)

    def __init__(
        self,
        update_actions_callback,
        status_message_callback: Callable[[str, int], None] | None = None,
        data: Any = _DEFAULT_DATA,
        file_path: str | None = None,
        show_root: bool = False,
        parent=None,
        permanent_message_callback: Callable[[str], None] | None = None,
    ):
        super().__init__(parent)

        self._status_message_callback = status_message_callback
        self._permanent_message_callback = permanent_message_callback

        init_layout(self)

        # option to edit headers is not needed
        # self.header_editor = HeaderViewEditorMixin(self.view.header())

        if data is _DEFAULT_DATA:
            model_data = _demo_data()
        else:
            model_data = data if data is not None else {}

        self.file_path = file_path
        self.save_format: str | None = None
        self._dirty = False

        init_model(self, model_data, show_root=show_root)
        init_delegates_and_connections(self, update_actions_callback)
        init_shortcuts(self)
        init_search_filter(self)

        self.undo_stack.cleanChanged.connect(self._on_clean_changed)
        self.undo_stack.setClean()
        self._set_dirty(False)

    @staticmethod
    def _proxy_to_source(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return proxy_to_source(index)

    def _source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return source_to_view(self, source_index)

    def _apply_filter(self) -> None:
        self.proxy.set_filter_text(self.search_edit.text())

    def _on_model_reset(self) -> None:
        self.resize_key_columns()

    def resize_key_columns(self) -> None:
        # Keep key/type columns snug while leaving value column flexible.
        self.view.resizeColumnToContents(0)
        self.view.resizeColumnToContents(1)

    def _set_font_pt(self, pt: int) -> None:
        clamped = max(6, min(48, int(pt)))
        self._font_pt = clamped
        font = self.view.font()
        font.setPointSize(clamped)
        self.view.setFont(font)

    def zoom_in(self) -> None:
        self._set_font_pt(self._font_pt + 1)
        self.resize_key_columns()

    def zoom_out(self) -> None:
        self._set_font_pt(self._font_pt - 1)
        self.resize_key_columns()

    def zoom_reset(self) -> None:
        self._set_font_pt(self._default_font_pt)
        self.resize_key_columns()

    def _on_type_changed(self, item_index, lossy: bool) -> None:
        # ``change_type`` already emitted ``dataChanged`` for the row, which
        # closes any persistent inline editor that might have been open on
        # the value cell. We additionally close it explicitly so the row is
        # in a clean state before any auto-reopen below.
        value_index = self.model.index(item_index.row(), 2, item_index.parent())
        self.view.closePersistentEditor(self._source_to_view(value_index))

        if lossy and self._status_message_callback is not None:
            self._status_message_callback("Type change dropped existing child nodes", 3000)

        # Auto-reopen the value editor only when the type change came from
        # a user-driven combo commit (Phase 5.1). Programmatic
        # ``model.setData`` paths (tests, scripted edits) bypass the
        # delegate entirely so ``_interactive`` stays ``False`` and we
        # avoid the spurious "edit: editing failed" warning that
        # ``tests/test_smoke_mainwindow.py`` regression-tests.
        if not getattr(self.type_delegate, "_interactive", False):
            return
        if not value_index.isValid():
            return
        # Defer via single-shot timer so Qt finishes the current commit
        # cycle (combo close + setModelData unwind) before we open a new
        # editor on the same row.
        pidx = QPersistentModelIndex(value_index)
        QTimer.singleShot(0, lambda: self._reopen_value_editor(pidx))

    def _reopen_value_editor(self, value_pindex: QPersistentModelIndex) -> None:
        if not value_pindex.isValid():
            return
        value_index = QModelIndex(value_pindex) if isinstance(value_pindex, QPersistentModelIndex) else value_pindex
        if not value_index.isValid():
            return
        flags = self.model.flags(value_index)
        if not (flags & Qt.ItemFlag.ItemIsEditable):
            return
        view_index = self._source_to_view(value_index)
        if not view_index.isValid():
            return
        self.view.setCurrentIndex(view_index)
        self.view.edit(view_index)

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirtyChanged.emit(dirty)

    def _on_clean_changed(self, clean: bool) -> None:
        self._set_dirty(not clean)

    def display_name(self) -> str:
        name = self.file_path.rsplit("/", 1)[-1] if self.file_path else "Untitled"
        return f"{name} *" if self._dirty else name

    def save(self) -> bool:
        return tab_save(self)

    def save_as(self, path: str | None = None) -> bool:
        return tab_save_as(self, path=path)

    def _snapshot(self) -> Any:
        return tab_snapshot(self)

    def _index_path(self, index: QModelIndex) -> tuple[int, ...]:
        return index_path(self, index)

    def _index_from_path(self, path: tuple[int, ...]) -> QModelIndex:
        return index_from_path(self, path)

    def _qualified_name(self, index: QModelIndex) -> str:
        return qualified_name(self, index)

    def _size_hint_for_item(self, item: JsonTreeItem) -> str | None:
        return size_hint_for_item(item)

    def _on_current_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        on_current_changed(self, current, _previous)

    def _collect_expanded_paths(self) -> list[tuple[int, ...]]:
        """Return paths of every currently expanded row.

        Kept as a standalone helper because a few tests (and any future
        view-state save/restore) want to enumerate expansion. It is no
        longer part of any undo/redo path.
        """
        paths: list[tuple[int, ...]] = []

        def visit(parent_index: QModelIndex) -> None:
            for r in range(self.model.rowCount(parent_index)):
                child = self.model.index(r, 0, parent_index)
                if not child.isValid():
                    continue
                view_child = self._source_to_view(child)
                if self.view.isExpanded(view_child):
                    paths.append(self._index_path(child))
                    visit(child)

        visit(QModelIndex())
        return paths

    # ------------------------------------------------------------------
    # Smart-restore diff helpers
    # ------------------------------------------------------------------

    def _diff_apply(self, item: JsonTreeItem, target: Any, item_index: QModelIndex) -> bool:
        """Mutate *item*'s subtree in place to match *target*.

        Always returns True. Container <-> leaf type changes are handled
        in place via ``_convert_container`` / ``_convert_to_leaf``, emitting
        the necessary ``beginRemoveRows`` / ``beginInsertRows`` /
        ``dataChanged`` signals so the view stays consistent without a
        full ``beginResetModel``.

        This is the hot path for undo / redo replay. Cheap ``isinstance``
        discriminates container vs leaf in O(1); identical-Python-typed
        leaves bypass ``parse_json_type`` re-parsing altogether.
        """
        if isinstance(target, dict):
            if item.json_type is JsonType.OBJECT:
                return self._diff_object(item, target, item_index)
            self._convert_container(item, item_index, JsonType.OBJECT, target)
            return True
        if isinstance(target, list):
            if item.json_type is JsonType.ARRAY:
                return self._diff_array(item, target, item_index)
            self._convert_container(item, item_index, JsonType.ARRAY, target)
            return True

        # Target is a leaf.
        if item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
            self._convert_to_leaf(item, item_index, target)
            return True

        # Leaf -> leaf fast path.
        if item.value == target:
            return True
        if type(item.value) is type(target) and not isinstance(target, str):
            item.value = item._normalize_value_for_type(target)
            item.editable = item._compute_editable()
        else:
            if isinstance(target, str) and item.json_type in TEXT_FAMILY:
                new_type = text_pseudotype_for(item.json_type, target)
            else:
                new_type = parse_json_type(target)
            if new_type in (JsonType.OBJECT, JsonType.ARRAY):
                self._convert_container(item, item_index, new_type, target)
                return True
            item._apply_typed_value(new_type, target)
        self._emit_row_changed(item_index)
        return True

    # -- low-level mutators used by diff and typed commands --------------

    def _emit_row_changed(self, item_index: QModelIndex) -> None:
        if item_index.isValid():
            row = item_index.row()
            parent = item_index.parent()
            top = self.model.index(row, 0, parent)
            bot = self.model.index(row, 2, parent)
            self.model.dataChanged.emit(
                top,
                bot,
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
            )

    def _clear_children(self, item: JsonTreeItem, item_index: QModelIndex) -> None:
        n = len(item.child_items)
        if n > 0:
            self.model.beginRemoveRows(item_index, 0, n - 1)
            item.child_items.clear()
            item.mark_children_dirty()
            self.model.endRemoveRows()

    def _convert_container(
        self,
        item: JsonTreeItem,
        item_index: QModelIndex,
        new_type: JsonType,
        value: Any,
    ) -> None:
        """Switch *item* to OBJECT or ARRAY and populate from *value*."""
        self._clear_children(item, item_index)
        item.json_type = new_type
        item.value = {} if new_type is JsonType.OBJECT else []
        item.editable = item._compute_editable()
        if new_type is JsonType.OBJECT:
            pairs = list(value.items())
        else:
            pairs = [(None, v) for v in value]
        if pairs:
            self.model.beginInsertRows(item_index, 0, len(pairs) - 1)
            for name, v in pairs:
                item.child_items.append(JsonTreeItem(item, v, name))
            item.mark_children_dirty()
            self.model.endInsertRows()
        self._emit_row_changed(item_index)

    def _convert_to_leaf(self, item: JsonTreeItem, item_index: QModelIndex, target: Any) -> None:
        self._clear_children(item, item_index)
        new_type = parse_json_type(target)
        item._apply_typed_value(new_type, target)
        self._emit_row_changed(item_index)

    def _insert_typed_item(
        self,
        parent_item: JsonTreeItem,
        parent_index: QModelIndex,
        position: int,
        value: Any,
        name: str | int | None = None,
    ) -> bool:
        """Insert a fully-built ``JsonTreeItem`` at *position*."""
        new_item = JsonTreeItem(parent_item, value, name)
        self.model.beginInsertRows(parent_index, position, position)
        parent_item.child_items.insert(position, new_item)
        parent_item.mark_children_dirty()
        self.model.endInsertRows()
        return True

    def _diff_object(self, item: JsonTreeItem, target_dict: dict, item_index: QModelIndex) -> bool:
        target_names = list(target_dict.keys())
        target_name_set = set(target_names)

        # Phase 1: drop children whose names are not in target. Walk
        # backwards so positional indices stay valid as we remove.
        for i in range(len(item.child_items) - 1, -1, -1):
            if item.child_items[i].name not in target_name_set:
                self.model.removeRow(i, item_index)

        # Phase 2: walk the target order, recursing in lockstep when
        # children are already aligned and falling back to a linear search
        # only on disorder.
        for target_pos, target_name in enumerate(target_names):
            target_value = target_dict[target_name]
            cur_pos: int | None = None
            children = item.child_items
            if target_pos < len(children) and children[target_pos].name == target_name:
                cur_pos = target_pos
            else:
                for i in range(target_pos, len(children)):
                    if children[i].name == target_name:
                        cur_pos = i
                        break
            if cur_pos is None:
                self._insert_typed_item(item, item_index, target_pos, target_value, name=target_name)
                continue
            assert cur_pos is not None
            if cur_pos != target_pos:
                self.model.move_row(item_index, cur_pos, target_pos)
            child = item.child_items[target_pos]
            child_index = self.model.index(target_pos, 0, item_index)
            self._diff_apply(child, target_value, child_index)
        return True

    def _diff_array(self, item: JsonTreeItem, target_list: list, item_index: QModelIndex) -> bool:
        target_len = len(target_list)

        # Trim trailing rows.
        while len(item.child_items) > target_len:
            last = len(item.child_items) - 1
            self.model.removeRow(last, item_index)

        # Recurse positionally; extend by appending.
        for pos in range(target_len):
            target_value = target_list[pos]
            if pos >= len(item.child_items):
                self._insert_typed_item(item, item_index, pos, target_value, name=None)
                continue
            child = item.child_items[pos]
            child_index = self.model.index(pos, 0, item_index)
            self._diff_apply(child, target_value, child_index)
        return True

    def commit_set_data(self, index: QModelIndex, value: Any, role: Qt.ItemDataRole = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        index = self._proxy_to_source(index)
        col = index.column()
        if col == 0:
            return self.push_rename(index, value)
        if col == 1:
            return self.push_change_type(index, value)
        if col == 2:
            return self.push_edit_value(index, value)
        return False

    # ------------------------------------------------------------------
    # Typed-command public API (action/compensation, no full-tree snapshot)
    # ------------------------------------------------------------------

    def push_move_row(self, parent_index: QModelIndex, src: int, dst: int, *, label: str = "move row") -> bool:
        if src == dst:
            return False
        parent_item = self.model.get_item(parent_index)
        n = parent_item.child_count()
        if not (0 <= src < n and 0 <= dst < n):
            return False
        target_qname = self._qualified_name(self.model.index(src, 0, parent_index))
        cmd = _MoveRowCmd(self, _make_label(label, target_qname), self._index_path(parent_index), src, dst)
        self.undo_stack.push(cmd)
        return True

    def push_rename(self, name_index: QModelIndex, new_name: Any, *, label: str = "rename") -> bool:
        if not name_index.isValid() or name_index.column() != 0:
            return False
        item = self.model.get_item(name_index)
        if not isinstance(new_name, str):
            return False
        candidate = new_name.strip()
        if not candidate or candidate == item.name:
            return False
        if item.parent_item is None or item.parent_item.json_type is JsonType.ARRAY:
            return False
        if item.parent_item.json_type is JsonType.OBJECT:
            siblings = {c.name for c in item.parent_item.child_items if c is not item and isinstance(c.name, str)}
            if candidate in siblings:
                return False
        target_qname = self._qualified_name(name_index)
        cmd = _RenameCmd(self, _make_label(label, target_qname), self._index_path(name_index), item.name, candidate)
        self.undo_stack.push(cmd)
        return True

    def push_edit_value(self, value_index: QModelIndex, new_value: Any, *, label: str = "edit value") -> bool:
        if not value_index.isValid() or value_index.column() != 2:
            return False
        name_idx = self.model.index(value_index.row(), 0, value_index.parent())
        item = self.model.get_item(name_idx)
        old_subtree = item.to_json()
        # Honour explicit_type strict coercion when the type was pinned.
        if item.explicit_type and item.json_type not in (JsonType.OBJECT, JsonType.ARRAY):
            ok, coerced = item._coerce_value_for_type(item.json_type, new_value, strict=True)
            if not ok:
                return False
            applied = coerced
        else:
            applied = new_value
        # No-op detection on the affected subtree (subset comparison).
        if old_subtree == applied and isinstance(applied, type(old_subtree)):
            return False
        target_qname = self._qualified_name(name_idx)
        cmd = _EditValueCmd(self, _make_label(label, target_qname), self._index_path(name_idx), old_subtree, applied)
        self.undo_stack.push(cmd)
        return True

    def push_change_type(self, type_index: QModelIndex, new_type: Any, *, label: str = "change type") -> bool:
        if not type_index.isValid() or type_index.column() != 1:
            return False
        try:
            target_type = new_type if isinstance(new_type, JsonType) else JsonType(str(new_type))
        except ValueError:
            return False
        name_idx = self.model.index(type_index.row(), 0, type_index.parent())
        item = self.model.get_item(name_idx)
        if item.json_type is target_type:
            return False
        old_subtree = item.to_json()
        old_explicit = item.explicit_type
        target_qname = self._qualified_name(name_idx)
        cmd = _ChangeTypeCmd(
            self,
            _make_label(label, target_qname),
            self._index_path(name_idx),
            old_subtree,
            old_explicit,
            target_type,
        )
        self.undo_stack.push(cmd)
        return True

    def push_insert_rows(self, inserts: list, *, label: str = "insert", target_qname: str | None = None) -> bool:
        """``inserts`` is a list of ``{parent_path, row, value, name}``."""
        if not inserts:
            return False
        qname = (
            target_qname
            if target_qname is not None
            else self._qualified_name(self._index_from_path(inserts[0]["parent_path"]))
        )
        cmd = _InsertRowsCmd(self, _make_label(label, qname), inserts)
        self.undo_stack.push(cmd)
        return True

    def push_remove_rows(self, indexes: list, *, label: str = "delete") -> bool:
        if not indexes:
            return False
        ordered = sorted(indexes, key=lambda i: (self._index_path(i.parent()), i.row()), reverse=True)
        removals = []
        for idx in ordered:
            row0 = self.model.index(idx.row(), 0, idx.parent())
            item = self.model.get_item(row0)
            removals.append(
                {
                    "parent_path": self._index_path(idx.parent()),
                    "row": idx.row(),
                    "name": item.name,
                    "value": item.to_json(),
                }
            )
        target_qname = self._qualified_name(ordered[0])
        cmd = _RemoveRowsCmd(self, _make_label(label, target_qname), removals)
        self.undo_stack.push(cmd)
        return True

    def push_sort_keys(self, index: QModelIndex, *, recursive: bool = False, label: str | None = None) -> bool:
        if not index.isValid():
            return False
        item = self.model.get_item(index)
        if item.json_type is not JsonType.OBJECT:
            return False
        old_subtree = item.to_json()
        if not recursive and list(old_subtree.keys()) == sorted(old_subtree.keys()):
            return False
        target_qname = self._qualified_name(index)
        text = label if label is not None else ("sort keys recursive" if recursive else "sort keys")
        cmd = _SortKeysCmd(self, _make_label(text, target_qname), self._index_path(index), old_subtree, recursive)
        self.undo_stack.push(cmd)
        return True

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
