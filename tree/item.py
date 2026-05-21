# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

import datetime
from typing import Any

from datetime_editor.enums import DateTimeCategory
from datetime_editor.regex import parse_datetime_text
from tree.item_coercion import coerce_value_for_type, compute_editable, normalize_value_for_type
from tree.item_names import unique_child_name, validated_child_name
from tree.types import DATETIME_FAMILY, TEXT_FAMILY, JsonType, parse_json_type, text_pseudotype_for
from tree.types_datetime import convert_datetime


class JsonTreeItem:
    EDITABLE_BLOB_LIMIT = 10_000

    def __init__(
        self,
        parent_item: "JsonTreeItem | None" = None,
        value: Any = None,
        name: str | int = None,
    ) -> None:
        self.parent_item: "JsonTreeItem | None" = parent_item

        self.name = name
        self.child_items: list["JsonTreeItem"] = []
        self.explicit_type = False

        # Cached row-in-parent index for O(1) ``row()`` lookups. The parent
        # owns the dirty flag below; when it flips True any of its children
        # may have stale ``_row_in_parent``, and the next ``row()`` call on
        # any child re-numbers the whole sibling list in one O(K) pass.
        self._row_in_parent: int = -1
        self._children_dirty: bool = True

        self.json_type = parse_json_type(value)
        self.value = None
        self._apply_typed_value(self.json_type, value)

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
        self._children_dirty = True

    def parent(self) -> "JsonTreeItem | None":
        return self.parent_item

    def child(self, number: int) -> "JsonTreeItem | None":
        if 0 <= number < len(self.child_items):
            return self.child_items[number]

    def child_count(self) -> int:
        return len(self.child_items)

    def row(self) -> int:
        parent = self.parent_item
        if parent is None:
            return 0
        if parent._children_dirty:
            # Re-number all siblings in one pass; subsequent row() calls on
            # any sibling are O(1) until the parent's child_items mutates.
            for i, c in enumerate(parent.child_items):
                c._row_in_parent = i
            parent._children_dirty = False
        return self._row_in_parent

    def mark_children_dirty(self) -> None:
        """Flag that ``self.child_items`` was mutated externally.

        Call this whenever a non-``JsonTreeItem`` API touches ``child_items``
        directly (e.g. ``tree_model.move_row`` doing ``pop`` + ``insert``,
        ``sort_keys`` doing an in-place sort, ``change_type`` clearing the
        list). Lazy re-numbering keeps ``row()`` O(1) on subsequent reads.
        """
        self._children_dirty = True

    def column_count(self) -> int:
        return 3

    def data(self, column: int) -> Any:
        match column:
            case 0:
                if self.parent_item is not None and self.parent_item.json_type is JsonType.ARRAY:
                    return f"#{self.row() + 1}"
                return self.name if self.name is not None else "<no name>"
            case 1:
                return self.json_type or "<no type>"
            case 2:
                return self.value

        raise IndexError(f"`JsonTreeItem.data()` does not support {column=}")

    def set_data(self, column: int, value: Any) -> bool:
        if column == 0:
            return self._set_name(value)

        if column == 1:
            try:
                new_type = value if isinstance(value, JsonType) else JsonType(str(value))
            except ValueError:
                return False

            # 3.5: ARRAY↔OBJECT morph — preserve children in-place.
            # Must intercept here (before model.change_type clears children).
            if (
                new_type in (JsonType.ARRAY, JsonType.OBJECT)
                and self.json_type in (JsonType.ARRAY, JsonType.OBJECT)
                and new_type is not self.json_type
            ):
                return self._morph_container(new_type)

            # Save old_type so coercion can re-encode bytes-family values correctly.
            old_type = self.json_type
            old_value = self.to_json() if self.json_type in (JsonType.ARRAY, JsonType.OBJECT) else self.value

            if old_type in DATETIME_FAMILY and new_type in DATETIME_FAMILY and isinstance(old_value, str):
                converted = self._convert_datetime_text(old_value, old_type, new_type)
                if converted is not None:
                    self.explicit_type = True
                    self._apply_typed_value(new_type, converted)
                    return True

            ok, coerced = self._coerce_value_for_type(new_type, old_value, strict=False, old_type=old_type)
            if not ok:
                return False

            if isinstance(coerced, str) and new_type in TEXT_FAMILY:
                # Keep pseudo text kinds canonical for current content when
                # user changes type manually in column 1.
                new_type = text_pseudotype_for(new_type, coerced)

            self.explicit_type = True
            self._apply_typed_value(new_type, coerced)
            return True

        if column == 2:
            if self.explicit_type:
                ok, coerced = self._coerce_value_for_type(self.json_type, value, strict=True)
                if not ok:
                    return False
                if isinstance(coerced, str) and self.json_type in TEXT_FAMILY:
                    # Pseudo text types auto-track ASCII vs non-ASCII even when
                    # type was explicitly chosen.
                    self._apply_typed_value(text_pseudotype_for(self.json_type, coerced), coerced)
                else:
                    self._apply_typed_value(self.json_type, coerced)
                return True

            if isinstance(value, str) and self.json_type in TEXT_FAMILY:
                self._apply_typed_value(text_pseudotype_for(self.json_type, value), value)
                return True

            inferred_type = parse_json_type(value)
            self._apply_typed_value(inferred_type, value)
            return True

        return False

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
            self._children_dirty = True
            return True
        return False

    def remove_children(self, begin: int, count: int) -> bool:
        end = begin + count
        if 0 <= begin and end <= len(self.child_items):
            del self.child_items[begin:end]
            self._children_dirty = True
            return True
        return False

    def insert_columns(self, position: int, columns: int) -> bool:
        # Columns API is not used for this JSON model; return False to keep interface consistent
        return False

    def remove_columns(self, begin: int, columns: int) -> bool:
        """declared but not implemented in c++"""
        return False

    def _unique_child_name(self, base: str = "new_key", used_names: set[str] | None = None) -> str:
        return unique_child_name(self.child_items, base=base, used_names=used_names)

    def _normalize_value_for_type(self, value: Any) -> Any:
        return normalize_value_for_type(self.json_type, value)

    def _apply_typed_value(self, json_type: JsonType, value: Any) -> None:
        self.json_type = json_type
        self.child_items = []
        self._children_dirty = True

        match json_type:
            case JsonType.ARRAY:
                arr = value if isinstance(value, list) else []
                self.child_items = [JsonTreeItem(self, x) for x in arr]
                self.value = []
            case JsonType.OBJECT:
                obj = value if isinstance(value, dict) else {}
                self.child_items = [JsonTreeItem(self, v, k) for k, v in obj.items()]
                self.value = {}
            case _:
                self.value = self._normalize_value_for_type(value)

        self.editable = self._compute_editable()

    def _set_name(self, value: Any) -> bool:
        candidate = validated_child_name(self.parent_item, self, value)
        if candidate is None:
            return False

        self.name = candidate
        return True

    def _morph_container(self, new_type: JsonType) -> bool:
        """Mutate ARRAY→OBJECT or OBJECT→ARRAY in-place, preserving children.

        ARRAY→OBJECT: assign deterministic names ``item1, item2, …`` to children
        that currently have no name.
        OBJECT→ARRAY: drop all child names (set to ``None``).
        """
        if new_type is JsonType.OBJECT:
            for i, child in enumerate(self.child_items, 1):
                if child.name is None:
                    child.name = f"item{i}"
        else:  # JsonType.ARRAY
            for child in self.child_items:
                child.name = None
        self.json_type = new_type
        self.explicit_type = True
        self.value = [] if new_type is JsonType.ARRAY else {}
        self.editable = False
        self._children_dirty = True
        return True

    def _coerce_value_for_type(
        self, json_type: JsonType, value: Any, strict: bool, old_type: JsonType | None = None
    ) -> tuple[bool, Any]:
        return coerce_value_for_type(json_type, value, strict, old_type=old_type)

    def _compute_editable(self) -> bool:
        return compute_editable(self.json_type, self.value, self.EDITABLE_BLOB_LIMIT)

    @staticmethod
    def _datetime_category_for_type(json_type: JsonType) -> DateTimeCategory | None:
        match json_type:
            case JsonType.DATE:
                return DateTimeCategory.Date
            case JsonType.TIME:
                return DateTimeCategory.Time
            case JsonType.DATETIME:
                return DateTimeCategory.DateTime
            case JsonType.DATETIMEZONE:
                return DateTimeCategory.DateTimeWithTZ
            case JsonType.DATETIMEUTC:
                return DateTimeCategory.DateTimeUTC
            case _:
                return None

    def _convert_datetime_text(self, value: str, src: JsonType, dst: JsonType) -> str | None:
        src_category = self._datetime_category_for_type(src)
        if src_category is None:
            return None
        parsed = parse_datetime_text(value, src_category)
        if parsed is None:
            return None
        converted = convert_datetime(parsed, src, dst)
        if isinstance(converted, datetime.date) and not isinstance(converted, datetime.datetime):
            return converted.isoformat()
        if isinstance(converted, datetime.time):
            return converted.isoformat()
        if isinstance(converted, datetime.datetime):
            if dst is JsonType.DATETIME:
                return converted.replace(tzinfo=None).isoformat()
            if dst is JsonType.DATETIMEZONE:
                aware = converted if converted.tzinfo is not None else converted.replace(tzinfo=datetime.timezone.utc)
                return aware.isoformat()
            if dst is JsonType.DATETIMEUTC:
                aware = (
                    converted if converted.tzinfo is not None else converted.replace(tzinfo=datetime.timezone.utc)
                ).astimezone(datetime.timezone.utc)
                return aware.isoformat().replace("+00:00", "Z")
        return None
