from typing import Any


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_int_list(value: Any) -> list[int] | None:
    if not isinstance(value, (list, tuple)):
        return None
    coerced: list[int] = []
    for part in value:
        number = _coerce_int(part)
        if number is None:
            return None
        coerced.append(number)
    return coerced


def _coerce_path(value: Any) -> tuple[int, ...] | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return ()
        # Accept either "0/1/2" or "0,1,2" for portability.
        separator = "/" if "/" in stripped else ","
        parts = [p for p in stripped.split(separator) if p != ""]
        coerced = _coerce_int_list(parts)
        return tuple(coerced) if coerced is not None else None

    coerced = _coerce_int_list(value)
    return tuple(coerced) if coerced is not None else None


def _coerce_paths(value: Any) -> list[tuple[int, ...]] | None:
    if not isinstance(value, (list, tuple)):
        return None
    paths: list[tuple[int, ...]] = []
    for entry in value:
        path = _coerce_path(entry)
        if path is None:
            return None
        paths.append(path)
    return paths
