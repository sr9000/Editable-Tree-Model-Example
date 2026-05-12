# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from contextlib import contextmanager
from typing import Any, Optional, cast

from PySide6.QtCore import QAbstractItemModel, QMimeData, QModelIndex, QPersistentModelIndex, Qt, QTimer, Signal

from themes.icon_provider import IconProvider, StubIconProvider
from tree.item import JsonTreeItem
from tree.model_roles import (
    JSON_TYPE_ROLE,
    display_role_value,
    edit_role_value,
    font_role_for_name,
    tooltip_role_for_value,
)
from tree.types import JsonType


class JsonTreeModel(QAbstractItemModel):
    typeChanged = Signal(QModelIndex, bool)

    def __init__(
        self,
        data: Any,
        /,
        parent: Optional[Any] = None,
        *,
        show_root: bool = False,
        icon_provider: IconProvider | None = None,
    ) -> None:
        super().__init__(parent)
        self.root_item = JsonTreeItem(None, data)
        self.show_root = show_root
        self._icon_provider: IconProvider = icon_provider or StubIconProvider()
        self._attached_view = None
        self._drag_source_rows: list[QModelIndex] = []
        self._suppress_external_remove_rows = False

    def attach_view(self, view) -> None:
        self._attached_view = view

    def consume_drag_source_rows(self) -> list[QModelIndex]:
        rows = list(self._drag_source_rows)
        self._drag_source_rows = []
        return rows

    def arm_external_remove_rows_suppression(self) -> None:
        """Ignore one event-loop tick of external removeRows calls.

        Some Qt drag/drop paths may call removeRows on the source model
        after dropMimeData(MoveAction) returns True. Internal moves are
        already applied via push_move_rows, so the extra remove would delete
        unrelated rows after indexes shift.
        """
        self._suppress_external_remove_rows = True

        def _clear() -> None:
            self._suppress_external_remove_rows = False

        QTimer.singleShot(0, _clear)

    def set_icon_provider(self, provider: IconProvider | None) -> None:
        next_provider = provider or StubIconProvider()
        if next_provider is self._icon_provider:
            return
        self._icon_provider = next_provider

    def _root_index(self) -> QModelIndex:
        if not self.show_root:
            return QModelIndex()
        return self.createIndex(0, 0, self.root_item)

    def get_item(self, index) -> JsonTreeItem:
        if index.isValid() and (item := index.internalPointer()):
            return item
        return self.root_item

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() and parent.column() != 0:
            return 0  # No children for column != 0
        if not parent.isValid() and self.show_root:
            return 1
        return self.get_item(parent).child_count()

    def columnCount(self, _: QModelIndex = QModelIndex()) -> int:
        return self.root_item.column_count()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled

        default = QAbstractItemModel.flags(self, index)
        item = self.get_item(index)

        edit_flags = default

        if index.column() == 0:
            if item is self.root_item:
                edit_flags = default
            else:
                parent_item = item.parent()
                if parent_item is not None and parent_item.json_type is JsonType.OBJECT:
                    edit_flags = default | Qt.ItemFlag.ItemIsEditable

        elif index.column() == 1:
            edit_flags = default | Qt.ItemFlag.ItemIsEditable

        elif item.editable:
            edit_flags = default | Qt.ItemFlag.ItemIsEditable

        if item is not self.root_item:
            edit_flags |= Qt.ItemFlag.ItemIsDragEnabled
        if item is self.root_item or item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
            edit_flags |= Qt.ItemFlag.ItemIsDropEnabled
        return edit_flags

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not parent.isValid() and self.show_root:
            if row == 0:
                return self.createIndex(0, column, self.root_item)
            return QModelIndex()
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()
        if childItem := self.get_item(parent).child(row):
            return self.createIndex(row, column, childItem)
        return QModelIndex()

    def parent(self, index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        parent_item = self.get_item(index).parent()

        if parent_item is self.root_item and self.show_root:
            return self.createIndex(0, 0, self.root_item)

        if parent_item not in (self.root_item, None):
            return self.createIndex(parent_item.row(), 0, parent_item)
        return QModelIndex()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        item = self.get_item(index)

        if role == Qt.ItemDataRole.FontRole and index.column() == 0:
            return font_role_for_name(item, is_root_item=(item is self.root_item))

        if role == Qt.ItemDataRole.DecorationRole and index.column() == 1:
            return self._icon_provider.for_type(item.json_type)

        if role == JSON_TYPE_ROLE and index.column() == 2:
            return item.json_type

        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 2:
            return tooltip_role_for_value(item)

        if role == Qt.ItemDataRole.EditRole:
            return edit_role_value(item, index.column(), is_root_item=(item is self.root_item))

        if role == Qt.ItemDataRole.DisplayRole:
            return display_role_value(item, index.column(), is_root_item=(item is self.root_item))

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["Name", "Type", "Value"][section]

    def mimeTypes(self) -> list[str]:
        from tree_actions.clipboard import MIME_JSON_TREE

        return [MIME_JSON_TREE, "text/plain"]

    def mimeData(self, indexes) -> QMimeData:  # type: ignore[override]
        from tree_actions.clipboard import build_tree_mime

        rows_by_path: dict[tuple[int, ...], QModelIndex] = {}
        for idx in indexes:
            if not idx.isValid():
                continue
            row0 = self.index(idx.row(), 0, idx.parent())
            if not row0.isValid():
                continue
            if self.get_item(row0) is self.root_item:
                continue
            path: list[int] = []
            cursor = row0
            while cursor.isValid():
                path.append(cursor.row())
                cursor = cursor.parent()
            rows_by_path[tuple(reversed(path))] = row0

        source_rows = [rows_by_path[path] for path in sorted(rows_by_path)]
        self._drag_source_rows = source_rows
        mime = build_tree_mime(self, source_rows)
        return mime if mime is not None else QMimeData()

    def supportedDragActions(self) -> Qt.DropAction:
        return cast(Qt.DropAction, Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)

    def supportedDropActions(self) -> Qt.DropAction:
        return cast(Qt.DropAction, Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)

    def canDropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        from tree_actions.dnd import can_drop

        return can_drop(self, data, action, row, column, parent)

    def dropMimeData(
        self,
        data: QMimeData,
        action: Qt.DropAction,
        row: int,
        column: int,
        parent: QModelIndex,
    ) -> bool:
        from tree_actions.dnd import handle_drop

        return handle_drop(self._attached_view, self, data, action, row, column, parent)

    @contextmanager
    def rows_insertion(self, parent: QModelIndex, position: int, rows: int):
        self.beginInsertRows(parent, position, position + rows - 1)
        try:
            yield
        finally:
            self.endInsertRows()

    def insertRows(self, position: int, rows: int, parent: QModelIndex = QModelIndex()) -> bool:
        if self.show_root and not parent.isValid():
            parent = self._root_index()
        if parent_item := self.get_item(parent):
            with self.rows_insertion(parent, position, rows):
                return parent_item.insert_children(position, rows, self.root_item.column_count())
        return False

    @contextmanager
    def rows_removal(self, parent: QModelIndex, position: int, rows: int):
        self.beginRemoveRows(parent, position, position + rows - 1)
        try:
            yield
        finally:
            self.endRemoveRows()

    def removeRows(self, position: int, rows: int, parent: QModelIndex = QModelIndex()) -> bool:
        if self._suppress_external_remove_rows:
            return True
        if self.show_root and not parent.isValid():
            parent = self._root_index()
        if parent_item := self.get_item(parent):
            with self.rows_removal(parent, position, rows):
                return parent_item.remove_children(position, rows)
        return False

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False

        if index.column() == 1:
            return self.change_type(index, value)

        if self.get_item(index).set_data(index.column(), value):
            roles = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.FontRole]
            top = self.index(index.row(), 0, index.parent())
            bot = self.index(index.row(), 2, index.parent())
            self.dataChanged.emit(top, bot, roles)
            return True
        return False

    def change_type(self, index: QModelIndex, new_type: JsonType | str) -> bool:
        if not index.isValid():
            return False

        try:
            target_type = new_type if isinstance(new_type, JsonType) else JsonType(str(new_type))
        except ValueError:
            return False

        item = self.get_item(index)
        value_parent_index = self.index(index.row(), 0, index.parent())

        # 3.5: ARRAY↔OBJECT morph — skip child removal; children are renamed in-place.
        if (
            target_type in (JsonType.ARRAY, JsonType.OBJECT)
            and item.json_type in (JsonType.ARRAY, JsonType.OBJECT)
            and target_type is not item.json_type
        ):
            if not item.set_data(1, target_type):
                return False
            roles = [
                Qt.ItemDataRole.DisplayRole,
                Qt.ItemDataRole.EditRole,
                Qt.ItemDataRole.FontRole,
                Qt.ItemDataRole.DecorationRole,
            ]
            top = self.index(index.row(), 0, index.parent())
            bot = self.index(index.row(), 2, index.parent())
            self.dataChanged.emit(top, bot, roles)
            # Children survived; their name column (col 0) has changed.
            n = item.child_count()
            if n > 0:
                child_top = self.index(0, 0, value_parent_index)
                child_bot = self.index(n - 1, 0, value_parent_index)
                self.dataChanged.emit(child_top, child_bot, [Qt.ItemDataRole.DisplayRole])
            self.typeChanged.emit(top, False)  # not lossy — children preserved
            return True

        had_children = item.json_type in (JsonType.ARRAY, JsonType.OBJECT)
        old_child_count = item.child_count()
        lossy = had_children and old_child_count > 0

        if had_children and old_child_count > 0:
            self.beginRemoveRows(value_parent_index, 0, old_child_count - 1)
            item.child_items.clear()
            item.mark_children_dirty()
            self.endRemoveRows()

        if not item.set_data(1, target_type):
            return False

        roles = [
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
            Qt.ItemDataRole.FontRole,
            Qt.ItemDataRole.DecorationRole,
        ]
        top = self.index(index.row(), 0, index.parent())
        bot = self.index(index.row(), 2, index.parent())
        self.dataChanged.emit(top, bot, roles)
        self.typeChanged.emit(top, lossy)
        return True

    def move_row(self, parent: QModelIndex, src_row: int, dst_row: int) -> bool:
        if src_row == dst_row:
            return False

        parent_item = self.get_item(parent)
        count = parent_item.child_count()
        if not (0 <= src_row < count and 0 <= dst_row < count):
            return False

        # Qt destination index is evaluated after source removal.
        qt_dst = dst_row if dst_row < src_row else dst_row + 1
        if not self.beginMoveRows(parent, src_row, src_row, parent, qt_dst):
            return False

        moved = parent_item.child_items.pop(src_row)
        parent_item.child_items.insert(dst_row, moved)
        parent_item.mark_children_dirty()
        self.endMoveRows()
        return True

    def sort_keys(self, index: QModelIndex, recursive: bool = False) -> bool:
        if not index.isValid() and self.show_root:
            index = self._root_index()

        if not index.isValid():
            return False

        item = self.get_item(index)
        if item.json_type is not JsonType.OBJECT:
            return False

        self.layoutAboutToBeChanged.emit()
        try:
            self._sort_object_item(item, recursive=recursive)
        finally:
            self.layoutChanged.emit()
        return True

    def _sort_object_item(self, item: JsonTreeItem, recursive: bool = False) -> None:
        if item.json_type is JsonType.OBJECT:
            item.child_items.sort(key=lambda c: c.name or "")
            item.mark_children_dirty()

        if not recursive:
            return

        for child in item.child_items:
            if child.json_type is JsonType.OBJECT:
                self._sort_object_item(child, recursive=True)
            elif child.json_type is JsonType.ARRAY:
                for nested in child.child_items:
                    if nested.json_type is JsonType.OBJECT:
                        self._sort_object_item(nested, recursive=True)
