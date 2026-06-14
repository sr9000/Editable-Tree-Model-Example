"""Decode/decompress amplification probes.

These tests cover base64, zlib, and gzip branches that can allocate decoded
buffers larger than the source text or repeat decode work.

Run with: ``pytest -m perf tests/perf/test_decode_amplification.py``
"""

from __future__ import annotations

import base64
import gzip
import os
import zlib

import pytest

from tests.perf.harness import classify_rows, measure_call, scaling_rows
from tests.perf.string_corpus import DEFAULT_SIZES, base64_like, plain_ascii

# Check if strict mode is enabled
PERF_STRICT = os.environ.get("PYTEST_PERF_STRICT", "0") == "1"

# Import target functions
from delegates.formatting.value_formatting import format_with_type
from tree.codecs.bytes_codec import decode_bytes
from tree.item_coercion import compute_editable
from tree.types import JsonType, _looks_like_base64, parse_json_type

# Collect all rows for report generation
_collected_rows: list = []


# ---------------------------------------------------------------------------
# Valid small fixtures for successful decode paths
# ---------------------------------------------------------------------------


def _make_valid_bytes_fixture() -> str:
    """Create a valid base64-encoded BYTES fixture (at least 20 chars for _B64_RE)."""
    # Need at least 20 chars to match _B64_RE pattern
    raw = b"Hello, World! This is a longer test message for base64 encoding."
    return base64.b64encode(raw).decode("ascii")


def _make_valid_zlib_fixture() -> str:
    """Create a valid base64-encoded ZLIB fixture."""
    raw = b"Hello, World! This is compressed data."
    compressed = zlib.compress(raw)
    return base64.b64encode(compressed).decode("ascii")


def _make_valid_gzip_fixture() -> str:
    """Create a valid base64-encoded GZIP fixture."""
    raw = b"Hello, World! This is gzip compressed data."
    compressed = gzip.compress(raw)
    return base64.b64encode(compressed).decode("ascii")


# ---------------------------------------------------------------------------
# Wrapper functions
# ---------------------------------------------------------------------------


def _wrap_looks_like_base64(text: str) -> bool:
    """Wrapper for _looks_like_base64."""
    return _looks_like_base64(text)


def _wrap_parse_json_type(text: str) -> JsonType:
    """Wrapper for parse_json_type."""
    return parse_json_type(text)


def _wrap_compute_editable_bytes(text: str) -> bool:
    """Wrapper for compute_editable with BYTES type."""
    return compute_editable(JsonType.BYTES, text, editable_blob_limit=1024 * 1024)


def _wrap_compute_editable_zlib(text: str) -> bool:
    """Wrapper for compute_editable with ZLIB type."""
    return compute_editable(JsonType.ZLIB, text, editable_blob_limit=1024 * 1024)


def _wrap_compute_editable_gzip(text: str) -> bool:
    """Wrapper for compute_editable with GZIP type."""
    return compute_editable(JsonType.GZIP, text, editable_blob_limit=1024 * 1024)


def _wrap_decode_bytes(text: str) -> bytes:
    """Wrapper for decode_bytes with BYTES type."""
    return decode_bytes(text, JsonType.BYTES)


def _wrap_decode_bytes_zlib(text: str) -> bytes:
    """Wrapper for decode_bytes with ZLIB type."""
    return decode_bytes(text, JsonType.ZLIB)


def _wrap_decode_bytes_gzip(text: str) -> bytes:
    """Wrapper for decode_bytes with GZIP type."""
    return decode_bytes(text, JsonType.GZIP)


def _wrap_format_with_type_bytes(text: str) -> str:
    """Wrapper for format_with_type with BYTES type."""
    return format_with_type(text, JsonType.BYTES)


def _wrap_format_with_type_zlib(text: str) -> str:
    """Wrapper for format_with_type with ZLIB type."""
    return format_with_type(text, JsonType.ZLIB)


def _wrap_format_with_type_gzip(text: str) -> str:
    """Wrapper for format_with_type with GZIP type."""
    return format_with_type(text, JsonType.GZIP)


# ---------------------------------------------------------------------------
# Valid fixture tests (not perf-marked, run in default suite)
# ---------------------------------------------------------------------------


class TestValidFixtures:
    """Verify that valid small fixtures exercise successful decode paths."""

    def test_valid_bytes_fixture_decodes(self):
        """Valid BYTES fixture should decode successfully."""
        fixture = _make_valid_bytes_fixture()
        result = decode_bytes(fixture, JsonType.BYTES)
        assert result == b"Hello, World! This is a longer test message for base64 encoding."

    def test_valid_zlib_fixture_decodes(self):
        """Valid ZLIB fixture should decompress successfully."""
        fixture = _make_valid_zlib_fixture()
        result = decode_bytes(fixture, JsonType.ZLIB)
        assert result == b"Hello, World! This is compressed data."

    def test_valid_gzip_fixture_decodes(self):
        """Valid GZIP fixture should decompress successfully."""
        fixture = _make_valid_gzip_fixture()
        result = decode_bytes(fixture, JsonType.GZIP)
        assert result == b"Hello, World! This is gzip compressed data."

    def test_parse_json_type_detects_bytes(self):
        """parse_json_type should detect valid base64 as BYTES."""
        fixture = _make_valid_bytes_fixture()
        result = parse_json_type(fixture)
        assert result == JsonType.BYTES

    def test_parse_json_type_detects_zlib(self):
        """parse_json_type should detect valid zlib as ZLIB."""
        fixture = _make_valid_zlib_fixture()
        result = parse_json_type(fixture)
        assert result == JsonType.ZLIB

    def test_parse_json_type_detects_gzip(self):
        """parse_json_type should detect valid gzip as GZIP."""
        fixture = _make_valid_gzip_fixture()
        result = parse_json_type(fixture)
        assert result == JsonType.GZIP

    def test_compute_editable_bytes_returns_true(self):
        """compute_editable should return True for valid BYTES."""
        fixture = _make_valid_bytes_fixture()
        result = compute_editable(JsonType.BYTES, fixture, editable_blob_limit=1024 * 1024)
        assert result is True

    def test_compute_editable_zlib_returns_true(self):
        """compute_editable should return True for valid ZLIB."""
        fixture = _make_valid_zlib_fixture()
        result = compute_editable(JsonType.ZLIB, fixture, editable_blob_limit=1024 * 1024)
        assert result is True

    def test_compute_editable_gzip_returns_true(self):
        """compute_editable should return True for valid GZIP."""
        fixture = _make_valid_gzip_fixture()
        result = compute_editable(JsonType.GZIP, fixture, editable_blob_limit=1024 * 1024)
        assert result is True


# ---------------------------------------------------------------------------
# Perf-marked scaling tests for decode paths
# ---------------------------------------------------------------------------

DECODE_TARGETS = [
    ("_looks_like_base64", _wrap_looks_like_base64, False),
    ("parse_json_type", _wrap_parse_json_type, False),
    ("compute_editable(BYTES)", _wrap_compute_editable_bytes, True),
    ("compute_editable(ZLIB)", _wrap_compute_editable_zlib, True),
    ("compute_editable(GZIP)", _wrap_compute_editable_gzip, True),
    ("decode_bytes(BYTES)", _wrap_decode_bytes, True),
    ("decode_bytes(ZLIB)", _wrap_decode_bytes_zlib, True),
    ("decode_bytes(GZIP)", _wrap_decode_bytes_gzip, True),
    ("format_with_type(BYTES)", _wrap_format_with_type_bytes, True),
    ("format_with_type(ZLIB)", _wrap_format_with_type_zlib, True),
    ("format_with_type(GZIP)", _wrap_format_with_type_gzip, True),
]


def _generate_test_params():
    """Generate test parameters for all decode targets and families."""
    params = []
    for name, wrapper, is_decode in DECODE_TARGETS:
        # Test with base64_like family (valid base64 syntax)
        params.append(
            pytest.param(
                name,
                wrapper,
                base64_like,
                "base64_like",
                is_decode,
                id=f"{name}-base64_like",
            )
        )
        # Test with plain_ascii family (non-base64)
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
class TestDecodeAmplification:
    """Amplification probes for decode/decompress paths."""

    @pytest.mark.parametrize("name,wrapper,factory,family_name,is_decode", _generate_test_params())
    def test_decode_scaling(self, name, wrapper, factory, family_name, is_decode):
        """Test scaling behavior for decode paths with various inputs."""
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
# Oversized text tests (not perf-marked, verify no crash)
# ---------------------------------------------------------------------------


class TestOversizedTextNoCrash:
    """Verify that oversized text does not crash the test process."""

    def test_looks_like_base64_oversized(self):
        """_looks_like_base64 should handle oversized text without crashing."""
        _, text = base64_like(65536)
        result = _looks_like_base64(text)
        # Result can be True or False, just shouldn't crash
        assert isinstance(result, bool)

    def test_parse_json_type_oversized(self):
        """parse_json_type should handle oversized text without crashing."""
        _, text = base64_like(65536)
        result = parse_json_type(text)
        # Should return a JsonType
        assert isinstance(result, JsonType)

    def test_compute_editable_oversized_bytes(self):
        """compute_editable should handle oversized BYTES text without crashing."""
        _, text = base64_like(65536)
        result = compute_editable(JsonType.BYTES, text, editable_blob_limit=1024 * 1024)
        assert isinstance(result, bool)

    def test_format_with_type_oversized_bytes(self):
        """format_with_type should handle oversized BYTES text without crashing."""
        _, text = base64_like(65536)
        result = format_with_type(text, JsonType.BYTES)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Report data access
# ---------------------------------------------------------------------------


def get_collected_rows():
    """Return all collected measurement rows for report generation."""
    return _collected_rows


def clear_collected_rows():
    """Clear the collected rows (for testing)."""
    _collected_rows.clear()
