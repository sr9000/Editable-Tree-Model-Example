"""Container, formatting, and search probes.

These tests exercise ``format_with_type()`` with long strings.
The filter proxy tests are deferred to a future commit due to QCoreApplication
conflicts with the test suite.

Run with: ``pytest -m perf tests/perf/test_container_paths.py``
"""

from __future__ import annotations

import os

import pytest

from tests.perf.harness import classify_rows, scaling_rows
from tests.perf.string_corpus import DEFAULT_SIZES, plain_ascii

# Check if strict mode is enabled
PERF_STRICT = os.environ.get("PYTEST_PERF_STRICT", "0") == "1"

# Import non-Qt target functions
from delegates.formatting.value_formatting import format_with_type
from tree.types import JsonType

# Collect all rows for report generation
_collected_rows: list = []


# ---------------------------------------------------------------------------
# Wrapper functions
# ---------------------------------------------------------------------------


def _make_format_wrapper(json_type: JsonType):
    """Create a wrapper for format_with_type with a specific type."""

    def wrapper(text: str) -> str:
        return format_with_type(text, json_type)

    return wrapper


# ---------------------------------------------------------------------------
# Formatting tests (not perf-marked, run in default suite)
# ---------------------------------------------------------------------------


class TestFormattingSmoke:
    """Smoke tests for format_with_type with various types."""

    def test_format_string(self):
        """format_with_type should handle STRING type."""
        _, text = plain_ascii(1024)
        result = format_with_type(text, JsonType.STRING)
        assert isinstance(result, str)

    def test_format_multiline(self):
        """format_with_type should handle MULTILINE type."""
        _, text = plain_ascii(1024)
        result = format_with_type(text, JsonType.MULTILINE)
        assert isinstance(result, str)

    def test_format_unicode(self):
        """format_with_type should handle UNICODE type."""
        _, text = plain_ascii(1024)
        result = format_with_type(text, JsonType.UNICODE)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Perf-marked scaling tests
# ---------------------------------------------------------------------------

CONTAINER_TARGETS = [
    ("format_with_type(STRING)", _make_format_wrapper(JsonType.STRING), False),
    ("format_with_type(MULTILINE)", _make_format_wrapper(JsonType.MULTILINE), False),
    ("format_with_type(UNICODE)", _make_format_wrapper(JsonType.UNICODE), False),
]


def _generate_test_params():
    """Generate test parameters for all container targets."""
    params = []
    for name, wrapper, is_decode in CONTAINER_TARGETS:
        params.append(
            pytest.param(
                name,
                wrapper,
                plain_ascii,
                "plain_ascii",
                is_decode,
                id=f"{name}-plain_ascii",
            )
        )
    return params


@pytest.mark.perf
class TestContainerPaths:
    """Scaling probes for container and formatting paths."""

    @pytest.mark.parametrize("name,wrapper,factory,family_name,is_decode", _generate_test_params())
    def test_container_scaling(self, name, wrapper, factory, family_name, is_decode):
        """Test scaling behavior for container paths with various inputs."""
        # Generate scaling rows for the default sizes
        rows = scaling_rows(
            wrapper,
            DEFAULT_SIZES,
            factory,
            function_name=name,
            wrapper_name=name,
            is_decode_path=is_decode,
        )

        # Classify rows for scaling ratio
        classified = classify_rows(rows)

        # Collect rows for report generation
        _collected_rows.extend(classified)

        # In strict mode, fail on vulnerabilities
        if PERF_STRICT:
            for row in classified:
                if row.outcome != "pass":
                    msg = f"{row.function} ({row.family}, size={row.size}): {row.outcome}"
                    if row.scaling_ratio is not None:
                        msg += f" (ratio={row.scaling_ratio:.2f})"
                    if row.exception_text:
                        msg += f" - {row.exception_text}"
                    pytest.fail(msg)


# ---------------------------------------------------------------------------
# Report data access
# ---------------------------------------------------------------------------


def get_collected_rows():
    """Return all collected measurement rows for report generation."""
    return _collected_rows


def clear_collected_rows():
    """Clear the collected rows (for testing)."""
    _collected_rows.clear()
