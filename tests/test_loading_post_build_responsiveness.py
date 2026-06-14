from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer

from app.loading.progress import (
    STAGE_APPLYING_RELOAD,
    STAGE_BINDING_UI,
    STAGE_COMPLETE,
    STAGE_DISCOVERING_SCHEMA,
    STAGE_VALIDATING_DOCUMENT,
)
from app.main_window import MainWindow
from documents.controllers.validation import TabValidationController
from documents.tab import JsonTab


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        maybe_tab = win.tabWidget.widget(i)
        if isinstance(maybe_tab, JsonTab):
            maybe_tab.undo_stack.setClean()
    win.close()
    win.deleteLater()


def test_large_open_keeps_event_loop_alive_after_build(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(TabValidationController, "_REPAINT_BATCH_SIZE", 5)

    doc = tmp_path / "data.json"
    schema = tmp_path / "data.schema.json"
    schema.write_text('{"type":"object","additionalProperties":{"type":"integer"}}', encoding="utf-8")
    payload = {f"k{i}": "bad" for i in range(300)}
    _write_json(doc, payload)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    probe = QTimer(win)
    try:
        stages: list[str] = []
        ticks_post_build = {"count": 0}
        win._load_coordinator.stage_changed.connect(lambda s: stages.append(s))

        def _on_probe() -> None:
            if STAGE_BINDING_UI in stages and STAGE_COMPLETE not in stages:
                ticks_post_build["count"] += 1

        probe.timeout.connect(_on_probe)
        probe.start(0)

        task_id = win._load_coordinator.open_file_async(str(doc))
        assert task_id is not None
        qtbot.waitUntil(lambda: task_id not in win._load_coordinator._tasks, timeout=6000)

        assert ticks_post_build["count"] >= 1
        assert STAGE_BINDING_UI in stages
        assert STAGE_DISCOVERING_SCHEMA in stages
        assert STAGE_VALIDATING_DOCUMENT in stages
        assert STAGE_COMPLETE in stages
    finally:
        probe.stop()
        _cleanup(win)


def test_large_reload_keeps_event_loop_alive_after_build(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(TabValidationController, "_REPAINT_BATCH_SIZE", 5)

    doc = tmp_path / "data.json"
    schema = tmp_path / "data.schema.json"
    schema.write_text('{"type":"object","additionalProperties":{"type":"integer"}}', encoding="utf-8")
    _write_json(doc, {"ok": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    probe = QTimer(win)
    try:
        assert win._open_path(str(doc))
        tab = win._current_tab()
        assert isinstance(tab, JsonTab)

        _write_json(doc, {f"k{i}": "bad" for i in range(400)})

        stages: list[str] = []
        ticks_post_build = {"count": 0}
        win._load_coordinator.stage_changed.connect(lambda s: stages.append(s))

        def _on_probe() -> None:
            if STAGE_APPLYING_RELOAD in stages and STAGE_COMPLETE not in stages:
                ticks_post_build["count"] += 1

        probe.timeout.connect(_on_probe)
        probe.start(0)

        task_id = win._load_coordinator.reload_file_async(tab, str(doc))
        assert task_id is not None
        qtbot.waitUntil(lambda: task_id not in win._load_coordinator._tasks, timeout=6000)

        assert ticks_post_build["count"] >= 1
        assert STAGE_APPLYING_RELOAD in stages
        assert STAGE_DISCOVERING_SCHEMA in stages
        assert STAGE_VALIDATING_DOCUMENT in stages
        assert STAGE_COMPLETE in stages
    finally:
        probe.stop()
        _cleanup(win)
