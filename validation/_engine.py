from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol


class CompiledValidator(Protocol):
    def iter_errors(self, instance: Any) -> Iterable[Any]: ...


def compile_schema(schema: Mapping[str, Any]) -> CompiledValidator:
    """Compile *schema* using jsonschema.

    Picks the validator class via ``jsonschema.validators.validator_for`` so
    that ``$schema`` keywords (draft-04 through draft-2020-12) are honoured.
    Calls ``check_schema`` eagerly so invalid meta-schema usage is caught at
    compile time rather than silently ignored.

    Format validation is enabled via ``jsonschema.FormatChecker``.  All
    formats that have a checker registered in the current environment are
    active (e.g. ``date-time``, ``email``, ``uri``, ``ipv4``/``ipv6``, …).
    Extra format support can be gained by installing optional dependencies
    such as *jsonschema[format]* (which pulls in ``fqdn``, ``idna``, etc.).

    The returned validator exposes ``iter_errors(instance)``.
    """
    try:
        import jsonschema
        import jsonschema.validators
    except ImportError as exc:  # pragma: no cover - exercised in integration envs
        raise RuntimeError("jsonschema is not installed") from exc

    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)  # raises SchemaError for invalid schemas
    return validator_cls(schema, format_checker=jsonschema.FormatChecker())
