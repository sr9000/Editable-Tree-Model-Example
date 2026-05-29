"""Marker base class used to identify ``JsonTab`` instances at runtime.

Extracted from the now-retired ``documents.tab_protocols`` so
``tree_actions/_tab_lookup.py`` can keep its ``isinstance(node,
JsonTabWidgetMarker)`` parent-chain walk without taking a hard
dependency on :mod:`documents.tab` (which would create a cycle:
``documents.tab`` imports ``tree_actions.*``).

See ``plans/20-decouple-jsontab.md`` Phase G.
"""

from __future__ import annotations


class JsonTabWidgetMarker:
    """Marker base used by tree_actions to identify tab widgets without importing documents.tab."""
