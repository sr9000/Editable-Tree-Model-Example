# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

import base64
import binascii
import gzip
import zlib
from typing import Any

from enums import JsonType, parse_json_type


class JsonTreeItem:
    EDITABLE_BLOB_LIMIT = 10_000

    def __init__(
        self,
        parent_item: "JsonTreeItem" = None,
        value: Any = None,
        name: str | int = None,
    ) -> None:
        self.parent_item: "JsonTreeItem" = parent_item

        self.name = name
        self.child_items: list["JsonTreeItem"] = []

        self.json_type = parse_json_type(value)
        self.value = self._normalize_value_for_type(value)

        match self.json_type:
            case JsonType.ARRAY:
                self.child_items = [JsonTreeItem(self, x) for x in value]
                self.value = []
            case JsonType.OBJECT:
                self.child_items = [JsonTreeItem(self, v, k) for k, v in value.items()]
                self.value = {}

        self.editable = self._compute_editable()

    def to_json(self) -> Any:
        match self.json_type:
            case JsonType.ARRAY:
                return [t.to_json() for t in self.child_items]
            case JsonType.OBJECT:
                for child in self.child_items:
                    if child.name is None:
                        raise ValueError(f"OBJECT child has no name (row {child.row()})")
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
        if column != 2:
            return False

        self.child_items = []
        self.json_type = parse_json_type(value)
        self.value = self._normalize_value_for_type(value)

        match self.json_type:
            case JsonType.ARRAY:
                self.child_items = [JsonTreeItem(self, x) for x in value]
                self.value = []
            case JsonType.OBJECT:
                self.child_items = [JsonTreeItem(self, v, k) for k, v in value.items()]
                self.value = {}

        self.editable = self._compute_editable()
        return True

    def insert_children(self, position: int, count: int, _columns: int) -> bool:
        if 0 <= position <= len(self.child_items):
            reserved_names: set[str] = set()
            new_items = []
            for _ in range(count):
                child_name = (
                    self._unique_child_name(used_names=reserved_names) if self.json_type is JsonType.OBJECT else None
                )
                if child_name is not None:
                    reserved_names.add(child_name)
                new_items.append(JsonTreeItem(parent_item=self, value=None, name=child_name))

            self.child_items[position:position] = new_items
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

    def _unique_child_name(self, base: str = "new_key", used_names: set[str] | None = None) -> str:
        used = {child.name for child in self.child_items if isinstance(child.name, str)}
        if used_names is not None:
            used |= used_names

        if base not in used:
            return base

        i = 2
        while f"{base}_{i}" in used:
            i += 1
        return f"{base}_{i}"

    def _normalize_value_for_type(self, value: Any) -> Any:
        if self.json_type is JsonType.STRING and not isinstance(value, str):
            return repr(value)
        return value

    def _compute_editable(self) -> bool:
        if self.json_type in (JsonType.NULL, JsonType.ARRAY, JsonType.OBJECT):
            return False

        try:
            match self.json_type:
                case JsonType.STRING | JsonType.MULTILINE:
                    return len(self.value) <= self.EDITABLE_BLOB_LIMIT
                case JsonType.BYTES:
                    raw = base64.b64decode(self.value, validate=True)
                    return len(raw) <= self.EDITABLE_BLOB_LIMIT
                case JsonType.ZLIB:
                    raw = base64.b64decode(self.value, validate=True)
                    return len(zlib.decompress(raw)) <= self.EDITABLE_BLOB_LIMIT
                case JsonType.GZIP:
                    raw = base64.b64decode(self.value, validate=True)
                    return len(gzip.decompress(raw)) <= self.EDITABLE_BLOB_LIMIT
                case _:
                    return True
        except (binascii.Error, zlib.error, OSError, ValueError, TypeError):
            return False
