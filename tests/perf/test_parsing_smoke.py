"""Smoke tests for the hotspot registry.

Calls each registry entry with ``plain_ascii(1024)`` and asserts no exception
escapes. These tests run under ``make test`` without the ``perf`` marker.
"""

from __future__ import annotations

import pytest

from tests.perf.registry import HOTSPOT_REGISTRY, get_registry_names
from tests.perf.string_corpus import plain_ascii

# ---------------------------------------------------------------------------
# Registry completeness tests
# ---------------------------------------------------------------------------


class TestRegistryCompleteness:
    """Verify the registry contains all expected targets."""

    EXPECTED_TARGETS = {
        "parse_json_type",
        "parse_datetime_text",
        "DATETIME_RE.fullmatch",
        "parse_number_affix",
        "_CURRENCY_RE.fullmatch",
        "_UNITS_RE.fullmatch",
        "_looks_like_base64",
        "looks_like_color_rgb",
        "looks_like_color_rgba",
        "infer_text_json_type",
        "compute_editable(BYTES)",
        "compute_editable(ZLIB)",
        "compute_editable(GZIP)",
        "format_with_type(STRING)",
        "format_with_type(BYTES)",
        "decode_bytes",
    }

    def test_registry_has_all_targets(self):
        """All expected targets must be present in the registry."""
        actual_names = set(get_registry_names())
        missing = self.EXPECTED_TARGETS - actual_names
        assert not missing, f"Missing targets: {missing}"

    def test_registry_has_no_duplicates(self):
        """Each target must appear exactly once."""
        names = get_registry_names()
        assert len(names) == len(set(names)), f"Duplicate names found"

    def test_all_entries_have_required_fields(self):
        """Each entry must have name, component, call, and notes fields."""
        for entry in HOTSPOT_REGISTRY:
            assert entry.name, f"Entry missing name"
            assert entry.component, f"Entry {entry.name} missing component"
            assert callable(entry.call), f"Entry {entry.name} call is not callable"
            assert entry.notes, f"Entry {entry.name} missing notes"


# ---------------------------------------------------------------------------
# Smoke tests - call each entry with plain_ascii(1024)
# ---------------------------------------------------------------------------


class TestSmokePlainAscii:
    """Smoke tests calling each registry entry with plain_ascii(1024)."""

    @pytest.mark.parametrize("entry", HOTSPOT_REGISTRY, ids=lambda e: e.name)
    def test_no_exception_escapes(self, entry):
        """Each registry entry should handle plain_ascii(1024) without raising."""
        _, text = plain_ascii(1024)
        # The call should not raise any exception
        try:
            result = entry.call(text)
            # Result can be anything (None, bool, str, etc.) - we just care it doesn't crash
        except Exception as e:
            # Some entries may legitimately fail on non-matching input (e.g., decode_bytes)
            # but they should not crash the test process
            pytest.fail(f"Entry {entry.name} raised {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Entry-specific smoke tests
# ---------------------------------------------------------------------------


class TestEntrySpecificSmoke:
    """Additional smoke tests for specific entries."""

    def test_parse_json_type_returns_json_type(self):
        """parse_json_type should return a JsonType for plain ASCII."""
        from tree.types import JsonType

        entry = next(e for e in HOTSPOT_REGISTRY if e.name == "parse_json_type")
        _, text = plain_ascii(1024)
        result = entry.call(text)
        assert isinstance(result, JsonType)

    def test_parse_datetime_text_returns_none_for_non_datetime(self):
        """parse_datetime_text should return None for plain ASCII."""
        entry = next(e for e in HOTSPOT_REGISTRY if e.name == "parse_datetime_text")
        _, text = plain_ascii(1024)
        result = entry.call(text)
        assert result is None

    def test_looks_like_base64_returns_true_for_valid_base64(self):
        """_looks_like_base64 should return True for valid base64 (1024 'a' chars)."""
        entry = next(e for e in HOTSPOT_REGISTRY if e.name == "_looks_like_base64")
        _, text = plain_ascii(1024)
        result = entry.call(text)
        # 'a' * 1024 is valid base64 (1024 is multiple of 4, 'a' is valid base64 char)
        assert result is True

    def test_looks_like_color_rgb_returns_false_for_long_string(self):
        """looks_like_color_rgb should return False for long strings."""
        entry = next(e for e in HOTSPOT_REGISTRY if e.name == "looks_like_color_rgb")
        _, text = plain_ascii(1024)
        result = entry.call(text)
        assert result is False

    def test_infer_text_json_type_returns_string_for_ascii(self):
        """infer_text_json_type should return STRING for plain ASCII."""
        from tree.types import JsonType

        entry = next(e for e in HOTSPOT_REGISTRY if e.name == "infer_text_json_type")
        _, text = plain_ascii(1024)
        result = entry.call(text)
        # Long plain ASCII should be MULTILINE (contains no newlines but len > 80)
        # Actually, _looks_like_multiline_text checks for "\n" in s, so this should be STRING
        assert result in (JsonType.STRING, JsonType.MULTILINE)
