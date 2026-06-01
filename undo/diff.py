from typing import Any

from PySide6.QtCore import QModelIndex, Qt

from tree.item import JsonTreeItem
from tree.types import (TEXT_FAMILY, JsonType, parse_json_type,
                        text_pseudotype_for)


class DiffApplier:
    def __init__(self, tab):
        self._tab = tab

    def apply(self, item: JsonTreeItem, target: Any, item_index: QModelIndex) -> bool:
        if isinstance(target, dict):
            if item.json_type is JsonType.OBJECT:
                return self.diff_object(item, target, item_index)
            self.convert_container(item, item_index, JsonType.OBJECT, target)
            return True
        if isinstance(target, list):
            if item.json_type is JsonType.ARRAY:
                return self.diff_array(item, target, item_index)
            self.convert_container(item, item_index, JsonType.ARRAY, target)
            return True

        if item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
            self.convert_to_leaf(item, item_index, target)
            return True

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
                self.convert_container(item, item_index, new_type, target)
                return True
            item._apply_typed_value(new_type, target)
        self.emit_row_changed(item_index)
        return True

    def emit_row_changed(self, item_index: QModelIndex) -> None:
        if item_index.isValid():
            row = item_index.row()
            parent = item_index.parent()
            top = self._tab.model.index(row, 0, parent)
            bot = self._tab.model.index(row, 2, parent)
            self._tab.model.dataChanged.emit(
                top,
                bot,
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
            )

    def clear_children(self, item: JsonTreeItem, item_index: QModelIndex) -> None:
        n = len(item.child_items)
        if n > 0:
            self._tab.model.beginRemoveRows(item_index, 0, n - 1)
            item.child_items.clear()
            item.mark_children_dirty()
            self._tab.model.endRemoveRows()

    def convert_container(
        self,
        item: JsonTreeItem,
        item_index: QModelIndex,
        new_type: JsonType,
        value: Any,
    ) -> None:
        self.clear_children(item, item_index)
        item.json_type = new_type
        item.value = {} if new_type is JsonType.OBJECT else []
        item.editable = item._compute_editable()
        if new_type is JsonType.OBJECT:
            pairs = list(value.items())
        else:
            pairs = [(None, v) for v in value]
        if pairs:
            self._tab.model.beginInsertRows(item_index, 0, len(pairs) - 1)
            for name, v in pairs:
                item.child_items.append(JsonTreeItem(item, v, name, secret_name_predicate=item._secret_name_predicate))
            item.mark_children_dirty()
            self._tab.model.endInsertRows()
        self.emit_row_changed(item_index)

    def convert_to_leaf(self, item: JsonTreeItem, item_index: QModelIndex, target: Any) -> None:
        self.clear_children(item, item_index)
        new_type = parse_json_type(target)
        item._apply_typed_value(new_type, target)
        self.emit_row_changed(item_index)

    def insert_typed_item(
        self,
        parent_item: JsonTreeItem,
        parent_index: QModelIndex,
        position: int,
        value: Any,
        name: str | int | None = None,
    ) -> bool:
        new_item = JsonTreeItem(parent_item, value, name, secret_name_predicate=parent_item._secret_name_predicate)
        self._tab.model.beginInsertRows(parent_index, position, position)
        parent_item.child_items.insert(position, new_item)
        parent_item.mark_children_dirty()
        self._tab.model.endInsertRows()
        return True

    def diff_object(self, item: JsonTreeItem, target_dict: dict, item_index: QModelIndex) -> bool:
        target_names = list(target_dict.keys())
        target_name_set = set(target_names)

        for i in range(len(item.child_items) - 1, -1, -1):
            if item.child_items[i].name not in target_name_set:
                self._tab.model.removeRow(i, item_index)

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
                self.insert_typed_item(item, item_index, target_pos, target_value, name=target_name)
                continue
            if cur_pos != target_pos:
                self._tab.model.move_row(item_index, cur_pos, target_pos)
            child = item.child_items[target_pos]
            child_index = self._tab.model.index(target_pos, 0, item_index)
            self.apply(child, target_value, child_index)
        return True

    def diff_array(self, item: JsonTreeItem, target_list: list, item_index: QModelIndex) -> bool:
        target_len = len(target_list)

        while len(item.child_items) > target_len:
            last = len(item.child_items) - 1
            self._tab.model.removeRow(last, item_index)

        for pos in range(target_len):
            target_value = target_list[pos]
            if pos >= len(item.child_items):
                self.insert_typed_item(item, item_index, pos, target_value, name=None)
                continue
            child = item.child_items[pos]
            child_index = self._tab.model.index(pos, 0, item_index)
            self.apply(child, target_value, child_index)
        return True
