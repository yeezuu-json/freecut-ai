"""Settings dialog — model selection + API key management."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.logger import get_logger
from app.paths import CONFIG_FILE
from services.model_manager import ModelManager
from ui.components.app_select import AppSelect

logger = get_logger(__name__)


# ── result dataclass ──────────────────────────────────────────────────────────

@dataclass
class SettingsResult:
    transcription_provider: str
    transcription_model: str
    transcription_language: str
    translation_provider: str
    translation_model: str
    translation_source_language: str
    translation_target_language: str
    deepinfra_api_key: str   # empty = use env fallback
    gemini_api_key: str


# ── dialog ────────────────────────────────────────────────────────────────────

_QSS = """
QDialog {
    background-color: #1a1f2e;
    color: #e2e8f0;
}

QLabel {
    color: #cbd5e1;
    font-size: 13px;
}

QLabel#sectionHeader {
    color: #f1f5f9;
    font-size: 13px;
    font-weight: 700;
}

QGroupBox {
    background-color: #242b3d;
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 10px;
    padding: 14px 12px 10px 12px;
    color: #94a3b8;
    font-size: 12px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #94a3b8;
    font-size: 12px;
}

QLineEdit {
    background-color: #2d3748;
    color: #e2e8f0;
    border: 1px solid #4a5568;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 32px;
}

QLineEdit:hover {
    border-color: #3b82f6;
}

QLineEdit:focus {
    border-color: #3b82f6;
    background-color: #1e3a5f;
}

QLineEdit::placeholder {
    color: #4a5568;
}

QLabel#hintLabel {
    color: #64748b;
    font-size: 11px;
    font-style: italic;
}

QLabel#envLabel {
    color: #22c55e;
    font-size: 11px;
}

QDialogButtonBox QPushButton {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 600;
    min-width: 80px;
}

QDialogButtonBox QPushButton:hover {
    background-color: #2563eb;
}

QDialogButtonBox QPushButton[text="Cancel"] {
    background-color: #374151;
}

QDialogButtonBox QPushButton[text="Cancel"]:hover {
    background-color: #4b5563;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background: #1a1f2e;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #4a5568;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

#cleanSelect {
    background-color: #2d3748;
    color: #e2e8f0;
    border: 1px solid #4a5568;
    border-radius: 7px;
    padding: 5px 10px;
    min-height: 30px;
    font-size: 12px;
    font-weight: 500;
}

#cleanSelect:hover {
    border: 1px solid #3b82f6;
}

#cleanSelect:focus {
    border: 1px solid #3b82f6;
    background-color: #1e3a5f;
}

#cleanSelect::drop-down {
    width: 26px;
    border: none;
    background-color: transparent;
}

#cleanSelect::down-arrow {
    image: none;
    width: 0px;
    height: 0px;
}

#cleanSelect QAbstractItemView {
    background-color: #2d3748;
    color: #e2e8f0;
    border: 1px solid #4a5568;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
    padding: 4px;
    outline: none;
}
"""


class SettingsDialog(QDialog):
    """Modal settings dialog for API keys and AI model selection."""

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.config = config
        self._result: Optional[SettingsResult] = None
        # Connections to the global ModelDownloadManager singleton that must be
        # explicitly disconnected when the dialog closes, because the singleton
        # outlives this dialog and would otherwise hold stale widget references.
        self._mgr_connections: list = []

        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self.setMinimumHeight(580)
        self.setStyleSheet(_QSS)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
        )

        self._build_ui()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        for signal, slot in self._mgr_connections:
            try:
                signal.disconnect(slot)
            except RuntimeError:
                pass
        self._mgr_connections.clear()
        super().closeEvent(event)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        # Title
        title = QLabel("Settings")
        title.setObjectName("sectionHeader")
        title.setStyleSheet("font-size: 18px; color: #f1f5f9; font-weight: 700;")
        root.addWidget(title)

        subtitle = QLabel("Configure AI models and API keys used by the app.")
        subtitle.setObjectName("hintLabel")
        root.addWidget(subtitle)

        # Scrollable body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        body_widget = QWidget()
        body_widget.setStyleSheet("background-color: transparent;")
        body = QVBoxLayout(body_widget)
        body.setContentsMargins(0, 4, 0, 4)
        body.setSpacing(14)

        body.addWidget(self._build_transcription_group())
        body.addWidget(self._build_translation_group())
        body.addWidget(self._build_api_keys_group())
        body.addWidget(self._build_local_models_group())
        body.addWidget(self._build_cache_group())
        body.addStretch()

        scroll.setWidget(body_widget)
        root.addWidget(scroll, 1)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.button(QDialogButtonBox.StandardButton.Save).setText("Save")
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

    # ── section groups ────────────────────────────────────────────────────────

    _DARK_MENU_QSS = """
        QMenu {
            background-color: #2d3748;
            color: #e2e8f0;
            border: 1px solid #4a5568;
            border-radius: 6px;
            padding: 4px 0;
            font-size: 13px;
        }
        QMenu::item {
            color: #e2e8f0;
            padding: 8px 16px;
            border-radius: 4px;
            margin: 2px 4px;
        }
        QMenu::item:selected {
            background-color: #3b82f6;
            color: #ffffff;
        }
        QMenu::item:checked {
            background-color: #1e3a5f;
            color: #93c5fd;
            font-weight: 600;
        }
        QMenu::separator {
            height: 1px;
            background: #4a5568;
            margin: 4px 8px;
        }
    """

    _DARK_BUTTON_QSS = """
        QPushButton#appSelect {
            background-color: #2d3748;
            color: #e2e8f0;
            border: 1px solid #4a5568;
            border-radius: 7px;
            padding: 0px 12px;
            text-align: left;
            font-size: 13px;
            font-weight: 500;
        }
        QPushButton#appSelect:hover {
            border-color: #3b82f6;
            background-color: #374151;
        }
        QPushButton#appSelect:pressed {
            background-color: #1e3a5f;
            border-color: #3b82f6;
        }
    """

    def _make_select(self, labels: list[str], current: str) -> AppSelect:
        sel = AppSelect(items=labels, value=current, width=320, height=32)

        # Override the global light #appSelect theme for this dark dialog.
        sel.setStyleSheet(self._DARK_BUTTON_QSS)

        qss = self._DARK_MENU_QSS

        # Re-apply the dark menu stylesheet every time the menu is rebuilt
        # (AppSelect.rebuild_menu() clears and recreates menu actions).
        original_rebuild = sel.rebuild_menu

        def _patched_rebuild():
            original_rebuild()
            sel.menu.setStyleSheet(qss)

        sel.rebuild_menu = _patched_rebuild
        sel.menu.setStyleSheet(qss)
        return sel

    def _build_transcription_group(self) -> QGroupBox:
        group = QGroupBox("Transcription")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        form.setContentsMargins(8, 16, 8, 8)

        labels = [m.label for m in self.config.transcription_models]
        current_label = next(
            (m.label for m in self.config.transcription_models
             if m.value == self.config.transcription_model),
            labels[0] if labels else "",
        )
        self._transcription_model_select = self._make_select(labels, current_label)
        form.addRow(self._label("Model"), self._transcription_model_select)

        self._transcription_lang = QLineEdit(self.config.transcription_language)
        self._transcription_lang.setPlaceholderText("e.g.  zh  en  ja  ko")
        form.addRow(self._label("Source Language"), self._transcription_lang)

        hint = QLabel("Use a BCP-47 code (zh, en, ja …).  Leave blank for auto-detect.")
        hint.setObjectName("hintLabel")
        form.addRow("", hint)

        return group

    def _build_translation_group(self) -> QGroupBox:
        group = QGroupBox("Translation")
        form = QFormLayout(group)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        form.setContentsMargins(8, 16, 8, 8)

        labels = [m.label for m in self.config.translation_models]
        current_label = next(
            (m.label for m in self.config.translation_models
             if m.value == self.config.translation_model),
            labels[0] if labels else "",
        )
        self._translation_model_select = self._make_select(labels, current_label)
        form.addRow(self._label("Model"), self._translation_model_select)

        self._translation_src_lang = QLineEdit(self.config.translation_source_language)
        self._translation_src_lang.setPlaceholderText("e.g.  Chinese")
        form.addRow(self._label("Source Language"), self._translation_src_lang)

        self._translation_tgt_lang = QLineEdit(self.config.translation_target_language)
        self._translation_tgt_lang.setPlaceholderText("e.g.  Khmer")
        form.addRow(self._label("Target Language"), self._translation_tgt_lang)

        return group

    def _build_api_keys_group(self) -> QGroupBox:
        group = QGroupBox("API Keys")
        vbox = QVBoxLayout(group)
        vbox.setSpacing(12)
        vbox.setContentsMargins(8, 16, 8, 8)

        # DeepInfra
        vbox.addLayout(self._api_key_row(
            "DeepInfra",
            "Used for cloud Whisper transcription.",
            env_var="DEEPINFRA_API_KEY",
            stored_value=self.config.deepinfra_api_key,
            attr="_deepinfra_key",
        ))

        # Gemini
        vbox.addLayout(self._api_key_row(
            "Google Gemini",
            "Used for Gemini translation models.",
            env_var="GEMINI_API_KEY",
            stored_value=self.config.gemini_api_key,
            attr="_gemini_key",
        ))

        return group

    def _build_local_models_group(self) -> QGroupBox:
        """Panel that shows each local model with its download status + button."""
        from services.model_download_manager import ModelDownloadManager

        group = QGroupBox("Local AI Models")
        vbox = QVBoxLayout(group)
        vbox.setSpacing(10)
        vbox.setContentsMargins(8, 16, 8, 12)

        hint = QLabel(
            "Local models are free and run entirely on your computer.\n"
            "They are only downloaded on demand — never at startup."
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        vbox.addWidget(hint)

        file_manager = ModelManager()
        dl_manager   = ModelDownloadManager.instance()

        whisper_models = [
            ("tiny",      "local",     "Whisper Tiny",       "~75 MB"),
            ("base",      "local",     "Whisper Base",       "~145 MB"),
            ("small",     "local",     "Whisper Small",      "~465 MB"),
            ("medium",    "local",     "Whisper Medium",     "~1.5 GB"),
            ("large-v3",  "local",     "Whisper Large V3",   "~3.1 GB"),
        ]
        nllb_models = [
            ("facebook/nllb-200-distilled-600M",  "local_nllb", "NLLB 600M",  "~2.4 GB"),
            ("facebook/nllb-200-distilled-1.3B",  "local_nllb", "NLLB 1.3B",  "~5.3 GB"),
        ]

        sep = QLabel("Whisper  (speech recognition)")
        sep.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600;")
        vbox.addWidget(sep)
        for m in whisper_models:
            vbox.addLayout(self._model_row(file_manager, dl_manager, *m))

        sep2 = QLabel("NLLB  (offline translation)")
        sep2.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 600; margin-top: 4px;")
        vbox.addWidget(sep2)
        for m in nllb_models:
            vbox.addLayout(self._model_row(file_manager, dl_manager, *m))

        return group

    def _model_row(
        self,
        file_manager: ModelManager,
        dl_manager,
        model_value: str,
        provider: str,
        label: str,
        size_hint: str,
    ) -> "QHBoxLayout":
        """One row: [label + size]  [status badge]  [Download / Ready button]"""
        row = QHBoxLayout()
        row.setSpacing(8)

        name_lbl = QLabel(f"{label}  <span style='color:#64748b;font-size:11px'>{size_hint}</span>")
        name_lbl.setTextFormat(Qt.TextFormat.RichText)
        row.addWidget(name_lbl, 1)

        if provider == "local":
            is_ready = file_manager.check_local_whisper_model(model_value).is_ready
        else:
            is_ready = file_manager.check_nllb_model(model_value).is_ready

        is_active = dl_manager.is_downloading(provider, model_value)

        if is_ready:
            initial_status_text  = "✓ Ready"
            initial_status_style = "color: #86efac; font-size: 11px;"
            initial_btn_text     = "Downloaded"
            btn_enabled          = False
        elif is_active:
            initial_status_text  = "⟳ Downloading…"
            initial_status_style = "color: #fbbf24; font-size: 11px;"
            initial_btn_text     = "Downloading…"
            btn_enabled          = False
        else:
            initial_status_text  = "Not downloaded"
            initial_status_style = "color: #94a3b8; font-size: 11px;"
            initial_btn_text     = "Download"
            btn_enabled          = True

        status_lbl = QLabel(initial_status_text)
        status_lbl.setStyleSheet(initial_status_style)
        row.addWidget(status_lbl)

        _btn_qss = """
            QPushButton {
                background-color: #1e3a5f;
                color: #93c5fd;
                border: 1px solid #3b82f6;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #2563eb; color: #ffffff; }
            QPushButton:disabled {
                background-color: #1f2937;
                color: #4b5563;
                border-color: #374151;
            }
        """
        btn = QPushButton(initial_btn_text)
        btn.setEnabled(btn_enabled)
        btn.setFixedWidth(110)
        btn.setStyleSheet(_btn_qss)

        # ── live updates from the manager ─────────────────────────────────────

        def _on_mgr_progress(p, m, pct, msg, sl=status_lbl, b=btn):
            if p != provider or m != model_value:
                return
            sl.setText(f"⟳ {pct}%")
            sl.setStyleSheet("color: #fbbf24; font-size: 11px;")
            b.setText("Downloading…")
            b.setEnabled(False)

        def _on_mgr_finished(p, m, success, sl=status_lbl, b=btn):
            if p != provider or m != model_value:
                return
            if success:
                sl.setText("✓ Ready")
                sl.setStyleSheet("color: #86efac; font-size: 11px;")
                b.setText("Downloaded")
                b.setEnabled(False)
            else:
                sl.setText("Failed — retry?")
                sl.setStyleSheet("color: #fca5a5; font-size: 11px;")
                b.setText("Retry")
                b.setEnabled(True)

        dl_manager.download_progress.connect(_on_mgr_progress)
        dl_manager.download_finished.connect(_on_mgr_finished)
        self._mgr_connections.append((dl_manager.download_progress, _on_mgr_progress))
        self._mgr_connections.append((dl_manager.download_finished, _on_mgr_finished))

        # ── button click ──────────────────────────────────────────────────────

        def _on_download(checked=False, p=provider, mv=model_value, sl=status_lbl, b=btn):
            from ui.components.model_download_dialog import ModelDownloadDialog
            ok = ModelDownloadDialog.ensure(p, mv, parent=self)
            if ok:
                sl.setText("✓ Ready")
                sl.setStyleSheet("color: #86efac; font-size: 11px;")
                b.setText("Downloaded")
                b.setEnabled(False)
            elif dl_manager.is_downloading(p, mv):
                sl.setText("⟳ Downloading…")
                sl.setStyleSheet("color: #fbbf24; font-size: 11px;")
                b.setText("Downloading…")
                b.setEnabled(False)

        btn.clicked.connect(_on_download)
        row.addWidget(btn)
        return row

    def _build_cache_group(self) -> QGroupBox:
        group = QGroupBox("Cache")
        vbox = QVBoxLayout(group)
        vbox.setSpacing(10)
        vbox.setContentsMargins(8, 16, 8, 8)

        # Compute sizes
        from app.paths import CACHE_DIR, PROJECTS_CACHE_DIR, STEMS_CACHE_DIR, TTS_CACHE_DIR

        rows = [
            ("Project timelines", PROJECTS_CACHE_DIR),
            ("Demucs stems",      STEMS_CACHE_DIR),
            ("TTS voice clips",   TTS_CACHE_DIR),
        ]
        total_bytes = 0
        for _, d in rows:
            sz = self._dir_size(d)
            total_bytes += sz

        # Size breakdown label
        breakdown_lines = []
        for label, d in rows:
            sz = self._dir_size(d)
            breakdown_lines.append(f"{label}:  {self._fmt_size(sz)}")
        breakdown_lines.append("")
        breakdown_lines.append(f"Total:  {self._fmt_size(total_bytes)}")

        breakdown_lbl = QLabel("\n".join(breakdown_lines))
        breakdown_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; line-height: 1.6;")
        vbox.addWidget(breakdown_lbl)

        # Cache location hint
        cache_hint = QLabel(f"Location:  {CACHE_DIR}")
        cache_hint.setObjectName("hintLabel")
        cache_hint.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        vbox.addWidget(cache_hint)

        # Clear button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._clear_cache_btn = QPushButton(
            f"Clear All Cache  ({self._fmt_size(total_bytes)})"
        )
        self._clear_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_cache_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f1d1d;
                color: #fecaca;
                border: 1px solid #991b1b;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #991b1b; }
            QPushButton:pressed { background-color: #b91c1c; }
            QPushButton:disabled {
                background-color: #374151;
                color: #6b7280;
                border-color: #374151;
            }
        """)
        self._clear_cache_btn.setEnabled(total_bytes > 0)
        self._clear_cache_btn.clicked.connect(
            lambda: self._on_clear_cache(rows, breakdown_lbl)
        )
        btn_row.addWidget(self._clear_cache_btn)
        vbox.addLayout(btn_row)

        return group

    # ── cache helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _dir_size(path: Path) -> int:
        """Return total bytes of all files under *path* (0 if missing)."""
        if not path.exists():
            return 0
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())

    @staticmethod
    def _fmt_size(n: int) -> str:
        """Human-readable file size."""
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
            n /= 1024
        return f"{n:.1f} TB"

    def _on_clear_cache(self, rows, breakdown_lbl) -> None:
        from app.paths import CACHE_DIR, PROJECTS_CACHE_DIR, STEMS_CACHE_DIR, TTS_CACHE_DIR
        import shutil

        total = sum(self._dir_size(d) for _, d in rows)

        # Confirmation dialog
        msg = QMessageBox(self)
        msg.setWindowTitle("Clear Cache")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            f"<b>Clear {self._fmt_size(total)} of cached data?</b>"
        )

        detail_lines = ["This will delete:"]
        for label, d in rows:
            sz = self._dir_size(d)
            if sz > 0:
                detail_lines.append(f"  • {label}  ({self._fmt_size(sz)})")
        detail_lines.append("")
        detail_lines.append(
            "Demucs stems, TTS clips, and project timelines will need to be\n"
            "regenerated on the next run.  SRT files next to your videos are NOT affected."
        )
        msg.setInformativeText("\n".join(detail_lines))
        msg.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        msg.button(QMessageBox.StandardButton.Ok).setText("Clear")
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)

        if msg.exec() != QMessageBox.StandardButton.Ok:
            return

        # Delete cache subdirectories (keep the root CACHE_DIR itself)
        deleted = 0
        errors = []
        for _, d in rows:
            if d.exists():
                try:
                    shutil.rmtree(d)
                    deleted += 1
                except Exception as exc:
                    errors.append(str(exc))

        # Refresh size labels
        new_lines = []
        for label, d in rows:
            new_lines.append(f"{label}:  {self._fmt_size(self._dir_size(d))}")
        new_lines.append("")
        new_lines.append(f"Total:  {self._fmt_size(0)}")
        breakdown_lbl.setText("\n".join(new_lines))

        self._clear_cache_btn.setText("Clear All Cache  (0 B)")
        self._clear_cache_btn.setEnabled(False)

        if errors:
            QMessageBox.warning(
                self, "Partial Clear",
                f"Some files could not be deleted:\n" + "\n".join(errors),
            )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _api_key_row(
        self,
        service: str,
        description: str,
        env_var: str,
        stored_value: str,
        attr: str,
    ) -> QVBoxLayout:
        container = QVBoxLayout()
        container.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        lbl = QLabel(service)
        lbl.setStyleSheet("color: #e2e8f0; font-weight: 600; font-size: 13px;")
        header.addWidget(lbl)
        header.addStretch()

        env_raw = os.getenv(env_var, "")
        if env_raw:
            env_badge = QLabel(f"  .env key active  ")
            env_badge.setObjectName("envLabel")
            env_badge.setStyleSheet(
                "color: #22c55e; font-size: 11px; background: #14532d;"
                " border-radius: 4px; padding: 2px 6px;"
            )
            header.addWidget(env_badge)

        container.addLayout(header)

        # Input
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText(
            "Paste your API key here  (leave blank to use app default)"
        )
        # Only pre-fill if the key did NOT come from the environment
        # (we never expose the env key back into the text field)
        if stored_value and stored_value != env_raw:
            field.setText(stored_value)

        setattr(self, attr, field)
        container.addWidget(field)

        desc = QLabel(description)
        desc.setObjectName("hintLabel")
        container.addWidget(desc)

        return container

    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return lbl

    # ── save ──────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        t_label = self._transcription_model_select.value
        t_model_cfg = next(
            (m for m in self.config.transcription_models if m.label == t_label),
            self.config.transcription_models[0] if self.config.transcription_models else None,
        )
        t_model = t_model_cfg.value if t_model_cfg else ""

        tr_label = self._translation_model_select.value
        tr_model_cfg = next(
            (m for m in self.config.translation_models if m.label == tr_label),
            self.config.translation_models[0] if self.config.translation_models else None,
        )
        tr_model = tr_model_cfg.value if tr_model_cfg else ""

        deepinfra_key = self._deepinfra_key.text().strip()
        gemini_key = self._gemini_key.text().strip()

        self._result = SettingsResult(
            transcription_provider=t_model_cfg.provider if t_model_cfg else "local",
            transcription_model=t_model,
            transcription_language=self._transcription_lang.text().strip(),
            translation_provider=tr_model_cfg.provider if tr_model_cfg else "gemini",
            translation_model=tr_model,
            translation_source_language=self._translation_src_lang.text().strip(),
            translation_target_language=self._translation_tgt_lang.text().strip(),
            deepinfra_api_key=deepinfra_key,
            gemini_api_key=gemini_key,
        )

        self._persist()
        self.accept()

    def _persist(self) -> None:
        """Write non-sensitive settings + user-supplied API keys to config/app.json.

        API keys from the environment are intentionally NOT written back so
        .env always takes precedence at runtime.
        """
        if self._result is None:
            return

        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = {}

            data["transcription_provider"] = self._result.transcription_provider
            data["transcription_model"] = self._result.transcription_model
            data["transcription_language"] = self._result.transcription_language
            data["translation_provider"] = self._result.translation_provider
            data["translation_model"] = self._result.translation_model
            data["translation_source_language"] = self._result.translation_source_language
            data["translation_target_language"] = self._result.translation_target_language

            # Only persist user-typed keys, not env-sourced ones.
            if self._result.deepinfra_api_key:
                data["deepinfra_api_key"] = self._result.deepinfra_api_key
            if self._result.gemini_api_key:
                data["gemini_api_key"] = self._result.gemini_api_key

            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info("Settings saved to %s", CONFIG_FILE)
        except Exception:
            logger.exception("Failed to persist settings.")

    # ── public API ────────────────────────────────────────────────────────────

    def get_result(self) -> Optional[SettingsResult]:
        return self._result
