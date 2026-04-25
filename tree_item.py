# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from typing import Any

from enums import JsonType, parse_json_type


class JsonTreeItem:
    def __init__(
        self,
        parent_item: "JsonTreeItem" = None,
        value: Any = None,
        name: str | int = None,
    ) -> None:
        self.parent_item: "JsonTreeItem" = parent_item

        self.json_type = parse_json_type(value)
        self.value = value
        self.name = name

        self.child_items: list["JsonTreeItem"] = []

        match self.json_type:
            case JsonType.ARRAY:
                self.child_items = [JsonTreeItem(self, x) for i, x in enumerate(value)]
                self.value = []
            case JsonType.OBJECT:
                self.child_items = [JsonTreeItem(self, v, k) for k, v in value.items()]
                self.value = {}

    def to_json(self) -> Any:
        match self.json_type:
            case JsonType.ARRAY:
                return [t.to_json() for t in self.child_items]
            case JsonType.OBJECT:
                return {t.name: t.to_json() for t in self.child_items}

        return self.value

    def append_child(self, child: "JsonTreeItem") -> None:
        self.child_items.append(child)

    def parent(self) -> "JsonTreeItem | None":
        return self.parent_item

    def child(self, number: int) -> "JsonTreeItem | None":
        if 0 <= number < len(self.child_items):
            return self.child_items[number]

    def child_count(self) -> int:
        return len(self.child_items)

    def row(self) -> int:
        return 0 if self.parent_item is None else self.parent_item.child_items.index(self)

    def column_count(self) -> int:
        return 3

    def data(self, column: int) -> Any:
        match column:
            case 0:
                return self.name if self.name is not None else "<no name>"
            case 1:
                return self.json_type or "<no type>"
            case 2:
                return self.value

        raise IndexError(f"`JsonTreeItem.data()` does not support {column=}")

    def set_data(self, column: int, value: Any) -> bool:
        # Only value edits are allowed; name/type changes are not supported here
        if column != 2:
            return False

        # Preserve the raw type: ints/bools/mpq/strings as provided by delegates
        self.value = value
        return True

    def insert_children(self, position: int, count: int, columns: int) -> bool:
        if 0 <= position <= len(self.child_items):
            self.child_items[position:position] = [
                JsonTreeItem(parent_item=self, value=[None] * columns) for _ in range(count)
            ]
            return True
        return False

    def remove_children(self, begin: int, count: int) -> bool:
        end = begin + count
        if 0 <= begin and end <= len(self.child_items):
            del self.child_items[begin:end]
            return True
        return False

    def insert_columns(self, position: int, columns: int) -> bool:
        # Columns API is not used for this JSON model; return False to keep interface consistent
        return False

    def remove_columns(self, begin: int, columns: int) -> bool:
        """declared but not implemented in c++"""
        return False
