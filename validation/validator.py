from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from validation.error_adapter import (
    err_context,
    err_instance_path,
    err_kind,
    err_message,
    err_path,
    err_schema_path,
    err_validator,
)
from validation.issue import ValidationIssue

from . import _engine


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


def _lookup_json_pointer(root: Any, pointer: str) -> tuple[tuple[str | int, ...], Any] | None:
    """Resolve a local JSON pointer against *root*.

    Returns both the decoded token path and the referenced object.  Only local
    references (``#`` / ``#/...``) are handled here; remote references do not
    have a stable location in the currently-open schema document to navigate
    to.
    """
    if not pointer.startswith("#"):
        return None

    tokens = _decode_json_pointer(pointer[1:])
    cursor = root
    for token in tokens:
        if isinstance(cursor, Mapping):
            if not isinstance(token, str) or token not in cursor:
                return None
            cursor = cursor[token]
            continue

        if isinstance(cursor, Sequence) and not isinstance(cursor, (bytes, bytearray, str)):
            if not isinstance(token, int) or token < 0 or token >= len(cursor):
                return None
            cursor = cursor[token]
            continue

        return None
    return tokens, cursor


def _schema_path_resolving_refs(root_schema: Mapping[str, Any], path: Any) -> tuple[str | int, ...]:
    """Convert jsonschema's logical schema path into a document path.

    ``jsonschema`` reports paths as if local ``$ref`` targets were inlined at
    the reference site.  That is useful for validation, but it is not a real
    path in the schema file, so UI navigation stops at the ``$ref`` owner (or
    fails and lands on the root).  While walking the reported path, whenever
    the next token is missing because the current schema node is a local
    ``$ref``, jump to the referenced definition and continue from there.
    """
    raw_tokens = _normalize_path(list(path) if path is not None else ())
    cursor: Any = root_schema
    physical: tuple[str | int, ...] = ()

    for token in raw_tokens:
        while isinstance(cursor, Mapping) and token not in cursor:
            ref = cursor.get("$ref")
            if not isinstance(ref, str):
                return raw_tokens
            resolved = _lookup_json_pointer(root_schema, ref)
            if resolved is None:
                return raw_tokens
            physical, cursor = resolved

        if isinstance(cursor, Mapping):
            if not isinstance(token, str) or token not in cursor:
                return raw_tokens
            cursor = cursor[token]
            physical = physical + (token,)
            continue

        if isinstance(cursor, Sequence) and not isinstance(cursor, (bytes, bytearray, str)):
            if not isinstance(token, int) or token < 0 or token >= len(cursor):
                return raw_tokens
            cursor = cursor[token]
            physical = physical + (token,)
            continue

        return raw_tokens

    return physical


def _error_kind(err: Any) -> str:
    return err_kind(err)


def _is_combinator(err: Any) -> bool:
    return err_validator(err) in ("oneOf", "anyOf") and bool(err_context(err))


def _branch_index(err: Any) -> int:
    """Return the index of the ``oneOf``/``anyOf`` sub-schema this error belongs to.

    For errors emitted inside a combinator's ``context``, the first element of
    ``schema_path`` is the integer branch index in the parent ``oneOf``/``anyOf``
    array.
    """
    sp = list(err_schema_path(err))
    if sp and isinstance(sp[0], int):
        return sp[0]
    return -1


def _branch_cost(errors: Sequence[Any]) -> int:
    """Approximate the number of edits needed to satisfy a single branch.

    Each "leaf" validation error in the branch counts as one required fix.
    Nested ``oneOf``/``anyOf`` errors are recursively reduced to the
    cheapest sub-branch (because the user only needs to satisfy one of them),
    matching how a human would patch the document.
    """
    total = 0
    for err in errors:
        if _is_combinator(err):
            best = _pick_cheapest_branch(err.context)
            total += _branch_cost(best) if best else 1
        else:
            total += 1
    return total


def _pick_cheapest_branch(context: Sequence[Any]) -> list[Any]:
    """Group *context* errors by branch index and return the cheapest one."""
    branches: dict[int, list[Any]] = {}
    for err in context:
        branches.setdefault(_branch_index(err), []).append(err)

    # Lowest cost wins; tie-break by branch index for determinism.
    best_idx = min(branches, key=lambda i: (_branch_cost(branches[i]), i))
    return branches[best_idx]


def _most_specific(errors: Sequence[Any]) -> Any | None:
    """Pick the most informative error inside a single chosen branch.

    Prefers concrete (non-``oneOf``/``anyOf``) errors over combinator wrappers,
    then prefers the deepest instance path (closest to the actual bad value),
    then the longest schema path. This points the UI at the specific field
    that must change, instead of a generic "is not valid under any of …".
    """
    if not errors:
        return None

    def score(err: Any) -> tuple[int, int, int]:
        concrete = 0 if _is_combinator(err) else 1
        instance_depth = len(list(err_path(err)))
        schema_depth = len(list(err_schema_path(err)))
        return (concrete, instance_depth, schema_depth)

    return max(errors, key=score)


def _unwrap_best(err: Any) -> Any:
    """Recursively replace a ``oneOf``/``anyOf`` error with its best sub-match.

    When a schema uses ``oneOf`` or ``anyOf``, jsonschema emits a single
    top-level error ("… is not valid under any of the given schemas") whose
    ``context`` contains one ``ValidationError`` per failing sub-schema.
    That top-level message is almost never the *useful* one, and it also
    points at the parent container rather than the offending field.

    The heuristic here picks the branch whose document is **closest to
    valid**, i.e. the one that would require the fewest individual fixes
    (leaf errors) to satisfy. This is a better proxy for "what did the
    author mean?" than jsonschema's built-in ``best_match``, which simply
    descends to the deepest error and can latch onto an unrelated branch
    that happens to have a long path.

    Within the chosen branch we then surface the most specific concrete
    error so the reported ``instance_path`` points at the actual bad field.

    Sub-errors inside ``context`` carry ``path``/``schema_path`` *relative*
    to the combinator's position in the document, so we re-prepend the
    parent's paths to keep absolute coordinates pointing at the real field.
    """
    if not _is_combinator(err):
        return err

    branch = _pick_cheapest_branch(err.context)
    chosen = _most_specific(branch)
    if chosen is None:
        return err

    # Re-attach absolute coordinates: child paths in .context are relative.
    parent_path = list(err_path(err))
    parent_schema_path = list(err_schema_path(err))
    from collections import deque  # noqa: PLC0415

    chosen.path = deque(parent_path + list(chosen.path))
    chosen.schema_path = deque(parent_schema_path + list(chosen.schema_path))
    return _unwrap_best(chosen)


def _to_issue(err: Any, root_schema: Mapping[str, Any]) -> ValidationIssue:
    # jsonschema uses .path (deque); legacy jsonschema-rs used .instance_path
    raw_instance_path = err_instance_path(err)
    if raw_instance_path is None:
        raw_instance_path = err_path(err)
    return ValidationIssue(
        message=err_message(err),
        instance_path=_normalize_path(list(raw_instance_path)),
        schema_path=_schema_path_resolving_refs(root_schema, err_schema_path(err)),
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
        issues.append(_to_issue(_unwrap_best(err), schema))
        if len(issues) >= max_issues:
            break

    return issues
