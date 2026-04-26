# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from contextlib import contextmanager
from typing import Any, Optional

import gmpy2
from PySide6.QtCore import QAbstractItemModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QFont

from enums import JsonType
from mpq2py import mpq_serialization
from tree_item import JsonTreeItem

JSON_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1


class JsonTreeModel(QAbstractItemModel):
    typeChanged = Signal(QModelIndex, bool)

    def __init__(
        self,
        data: Any,
        /,
        parent: Optional[Any] = None,
        *,
        show_root: bool = False,
    ) -> None:
        super().__init__(parent)
        self.root_item = JsonTreeItem(None, data)
        self.show_root = show_root

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
            return Qt.ItemFlag.NoItemFlags

        default = QAbstractItemModel.flags(self, index)
        item = self.get_item(index)

        if index.column() == 0:
            if item is self.root_item:
                return default
            parent_item = item.parent()
            if parent_item is not None and parent_item.json_type is JsonType.OBJECT:
                return default | Qt.ItemFlag.ItemIsEditable
            return default

        if index.column() == 1:
            return default | Qt.ItemFlag.ItemIsEditable

        return default | Qt.ItemFlag.ItemIsEditable if item.editable else default

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
            if item is not self.root_item and isinstance(item.name, str) and any(ord(ch) > 127 for ch in item.name):
                font = QFont()
                font.setItalic(True)
                return font
            return None

        if role == JSON_TYPE_ROLE and index.column() == 2:
            return item.json_type

        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 2:
            raw = item.data(2)
            text = "" if raw is None else str(raw)
            if len(text) <= 80:
                return None
            return text[:4096] + ("…" if len(text) > 4096 else "")

        if role == Qt.ItemDataRole.EditRole:
            if item is self.root_item and index.column() == 0:
                return "<root>"
            return item.data(index.column())

        if role == Qt.ItemDataRole.DisplayRole:
            if item is self.root_item and index.column() == 0:
                return "<root>"
            data = item.data(index.column())
            match data:
                case bool():
                    # Show JSON-style lowercase
                    return "true" if data else "false"
                case gmpy2.mpq():
                    data = mpq_serialization(data)[0]
                case None:
                    return "null"

            return str(data)

        return None

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

        roles = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.FontRole]
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
