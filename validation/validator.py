from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from validation import _engine
from validation.issue import ValidationIssue


def _decode_json_pointer(pointer: str) -> tuple[str | int, ...]:
    if pointer in ("", "/"):
        return ()

    parts = pointer.lstrip("/").split("/")
    tokens: list[str | int] = []
    for part in parts:
        text = part.replace("~1", "/").replace("~0", "~")
        if text.isdigit():
            tokens.append(int(text))
        else:
            tokens.append(text)
    return tuple(tokens)


def _normalize_path(path: Any) -> tuple[str | int, ...]:
    if path is None:
        return ()

    if isinstance(path, str):
        return _decode_json_pointer(path)

    if isinstance(path, Sequence) and not isinstance(path, (bytes, bytearray, str)):
        tokens: list[str | int] = []
        for token in path:
            if isinstance(token, (str, int)):
                tokens.append(token)
            else:
                tokens.append(str(token))
        return tuple(tokens)

    return ()


def _error_kind(err: Any) -> str:
    for attr in ("kind", "validator", "keyword", "rule"):
        value = getattr(err, attr, None)
        if value:
            if isinstance(value, str):
                return value

            # jsonschema exposes rich enum objects for .kind;
            # use the class suffix for a stable machine-friendly key.
            class_name = value.__class__.__name__
            if "_" in class_name:
                class_name = class_name.rsplit("_", 1)[-1]
            return class_name.lower()
    return "validation_error"


def _to_issue(err: Any) -> ValidationIssue:
    # jsonschema uses .path (deque); legacy jsonschema-rs used .instance_path
    raw_instance_path = getattr(err, "instance_path", None)
    if raw_instance_path is None:
        raw_instance_path = getattr(err, "path", ())
    return ValidationIssue(
        severity="error",
        message=str(getattr(err, "message", err)),
        instance_path=_normalize_path(list(raw_instance_path)),
        schema_path=_normalize_path(list(getattr(err, "schema_path", ()))),
        kind=_error_kind(err),
    )


def is_schema_valid(schema: Mapping[str, Any]) -> tuple[bool, str | None]:
    try:
        _engine.compile_schema(schema)
    except Exception as exc:  # pragma: no cover - depends on jsonschema internals
        return False, str(exc)
    return True, None


def validate_document(data: Any, schema: Mapping[str, Any], *, max_issues: int = 500) -> list[ValidationIssue]:
    if max_issues <= 0:
        return []

    try:
        compiled = _engine.compile_schema(schema)
    except Exception as exc:
        raise ValueError(f"Invalid JSON schema: {exc}") from exc

    issues: list[ValidationIssue] = []
    for err in compiled.iter_errors(data):
        issues.append(_to_issue(err))
        if len(issues) >= max_issues:
            break

    return issues
