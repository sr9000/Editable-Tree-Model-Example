"""Backwards-compatibility shim.

``FrozenValue`` was the original name for the raw-literal wrapper. It now aliases
:class:`core.raw_numeric.RawNumericValue`, which preserves unsupported numeric
literals as editable raw text.
"""

from core.raw_numeric import RawNumericValue as FrozenValue

__all__ = ["FrozenValue"]
