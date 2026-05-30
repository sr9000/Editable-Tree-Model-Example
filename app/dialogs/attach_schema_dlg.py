from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from state.recent_schemas import recent_schemas
from validation.schema_registry import SchemaSource


class AttachSchemaDialog(QDialog):
    def __init__(self, parent=None, *, start_dir: str = "", recent_sources: list[SchemaSource] | None = None) -> None:
        super().__init__(parent)
        self._start_dir = start_dir

        self.setWindowTitle(self.tr("Attach JSON Schema"))
        self.resize(540, 110)

        label = QLabel(self.tr("Schema file path or URL (http/https):"), self)
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText("https://...  or  /path/to/schema.json")

        self._recent_label = QLabel(self.tr("Recent schemas:"), self)
        self._recent_combo = QComboBox(self)
        self._recent_combo.currentIndexChanged.connect(self._on_recent_selected)

        recent_row = QHBoxLayout()
        recent_row.setContentsMargins(0, 0, 0, 0)
        recent_row.addWidget(self._recent_label)
        recent_row.addWidget(self._recent_combo, 1)

        self._recent_row_widget = QWidget(self)
        self._recent_row_widget.setLayout(recent_row)

        recents = list(recent_sources) if recent_sources is not None else recent_schemas()
        self._populate_recent_combo(recents)
        self._recent_row_widget.setVisible(bool(recents))

        browse = QPushButton(self.tr("Browse..."), self)
        browse.clicked.connect(self._browse)

        row = QHBoxLayout()
        row.addWidget(self._edit, 1)
        row.addWidget(browse)

        buttons = QDialogButtonBox(parent=self)
        buttons.setStandardButtons(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._recent_row_widget)
        layout.addWidget(label)
        layout.addLayout(row)
        layout.addWidget(buttons)

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
