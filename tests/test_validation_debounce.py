"""test_validation_debounce.py — Tests for 250 ms trailing debounce.

Verifies that:
- _Debouncer fires exactly once after a burst of schedule() calls;
- 10 rapid model mutations with auto_rescan=True produce exactly one
  validationChanged emission after the burst settles.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.validation_dock_actions import _Debouncer
from documents.tab import JsonTab
from tree.types import JsonType
from validation.schema_source import SchemaRef


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ── _Debouncer unit tests ─────────────────────────────────────────────────


def test_debouncer_fires_once_after_burst(qtbot):
    """10 rapid schedule() calls collapse into a single invocation."""
    _qapp()
    counter = [0]
    debouncer = _Debouncer()

    def increment():
        counter[0] += 1

    # Fire 10 rapid calls — each resets the 250 ms timer.
    for _ in range(10):
        debouncer.schedule(increment)

    # Wait 400 ms for the timer to fire.
    qtbot.waitUntil(lambda: counter[0] == 1, timeout=600)
    assert counter[0] == 1, "callable should be invoked exactly once"


def test_debouncer_cancel_prevents_invocation(qtbot):
    """cancel() prevents a pending invocation from firing."""
    _qapp()
    counter = [0]
    debouncer = _Debouncer()

    debouncer.schedule(lambda: counter.__setitem__(0, counter[0] + 1))
    debouncer.cancel()

    qtbot.wait(400)
    assert counter[0] == 0, "cancelled debouncer must not fire"


def test_debouncer_reschedule_resets_timer(qtbot):
    """Calling schedule() again before the timer fires resets the delay."""
    _qapp()
    fired_at: list[float] = []

    import time

    debouncer = _Debouncer()

    debouncer.schedule(lambda: fired_at.append(time.monotonic()))
    qtbot.wait(100)  # 100 ms in — timer NOT yet fired
    assert len(fired_at) == 0, "should not have fired yet"
    # Reset timer
    debouncer.schedule(lambda: fired_at.append(time.monotonic()))
    qtbot.wait(100)  # another 100 ms — total 200 ms from first call, 100 from second
    assert len(fired_at) == 0, "second call reset timer; still should not have fired"
    # Now wait the remaining 200 ms
    qtbot.waitUntil(lambda: len(fired_at) == 1, timeout=400)
    assert len(fired_at) == 1


# ── integration: 10 rapid mutations → exactly one validationChanged ───────


def test_rapid_mutations_collapse_to_one_revalidation(qtbot):
    """10 rapid model mutations → exactly one validationChanged emission."""
    _qapp()
    schema = {
        "type": "object",
        "properties": {"x": {"type": "integer"}},
        "required": ["x"],
    }
    tab = JsonTab(lambda *_: None, data={"x": 1}, show_root=True)
    qtbot.addWidget(tab)
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="manual"))

    tab.validation.set_auto_rescan(True)

    emission_count = [0]
    tab.validationChanged.connect(lambda _: emission_count.__setitem__(0, emission_count[0] + 1))

    # Perform 10 rapid push_rename mutations on the 'x' key at the doc level.
    # Use push_change_type to avoid no-op detection; alternate INTEGER / FLOAT.
    doc_idx = tab.model.index(0, 0)
    x_name_idx = tab.model.index(0, 0, doc_idx)
    type_idx = x_name_idx.siblingAtColumn(1)

    types = [JsonType.FLOAT, JsonType.INTEGER] * 5
    for t in types:
        tab.editing.commands.push_change_type(type_idx, t)

    # Wait 400 ms for the debounce to settle.
    qtbot.waitUntil(lambda: emission_count[0] >= 1, timeout=600)
    # Allow an extra wait to confirm no second emission arrives.
    qtbot.wait(100)

    assert emission_count[0] == 1, f"expected exactly 1 validationChanged after burst, got {emission_count[0]}"
