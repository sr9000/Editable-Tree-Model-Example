"""Tests for tree/inference_limits.py helpers.

Boundary tests cover allowed-at-limit and rejected-above-limit for every
length-gated helper. base64_syntax_valid tests cover valid base64 at various
sizes, invalid length (not mod 4), invalid characters, and empty string.
"""

import base64

import settings
from state.edit_limits import set_base64_inference_min_length_chars
from tree.inference_limits import (
    affix_inference_allowed,
    base64_syntax_valid,
    color_inference_allowed,
    datetime_inference_allowed,
    format_preview_decode_allowed,
)
from tree.types import JsonType, _looks_like_base64, parse_json_type


class TestDatetimeInferenceAllowed:
    """Boundary tests for datetime_inference_allowed."""

    def test_allowed_at_limit(self):
        text = "x" * settings.INFERENCE_MAX_DATETIME_CHARS
        assert datetime_inference_allowed(text) is True

    def test_rejected_above_limit(self):
        text = "x" * (settings.INFERENCE_MAX_DATETIME_CHARS + 1)
        assert datetime_inference_allowed(text) is False

    def test_bypass_allows_oversized(self):
        text = "x" * (settings.INFERENCE_MAX_DATETIME_CHARS + 100)
        assert datetime_inference_allowed(text, allow_expensive=True) is True

    def test_empty_string_allowed(self):
        assert datetime_inference_allowed("") is True


class TestAffixInferenceAllowed:
    """Boundary tests for affix_inference_allowed."""

    def test_allowed_at_limit(self):
        text = "x" * settings.INFERENCE_MAX_AFFIX_CHARS
        assert affix_inference_allowed(text) is True

    def test_rejected_above_limit(self):
        text = "x" * (settings.INFERENCE_MAX_AFFIX_CHARS + 1)
        assert affix_inference_allowed(text) is False

    def test_bypass_allows_oversized(self):
        text = "x" * (settings.INFERENCE_MAX_AFFIX_CHARS + 100)
        assert affix_inference_allowed(text, allow_expensive=True) is True

    def test_empty_string_allowed(self):
        assert affix_inference_allowed("") is True


class TestColorInferenceAllowed:
    """Boundary tests for color_inference_allowed."""

    def test_allowed_at_limit(self):
        text = "x" * settings.INFERENCE_MAX_COLOR_CHARS
        assert color_inference_allowed(text) is True

    def test_rejected_above_limit(self):
        text = "x" * (settings.INFERENCE_MAX_COLOR_CHARS + 1)
        assert color_inference_allowed(text) is False

    def test_bypass_allows_oversized(self):
        text = "x" * (settings.INFERENCE_MAX_COLOR_CHARS + 100)
        assert color_inference_allowed(text, allow_expensive=True) is True

    def test_empty_string_allowed(self):
        assert color_inference_allowed("") is True


class TestBase64SyntaxValid:
    """Tests for base64_syntax_valid content validation."""

    def test_valid_base64_short(self):
        # "YWJj" is base64 for "abc" (4 chars, mod 4 == 0)
        assert base64_syntax_valid("YWJj") is True

    def test_valid_base64_with_padding(self):
        # "YQ==" is base64 for "a" (4 chars with padding)
        assert base64_syntax_valid("YQ==") is True
        # "YWI=" is base64 for "ab" (4 chars with 1 pad)
        assert base64_syntax_valid("YWI=") is True

    def test_valid_base64_large(self):
        # Generate a large valid base64 string (1MB)
        raw = b"x" * (1024 * 1024)
        encoded = base64.b64encode(raw).decode("ascii")
        assert base64_syntax_valid(encoded) is True

    def test_invalid_length_not_mod_4(self):
        # 5 chars: not divisible by 4
        assert base64_syntax_valid("YWJjx") is False
        # 3 chars
        assert base64_syntax_valid("YWJ") is False
        # 1 char
        assert base64_syntax_valid("Y") is False

    def test_invalid_characters_whitespace(self):
        # Spaces are not valid base64 characters
        assert base64_syntax_valid("YW Jj") is False
        assert base64_syntax_valid("YWJj\n") is False
        assert base64_syntax_valid(" YWJ") is False

    def test_invalid_characters_special(self):
        # Special characters not in base64 alphabet
        assert base64_syntax_valid("YW!j") is False
        assert base64_syntax_valid("YW@j") is False
        assert base64_syntax_valid("YW#j") is False

    def test_empty_string_invalid(self):
        assert base64_syntax_valid("") is False

    def test_padding_only_rejected(self):
        # "====" has 4 padding chars; regex allows max 2
        assert base64_syntax_valid("====") is False

    def test_two_padding_passes_syntax(self):
        # "AA==" is syntactically valid (2 data chars + 2 padding)
        assert base64_syntax_valid("AA==") is True

    def test_too_much_padding(self):
        # "Y===" has 3 padding chars, regex allows max 2
        assert base64_syntax_valid("Y===") is False


class TestBase64InferenceMinimumLength:
    def teardown_method(self):
        set_base64_inference_min_length_chars(settings.BASE64_INFERENCE_MIN_LENGTH_CHARS)

    def test_short_valid_base64_is_not_inferred_by_default(self):
        assert len("bXkgbG92ZWx5IGJ5dGVzIQ==") < settings.BASE64_INFERENCE_MIN_LENGTH_CHARS
        assert _looks_like_base64("bXkgbG92ZWx5IGJ5dGVzIQ==") is False
        assert parse_json_type("bXkgbG92ZWx5IGJ5dGVzIQ==") is JsonType.STRING

    def test_valid_base64_at_default_minimum_length_is_inferred(self):
        raw = b"x" * 75
        encoded = base64.b64encode(raw).decode("ascii")
        assert len(encoded) == settings.BASE64_INFERENCE_MIN_LENGTH_CHARS
        assert _looks_like_base64(encoded) is True
        assert parse_json_type(encoded) is JsonType.BYTES

    def test_lowered_minimum_allows_shorter_valid_base64(self):
        set_base64_inference_min_length_chars(20)
        assert _looks_like_base64("bXkgbG92ZWx5IGJ5dGVzIQ==") is True
        assert parse_json_type("bXkgbG92ZWx5IGJ5dGVzIQ==") is JsonType.BYTES


class TestFormatPreviewDecodeAllowed:
    """Boundary tests for format_preview_decode_allowed."""

    def test_allowed_at_limit(self):
        assert format_preview_decode_allowed(settings.FORMAT_PREVIEW_DECODE_LIMIT_BYTES) is True

    def test_rejected_above_limit(self):
        assert format_preview_decode_allowed(settings.FORMAT_PREVIEW_DECODE_LIMIT_BYTES + 1) is False

    def test_zero_allowed(self):
        assert format_preview_decode_allowed(0) is True

    def test_one_byte_allowed(self):
        assert format_preview_decode_allowed(1) is True
