from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt

from enums import JsonType
from tree_model import JsonTreeModel


class TreeFilterProxy(QSortFilterProxyModel):
    """Recursive name/value substring filter for the JSON tree model."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._needle = ""
        self.setRecursiveFilteringEnabled(True)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_filter_text(self, text: str) -> None:
        # Keep a normalized plain-string needle; no regex semantics.
        self._needle = (text or "").strip().casefold()
        self.invalidate()

    def filterAcceptsRow(self, src_row: int, src_parent: QModelIndex) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        if not isinstance(model, JsonTreeModel):
            return False

        index0 = model.index(src_row, 0, src_parent)
        if not index0.isValid():
            return False

        if not self._needle:
            return True

        item = model.get_item(index0)

        # Match the name text for all nodes.
        name_text = "" if item.name is None else str(item.name)
        if self._needle in name_text.casefold():
            return True

        # Match the value text only for leaves (containers are shown via descendant matches).
        if item.json_type not in (JsonType.OBJECT, JsonType.ARRAY):
            value_text = "" if item.value is None else str(item.value)
            if self._needle in value_text.casefold():
                return True

        # Keep ancestors of matching descendants visible.
        for child_row in range(model.rowCount(index0)):
            if self.filterAcceptsRow(child_row, index0):
                return True

        return False
