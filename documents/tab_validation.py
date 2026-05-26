"""Tab-scoped validation controller.

Owns the schema reference/inline payload, the issue index, the auto-rescan
debounce timer, and the registry binding for the host tab.  All Qt
connections it creates are torn down by ``release()``; the host tab's
``closeEvent`` invokes ``release()`` so file watchers, registry
ref-counts, and timers do not leak.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer

from io_formats.detect import SAVE_FORMAT_YAML_MULTI
from tree.model_roles import VALIDATION_SEVERITY_ROLE
from validation._sanitize import to_jsonschema_input
from validation.index import IssueIndex
from validation.issue import ValidationIssue
from validation.schema_registry import SchemaSource
from validation.schema_registry import schema_registry as _default_registry
from validation.schema_source import SchemaRef, discover_schema, load_schema
from validation.validator import validate_document
from validation.yaml_validate import validate_yaml_documents


def _registry():
    """Late-bound registry lookup so tests can monkeypatch
    ``documents.tab.schema_registry`` and have controllers honour the
    substitution.
    """
    import documents.tab as _tab_module

    return getattr(_tab_module, "schema_registry", _default_registry)


class TabValidationController(QObject):
    """Validation/schema state for a single JsonTab.

    The controller is parented to the tab (Qt parent), the debounce timer
    is parented to the controller — so destruction cascades cleanly.
    """

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

        # ── debounce timer ────────────────────────────────────────────────
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.setInterval(250)
        self.debounce_timer.timeout.connect(self.revalidate)

        # Connections kept alive so we can disconnect them on release().
        self._model_conns = [
            self._model.dataChanged.connect(self._on_data_changed_mutation),
            self._model.rowsInserted.connect(self._schedule_debounced_revalidation),
            self._model.rowsRemoved.connect(self._schedule_debounced_revalidation),
            self._model.rowsMoved.connect(self._schedule_debounced_revalidation),
            self._model.modelReset.connect(self._schedule_debounced_revalidation),
        ]
        _registry().schemaReloaded.connect(self._on_registry_schema_reloaded)
        self._released = False

    # ----- read-only views ----------------------------------------------
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

    # ----- initialisation ------------------------------------------------
    def init_state(self, model_data: Any, *, doc_path: Path | None = None) -> None:
        from state.validation_settings import _is_url, read_schema_ref_str

        if doc_path is None and self._tab.file_path:
            doc_path = Path(self._tab.file_path).expanduser().resolve()
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

    # ----- schema mutators ----------------------------------------------
    def set_schema(self, ref: SchemaRef) -> None:
        self._swap_source(SchemaSource.from_ref(ref), ref)

    def set_schema_from_source(self, source: SchemaSource) -> None:
        self._swap_source(source, source.as_ref())

    def clear_schema(self) -> None:
        self.set_schema(SchemaRef(path=None, inline=None, origin="none"))

    def set_schema_view_source(self, source: SchemaSource | None) -> None:
        """Tag this tab as representing *source* for navigation/pool reuse."""
        self._schema_source = source
        self._schema_ref = (
            source.as_ref(origin="manual") if source is not None else SchemaRef(path=None, inline=None, origin="none")
        )
        self._on_schema_changed(self._schema_ref)

    def _swap_source(self, source: SchemaSource | None, ref: SchemaRef) -> None:
        if self._schema_source is not None:
            _registry().release(self._schema_source, self._tab)

        inline_hint = ref.inline if isinstance(ref.inline, Mapping) else None
        entry = _registry().acquire(source, self._tab, inline_hint=inline_hint) if source is not None else None

        self._schema_source = source
        self._schema_ref = ref
        if source is None and ref.inline is not None:
            self._schema = dict(ref.inline)
        else:
            self._schema = entry.inline if entry is not None else None
        self._on_schema_changed(self._schema_ref)
        self.revalidate()

    # ----- revalidation --------------------------------------------------
    def revalidate(self) -> None:
        root_data = self._model.root_item.to_json()
        issues: list[ValidationIssue] = []
        if self._schema is not None:
            sanitized = to_jsonschema_input(root_data)
            if self._tab.save_format == SAVE_FORMAT_YAML_MULTI and isinstance(sanitized, list):
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

    # ----- severity provider lookup -------------------------------------
    def severity_for(self, model_path: tuple[int, ...]) -> str | None:
        exact = self._issue_index.severity_at(model_path)
        if exact is not None:
            return exact
        return self._issue_index.ancestor_severity(model_path)

    # ----- teardown ------------------------------------------------------
    def release(self) -> None:
        """Stop the timer, release the schema source, disconnect all slots.

        Safe to call multiple times.  Invoked by ``JsonTab.closeEvent``.
        """
        if self._released:
            return
        self._released = True

        self.debounce_timer.stop()

        if self._schema_source is not None:
            _registry().release(self._schema_source, self._tab)
            self._schema_source = None

        try:
            _registry().schemaReloaded.disconnect(self._on_registry_schema_reloaded)
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


__all__ = ["TabValidationController"]
