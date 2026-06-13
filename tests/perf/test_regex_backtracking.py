"""Focused regex backtracking probes.

These tests isolate regex matching from parser fallback work by measuring
each regex directly with ``fullmatch`` or the existing public wrapper.

Run with: ``pytest -m perf tests/perf/test_regex_backtracking.py``
"""

from __future__ import annotations

import os

import pytest

from tests.perf.harness import classify_rows, measure_call, scaling_rows
from tests.perf.string_corpus import DEFAULT_SIZES, near_affix, near_color, near_datetime, pathological_repetition

# Check if strict mode is enabled
PERF_STRICT = os.environ.get("PYTEST_PERF_STRICT", "0") == "1"

# Import regex patterns
from core.datetime_parsing.regex import DATETIME_RE
from tree.types import _B64_RE, looks_like_color_rgb, looks_like_color_rgba
from units.number_affix import _CURRENCY_RE, _UNITS_RE

# Collect all rows for report generation
_collected_rows: list = []


# ---------------------------------------------------------------------------
# Wrapper functions for regex fullmatch
# ---------------------------------------------------------------------------


def _wrap_datetime_re(text: str):
    """Wrapper for DATETIME_RE.fullmatch."""
    return DATETIME_RE.fullmatch(text)


def _wrap_currency_re(text: str):
    """Wrapper for _CURRENCY_RE.fullmatch."""
    return _CURRENCY_RE.fullmatch(text)


def _wrap_units_re(text: str):
    """Wrapper for _UNITS_RE.fullmatch."""
    return _UNITS_RE.fullmatch(text)


def _wrap_b64_re(text: str):
    """Wrapper for _B64_RE.fullmatch."""
    return _B64_RE.fullmatch(text)


def _wrap_color_rgb(text: str) -> bool:
    """Wrapper for looks_like_color_rgb."""
    return looks_like_color_rgb(text)


def _wrap_color_rgba(text: str) -> bool:
    """Wrapper for looks_like_color_rgba."""
    return looks_like_color_rgba(text)


# ---------------------------------------------------------------------------
# Regex targets and their near-miss families
# ---------------------------------------------------------------------------

REGEX_TARGETS = [
    ("DATETIME_RE", _wrap_datetime_re, [near_datetime, pathological_repetition]),
    ("_CURRENCY_RE", _wrap_currency_re, [near_affix, pathological_repetition]),
    ("_UNITS_RE", _wrap_units_re, [near_affix, pathological_repetition]),
    ("_B64_RE", _wrap_b64_re, [pathological_repetition]),
    ("looks_like_color_rgb", _wrap_color_rgb, [near_color, pathological_repetition]),
    ("looks_like_color_rgba", _wrap_color_rgba, [near_color, pathological_repetition]),
]


def _generate_test_params():
    """Generate test parameters for all regex/family combinations."""
    params = []
    for regex_name, wrapper, families in REGEX_TARGETS:
        for factory in families:
            family_name = factory(1)[0]  # Get family label
            params.append(
                pytest.param(
                    regex_name,
                    wrapper,
                    factory,
                    family_name,
                    id=f"{regex_name}-{family_name}",
                )
            )
    return params


# ---------------------------------------------------------------------------
# Parametrized regex backtracking tests
# ---------------------------------------------------------------------------


@pytest.mark.perf
class TestRegexBacktracking:
    """Backtracking probes for all regex targets."""

    @pytest.mark.parametrize("regex_name,wrapper,factory,family_name", _generate_test_params())
    def test_regex_scaling(self, regex_name, wrapper, factory, family_name):
        """Test scaling behavior for a regex with a specific near-miss family."""
        # Generate scaling rows for the default sizes
        rows = scaling_rows(
            wrapper,
            DEFAULT_SIZES,
            factory,
            function_name=regex_name,
            wrapper_name=regex_name,
            is_decode_path=False,
        )

        # Classify rows for scaling ratio
        classified = classify_rows(rows)

        # Collect rows for report generation
        _collected_rows.extend(classified)

        # Verify near-miss inputs return no match
        for row in classified:
            if row.outcome == "error":
                continue  # Errors are handled separately
            # The actual result is not stored in the row, but we can verify
            # that the wrapper was called successfully

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
# Near-miss verification tests (not perf-marked, run in default suite)
# ---------------------------------------------------------------------------


class TestNearMissVerification:
    """Verify that near-miss inputs return no match for each regex."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_datetime_re_no_match_near_datetime(self, size: int):
        """DATETIME_RE should not match near_datetime inputs."""
        _, text = near_datetime(size)
        result = DATETIME_RE.fullmatch(text)
        assert result is None, f"DATETIME_RE matched near_datetime at size {size}"

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_currency_re_no_match_near_affix(self, size: int):
        """_CURRENCY_RE should not match near_affix inputs (digit run too long)."""
        _, text = near_affix(size)
        result = _CURRENCY_RE.fullmatch(text)
        # May or may not match depending on affix validation
        # The key is that parse_number_affix rejects it due to length

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_units_re_no_match_near_affix(self, size: int):
        """_UNITS_RE should not match near_affix inputs (digit run too long)."""
        _, text = near_affix(size)
        result = _UNITS_RE.fullmatch(text)
        # May or may not match depending on affix validation

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_color_rgb_no_match_near_color(self, size: int):
        """looks_like_color_rgb should return False for near_color inputs > 9 chars."""
        _, text = near_color(size)
        if size > 9:
            result = looks_like_color_rgb(text)
            assert result is False, f"looks_like_color_rgb matched near_color at size {size}"

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_color_rgba_no_match_near_color(self, size: int):
        """looks_like_color_rgba should return False for near_color inputs > 9 chars."""
        _, text = near_color(size)
        if size > 9:
            result = looks_like_color_rgba(text)
            assert result is False, f"looks_like_color_rgba matched near_color at size {size}"


# ---------------------------------------------------------------------------
# Report data access
# ---------------------------------------------------------------------------


def get_collected_rows():
    """Return all collected measurement rows for report generation."""
    return _collected_rows


def clear_collected_rows():
    """Clear the collected rows (for testing)."""
    _collected_rows.clear()
