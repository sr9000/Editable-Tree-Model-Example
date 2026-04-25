# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

import base64
import gzip
import zlib
from contextlib import contextmanager
from typing import Any, Mapping, Optional

import gmpy2
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from enums import JsonType
from mpq2py import mpq_serialization
from tree_item import JsonTreeItem


class JsonTreeModel(QAbstractItemModel):
    def __init__(
        self,
        data: Mapping[str, Any],
        /,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.root_item = JsonTreeItem(None, data)

    def get_item(self, index: QModelIndex) -> JsonTreeItem:
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
        if index.isValid():
            default = QAbstractItemModel.flags(self, index)
            if index.column() == 2:
                item = index.internalPointer()
                match item.json_type:
                    case JsonType.NULL | JsonType.ARRAY | JsonType.OBJECT:
                        return default
                    case JsonType.STRING | JsonType.MULTILINE:
                        if len(item.value) > 10_000:
                            return default
                    case JsonType.BYTES:
                        binary = base64.b64decode(item.value, validate=True)
                        if len(binary) > 10_000:
                            return default
                    case JsonType.ZLIB:
                        raw = base64.b64decode(item.value, validate=True)
                        uncompressed = zlib.decompress(raw)
                        if len(uncompressed) > 10_000:
                            return default
                    case JsonType.GZIP:
                        raw = base64.b64decode(item.value, validate=True)
                        uncompressed = gzip.decompress(raw)
                        if len(uncompressed) > 10_000:
                            return default
            # Combine flags with ItemIsEditable
            return default | Qt.ItemFlag.ItemIsEditable
        return Qt.ItemFlag.NoItemFlags

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if parent.isValid() and parent.column() != 0:
            return QModelIndex()
        if childItem := self.get_item(parent).child(row):
            return self.createIndex(row, column, childItem)
        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
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
    def columns_insertion(self, parent: QModelIndex, position: int, columns: int):
        self.beginInsertColumns(parent, position, position + columns - 1)
        try:
            yield
        finally:
            self.endInsertColumns()

    def insertColumns(self, position: int, columns: int, parent: QModelIndex = QModelIndex()) -> bool:
        with self.columns_insertion(parent, position, columns):
            return self.root_item.insert_columns(position, columns)

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
    def columns_removal(self, parent: QModelIndex, position: int, columns: int):
        self.beginRemoveColumns(parent, position, position + columns - 1)
        try:
            yield
        finally:
            self.endRemoveColumns()
            self.cleanup_columns_removal()

    def cleanup_columns_removal(self):
        """Remove rows if there are no columns left."""
        if self.root_item.column_count() == 0:
            self.removeRows(0, self.rowCount())

    def removeColumns(self, position: int, columns: int, parent: QModelIndex = QModelIndex()) -> bool:
        with self.columns_removal(parent, position, columns):
            return self.root_item.remove_columns(position, columns)

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
        if role == Qt.ItemDataRole.EditRole:
            if self.get_item(index).set_data(index.column(), value):
                roles = [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole]
                self.dataChanged.emit(index, index, roles)
                return True
        return False

    def setHeaderData(
        self,
        section: int,
        orientation: Qt.Orientation,
        value: Any,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if role == Qt.ItemDataRole.EditRole and orientation == Qt.Orientation.Horizontal:
            if self.root_item.set_data(section, value):
                self.headerDataChanged.emit(orientation, section, section)
                return True
        return False
