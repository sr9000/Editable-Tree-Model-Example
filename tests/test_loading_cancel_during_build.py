"""Tests for cooperative cancellation during chunked build (Plan 3, Commit 3.4)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from app.loading.builder import ChunkedTreeBuilder
from app.loading.cancellation import CancellationToken
from app.loading.progress import STAGE_BUILDING_TREE
from app.main_window import MainWindow
from app.recent_files import recent_files
from documents.tab import JsonTab
from validation.schema_registry import get_schema_registry
from validation.schema_types import SchemaSource


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        maybe_tab = win.tabWidget.widget(i)
        if isinstance(maybe_tab, JsonTab):
            maybe_tab.undo_stack.setClean()
    win.close()
    win.deleteLater()
    QApplication.processEvents()


def test_builder_cancelled_signal_emits_and_never_finishes(qtbot):
    token = CancellationToken()
    data = {"items": [{"id": i, "value": f"v{i}"} for i in range(3000)]}

    cancelled = [0]
    finished = [0]

    def on_progress(_done: int, _total: int) -> None:
        if not token.is_cancelled:
            token.cancel()

    builder = ChunkedTreeBuilder(data, cancellation_token=token)
    builder.progress.connect(on_progress)
    builder.cancelled.connect(lambda: cancelled.__setitem__(0, cancelled[0] + 1))
    builder.finished.connect(lambda _model: finished.__setitem__(0, finished[0] + 1))
    builder.start()

    qtbot.waitUntil(lambda: cancelled[0] == 1, timeout=2000)

    assert finished[0] == 0
    assert builder._root_item is None


def test_cancel_open_during_chunked_build_has_no_side_effects(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "big.json"
    _write_json(doc, {"seed": True})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        initial_tabs = win.tabWidget.count()
        initial_recent = list(recent_files(win))

        schema_registry = get_schema_registry()
        schema_source = SchemaSource.for_file(doc)
        assert schema_registry.lookup(schema_source) is None

        build_cancelled = [0]
        build_finished = [0]
        hooked_builder = [False]

        def fast_parser(_path: str):
            return {"items": [{"id": i, "value": f"value_{i}"} for i in range(12000)]}, "json"

        with patch.object(QMessageBox, "critical") as mock_critical:
            task_id = win._load_coordinator.open_file_async(str(doc), parser=fast_parser)
            assert task_id is not None

            def on_stage(stage: str) -> None:
                if stage != STAGE_BUILDING_TREE or hooked_builder[0]:
                    return
                task = win._load_coordinator._tasks.get(task_id)
                if task is None or task.builder is None:
                    return
                hooked_builder[0] = True
                task.builder.cancelled.connect(lambda: build_cancelled.__setitem__(0, build_cancelled[0] + 1))
                task.builder.finished.connect(lambda _model: build_finished.__setitem__(0, build_finished[0] + 1))
                QTimer.singleShot(0, win._load_coordinator.cancel_current)

            win._load_coordinator.stage_changed.connect(on_stage)

            assert not win._load_coordinator._run_blocking(task_id)

            qtbot.waitUntil(lambda: task_id not in win._load_coordinator._tasks, timeout=2000)
            qtbot.waitUntil(lambda: build_cancelled[0] == 1, timeout=2000)

            assert build_finished[0] == 0
            assert win._load_coordinator._current_task_id is None
            assert win.tabWidget.count() == initial_tabs
            assert list(recent_files(win)) == initial_recent
            assert schema_registry.lookup(schema_source) is None
            assert "Open cancelled" in win.statusBar.currentMessage()
            mock_critical.assert_not_called()
    finally:
        _cleanup(win)
