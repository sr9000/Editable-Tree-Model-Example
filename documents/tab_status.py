from PySide6.QtCore import QModelIndex

from delegates.bytes_codec import decode_bytes
from tree.item import JsonTreeItem
from tree.types import JsonType
from units import format_bytes


def size_hint_for_item(item: JsonTreeItem) -> str | None:
    if item.json_type in (JsonType.STRING, JsonType.UNICODE, JsonType.MULTILINE, JsonType.TEXT):
        return f"{len(str(item.value or ''))} chars"
    if item.json_type in (JsonType.OBJECT, JsonType.ARRAY):
        return f"{item.child_count()} items"
    if item.json_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):
        try:
            raw = decode_bytes(str(item.value or ""), item.json_type)
        except Exception:
            return None
        return format_bytes(len(raw))
    return None


def on_current_changed(tab, current: QModelIndex, _previous: QModelIndex) -> None:
    if tab._permanent_message_callback is None:
        return
    if not current.isValid():
        tab._permanent_message_callback("")
        return

    current = tab._proxy_to_source(current)
    row0 = current.siblingAtColumn(0)
    if not row0.isValid():
        tab._permanent_message_callback("")
        return

    item = tab.model.get_item(row0)
    breadcrumb = tab._qualified_name(row0)
    item_type = item.json_type.value
    size_hint = size_hint_for_item(item)
    extra = f", {size_hint}" if size_hint else ""
    tab._permanent_message_callback(f"{breadcrumb}  ({item_type}{extra})")
