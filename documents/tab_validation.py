"""Per-tab schema and validation controller."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QObject, Qt, QTimer
from PySide6.QtWidgets import QAbstractItemView

from io_formats.detect import SAVE_FORMAT_YAML_MULTI
from tree.model_roles import VALIDATION_SEVERITY_ROLE
from validation import get_schema_registry
from validation._sanitize import to_jsonschema_input
from validation.index import IssueIndex
from validation.issue import ValidationIssue
from validation.json_pointer import instance_path_to_model_path
from validation.schema_registry import SchemaSource
from validation.schema_source import SchemaRef, discover_schema, load_schema
from validation.validator import validate_document
from validation.yaml_validate import validate_yaml_documents


class TabValidationController(QObject):
    """Own schema state, issue tracking, and revalidation for one tab."""

    def __init__(
        self,
        tab,
        model,
        *,
        on_schema_changed: Callable[[SchemaRef], None],
        on_validation_changed: Callable[[IssueIndex], None],
        initial_data: Any,
    ) -> None:
        super().__init__(tab)
        self._tab = tab
        self._model = model
        self._on_schema_changed = on_schema_changed
        self._on_validation_changed = on_validation_changed

        self._schema_ref: SchemaRef = SchemaRef(path=None, inline=None, origin="none")
        self._schema_source: SchemaSource | None = None
        self._schema: dict[str, Any] | None = None
        self._issue_index = IssueIndex([], initial_data)
        self._auto_rescan: bool = False

        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(250)
        self.debounce_timer.timeout.connect(self.revalidate)

        self._model_conns = [
            self._model.dataChanged.connect(self._on_data_changed_mutation),
            self._model.rowsInserted.connect(self._schedule_debounced_revalidation),
            self._model.rowsRemoved.connect(self._schedule_debounced_revalidation),
            self._model.rowsMoved.connect(self._schedule_debounced_revalidation),
            self._model.modelReset.connect(self._schedule_debounced_revalidation),
        ]
        get_schema_registry().schemaReloaded.connect(self._on_registry_schema_reloaded)
        self._released = False

    @property
    def schema_ref(self) -> SchemaRef:
        return self._schema_ref

    @property
    def schema_source(self) -> SchemaSource | None:
        return self._schema_source

    @property
    def schema(self) -> dict[str, Any] | None:
        return self._schema

    @property
    def issue_index(self) -> IssueIndex:
        return self._issue_index

    @property
    def auto_rescan(self) -> bool:
        return self._auto_rescan

    def init_state(self, model_data: Any, *, doc_path: Path | None = None) -> None:
        from state.validation_settings import _is_url, read_schema_ref_str

        if doc_path is None and self._tab.io.file_path:
            doc_path = Path(self._tab.io.file_path).expanduser().resolve()
        ref = discover_schema(doc_path, model_data)

        if ref.origin == "none" and doc_path is not None:
            persisted = read_schema_ref_str(doc_path)
            if persisted is not None:
                if _is_url(persisted):
                    candidate = SchemaRef(path=None, inline=None, origin="manual", url=persisted)
                else:
                    candidate = SchemaRef(path=Path(persisted), inline=None, origin="manual")
                try:
                    loaded = load_schema(candidate)
                except Exception:
                    loaded = None
                if loaded is not None:
                    if _is_url(persisted):
                        ref = SchemaRef(path=None, inline=dict(loaded), origin="manual", url=persisted)
                    else:
                        ref = SchemaRef(path=Path(persisted), inline=dict(loaded), origin="manual")

        self.set_schema(ref)

    def set_schema(self, ref: SchemaRef) -> None:
        self._swap_source(SchemaSource.from_ref(ref), ref)

    def set_schema_from_source(self, source: SchemaSource) -> None:
        self._swap_source(source, source.as_ref())

    def clear_schema(self) -> None:
        self.set_schema(SchemaRef(path=None, inline=None, origin="none"))

    def set_schema_view_source(self, source: SchemaSource | None) -> None:
        """Mark this tab as the active source view for a schema."""
        self._schema_source = source
        self._schema_ref = (
            source.as_ref(origin="manual") if source is not None else SchemaRef(path=None, inline=None, origin="none")
        )
        self._on_schema_changed(self._schema_ref)

    def _swap_source(self, source: SchemaSource | None, ref: SchemaRef) -> None:
        if self._schema_source is not None:
            get_schema_registry().release(self._schema_source, self._tab)

        inline_hint = ref.inline if isinstance(ref.inline, Mapping) else None
        entry = (
            get_schema_registry().acquire(source, self._tab, inline_hint=inline_hint) if source is not None else None
        )

        self._schema_source = source
        self._schema_ref = ref
        if source is None and ref.inline is not None:
            self._schema = dict(ref.inline)
        else:
            self._schema = entry.inline if entry is not None else None
        self._on_schema_changed(self._schema_ref)
        self.revalidate()

    def revalidate(self) -> None:
        root_data = self._model.root_item.to_json()
        issues: list[ValidationIssue] = []
        if self._schema is not None:
            sanitized = to_jsonschema_input(root_data)
            if self._tab.io.save_format == SAVE_FORMAT_YAML_MULTI and isinstance(sanitized, list):
                issues = validate_yaml_documents(sanitized, self._schema)
            else:
                issues = validate_document(sanitized, self._schema)
        self._issue_index = IssueIndex(issues, root_data)
        self._on_validation_changed(self._issue_index)

    def set_auto_rescan(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._auto_rescan == enabled:
            return
        self._auto_rescan = enabled
        if not enabled:
            self.debounce_timer.stop()

    def _on_data_changed_mutation(self, _top_left, _bottom_right, roles=None) -> None:
        if not self._auto_rescan:
            return
        if roles is not None and len(roles) > 0 and all(r == VALIDATION_SEVERITY_ROLE for r in roles):
            return
        self.debounce_timer.start()

    def _schedule_debounced_revalidation(self, *_args) -> None:
        if not self._auto_rescan:
            return
        self.debounce_timer.start()

    def _on_registry_schema_reloaded(self, source: SchemaSource) -> None:
        if source == self._schema_source:
            self.revalidate()

    def severity_for(self, model_path: tuple[int, ...]) -> str | None:
        exact = self._issue_index.severity_at(model_path)
        if exact is not None:
            return exact
        return self._issue_index.ancestor_severity(model_path)

    def release(self) -> None:
        """Disconnect signals, stop timers, and release schema state."""
        if self._released:
            return
        self._released = True

        self.debounce_timer.stop()

        if self._schema_source is not None:
            get_schema_registry().release(self._schema_source, self._tab)
            self._schema_source = None

        try:
            get_schema_registry().schemaReloaded.disconnect(self._on_registry_schema_reloaded)
        except (RuntimeError, TypeError):
            pass
        for sig, slot in (
            (self._model.dataChanged, self._on_data_changed_mutation),
            (self._model.rowsInserted, self._schedule_debounced_revalidation),
            (self._model.rowsRemoved, self._schedule_debounced_revalidation),
            (self._model.rowsMoved, self._schedule_debounced_revalidation),
            (self._model.modelReset, self._schedule_debounced_revalidation),
        ):
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    _SELECT_ROW_FLAGS = QItemSelectionModel.SelectionFlag(
        QItemSelectionModel.SelectionFlag.ClearAndSelect.value | QItemSelectionModel.SelectionFlag.Rows.value
    )
    _EDITABLE_ITEM_FLAG = Qt.ItemFlag.ItemIsEditable.value

    def goto_validation_issue(self, issue: ValidationIssue, *, edit: bool = False) -> bool:
        root_data = self._tab.model.root_item.to_json()
        model_path = instance_path_to_model_path(root_data, issue.instance_path)
        if model_path is None:
            self._tab.show_status("Validation issue path no longer exists", 2000)
            return False
        source_row = self._tab.view_controller.index_from_path(model_path)
        if not source_row.isValid():
            self._tab.show_status("Validation issue path no longer exists", 2000)
            return False
        source_row = source_row.siblingAtColumn(0)
        view_row = self._tab.view_controller.source_to_view(source_row)
        if not view_row.isValid():
            self._tab.show_status("Validation issue path no longer exists", 2000)
            return False
        selection_model = self._tab.view_state.view.selectionModel()
        if selection_model is not None:
            selection_model.select(view_row, self._SELECT_ROW_FLAGS)
            selection_model.setCurrentIndex(view_row, QItemSelectionModel.SelectionFlag.NoUpdate)
        view = self._tab.view_state.view
        view.setCurrentIndex(view_row)
        view.scrollTo(view_row, QAbstractItemView.ScrollHint.PositionAtCenter)
        if not edit:
            return True
        source_value = source_row.siblingAtColumn(2)
        if not source_value.isValid():
            return True
        if not (self._tab.model.flags(source_value).value & self._EDITABLE_ITEM_FLAG):
            return True
        view_value = self._tab.view_controller.source_to_view(source_value)
        if not view_value.isValid():
            return True
        view.setCurrentIndex(view_value)
        view.edit(view_value)
        return True

    def severity_provider(self, model_path: tuple[int, ...]) -> str | None:
        return self.severity_for(model_path)

    def on_validation_changed(self, _index: IssueIndex) -> None:
        """Emit recursive dataChanged so all visible rows repaint their badges."""

        def emit_ranges(parent: QModelIndex) -> None:
            model = self._tab.model
            rows = model.rowCount(parent)
            if rows <= 0:
                return
            top_left = model.index(0, 0, parent)
            bottom_right = model.index(rows - 1, model.columnCount(parent) - 1, parent)
            model.dataChanged.emit(top_left, bottom_right, [VALIDATION_SEVERITY_ROLE])
            for row in range(rows):
                emit_ranges(model.index(row, 0, parent))

        emit_ranges(QModelIndex())


__all__ = ["TabValidationController"]
