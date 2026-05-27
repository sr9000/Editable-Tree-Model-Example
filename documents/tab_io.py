from PySide6.QtWidgets import QFileDialog

from io_formats import (
    SAVE_FORMAT_JSON,
    SAVE_FORMAT_JSONL,
    SAVE_FORMAT_YAML,
    SAVE_FORMAT_YAML_MULTI,
    detect_format,
    save_file,
)


def snapshot(tab):
    return tab.model.root_item.to_json()


def save(tab) -> bool:
    if not tab.file_path:
        return save_as(tab)
    try:
        save_file(tab.file_path, tab.model.root_item.to_json(), save_format=tab.save_format)
    except Exception as exc:
        tab.show_status(f"Save failed: {exc}", 4000)
        return False
    tab.undo_stack.setClean()
    tab.show_status(f"Saved: {tab.file_path}", 2000)
    return True


def save_as(tab, path: str | None = None) -> bool:
    target = path
    selected_filter = ""
    if not target:
        target, selected_filter = QFileDialog.getSaveFileName(
            tab,
            "Save As",
            tab.file_path or "",
            "JSON (*.json);;JSON Lines (*.jsonl *.ndjson);;YAML (*.yaml *.yml);;YAML multi-document (*.yaml *.yml)",
        )
    if not target:
        return False
    if selected_filter.startswith("JSON Lines"):
        tab.save_format = SAVE_FORMAT_JSONL
    elif selected_filter.startswith("YAML multi-document"):
        tab.save_format = SAVE_FORMAT_YAML_MULTI
    elif selected_filter.startswith("YAML"):
        tab.save_format = SAVE_FORMAT_YAML
    elif selected_filter.startswith("JSON"):
        tab.save_format = SAVE_FORMAT_JSON
    elif target:
        try:
            tab.save_format = detect_format(target)
        except ValueError:
            pass
    tab.file_path = target
    return save(tab)
