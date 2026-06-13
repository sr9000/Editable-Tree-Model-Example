"""Opt-in scaling tests for registry entries.

These tests are marked with ``@pytest.mark.perf`` and are opt-in.
With ``PYTEST_PERF_STRICT`` unset, the module records rows without failing.
With ``PYTEST_PERF_STRICT=1``, rows classified as vulnerabilities fail the test.

Run with: ``pytest -m perf tests/perf/test_parsing_scaling.py``
"""

from __future__ import annotations

import os

import pytest

from tests.perf.harness import classify_rows, measure_call, scaling_rows
from tests.perf.registry import HOTSPOT_REGISTRY
from tests.perf.string_corpus import DEFAULT_SIZES, FAMILY_REGISTRY

# Check if strict mode is enabled
PERF_STRICT = os.environ.get("PYTEST_PERF_STRICT", "0") == "1"

# Collect all rows for report generation
_collected_rows: list = []


def pytest_collection_modifyitems(config, items):
    """Skip perf tests unless explicitly requested with -m perf."""
    if not config.getoption("-m", default=""):
        skip_perf = pytest.mark.skip(reason="perf tests are opt-in; use -m perf to run")
        for item in items:
            if "perf" in item.keywords:
                item.add_marker(skip_perf)


# ---------------------------------------------------------------------------
# Parametrized scaling tests
# ---------------------------------------------------------------------------


def _generate_test_params():
    """Generate test parameters for all registry/family combinations."""
    params = []
    for entry in HOTSPOT_REGISTRY:
        for family_name, factory in FAMILY_REGISTRY.items():
            params.append(
                pytest.param(
                    entry,
                    family_name,
                    factory,
                    id=f"{entry.name}-{family_name}",
                )
            )
    return params


@pytest.mark.perf
class TestParsingScaling:
    """Scaling tests for all registry entries across all families."""

    @pytest.mark.parametrize("entry,family_name,factory", _generate_test_params())
    def test_scaling(self, entry, family_name, factory):
        """Test scaling behavior for a registry entry with a specific family."""
        # Generate scaling rows for the default sizes
        rows = scaling_rows(
            entry.call,
            DEFAULT_SIZES,
            factory,
            function_name=entry.name,
            wrapper_name=entry.name,
            is_decode_path=entry.is_decode_path,
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
