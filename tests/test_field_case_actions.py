from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel

from documents.tab import JsonTab, _SwitchFieldCaseCmd
from tree_actions.context_menu import show_context_menu
from tree_actions.field_case import convert_field_name
from tree_actions.structure import switch_document_case, switch_selection_case


def _make_tab(qtbot, data, *, show_root: bool = False) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data, show_root=show_root)
    qtbot.addWidget(tab)
    tab.show()
    return tab


def _select_rows(tab: JsonTab, *paths: tuple[int, ...]) -> None:
    sm = tab.view.selectionModel()
    first, *rest = paths
    first_view = tab._source_to_view(tab._index_from_path(first))
    sm.select(first_view, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sm.setCurrentIndex(first_view, QItemSelectionModel.SelectionFlag.NoUpdate)
    for path in rest:
        sm.select(tab._source_to_view(tab._index_from_path(path)), QItemSelectionModel.SelectionFlag.Select)


def test_convert_field_name_variants():
    assert convert_field_name("someHTTPField-id", "snake_case") == "some_http_field_id"
    assert convert_field_name("someHTTPField-id", "SNAKE_CASE_UPPER") == "SOME_HTTP_FIELD_ID"
    assert convert_field_name("someHTTPField-id", "kebab-case") == "some-http-field-id"
    assert convert_field_name("someHTTPField-id", "KEBAB-CASE-UPPER") == "SOME-HTTP-FIELD-ID"
    assert convert_field_name("some_http_field-id", "camelCase") == "someHttpFieldId"
    assert convert_field_name("some_http_field-id", "PascalCase") == "SomeHttpFieldId"


def test_switch_selection_case_non_recursive(qtbot):
    tab = _make_tab(qtbot, {"outerNode": {"innerKey": 1}, "tailValue": 2})
    _select_rows(tab, (0,))

    assert switch_selection_case(tab.view, "snake_case", recursive=False)
    assert tab.model.root_item.to_json() == {"outer_node": {"innerKey": 1}, "tailValue": 2}


def test_switch_selection_case_recursive(qtbot):
    tab = _make_tab(qtbot, {"outerNode": {"innerKey": 1}, "tailValue": 2})
    _select_rows(tab, (0,))

    assert switch_selection_case(tab.view, "snake_case", recursive=True)
    assert tab.model.root_item.to_json() == {"outer_node": {"inner_key": 1}, "tailValue": 2}


def test_switch_document_case_undo_redo_and_typed_command(qtbot):
    tab = _make_tab(qtbot, {"myKey": {"innerKey": 1}, "Another-Key": 2})
    before = tab.model.root_item.to_json()

    assert switch_document_case(tab.view, "PascalCase")
    after = tab.model.root_item.to_json()
    assert after == {"MyKey": {"InnerKey": 1}, "AnotherKey": 2}

    cmd = tab.undo_stack.command(tab.undo_stack.count() - 1)
    assert isinstance(cmd, _SwitchFieldCaseCmd)

    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == before
    tab.undo_stack.redo()
    assert tab.model.root_item.to_json() == after


def test_switch_document_case_rejects_name_collision(qtbot):
    tab = _make_tab(qtbot, {"myKey": 1, "my_key": 2})
    before = tab.model.root_item.to_json()
    count_before = tab.undo_stack.count()

    assert not switch_document_case(tab.view, "snake_case")
    assert tab.model.root_item.to_json() == before
    assert tab.undo_stack.count() == count_before


def test_context_menu_contains_switch_case_submenus(qtbot):
    tab = _make_tab(qtbot, {"obj": {"xKey": 1}, "tailValue": 3}, show_root=True)
    tab.view.expandAll()
    _select_rows(tab, (0, 0))

    nested = tab._index_from_path((0, 0))
    position = tab.view.visualRect(tab._source_to_view(nested)).center()
    menu = show_context_menu(tab.view, position, execute=False)

    top_titles = [action.text() for action in menu.actions() if action.text()]
    assert "Switch Case" in top_titles
    assert "Switch Case (Recursive)" in top_titles

    seen: dict[str, int] = {}

    def _collect(submenu):
        for action in submenu.actions():
            child = action.menu()
            if child is not None:
                _collect(child)
                continue
            text = action.text()
            if text:
                seen[text] = seen.get(text, 0) + 1

    _collect(menu)
    assert seen["snake_case"] == 2
    assert seen["SNAKE_CASE_UPPER"] == 2
    assert seen["kebab-case"] == 2
    assert seen["KEBAB-CASE-UPPER"] == 2
    assert seen["camelCase"] == 2
    assert seen["PascalCase"] == 2
