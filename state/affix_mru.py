from __future__ import annotations

from collections import OrderedDict
from typing import Any

import settings
from units.number_affix import AffixKind, NumberAffix


class AffixMRU:
    def __init__(self, max_size: int | None = None) -> None:
        configured = getattr(settings, "NUMBER_AFFIX_MRU_SIZE", 50)
        self._max_size = int(max_size if max_size is not None else configured)
        self._prefix: OrderedDict[str, None] = OrderedDict()
        self._suffix: OrderedDict[str, None] = OrderedDict()

    def _store_for(self, kind: AffixKind) -> OrderedDict[str, None]:
        return self._prefix if kind is AffixKind.CURRENCY else self._suffix

    def push(self, kind: AffixKind, affix: str) -> None:
        if not affix:
            return
        store = self._store_for(kind)
        if affix in store:
            del store[affix]
        store[affix] = None
        store.move_to_end(affix, last=False)
        while len(store) > self._max_size:
            store.popitem(last=True)

    def items(self, kind: AffixKind) -> list[str]:
        return list(self._store_for(kind).keys())

    def bootstrap_from_tree(self, root: Any) -> None:
        def walk(node: Any):
            if isinstance(node, NumberAffix):
                self.push(node.kind, node.affix)
                return
            if hasattr(node, "child_items"):
                for child in getattr(node, "child_items", []):
                    walk(child)
                return
            if isinstance(node, dict):
                for value in node.values():
                    walk(value)
                return
            if isinstance(node, list):
                for value in node:
                    walk(value)

        walk(root)
