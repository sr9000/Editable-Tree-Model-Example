import base64
import gzip
import time
import zlib
from datetime import datetime
from typing import Any, Callable

import gmpy2
from PySide6.QtCore import QEvent, QModelIndex, QPersistentModelIndex, Qt, QTimer, Signal
from PySide6.QtWidgets import QAbstractItemView, QComboBox, QWidget

from documents.tab_io import save as tab_save
from documents.tab_io import save_as as tab_save_as
from documents.tab_io import snapshot as tab_snapshot
from documents.tab_paths import index_from_path, index_path, proxy_to_source, qualified_name, source_to_view
from documents.tab_setup import (
    init_delegates_and_connections,
    init_layout,
    init_model,
    init_search_filter,
    init_shortcuts,
)
from documents.tab_status import on_current_changed, size_hint_for_item
from themes import LIGHT_DEFAULT
from themes.icon_provider import IconProvider, StubIconProvider
from themes.spec import ThemeSpec
from tree.item import JsonTreeItem
from tree.types import JsonType
from tree_actions.clipboard import copy_selection
from tree_actions.paste import paste_from_clipboard
from tree_actions.structure import (
    cut_selection,
    delete_selection,
    duplicate_selection,
    insert_child_current,
    insert_sibling_after,
    insert_sibling_before,
    move_selection_down,
    move_selection_up,
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
from undo.diff import DiffApplier


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

    def eventFilter(self, watched, event):  # type: ignore[override]
        view = getattr(self, "view", None)
        if view is not None and watched in (view, view.viewport()):
            if event.type() == QEvent.Type.KeyPress:
                if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self.edit_name_or_value_from_enter()
                    return True
                if event.key() == Qt.Key.Key_Space and event.modifiers() == Qt.KeyboardModifier.NoModifier:
                    self._toggle_current_row_expansion_with_space()
                    return True
                if self._handle_arrow_navigation(event.key(), event.modifiers()):
                    return True
        return super().eventFilter(watched, event)

    def _toggle_current_row_expansion_with_space(self) -> None:
        current = self.view.currentIndex()
        if not current.isValid():
            return
        row_anchor = current.siblingAtColumn(0)
        if not row_anchor.isValid():
            return
        self.view.setExpanded(row_anchor, not self.view.isExpanded(row_anchor))

    def _handle_arrow_navigation(self, key: Qt.Key, modifiers: Qt.KeyboardModifier) -> bool:
        """Use arrows for cell navigation; never expand/collapse rows."""
        if modifiers != Qt.KeyboardModifier.NoModifier:
            return False
        if key not in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            return False

        current = self.view.currentIndex()
        if not current.isValid():
            return True

        target = QModelIndex(current)
        if key == Qt.Key.Key_Left:
            target = current.siblingAtColumn(max(0, current.column() - 1))
        elif key == Qt.Key.Key_Right:
            last_col = max(0, self.view.model().columnCount(current.parent()) - 1)
            target = current.siblingAtColumn(min(last_col, current.column() + 1))
        elif key == Qt.Key.Key_Up:
            above = self.view.indexAbove(current)
            if above.isValid():
                target = above
        elif key == Qt.Key.Key_Down:
            below = self.view.indexBelow(current)
            if below.isValid():
                target = below

        self.view.setCurrentIndex(target)
        return True

    def __init__(
        self,
        update_actions_callback,
        status_message_callback: Callable[[str, int], None] | None = None,
        data: Any = _DEFAULT_DATA,
        file_path: str | None = None,
        show_root: bool = False,
        parent=None,
        permanent_message_callback: Callable[[str], None] | None = None,
        theme: ThemeSpec | None = None,
        icon_provider: IconProvider | None = None,
    ):
        super().__init__(parent)

        self._status_message_callback = status_message_callback
        self._permanent_message_callback = permanent_message_callback
        self._theme = theme or LIGHT_DEFAULT
        self._icon_provider: IconProvider = icon_provider or StubIconProvider()
        self._monospace_fields_enabled = False

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
        self.set_monospace_fields_enabled(self._monospace_fields_enabled)
        init_shortcuts(self)
        init_search_filter(self)
        self._diff_applier = DiffApplier(self)

        self.undo_stack.cleanChanged.connect(self._on_clean_changed)
        self.undo_stack.setClean()
        self._set_dirty(False)

    def set_theme(self, theme: ThemeSpec, icon_provider: IconProvider | None = None) -> None:
        self._theme = theme
        self._icon_provider = icon_provider or self._icon_provider
        self.value_delegate.set_theme(theme)
        self.type_delegate.set_theme(theme)
        self.type_delegate.set_icon_provider(self._icon_provider)
        self.model.set_icon_provider(self._icon_provider)

        roles = [
            Qt.ItemDataRole.ForegroundRole,
            Qt.ItemDataRole.BackgroundRole,
            Qt.ItemDataRole.FontRole,
            Qt.ItemDataRole.DecorationRole,
        ]

        def emit_ranges(parent: QModelIndex) -> None:
            rows = self.model.rowCount(parent)
            if rows <= 0:
                return

            top_left = self.model.index(0, 0, parent)
            bottom_right = self.model.index(rows - 1, self.model.columnCount(parent) - 1, parent)
            self.model.dataChanged.emit(top_left, bottom_right, roles)

            for row in range(rows):
                child_parent = self.model.index(row, 0, parent)
                emit_ranges(child_parent)

        emit_ranges(QModelIndex())

    def set_monospace_fields_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._monospace_fields_enabled == enabled:
            return
        self._monospace_fields_enabled = enabled
        self.name_delegate.set_monospace_fields_enabled(enabled)
        self.value_delegate.set_monospace_fields_enabled(enabled)
        self.view.viewport().update()

    @staticmethod
    def _proxy_to_source(index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return proxy_to_source(index)

    def _source_to_view(self, source_index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        return source_to_view(self, source_index)

    def _apply_filter(self) -> None:
        self.proxy.set_filter_text(self.search_edit.text())

    def _on_model_reset(self) -> None:
        # Force-resize so a brand-new model always gets snug initial widths,
        # regardless of whether the user had previously hand-resized those cols.
        self.resize_key_columns(force=True)

    def resize_key_columns(self, force: bool = False) -> None:
        """Snap name/type columns to content width.

        When *force* is False (the default), columns that the user has
        manually resized (tracked in ``_user_sized_columns``) are left alone.
        Pass ``force=True`` (e.g. on model reset) to override.
        """
        self._programmatic_column_resize = True
        try:
            for col in (0, 1):
                if force or col not in self._user_sized_columns:
                    self.view.resizeColumnToContents(col)
        finally:
            self._programmatic_column_resize = False

    def _scale_columns_for_font(self, old_pt: int, new_pt: int) -> None:
        """Proportionally scale name/type column widths when the font changes.

        Columns the user has hand-resized are left alone.  The value column
        (col 2) is never touched because it is set to stretch.
        """
        if old_pt <= 0 or new_pt <= 0 or old_pt == new_pt:
            return
        scale = new_pt / old_pt
        self._programmatic_column_resize = True
        try:
            for col in (0, 1):
                if col in self._user_sized_columns:
                    continue  # respect the user's manual choice
                current = self.view.columnWidth(col)
                new_w = max(20, min(2000, int(current * scale)))
                self.view.setColumnWidth(col, new_w)
        finally:
            self._programmatic_column_resize = False

    def _set_font_pt(self, pt: int) -> None:
        clamped = max(6, min(48, int(pt)))
        self._font_pt = clamped
        font = self.view.font()
        font.setPointSize(clamped)
        self.view.setFont(font)

    def zoom_in(self) -> None:
        old_pt = self._font_pt
        self._set_font_pt(self._font_pt + 1)
        self._scale_columns_for_font(old_pt, self._font_pt)

    def zoom_out(self) -> None:
        old_pt = self._font_pt
        self._set_font_pt(self._font_pt - 1)
        self._scale_columns_for_font(old_pt, self._font_pt)

    def zoom_reset(self) -> None:
        old_pt = self._font_pt
        self._set_font_pt(self._default_font_pt)
        self._scale_columns_for_font(old_pt, self._font_pt)

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

    def edit_name_or_value_from_enter(self) -> None:
        """Start editing from Enter with type-column support.

        - Name/Value columns: edit the current editable cell.
        - Type column: open the inline type combobox editor.
        """
        if self.view.state() == QAbstractItemView.State.EditingState:
            return
        current = self.view.currentIndex()
        if not current.isValid():
            return

        if current.column() == 1:
            if self.view.model().flags(current) & Qt.ItemFlag.ItemIsEditable:
                self.view.edit(current)
                QTimer.singleShot(0, self._open_active_type_combo_popup)
            return

        candidates: list[QModelIndex] = []
        if current.column() in (0, 2):
            candidates.append(current)
        candidates.extend((current.siblingAtColumn(2), current.siblingAtColumn(0)))

        model = self.view.model()
        for idx in candidates:
            if not idx.isValid():
                continue
            if not (model.flags(idx) & Qt.ItemFlag.ItemIsEditable):
                continue
            self.view.setCurrentIndex(idx)
            self.view.edit(idx)
            return

    def _open_active_type_combo_popup(self) -> None:
        for combo in self.view.findChildren(QComboBox):
            if combo.parent() is self.view.viewport() and combo.isVisible():
                combo.showPopup()
                return

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
        return self._diff_applier.apply(item, target, item_index)

    # -- low-level mutators used by diff and typed commands --------------

    def _emit_row_changed(self, item_index: QModelIndex) -> None:
        self._diff_applier.emit_row_changed(item_index)

    def _clear_children(self, item: JsonTreeItem, item_index: QModelIndex) -> None:
        self._diff_applier.clear_children(item, item_index)

    def _convert_container(
        self,
        item: JsonTreeItem,
        item_index: QModelIndex,
        new_type: JsonType,
        value: Any,
    ) -> None:
        self._diff_applier.convert_container(item, item_index, new_type, value)

    def _convert_to_leaf(self, item: JsonTreeItem, item_index: QModelIndex, target: Any) -> None:
        self._diff_applier.convert_to_leaf(item, item_index, target)

    def _insert_typed_item(
        self,
        parent_item: JsonTreeItem,
        parent_index: QModelIndex,
        position: int,
        value: Any,
        name: str | int | None = None,
    ) -> bool:
        return self._diff_applier.insert_typed_item(parent_item, parent_index, position, value, name=name)

    def _diff_object(self, item: JsonTreeItem, target_dict: dict, item_index: QModelIndex) -> bool:
        return self._diff_applier.diff_object(item, target_dict, item_index)

    def _diff_array(self, item: JsonTreeItem, target_list: list, item_index: QModelIndex) -> bool:
        return self._diff_applier.diff_array(item, target_list, item_index)

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
