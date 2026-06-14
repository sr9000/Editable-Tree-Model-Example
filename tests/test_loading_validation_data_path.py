from __future__ import annotations

from documents.tab import JsonTab
from validation.schema_source import SchemaRef


def test_loading_validation_uses_supplied_parsed_data_not_tree_snapshot(qtbot, monkeypatch):
    tab = JsonTab(lambda *_: None, data={"value": "oops"}, show_root=True)
    qtbot.addWidget(tab)

    schema = {
        "type": "object",
        "properties": {"value": {"type": "integer"}},
        "required": ["value"],
    }
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="manual"), revalidate=False)

    monkeypatch.setattr(
        tab.model.root_item,
        "to_json",
        lambda: (_ for _ in ()).throw(AssertionError("loading validation must not call model snapshot")),
    )

    tab.validation.revalidate_loading_data({"value": "oops"})
    assert len(tab.validation.issue_index) == 1
