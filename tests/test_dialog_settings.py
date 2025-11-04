#!/usr/bin/env python3
"""Test script to verify dialog settings persistence"""

import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication


def test_multiline_settings():
    """Test QMultilineDialog settings"""
    # Clear existing settings
    settings = QSettings("Editable-Tree-Model", "QMultilineDialog")
    settings.clear()

    # Verify default values
    word_wrap = bool(settings.value("wordWrap", True, type=bool))
    line_numbers = bool(settings.value("lineNumbers", True, type=bool))

    print("QMultilineDialog - Initial state:")
    print(f"  Word wrap: {word_wrap} (expected: True)")
    print(f"  Line numbers: {line_numbers} (expected: True)")

    # Simulate saving settings
    settings.setValue("wordWrap", False)
    settings.setValue("lineNumbers", False)

    # Verify saved values
    word_wrap = bool(settings.value("wordWrap", True, type=bool))
    line_numbers = bool(settings.value("lineNumbers", True, type=bool))

    print("\nQMultilineDialog - After saving:")
    print(f"  Word wrap: {word_wrap} (expected: False)")
    print(f"  Line numbers: {line_numbers} (expected: False)")

    assert word_wrap == False, "Word wrap should be False"
    assert line_numbers == False, "Line numbers should be False"
    print("✓ QMultilineDialog settings test passed!")


def test_hex_settings():
    """Test QHexDialog settings"""
    # Clear existing settings
    settings = QSettings("Editable-Tree-Model", "QHexDialog")
    settings.clear()

    # Verify default values
    address_area = bool(settings.value("addressArea", True, type=bool))
    ascii_area = bool(settings.value("asciiArea", True, type=bool))
    highlighting = bool(settings.value("highlighting", True, type=bool))

    print("\nQHexDialog - Initial state:")
    print(f"  Address area: {address_area} (expected: True)")
    print(f"  ASCII area: {ascii_area} (expected: True)")
    print(f"  Highlighting: {highlighting} (expected: True)")

    # Simulate saving settings
    settings.setValue("addressArea", False)
    settings.setValue("asciiArea", False)
    settings.setValue("highlighting", False)

    # Verify saved values
    address_area = bool(settings.value("addressArea", True, type=bool))
    ascii_area = bool(settings.value("asciiArea", True, type=bool))
    highlighting = bool(settings.value("highlighting", True, type=bool))

    print("\nQHexDialog - After saving:")
    print(f"  Address area: {address_area} (expected: False)")
    print(f"  ASCII area: {ascii_area} (expected: False)")
    print(f"  Highlighting: {highlighting} (expected: False)")

    assert address_area == False, "Address area should be False"
    assert ascii_area == False, "ASCII area should be False"
    assert highlighting == False, "Highlighting should be False"
    print("✓ QHexDialog settings test passed!")


if __name__ == "__main__":
    # QSettings needs QApplication to exist
    app = QApplication(sys.argv)

    try:
        test_multiline_settings()
        test_hex_settings()
        print("\n" + "=" * 50)
        print("All settings persistence tests passed!")
        print("=" * 50)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
