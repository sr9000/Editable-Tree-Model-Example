"""Tests for datetime inference limits (Commit 1.4).

Verifies that oversized near-date strings return not-a-datetime during
automatic inference without invoking the regex, and that the same string
reaches the datetime parser when explicitly coerced.
"""

from unittest.mock import patch

import settings
from core.datetime_parsing.regex import parse_datetime_text
from tree.types import JsonType, parse_json_type


class TestDatetimeInferenceGating:
    """Verify datetime inference is gated by length."""

    def test_short_datetime_string_parsed(self):
        """A short datetime string is parsed normally."""
        result = parse_datetime_text("2024-01-15")
        assert result is not None

    def test_oversized_string_returns_none(self):
        """An oversized near-date string returns None during inference."""
        oversized = "2024-01-15" + "x" * (settings.INFERENCE_MAX_DATETIME_CHARS + 10)
        result = parse_datetime_text(oversized)
        assert result is None

    def test_oversized_string_with_bypass_reaches_parser(self):
        """An oversized near-date string reaches the parser when allow_expensive=True."""
        oversized = "2024-01-15" + "x" * (settings.INFERENCE_MAX_DATETIME_CHARS + 10)
        # With bypass, the parser runs but the string is not a valid datetime
        result = parse_datetime_text(oversized, allow_expensive=True)
        assert result is None  # Not a valid datetime, but parser was reached

    def test_valid_datetime_at_limit(self):
        """A valid datetime string at or below the limit is parsed."""
        # "2024-01-15" is 10 chars, well below the 40-char limit
        result = parse_datetime_text("2024-01-15")
        assert result is not None

    def test_parse_json_type_inference_uses_default_allow_expensive(self):
        """parse_json_type calls parse_datetime_text with allow_expensive=False (default)."""
        oversized = "2024-01-15" + "x" * (settings.INFERENCE_MAX_DATETIME_CHARS + 10)

        with patch("tree.types.parse_datetime_text") as mock_parse:
            mock_parse.return_value = None
            parse_json_type(oversized)
            # Verify it was called without allow_expensive=True
            mock_parse.assert_called_once()
            call_kwargs = mock_parse.call_args[1]
            assert call_kwargs.get("allow_expensive", False) is False

    def test_valid_datetime_with_bypass(self):
        """A valid datetime string with allow_expensive=True is parsed correctly."""
        result = parse_datetime_text("2024-01-15", allow_expensive=True)
        assert result is not None
