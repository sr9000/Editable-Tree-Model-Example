"""Foreign-error attribute adapter.

This module is the **single** site in :mod:`validation` permitted to use
``getattr`` against foreign error objects (``jsonschema.ValidationError``
and shape-compatible duck types). Every accessor here normalizes one
attribute and returns a typed Python value. Code outside this module
must consume errors via these helpers, not via ``getattr``.

Allowlisted by the project-wide pre-commit hook (stage 10 of the
``plans/`` series).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def err_validator(err: Any) -> str | None:
    """Return the keyword that produced *err* (``"oneOf"``, ``"type"``, ...) or ``None``."""
    value = getattr(err, "validator", None)
    return value if isinstance(value, str) else None


def err_context(err: Any) -> Sequence[Any]:
    """Return the sub-errors emitted by a combinator, or an empty tuple."""
    value = getattr(err, "context", None) or ()
    return value


def err_path(err: Any) -> Sequence[Any]:
    """Return the instance-side path (a ``deque`` in jsonschema), or ``()``."""
    value = getattr(err, "path", None)
    return value if value is not None else ()


def err_schema_path(err: Any) -> Sequence[Any]:
    """Return the schema-side path, or ``()`` when absent."""
    value = getattr(err, "schema_path", None)
    return value if value is not None else ()


def err_instance_path(err: Any) -> Sequence[Any] | None:
    """Return the legacy ``instance_path`` attribute (jsonschema-rs), or ``None``."""
    return getattr(err, "instance_path", None)


def err_message(err: Any) -> str:
    """Return the user-facing error message; falls back to ``str(err)``."""
    value = getattr(err, "message", None)
    return str(value) if value is not None else str(err)


_KIND_ATTRS: tuple[str, ...] = ("kind", "validator", "keyword", "rule")


def err_kind(err: Any) -> str:
    """Normalize the error kind across engines.

    jsonschema 4.x exposes ``.validator`` as a string keyword;
    jsonschema-rs exposes a structured ``.kind`` enum-like object;
    other engines may expose ``.keyword`` or ``.rule``. Returns the first
    non-empty candidate (string, or the enum class-name suffix for
    structured kinds) or ``"validation_error"`` when nothing matches.
    """
    for attr in _KIND_ATTRS:
        value = getattr(err, attr, None)
        if not value:
            continue
        if isinstance(value, str):
            return value
        # Rich enum objects: use the class suffix as a stable machine-key.
        class_name = value.__class__.__name__
        if "_" in class_name:
            class_name = class_name.rsplit("_", 1)[-1]
        return class_name.lower()
    return "validation_error"
