"""Tests for the explicit coercion bypass seam (Commit 1.3).

Verifies that automatic inference passes allow_expensive=False and explicit
type changes pass allow_expensive=True to coerce_value_for_type.
"""

from unittest.mock import patch

from tree.item import JsonTreeItem
from tree.item_coercion import coerce_value_for_type
from tree.types import JsonType


class TestExplicitCoercionBypassSeam:
    """Verify allow_expensive is passed correctly from JsonTreeItem."""

    def test_automatic_inference_passes_allow_expensive_false(self):
        """When explicit_type is False, _coerce_value_for_type passes allow_expensive=False."""
        item = JsonTreeItem(value="hello")
        assert item.explicit_type is False

        captured = {}

        original = coerce_value_for_type

        def spy(json_type, value, strict, old_type=None, *, allow_expensive=False):
            captured["allow_expensive"] = allow_expensive
            return original(json_type, value, strict, old_type=old_type, allow_expensive=allow_expensive)

        with patch("tree.item.coerce_value_for_type", side_effect=spy):
            item._coerce_value_for_type(JsonType.STRING, "test", strict=False)

        assert captured.get("allow_expensive") is False

    def test_explicit_type_passes_allow_expensive_true(self):
        """When explicit_type is True, _coerce_value_for_type passes allow_expensive=True."""
        item = JsonTreeItem(value="hello")
        item.explicit_type = True

        captured = {}

        original = coerce_value_for_type

        def spy(json_type, value, strict, old_type=None, *, allow_expensive=False):
            captured["allow_expensive"] = allow_expensive
            return original(json_type, value, strict, old_type=old_type, allow_expensive=allow_expensive)

        with patch("tree.item.coerce_value_for_type", side_effect=spy):
            item._coerce_value_for_type(JsonType.STRING, "test", strict=False)

        assert captured.get("allow_expensive") is True


class TestCoerceValueTypeAcceptsAllowExpensive:
    """Verify coerce_value_for_type accepts the allow_expensive parameter."""

    def test_accepts_allow_expensive_false(self):
        ok, value = coerce_value_for_type(JsonType.STRING, "test", strict=False, allow_expensive=False)
        assert ok is True
        assert value == "test"

    def test_accepts_allow_expensive_true(self):
        ok, value = coerce_value_for_type(JsonType.STRING, "test", strict=False, allow_expensive=True)
        assert ok is True
        assert value == "test"

    def test_default_allow_expensive_is_false(self):
        ok, value = coerce_value_for_type(JsonType.STRING, "test", strict=False)
        assert ok is True
        assert value == "test"
