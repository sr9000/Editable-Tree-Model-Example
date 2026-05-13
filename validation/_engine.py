from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol


class CompiledValidator(Protocol):
    def iter_errors(self, instance: Any) -> Iterable[Any]: ...


def compile_schema(schema: Mapping[str, Any]) -> CompiledValidator:
    """Compile *schema* using jsonschema-rs with light version compatibility."""
    try:
        import jsonschema_rs
    except ImportError as exc:  # pragma: no cover - exercised in integration envs
        raise RuntimeError("jsonschema-rs is not installed") from exc

    if hasattr(jsonschema_rs, "validator_for"):
        return jsonschema_rs.validator_for(schema)

    if hasattr(jsonschema_rs, "JSONSchema"):
        return jsonschema_rs.JSONSchema(schema)

    raise RuntimeError("Unsupported jsonschema-rs API: expected validator_for() or JSONSchema")
