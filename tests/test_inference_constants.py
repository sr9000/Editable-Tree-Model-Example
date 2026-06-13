"""Tests for inference safety constants in settings.py.

These constants are load-time safety limits that gate expensive inference
work (regex, datetime parsing, color checks) during automatic type
classification. They are NOT editor-warning limits
(STRING_EDIT_WARNING_LIMIT_CHARS, MULTILINE_EDIT_WARNING_LIMIT_CHARS,
BINARY_ATTACH_WARNING_LIMIT_BYTES, BINARY_EDIT_WARNING_LIMIT_BYTES) which
control manual editor UX rather than load-time inference.
"""

import settings


class TestInferenceConstantsArePositiveIntegers:
    """Each inference constant must be an int greater than zero."""

    def test_inference_max_datetime_chars_is_positive_int(self):
        """INFERENCE_MAX_DATETIME_CHARS is a load-time safety limit, not an editor-warning limit."""
        assert isinstance(settings.INFERENCE_MAX_DATETIME_CHARS, int)
        assert settings.INFERENCE_MAX_DATETIME_CHARS > 0

    def test_inference_max_affix_chars_is_positive_int(self):
        """INFERENCE_MAX_AFFIX_CHARS is a load-time safety limit, not an editor-warning limit."""
        assert isinstance(settings.INFERENCE_MAX_AFFIX_CHARS, int)
        assert settings.INFERENCE_MAX_AFFIX_CHARS > 0

    def test_inference_max_color_chars_is_positive_int(self):
        """INFERENCE_MAX_COLOR_CHARS is a load-time safety limit, not an editor-warning limit."""
        assert isinstance(settings.INFERENCE_MAX_COLOR_CHARS, int)
        assert settings.INFERENCE_MAX_COLOR_CHARS > 0

    def test_format_preview_decode_limit_bytes_is_positive_int(self):
        """FORMAT_PREVIEW_DECODE_LIMIT_BYTES is a load-time safety limit, not an editor-warning limit."""
        assert isinstance(settings.FORMAT_PREVIEW_DECODE_LIMIT_BYTES, int)
        assert settings.FORMAT_PREVIEW_DECODE_LIMIT_BYTES > 0


class TestInferenceConstantsDistinctFromEditorWarningLimits:
    """Inference limits must be distinct from editor-opening warning limits.

    Editor-warning limits (STRING_EDIT_WARNING_LIMIT_CHARS,
    MULTILINE_EDIT_WARNING_LIMIT_CHARS, BINARY_ATTACH_WARNING_LIMIT_BYTES,
    BINARY_EDIT_WARNING_LIMIT_BYTES) control manual editor UX. Inference
    limits gate load-time type classification work.
    """

    def test_inference_datetime_chars_distinct_from_string_edit_warning(self):
        """INFERENCE_MAX_DATETIME_CHARS is a load-time safety limit, distinct from STRING_EDIT_WARNING_LIMIT_CHARS."""
        assert settings.INFERENCE_MAX_DATETIME_CHARS != settings.STRING_EDIT_WARNING_LIMIT_CHARS

    def test_inference_datetime_chars_distinct_from_multiline_edit_warning(self):
        """INFERENCE_MAX_DATETIME_CHARS is a load-time safety limit, distinct from MULTILINE_EDIT_WARNING_LIMIT_CHARS."""
        assert settings.INFERENCE_MAX_DATETIME_CHARS != settings.MULTILINE_EDIT_WARNING_LIMIT_CHARS

    def test_inference_affix_chars_distinct_from_string_edit_warning(self):
        """INFERENCE_MAX_AFFIX_CHARS is a load-time safety limit, distinct from STRING_EDIT_WARNING_LIMIT_CHARS."""
        assert settings.INFERENCE_MAX_AFFIX_CHARS != settings.STRING_EDIT_WARNING_LIMIT_CHARS

    def test_inference_color_chars_distinct_from_string_edit_warning(self):
        """INFERENCE_MAX_COLOR_CHARS is a load-time safety limit, distinct from STRING_EDIT_WARNING_LIMIT_CHARS."""
        assert settings.INFERENCE_MAX_COLOR_CHARS != settings.STRING_EDIT_WARNING_LIMIT_CHARS

    def test_format_preview_limit_distinct_from_binary_attach_warning(self):
        """FORMAT_PREVIEW_DECODE_LIMIT_BYTES is a load-time safety limit, distinct from BINARY_ATTACH_WARNING_LIMIT_BYTES."""
        assert settings.FORMAT_PREVIEW_DECODE_LIMIT_BYTES != settings.BINARY_ATTACH_WARNING_LIMIT_BYTES

    def test_format_preview_limit_distinct_from_binary_edit_warning(self):
        """FORMAT_PREVIEW_DECODE_LIMIT_BYTES is a load-time safety limit, distinct from BINARY_EDIT_WARNING_LIMIT_BYTES."""
        assert settings.FORMAT_PREVIEW_DECODE_LIMIT_BYTES != settings.BINARY_EDIT_WARNING_LIMIT_BYTES
