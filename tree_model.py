# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from contextlib import contextmanager
from typing import Any, Mapping, Optional

import gmpy2
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, Qt, Signal

from enums import JsonType
from mpq2py import mpq_serialization
from tree_item import JsonTreeItem


class JsonTreeModel(QAbstractItemModel):
    typeChanged = Signal(QModelIndex, bool)

    def __init__(
        self,
        data: Mapping[str, Any],
        /,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.root_item = JsonTreeItem(None, data)

    def get_item(self, index) -> JsonTreeItem:
        if index.isValid() and (item := index.internalPointer()):
            return item
        return self.root_item

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() and parent.column() != 0:
            return 0  # No children for column != 0
        return self.get_item(parent).child_count()

    def columnCount(self, _: QModelIndex = QModelIndex()) -> int:
        return self.root_item.column_count()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags

        default = QAbstractItemModel.flags(self, index)
        item = self.get_item(index)

        if index.column() == 0:
            parent_item = item.parent()
            if parent_item is not None and parent_item.json_type is JsonType.OBJECT:
                return default | Qt.ItemFlag.ItemIsEditable
            return default

        if index.column() == 1:
            return default | Qt.ItemFlag.ItemIsEditable

        return default | Qt.ItemFlag.ItemIsEditable if item.editable else default

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()
        if childItem := self.get_item(parent).child(row):
            return self.createIndex(row, column, childItem)
        return QModelIndex()

    def parent(self, index: QModelIndex | QPersistentModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()

        parent_item = self.get_item(index).parent()

        if parent_item not in (self.root_item, None):
            return self.createIndex(parent_item.row(), 0, parent_item)
        return QModelIndex()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if index.isValid() and role in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
        ):
            data = self.get_item(index).data(index.column())
            match data:
                case bool():
                    # Show JSON-style lowercase
                    return "true" if data else "false"
                case gmpy2.mpq():
                    data = mpq_serialization(data)[0]
                case None:
                    return "null"

            return str(data)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ["Name", "Type", "Value"][section]

    @contextmanager
    def rows_insertion(self, parent: QModelIndex, position: int, rows: int):
        self.beginInsertRows(parent, position, position + rows - 1)
        try:
            yield
        finally:
            self.endInsertRows()

    def insertRows(self, position: int, rows: int, parent: QModelIndex = QModelIndex()) -> bool:
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
            roles = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
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
        had_children = item.json_type in (JsonType.ARRAY, JsonType.OBJECT)
        old_child_count = item.child_count()
        value_parent_index = self.index(index.row(), 0, index.parent())
        lossy = had_children and old_child_count > 0

        if had_children and old_child_count > 0:
            self.beginRemoveRows(value_parent_index, 0, old_child_count - 1)
            item.child_items.clear()
            item.mark_children_dirty()
            self.endRemoveRows()

        if not item.set_data(1, target_type):
            return False

        roles = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
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
