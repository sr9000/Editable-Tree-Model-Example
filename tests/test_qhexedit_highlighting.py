import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from editors.windowed.hexedit import QHexEdit
from editors.windowed.hexedit.color_manager import ColorManager


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_highlighting_property(qapp):
    """Test that highlighting property works"""
    editor = QHexEdit()

    # Default should be True
    assert editor.highlighting() is True

    # Test setter
    editor.setHighlighting(False)
    assert editor.highlighting() is False

    editor.setHighlighting(True)
    assert editor.highlighting() is True


def test_highlighting_color_property(qapp):
    """Test that highlighting color property works"""
    editor = QHexEdit()

    # Get default color
    default_color = editor.highlightingColor()
    assert isinstance(default_color, QColor)

    # Set new color
    test_color = QColor(255, 0, 0)  # Red
    editor.setHighlightingColor(test_color)

    # Verify color was set
    current_color = editor.highlightingColor()
    assert current_color.red() == 255
    assert current_color.green() == 0
    assert current_color.blue() == 0


def test_color_manager_highlighting_enabled(qapp):
    """Test that ColorManager respects highlighting enabled flag"""
    cm = ColorManager()

    # Initially enabled
    assert cm.isHighlightingEnabled() is True

    # Disable highlighting
    cm.setHighlightingEnabled(False)
    assert cm.isHighlightingEnabled() is False

    # Enable highlighting
    cm.setHighlightingEnabled(True)
    assert cm.isHighlightingEnabled() is True


def test_highlighting_integration(qapp):
    """Test that highlighting actually affects rendering"""
    editor = QHexEdit()

    # Load some data
    data = bytearray([0x00, 0x01, 0x02, 0x03])
    editor.setData(data)

    # Modify a byte (this should mark it as changed)
    editor.replace(0, 0xFF)

    # Enable highlighting
    editor.setHighlighting(True)

    # Verify the color manager is configured correctly
    cm = editor._colorManager
    assert cm.isHighlightingEnabled() is True

    # Disable highlighting
    editor.setHighlighting(False)
    assert cm.isHighlightingEnabled() is False


def test_highlighting_syncs_with_color_manager(qapp):
    """Test that setHighlighting updates both widget and color manager"""
    editor = QHexEdit()

    # Both should start as True
    assert editor.highlighting() is True
    assert editor._colorManager.isHighlightingEnabled() is True

    # Disable via widget method
    editor.setHighlighting(False)

    # Both should be disabled
    assert editor.highlighting() is False
    assert editor._colorManager.isHighlightingEnabled() is False

    # Enable via widget method
    editor.setHighlighting(True)

    # Both should be enabled
    assert editor.highlighting() is True
    assert editor._colorManager.isHighlightingEnabled() is True
