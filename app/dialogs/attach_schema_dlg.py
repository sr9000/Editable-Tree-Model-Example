from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFileDialog

from state.recent_schemas import recent_schemas
from ui.dialogs import Ui_AttachSchemaDialog
from validation.schema_types import SchemaSource


class AttachSchemaDialog(QDialog):
    def __init__(self, parent=None, *, start_dir: str = "", recent_sources: list[SchemaSource] | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_AttachSchemaDialog()
        self._ui.setupUi(self)
        self._start_dir = start_dir

        self._edit = self._ui.pathLineEdit
        self._recent_label = self._ui.recentLabel
        self._recent_combo = self._ui.recentComboBox
        self._recent_row_widget = self._ui.recentRowWidget
        self.buttonBox = self._ui.buttonBox

        self._recent_combo.currentIndexChanged.connect(self._on_recent_selected)

        recents = list(recent_sources) if recent_sources is not None else recent_schemas()
        self._populate_recent_combo(recents)
        self._recent_row_widget.setVisible(bool(recents))
        self._ui.browseButton.clicked.connect(self._browse)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    @classmethod
    def ask(
        cls,
        parent=None,
        *,
        start_dir: str = "",
        recent_sources: list[SchemaSource] | None = None,
    ) -> SchemaSource | None:
        dlg = cls(parent, start_dir=start_dir, recent_sources=recent_sources)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.source()

    def _populate_recent_combo(self, recents: list[SchemaSource]) -> None:
        self._recent_combo.blockSignals(True)
        self._recent_combo.clear()
        for source in recents:
            self._recent_combo.addItem(source.display, source)
        self._recent_combo.setCurrentIndex(-1)
        self._recent_combo.blockSignals(False)

    def _on_recent_selected(self, index: int) -> None:
        if index < 0:
            return
        source = self._recent_combo.itemData(index, Qt.ItemDataRole.UserRole)
        if isinstance(source, SchemaSource):
            self._edit.setText(source.key)

    @classmethod
    def parse_source(cls, raw: str, *, start_dir: str = "") -> SchemaSource | None:
        text = raw.strip()
        if not text:
            return None
        lowered = text.casefold()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            return SchemaSource.for_url(text)

        start = Path(start_dir).expanduser() if start_dir else None
        base_dir = start.parent if start is not None and start.suffix else start

        candidate = Path(text).expanduser()
        if not candidate.is_absolute() and base_dir is not None:
            candidate = base_dir / candidate
        if not candidate.exists() or not candidate.is_file():
            return None
        return SchemaSource.for_file(candidate)

    def source(self) -> SchemaSource | None:
        return self.parse_source(self._edit.text(), start_dir=self._start_dir)

    def _browse(self) -> None:
        picked, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Schema File"),
            self._start_dir,
            self.tr("JSON Schema (*.json *.yaml *.yml);;All files (*)"),
        )
        if picked:
            self._edit.setText(picked)
