from PySide6.QtCore import QModelIndex

from documents.tab import JsonTab
from documents.tab_dependencies import JsonTabServices
from themes import LIGHT_DEFAULT
from themes.icon_provider import StubIconProvider


class _Host:
    def __init__(self) -> None:
        self.refresh_calls = 0
        self.status_messages: list[tuple[str, int]] = []
        self.permanent_messages: list[str] = []

    def refresh_actions(self) -> None:
        self.refresh_calls += 1

    def show_status_message(self, message: str, timeout_ms: int = 0) -> None:
        self.status_messages.append((message, timeout_ms))

    def show_permanent_message(self, message: str) -> None:
        self.permanent_messages.append(message)


def test_json_tab_accepts_service_bundle_and_uses_ui_layout(qtbot):
    host = _Host()
    tab = JsonTab(
        data={"foo": "bar"},
        services=JsonTabServices(
            host=host,
            theme=LIGHT_DEFAULT,
            icon_provider=StubIconProvider(),
        ),
    )
    qtbot.addWidget(tab)

    assert tab.view_controller.ui is not None
    assert tab.view_controller.search_edit is tab.view_controller.ui.searchEdit
    assert tab.view is tab.view_controller.ui.treeView
    assert tab.view_controller.search_edit.placeholderText() == "Filter (Ctrl+F)"

    tab.show_status("hello", 250)
    assert host.status_messages[-1] == ("hello", 250)

    foo_index = tab.model.index(0, 0, QModelIndex())
    tab.view.setCurrentIndex(tab.view_controller.source_to_view(foo_index))
    assert host.permanent_messages[-1] == "$.foo  (string, 3 chars)"

    before = host.refresh_calls
    tab.refresh_actions()
    assert host.refresh_calls == before + 1
