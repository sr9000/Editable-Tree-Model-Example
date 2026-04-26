import json
from typing import Any

import simplejson
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication, QTreeView

from enums import JsonType
from mpq2py import mpq_json_default
from tree_actions.selection import _index_path, _resolve_model, _top_level_selected_rows
from tree_model import JsonTreeModel

MIME_JSON_TREE = "application/x-json-tree"


def _build_copy_entries(model: JsonTreeModel, rows) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for idx in rows:
        item = model.get_item(idx)
        entries.append(
            {
                "name": item.name if isinstance(item.name, str) else None,
                "value": item.to_json(),
            }
        )
    return entries


def _entries_text_payload(model: JsonTreeModel, rows, entries: list[dict[str, Any]]) -> Any:
    if not entries:
        return None

    first_parent = rows[0].parent()
    same_parent = all(idx.parent() == first_parent for idx in rows)
    all_named = all(isinstance(entry.get("name"), str) and entry["name"] for entry in entries)

    if same_parent and all_named:
        parent_item = model.get_item(first_parent)
        if parent_item.json_type is JsonType.OBJECT:
            names = [entry["name"] for entry in entries]
            if len(set(names)) == len(names):
                return {entry["name"]: entry["value"] for entry in entries}

    if len(entries) == 1:
        return entries[0]["value"]
    return [entry["value"] for entry in entries]


def copy_selection(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    rows = sorted(_top_level_selected_rows(tree_view), key=_index_path)
    if not rows:
        return False

    entries = _build_copy_entries(model, rows)
    text_payload = _entries_text_payload(model, rows, entries)

    text = simplejson.dumps(text_payload, default=mpq_json_default, indent=2)
    metadata = simplejson.dumps({"entries": entries}, default=mpq_json_default)

    mime = QMimeData()
    mime.setData(MIME_JSON_TREE, metadata.encode("utf-8"))
    mime.setText(text)
    QApplication.clipboard().setMimeData(mime)
    return True


def _clipboard_entries() -> list[dict[str, Any]] | None:
    md = QApplication.clipboard().mimeData()
    if md is None:
        return None

    if md.hasFormat(MIME_JSON_TREE):
        try:
            raw = md.data(MIME_JSON_TREE).data().decode("utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                entries = parsed.get("entries")
                if isinstance(entries, list):
                    normalized: list[dict[str, Any]] = []
                    for entry in entries:
                        if not isinstance(entry, dict) or "value" not in entry:
                            continue
                        name = entry.get("name")
                        normalized.append({"name": name if isinstance(name, str) else None, "value": entry["value"]})
                    if normalized:
                        return normalized

                items = parsed.get("items")
                if isinstance(items, list):
                    return [{"name": None, "value": value} for value in items]
        except Exception:
            pass

    text = md.text().strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
    except Exception:
        return None

    if isinstance(parsed, dict):
        return [{"name": str(name), "value": value} for name, value in parsed.items()]
    if isinstance(parsed, list):
        return [{"name": None, "value": value} for value in parsed]
    return [{"name": None, "value": parsed}]
