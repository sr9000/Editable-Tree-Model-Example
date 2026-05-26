"""Clipboard text-format preference (JSON vs YAML)."""

from PySide6.QtCore import QSettings

from settings import APPLICATION_ID

CLIPBOARD_TEXT_FORMAT_JSON = "json"
CLIPBOARD_TEXT_FORMAT_YAML = "yaml"

_VALID = {CLIPBOARD_TEXT_FORMAT_JSON, CLIPBOARD_TEXT_FORMAT_YAML}


def get_clipboard_text_format() -> str:
    val = QSettings(APPLICATION_ID, "app").value("clipboard/text_format", CLIPBOARD_TEXT_FORMAT_JSON)
    return val if val in _VALID else CLIPBOARD_TEXT_FORMAT_JSON


def set_clipboard_text_format(fmt: str) -> None:
    if fmt not in _VALID:
        fmt = CLIPBOARD_TEXT_FORMAT_JSON
    QSettings(APPLICATION_ID, "app").setValue("clipboard/text_format", fmt)
