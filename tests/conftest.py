from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QStandardPaths

from settings import APPLICATION_ID

_SETTINGS_ROOT = Path(tempfile.mkdtemp(prefix="editable-tree-model-pytest-settings-"))


def pytest_configure(config):
    """Keep test QSettings away from the developer's real app settings."""
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(_SETTINGS_ROOT))
    QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, str(_SETTINGS_ROOT))
    QStandardPaths.setTestModeEnabled(True)


def pytest_unconfigure(config):
    shutil.rmtree(_SETTINGS_ROOT, ignore_errors=True)


_SETTINGS_APPLICATIONS = (
    "app",
    "theme",
    "validation",
    "view_state",
    "QHexDialog-7a927c68-412c-4f06-8ce6-2158dde1314e",
    "QMultilineDialog-19beb602-e9c1-479b-a037-d9dbfbddec65",
)


@pytest.fixture(autouse=True)
def isolated_qsettings():
    """Start every test from clean per-test app settings.

    Individual tests can still verify persistence by constructing multiple
    windows/dialogs inside the same test.  The temp INI backend prevents both
    directions of pollution: developer runs do not affect tests, and tests do
    not write into the developer's real QSettings store.
    """
    _clear_test_settings()
    yield
    _clear_test_settings()


def _clear_test_settings() -> None:
    for application in _SETTINGS_APPLICATIONS:
        settings = QSettings(APPLICATION_ID, application)
        settings.clear()
        settings.sync()
