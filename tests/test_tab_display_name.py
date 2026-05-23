"""Regression tests for ``JsonTab.display_name`` (issue #03).

The display name must be the *basename* of the file path on both POSIX and
Windows-style separators, and must fall back to ``"Untitled"`` when the
tab has no associated file.
"""

from __future__ import annotations

import pytest

from documents.tab import JsonTab


@pytest.fixture
def tab(qtbot):
    t = JsonTab(update_actions_callback=lambda: None, data={}, show_root=False)
    qtbot.addWidget(t)
    return t


@pytest.mark.parametrize(
    "file_path,expected",
    [
        ("/home/me/data.json", "data.json"),
        ("C:\\Users\\me\\Documents\\data.json", "data.json"),
        ("C:/Users/me/data.json", "data.json"),
        ("data.json", "data.json"),
        # Mixed separators (rare but possible after string concat on Windows).
        ("C:\\Users/me\\data.json", "data.json"),
    ],
)
def test_display_name_uses_basename(tab, file_path, expected):
    tab.file_path = file_path
    assert tab.display_name() == expected


@pytest.mark.parametrize("file_path", ["", None])
def test_display_name_untitled_when_no_path(tab, file_path):
    tab.file_path = file_path
    assert tab.display_name() == "Untitled"


def test_display_name_appends_dirty_marker(tab):
    tab.file_path = "C:\\Users\\me\\data.json"
    tab._set_dirty(True)
    assert tab.display_name() == "data.json *"
