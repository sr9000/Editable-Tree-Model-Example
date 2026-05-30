from PySide6.QtCore import QModelIndex

from delegates.bytes_codec import decode_bytes
from tree.item import JsonTreeItem
from tree.types import TEXT_FAMILY, JsonType
from units import counts, format_bytes


def format_validation_status(issue_index) -> str:
    """Return a short human-readable summary of *issue_index* for status bars.

    Returns an empty string when there are no issues (caller should hide the
    widget).  Example non-empty returns: ``"Validation: 3 errors · 1 warning"``.
    """
    n = len(issue_index)
    if n == 0:
        return ""
    count = len(issue_index.all_issues())
    return "Validation: " + f"{count} issue{'s' if count != 1 else ''}"


def size_hint_for_item(item: JsonTreeItem) -> str | None:
    if item.json_type in TEXT_FAMILY:
        return f"{counts(len(str(item.value or '')))} chars"
    if item.json_type is JsonType.ARRAY:
        return f"{counts(item.child_count())} items"
    if item.json_type is JsonType.OBJECT:
        return f"{counts(item.child_count())} keys"
    if item.json_type in (JsonType.BYTES, JsonType.ZLIB, JsonType.GZIP):
        try:
            raw = decode_bytes(str(item.value or ""), item.json_type)
        except Exception:
            return None
        return format_bytes(len(raw))
    return None


def on_current_changed(tab, current: QModelIndex, _previous: QModelIndex) -> None:
    if not current.isValid():
        tab.show_permanent_message("")
        return

    current = tab.view_controller.proxy_to_source(current)
    row0 = current.siblingAtColumn(0)
    if not row0.isValid():
        tab.show_permanent_message("")
        return

    item = tab.model.get_item(row0)
    breadcrumb = tab.view_controller.qualified_name(row0)
    item_type = item.json_type.value
    size_hint = size_hint_for_item(item)
    extra = f", {size_hint}" if size_hint else ""
    tab.show_permanent_message(f"{breadcrumb}  ({item_type}{extra})")
