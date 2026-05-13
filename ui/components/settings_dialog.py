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
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.config import AppConfig
from app.logger import get_logger
from app.paths import CONFIG_FILE
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

        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self.setMinimumHeight(580)
        self.setStyleSheet(_QSS)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
        )

        self._build_ui()

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
