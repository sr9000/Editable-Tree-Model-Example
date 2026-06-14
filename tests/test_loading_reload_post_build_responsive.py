from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QTimer

from app.loading.progress import STAGE_APPLYING_RELOAD, STAGE_COMPLETE
from app.main_window import MainWindow
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


def test_reload_does_not_call_root_data_before_apply(qtbot, tmp_path, monkeypatch):
    doc = tmp_path / "data.json"
    _write_json(doc, {"a": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
        tab = win._current_tab()
        assert isinstance(tab, JsonTab)

        monkeypatch.setattr(
            tab,
            "root_data",
            lambda: (_ for _ in ()).throw(AssertionError("reload must not snapshot root_data() before apply")),
        )

        _write_json(doc, {"a": 2, "b": 3})
        assert win._load_coordinator.reload_file(tab, str(doc))
        assert tab.model.root_item.to_json() == {"a": 2, "b": 3}
    finally:
        _cleanup(win)


def test_reload_apply_and_finalize_yields_event_loop_turn(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    doc = tmp_path / "data.json"
    _write_json(doc, {"a": 1})

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    probe = QTimer(win)
    try:
        assert win._open_path(str(doc))
        tab = win._current_tab()
        assert isinstance(tab, JsonTab)
        _write_json(doc, {f"k{i}": "x" for i in range(300)})

        stages: list[str] = []
        ticks_after_apply = {"count": 0}
        win._load_coordinator.stage_changed.connect(lambda s: stages.append(s))

        def _on_probe() -> None:
            if STAGE_APPLYING_RELOAD in stages and STAGE_COMPLETE not in stages:
                ticks_after_apply["count"] += 1

        probe.timeout.connect(_on_probe)
        probe.start(0)

        task_id = win._load_coordinator.reload_file_async(tab, str(doc))
        assert task_id is not None
        qtbot.waitUntil(lambda: task_id not in win._load_coordinator._tasks, timeout=5000)
        assert ticks_after_apply["count"] >= 1
    finally:
        probe.stop()
        _cleanup(win)
