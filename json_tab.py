"""Compatibility imports for JsonTab."""

import time

from documents.tab import (
    _CMD_ID_EDIT_VALUE,
    _CMD_ID_RENAME,
    _MERGE_WINDOW_SECONDS,
    JsonTab,
    _ChangeTypeCmd,
    _EditValueCmd,
    _InsertRowsCmd,
    _MoveRowCmd,
    _RemoveRowsCmd,
    _RenameCmd,
    _SortKeysCmd,
)

__all__ = [
    "JsonTab",
    "_CMD_ID_RENAME",
    "_CMD_ID_EDIT_VALUE",
    "_MERGE_WINDOW_SECONDS",
    "_ChangeTypeCmd",
    "_MoveRowCmd",
    "_EditValueCmd",
    "_InsertRowsCmd",
    "_RemoveRowsCmd",
    "_RenameCmd",
    "_SortKeysCmd",
    "time",
]
