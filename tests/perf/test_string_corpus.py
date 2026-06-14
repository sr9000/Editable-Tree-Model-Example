"""Tests for the adversarial string corpus generators.

Tests every family at sizes 32, 128, and 1024. Each output must satisfy
the acceptance check defined in the plan's family table.
"""

from __future__ import annotations

import pytest

from tests.perf.string_corpus import (
    DEFAULT_SIZES,
    EXTENDED_SIZES,
    FAMILY_REGISTRY,
    base64_like,
    digits,
    escape_heavy,
    mixed_interleaved,
    near_affix,
    near_color,
    near_datetime,
    pathological_repetition,
    plain_ascii,
    source_code_repetition,
    trace_repetition,
    unicode_bulk,
    whitespace,
)

# Try to import the affix limit; fall back to default if not available
try:
    from settings import NUMBER_AFFIX_MAX_LEN as AFFIX_LIMIT
except ImportError:
    AFFIX_LIMIT = 20


# ---------------------------------------------------------------------------
# Registry completeness tests
# ---------------------------------------------------------------------------


class TestRegistryCompleteness:
    """Verify all ten family labels are present exactly once."""

    EXPECTED_FAMILIES = {
        "plain_ascii",
        "whitespace",
        "digits",
        "base64_like",
        "near_datetime",
        "near_affix",
        "near_color",
        "unicode_bulk",
        "pathological_repetition",
        "mixed_interleaved",
        "trace_repetition",
        "source_code_repetition",
        "escape_heavy",
    }

    def test_registry_has_all_families(self):
        """All ten family labels must be present in the registry."""
        assert set(FAMILY_REGISTRY.keys()) == self.EXPECTED_FAMILIES

    def test_registry_has_no_duplicates(self):
        """Each family label must appear exactly once."""
        assert len(FAMILY_REGISTRY) == len(self.EXPECTED_FAMILIES)

    def test_registry_values_are_callable(self):
        """Each registry value must be callable."""
        for name, func in FAMILY_REGISTRY.items():
            assert callable(func), f"{name} is not callable"


# ---------------------------------------------------------------------------
# Family-specific acceptance tests
# ---------------------------------------------------------------------------


class TestPlainAscii:
    """Tests for the plain_ascii family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = plain_ascii(size)
        assert label == "plain_ascii"
        assert len(text) == size
        assert all(c.isascii() for c in text)
        assert text == "a" * size

    def test_non_empty(self):
        label, text = plain_ascii(32)
        assert text != ""


class TestWhitespace:
    """Tests for the whitespace family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = whitespace(size)
        assert label == "whitespace"
        assert text.strip() == ""

    def test_contains_newline(self):
        """At least one variant must contain a newline."""
        _, text = whitespace(32)
        assert "\n" in text

    def test_non_empty(self):
        label, text = whitespace(32)
        assert text != ""


class TestDigits:
    """Tests for the digits family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = digits(size)
        assert label == "digits"
        assert text.isdigit()
        assert len(text) == size

    def test_non_empty(self):
        label, text = digits(32)
        assert text != ""


class TestBase64Like:
    """Tests for the base64_like family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = base64_like(size)
        assert label == "base64_like"
        assert len(text) % 4 == 0

    def test_non_empty(self):
        label, text = base64_like(32)
        assert text != ""


class TestNearDatetime:
    """Tests for the near_datetime family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = near_datetime(size)
        assert label == "near_datetime"
        # Must start with date-like prefix for sizes >= 10
        if size >= 10:
            assert text.startswith("2026-06-13")
        # Must not parse as datetime (contains invalid suffix)
        from core.datetime_parsing import parse_datetime_text

        result = parse_datetime_text(text)
        assert result is None, f"near_datetime text should not parse: {text[:50]}..."

    def test_non_empty(self):
        label, text = near_datetime(32)
        assert text != ""


class TestNearAffix:
    """Tests for the near_affix family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = near_affix(size)
        assert label == "near_affix"
        # Must contain a supported affix prefix/suffix
        assert "$" in text or "€" in text or "£" in text or text[0] in "$€£"
        # For sizes > affix limit, the digit run should exceed the limit
        if size > AFFIX_LIMIT + 5:
            # Count consecutive digits after the prefix
            digit_start = 1  # After '$'
            digit_count = 0
            for c in text[digit_start:]:
                if c.isdigit():
                    digit_count += 1
                else:
                    break
            assert digit_count > AFFIX_LIMIT, f"Digit run {digit_count} should exceed {AFFIX_LIMIT}"

    def test_non_empty(self):
        label, text = near_affix(32)
        assert text != ""


class TestNearColor:
    """Tests for the near_color family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = near_color(size)
        assert label == "near_color"
        if size > 0:
            assert text.startswith("#")
        # For stress sizes (size > 9), length exceeds valid color
        if size > 9:
            assert len(text) > 9

    def test_non_empty(self):
        label, text = near_color(32)
        assert text != ""


class TestUnicodeBulk:
    """Tests for the unicode_bulk family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = unicode_bulk(size)
        assert label == "unicode_bulk"
        assert len(text) == size
        # At least one char must have ord > 127
        assert any(ord(ch) > 127 for ch in text)

    def test_non_empty(self):
        label, text = unicode_bulk(32)
        assert text != ""


class TestPathologicalRepetition:
    """Tests for the pathological_repetition family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = pathological_repetition(size)
        assert label == "pathological_repetition"
        # Generated length is within one motif of size
        # Motifs are at most 5 chars ("2026-"), so allow up to 5 chars difference
        assert abs(len(text) - size) <= 5 or len(text) == size

    def test_non_empty(self):
        label, text = pathological_repetition(32)
        assert text != ""


class TestMixedInterleaved:
    """Tests for the mixed_interleaved family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = mixed_interleaved(size)
        assert label == "mixed_interleaved"
        # Must contain at least three newline-separated families
        # (i.e., at least 2 newlines creating 3+ chunks)
        if size >= 10:
            assert text.count("\n") >= 2, f"Expected at least 2 newlines, got {text.count('\\n')}"

    def test_non_empty(self):
        label, text = mixed_interleaved(32)
        assert text != ""


class TestTraceRepetition:
    """Tests for the trace_repetition family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = trace_repetition(size)
        assert label == "trace_repetition"
        assert len(text) == size
        # Should contain trace-like content (Traceback, File, line numbers)
        if size >= 50:
            assert "Traceback" in text or "File" in text or "line" in text

    def test_non_empty(self):
        label, text = trace_repetition(32)
        assert text != ""


class TestSourceCodeRepetition:
    """Tests for the source_code_repetition family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = source_code_repetition(size)
        assert label == "source_code_repetition"
        assert len(text) == size
        # Should contain code-like content (import, def, =, etc.)
        if size >= 50:
            assert "import" in text or "def" in text or "=" in text or "pygame" in text

    def test_non_empty(self):
        label, text = source_code_repetition(32)
        assert text != ""


class TestEscapeHeavy:
    """Tests for the escape_heavy family."""

    @pytest.mark.parametrize("size", [32, 128, 1024])
    def test_acceptance_check(self, size: int):
        label, text = escape_heavy(size)
        assert label == "escape_heavy"
        assert len(text) == size
        # Should contain many backslashes from escaping
        if size >= 50:
            assert "\\" in text, "escape_heavy should contain backslashes"

    def test_non_empty(self):
        label, text = escape_heavy(32)
        assert text != ""

    def test_contains_escaped_sequences(self):
        """Escape heavy text should contain escaped sequences like \\n, \\"."""
        label, text = escape_heavy(1024)
        # Should have escaped newlines or quotes
        assert "\\n" in text or '\\"' in text or "\\\\" in text


# ---------------------------------------------------------------------------
# Determinism tests
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Verify that calling each generator with the same size produces the same output."""

    @pytest.mark.parametrize("family_name", list(FAMILY_REGISTRY.keys()))
    def test_deterministic_output(self, family_name: str):
        """Same size must produce same label and text across runs."""
        generator = FAMILY_REGISTRY[family_name]
        size = 128
        result1 = generator(size)
        result2 = generator(size)
        assert result1 == result2, f"{family_name} is not deterministic"


# ---------------------------------------------------------------------------
# Size constants tests
# ---------------------------------------------------------------------------


class TestSizeConstants:
    """Verify the size constants are defined correctly."""

    def test_default_sizes(self):
        assert DEFAULT_SIZES == (1024, 4096, 16384, 65536)

    def test_extended_sizes(self):
        assert EXTENDED_SIZES == (262144, 1048576, 10485760)

    def test_default_sizes_are_positive(self):
        assert all(s > 0 for s in DEFAULT_SIZES)

    def test_extended_sizes_are_positive(self):
        assert all(s > 0 for s in EXTENDED_SIZES)
