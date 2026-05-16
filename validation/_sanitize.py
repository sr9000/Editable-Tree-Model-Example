"""validation/_sanitize.py — coerce mpq/Decimal/datetime/bytes to jsonschema-rs primitives.

Precision loss is intentional and validation-only; the original data stored
in ``JsonTreeItem`` is never modified.  Call ``to_jsonschema_input`` before
passing tree data to any validation engine.
"""
from __future__ import annotations

import base64
import logging
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

_log = logging.getLogger(__name__)


def to_jsonschema_input(value: Any, *, _lossy: list[bool] | None = None) -> Any:
    """Recursively coerce *value* to JSON-schema-rs-friendly primitives.

    Coercion rules:

    - ``gmpy2.mpq``  → ``float``  (lossy for irrationals; single warning logged
      per top-level call when any such coercion occurs)
    - ``gmpy2.mpz``  → ``int``
    - ``Fraction``   → ``float``
    - ``Decimal``    → ``float``
    - ``datetime``   → ISO-format string  (``datetime`` before ``date`` — subclass!)
    - ``date``       → ISO-format string
    - ``time``       → ISO-format string
    - ``bytes`` / ``bytearray`` → Base64-encoded ASCII string
    - ``dict``       → recursively coerced mapping
    - ``list``       → recursively coerced list
    - everything else returned unchanged

    Args:
        value: The Python object tree to sanitize.

    Returns:
        A deep copy with unsupported leaf types replaced by JSON primitives.
    """
    _root_call = _lossy is None
    if _root_call:
        _lossy = [False]

    result = _coerce(value, _lossy)

    if _root_call and _lossy[0]:
        _log.warning(
            "validation: mpq value(s) coerced to float for schema validation; "
            "precision loss is validation-only and never reaches storage."
        )
    return result


def _coerce(value: Any, lossy: list[bool]) -> Any:  # noqa: PLR0911
    # ── gmpy2 exact numerics ──────────────────────────────────────────────
    try:
        import gmpy2  # noqa: PLC0415

        if isinstance(value, gmpy2.mpq):
            lossy[0] = True
            return float(value)
        if isinstance(value, gmpy2.mpz):
            return int(value)
    except ImportError:
        pass

    # ── fractions.Fraction ───────────────────────────────────────────────
    try:
        from fractions import Fraction  # noqa: PLC0415

        if isinstance(value, Fraction):
            lossy[0] = True
            return float(value)
    except ImportError:
        pass

    # ── Decimal ──────────────────────────────────────────────────────────
    if isinstance(value, Decimal):
        return float(value)

    # ── temporal (datetime before date — subclass order matters) ─────────
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()

    # ── binary ───────────────────────────────────────────────────────────
    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).decode("ascii")

    # ── containers ───────────────────────────────────────────────────────
    if isinstance(value, dict):
        return {k: _coerce(v, lossy) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce(item, lossy) for item in value]

    return value
