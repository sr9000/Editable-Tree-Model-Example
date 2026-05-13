from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def instance_path_to_model_path(root_data: Any, instance_path: Sequence[str | int]) -> tuple[int, ...] | None:
    """Translate a jsonschema instance path into a row-based model path."""
    current = root_data
    model_path: list[int] = []

    for token in instance_path:
        if isinstance(current, Mapping):
            if not isinstance(token, str):
                return None
            keys = list(current.keys())
            try:
                row = keys.index(token)
            except ValueError:
                return None
            model_path.append(row)
            current = current[token]
            continue

        if isinstance(current, list):
            if not isinstance(token, int):
                return None
            if token < 0 or token >= len(current):
                return None
            model_path.append(token)
            current = current[token]
            continue

        return None

    return tuple(model_path)


def model_path_to_instance_path(root_data: Any, model_path: Sequence[int]) -> tuple[str | int, ...]:
    """Translate a row-based model path into a jsonschema instance path."""
    current = root_data
    instance_path: list[str | int] = []

    for row in model_path:
        if not isinstance(row, int):
            raise ValueError(f"Model path entries must be int, got: {type(row).__name__}")

        if isinstance(current, Mapping):
            keys = list(current.keys())
            if row < 0 or row >= len(keys):
                raise ValueError(f"Model path points outside object bounds: {row}")
            key = keys[row]
            instance_path.append(key)
            current = current[key]
            continue

        if isinstance(current, list):
            if row < 0 or row >= len(current):
                raise ValueError(f"Model path points outside array bounds: {row}")
            instance_path.append(row)
            current = current[row]
            continue

        raise ValueError("Model path descends into a scalar value")

    return tuple(instance_path)
