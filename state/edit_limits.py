from __future__ import annotations

from PySide6.QtCore import QSettings

from settings import (APPLICATION_ID, BINARY_ATTACH_WARNING_LIMIT_BYTES,
                      BINARY_EDIT_WARNING_LIMIT_BYTES,
                      MULTILINE_EDIT_WARNING_LIMIT_CHARS,
                      STRING_EDIT_WARNING_LIMIT_CHARS)

_STRING_LIMIT_KEY = "edit_limits/string_chars"
_MULTILINE_LIMIT_KEY = "edit_limits/multiline_chars"
_BINARY_EDIT_LIMIT_KEY = "edit_limits/binary_bytes"
_ATTACH_LIMIT_KEY = "edit_limits/attach_bytes"


def _settings() -> QSettings:
    return QSettings(APPLICATION_ID, "app")


def _coerce_positive_int(value, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return int(default)
    return number if number > 0 else int(default)


def get_string_edit_warning_limit_chars() -> int:
    return _coerce_positive_int(_settings().value(_STRING_LIMIT_KEY), default=STRING_EDIT_WARNING_LIMIT_CHARS)


def set_string_edit_warning_limit_chars(limit: int) -> None:
    _settings().setValue(_STRING_LIMIT_KEY, _coerce_positive_int(limit, default=STRING_EDIT_WARNING_LIMIT_CHARS))


def get_multiline_edit_warning_limit_chars() -> int:
    return _coerce_positive_int(_settings().value(_MULTILINE_LIMIT_KEY), default=MULTILINE_EDIT_WARNING_LIMIT_CHARS)


def set_multiline_edit_warning_limit_chars(limit: int) -> None:
    _settings().setValue(_MULTILINE_LIMIT_KEY, _coerce_positive_int(limit, default=MULTILINE_EDIT_WARNING_LIMIT_CHARS))


def get_binary_edit_warning_limit_bytes() -> int:
    return _coerce_positive_int(_settings().value(_BINARY_EDIT_LIMIT_KEY), default=BINARY_EDIT_WARNING_LIMIT_BYTES)


def set_binary_edit_warning_limit_bytes(limit: int) -> None:
    _settings().setValue(_BINARY_EDIT_LIMIT_KEY, _coerce_positive_int(limit, default=BINARY_EDIT_WARNING_LIMIT_BYTES))


def get_attach_file_warning_limit_bytes() -> int:
    return _coerce_positive_int(_settings().value(_ATTACH_LIMIT_KEY), default=BINARY_ATTACH_WARNING_LIMIT_BYTES)


def set_attach_file_warning_limit_bytes(limit: int) -> None:
    _settings().setValue(_ATTACH_LIMIT_KEY, _coerce_positive_int(limit, default=BINARY_ATTACH_WARNING_LIMIT_BYTES))
