"""VoxCPM2 Voice Clone Studio.

Tab 1 — Clone Voice
    Pick a built-in sample card (or import custom audio), enter transcript /
    test text, generate a voice test, then save to the Voice Library so it
    becomes available in the Gender Assignment dropdowns.

Tab 2 — Hardware Check
    Shows GPU / VRAM / CUDA info from VoxCpmService.get_device_info() and
    runs a quick synthesize benchmark to measure Real-Time Factor (RTF).
"""
from __future__ import annotations

import datetime
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.logger import get_logger
from app.paths import DEFAULT_VOICES_DIR
from services.prompt_library_service import BUILTIN_PROMPTS, PromptLibraryService
from services.voice_library_service import VoiceLibraryService
from ui.components.app_select import AppSelect
from ui.components.model_download_dialog import ModelDownloadDialog
from utils.font_manager import get_google_sans
from workers.voxcpm_worker import VoxCpmWorker


logger = get_logger(__name__)


_QSS = """
QDialog { background-color: #1a1f2e; color: #e2e8f0; }

QTabWidget::pane {
    background-color: #1a1f2e;
    border: 1px solid #2d3748;
    border-radius: 6px;
}
QTabBar::tab {
    background: #0f131e;
    color: #94a3b8;
    border: none;
    padding: 8px 22px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-size: 13px;
    font-weight: 600;
}
QTabBar::tab:selected { background: #1a1f2e; color: #e2e8f0; }
QTabBar::tab:hover { color: #e2e8f0; }

QLabel { color: #cbd5e1; font-size: 13px; }
QLabel#title   { color: #f1f5f9; font-size: 16px; font-weight: 700; }
QLabel#subtitle { color: #94a3b8; font-size: 12px; }
QLabel#fieldLabel { color: #cbd5e1; font-size: 13px; font-weight: 600; }
QLabel#fileLabel  { color: #94a3b8; font-size: 12px; }
QLabel#fileName   { color: #e2e8f0; font-size: 12px; font-weight: 700; }
QLabel#hwValue    { color: #e2e8f0; font-size: 13px; font-weight: 700; }
QLabel#hwLabel    { color: #94a3b8; font-size: 13px; }

QLineEdit {
    background-color: #111827; color: #e5e7eb;
    border: 1px solid #374151; border-radius: 7px;
    padding: 8px 10px; font-size: 13px; min-height: 22px;
}
QLineEdit:focus { border: 1px solid #3b82f6; }

QTextEdit {
    background-color: #111827; color: #e5e7eb;
    border: 1px solid #374151; border-radius: 7px;
    padding: 10px; font-size: 13px;
    selection-background-color: #3b82f6;
}
QTextEdit:focus { border: 1px solid #3b82f6; }

QSpinBox {
    background-color: #111827; color: #e5e7eb;
    border: 1px solid #374151; border-radius: 7px;
    padding: 7px 10px; font-size: 13px; min-width: 90px;
}
QSpinBox:focus { border-color: #3b82f6; }

QProgressBar {
    background-color: #2d3748; border: 1px solid #374151;
    border-radius: 5px; height: 10px; text-align: center;
    color: #fff; font-size: 9px; font-weight: 700;
}
QProgressBar::chunk { background-color: #3b82f6; border-radius: 4px; }

QFrame#separator { background-color: #1f2937; min-height: 1px; max-height: 1px; }

QPushButton#primaryBtn {
    background-color: #3b82f6; color: #fff;
    border: none; border-radius: 8px; padding: 0px 14px;
    font-size: 13px; font-weight: 700;
}
QPushButton#primaryBtn:hover    { background-color: #2563eb; }
QPushButton#primaryBtn:pressed  { background-color: #1d4ed8; }
QPushButton#primaryBtn:disabled { background-color: #1e3a5f; color: #4b6fa0; }

QPushButton#secondaryBtn {
    background-color: transparent; color: #94a3b8;
    border: 1px solid #374151; border-radius: 8px; padding: 0px 14px;
    font-size: 13px; font-weight: 600;
}
QPushButton#secondaryBtn:hover    { background-color: #1f2937; color: #e2e8f0; border-color: #4b5563; }
QPushButton#secondaryBtn:pressed  { background-color: #374151; }
QPushButton#secondaryBtn:disabled { color: #4b5563; border-color: #2d3748; }

QPushButton#sampleCard {
    background-color: #1e2436; color: #cbd5e1;
    border: 1px solid #2d3748; border-radius: 8px;
    padding: 8px 12px; font-size: 12px; text-align: left;
    min-width: 130px; max-width: 150px; min-height: 60px;
}
QPushButton#sampleCard:hover   { border-color: #3b82f6; background-color: #252d42; }
QPushButton#sampleCard:checked { border-color: #3b82f6; background-color: #1e3a5f; color: #93c5fd; }

QScrollArea { background: transparent; border: none; }

QPushButton#promptChip {
    background-color: #1e2a3a; color: #93c5fd;
    border: 1px solid #2d4a6e; border-radius: 12px;
    padding: 3px 10px; font-size: 11px;
}
QPushButton#promptChip:hover { background-color: #1e3a5f; border-color: #3b82f6; }
QPushButton#promptChip:checked { background-color: #1e3a5f; border-color: #3b82f6; color: #fff; }

QPushButton#promptChipSaved {
    background-color: #1e3a2a; color: #6ee7b7;
    border: 1px solid #2d6a4a; border-radius: 12px;
    padding: 3px 10px; font-size: 11px;
}
QPushButton#promptChipSaved:hover { background-color: #14532d; border-color: #22c55e; }
QPushButton#promptChipSaved:checked { background-color: #14532d; border-color: #22c55e; color: #fff; }

QPushButton#promptChipDel {
    background-color: transparent; color: #94a3b8;
    border: none; padding: 2px 4px; font-size: 11px; max-width: 18px;
}
QPushButton#promptChipDel:hover { color: #ef4444; }

QScrollBar:horizontal {
    background: #12151f; border: none; height: 6px; border-radius: 3px;
}
QScrollBar::handle:horizontal {
    background: #3b4268; border-radius: 3px; min-width: 30px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0; height: 0;
}
QScrollBar:vertical {
    background: #12151f; border: none; width: 6px; border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #3b4268; border-radius: 3px; min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    width: 0; height: 0;
}
"""


@dataclass
class VoxCPMResult:
    voice_name: str
    gender: str
    sample_wav: str
    sample_text: str
    test_text: str
    output_file: str
    progress: int
    status: str
    error: str
    success: bool
    message: str
    timestamp: datetime.datetime
    version: str
    model: str
    provider: str


class VoxCPMDialog(QDialog):
    """Two-tab Voice Clone Studio: Clone Voice + Hardware Check."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._result: Optional[VoxCPMResult] = None
        self._thread: QThread | None = None
        self._worker: VoxCpmWorker | None = None
        self._output_path: Path | None = None
        self._sample_wav_path: Path | None = None
        self._selected_card: Optional[QPushButton] = None
        self._builtin_voices: list[dict] = self._load_builtin_manifest()
        self._voice_library = VoiceLibraryService()
        self._prompt_library = PromptLibraryService()

        self.setWindowTitle("Voice Clone Studio")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(860)
        self.setMaximumWidth(980)
        self.resize(900, 820)
        self.setStyleSheet(_QSS)

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(10)

        title = QLabel("Voice Clone Studio")
        title.setObjectName("title")
        title.setFont(get_google_sans(size=16, weight="Bold"))
        root.addWidget(title)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_clone_tab(), "🎙 Clone Voice")
        self._tabs.addTab(self._build_hardware_tab(), "⚡ Hardware Check")
        root.addWidget(self._tabs, 1)

    # ── Tab 1: Clone Voice ────────────────────────────────────────────────────

    def _build_clone_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # ── Sample cards ──────────────────────────────────────────────────────
        cards_label = QLabel("Sample Audio")
        cards_label.setObjectName("fieldLabel")
        layout.addWidget(cards_label)

        cards_scroll = QScrollArea()
        cards_scroll.setFixedHeight(100)
        cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setStyleSheet(
            "QScrollArea { background: #12151f; border: 1px solid #2d3748; border-radius: 6px; }"
        )

        cards_inner = QWidget()
        cards_inner.setStyleSheet("background: transparent;")
        cards_row = QHBoxLayout(cards_inner)
        cards_row.setContentsMargins(0, 4, 0, 4)
        cards_row.setSpacing(8)

        self._sample_cards: list[QPushButton] = []

        for voice in self._builtin_voices:
            gender_icon = "♂" if voice.get("gender") == "male" else "♀"
            btn = QPushButton(f"{gender_icon} {voice['name']}\n[built-in]")
            btn.setObjectName("sampleCard")
            btn.setCheckable(True)
            btn.setFont(get_google_sans(size=11))
            btn.clicked.connect(lambda _=False, v=voice, b=btn: self._on_builtin_card_clicked(v, b))
            cards_row.addWidget(btn)
            self._sample_cards.append(btn)

        cards_row.addStretch()

        cards_scroll.setWidget(cards_inner)
        layout.addWidget(cards_scroll)

        # ── Custom Audio File (always visible) ────────────────────────────────
        custom_lbl = QLabel("Or use your own audio:")
        custom_lbl.setObjectName("fieldLabel")
        layout.addWidget(custom_lbl)

        custom_row = QHBoxLayout()
        custom_row.setSpacing(6)
        self.sample_file_edit = QLineEdit()
        self.sample_file_edit.setPlaceholderText("Select or drag a .wav / .mp3 / .m4a / .flac file…")
        self.sample_file_edit.setReadOnly(True)
        browse_btn = QPushButton("Browse…")
        browse_btn.setObjectName("secondaryBtn")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._on_choose_sample_clicked)
        custom_row.addWidget(self.sample_file_edit, 1)
        custom_row.addWidget(browse_btn)
        layout.addLayout(custom_row)

        # keep the old label for backward-compat code that writes to it
        self.sample_file_label = self.sample_file_edit

        # ── Voice Design ──────────────────────────────────────────────────────
        vd_header = QHBoxLayout()
        vd_title = QLabel("Voice Design")
        vd_title.setObjectName("fieldLabel")
        vd_hint = QLabel("ℹ")
        vd_hint.setToolTip(
            "Describe a voice in plain language — no reference audio needed.\n"
            "VoxCPM2 prepends (description) to your text.\n"
            "Ignored when a sample card is selected above."
        )
        vd_hint.setStyleSheet("color: #4b6fa0; font-size: 13px;")
        vd_header.addWidget(vd_title)
        vd_header.addWidget(vd_hint)
        vd_header.addStretch()
        layout.addLayout(vd_header)

        # Input + Save button row
        vd_input_row = QHBoxLayout()
        vd_input_row.setSpacing(6)
        self.voice_design_edit = QLineEdit()
        self.voice_design_edit.setPlaceholderText(
            'e.g. "young man, calm and deep" or "woman, emotional, dramatic"'
        )
        vd_save_btn = QPushButton("Save")
        vd_save_btn.setObjectName("secondaryBtn")
        vd_save_btn.setFixedSize(60, 34)
        vd_save_btn.setToolTip("Save this prompt for quick reuse")
        vd_save_btn.clicked.connect(self._on_save_prompt)
        vd_input_row.addWidget(self.voice_design_edit, 1)
        vd_input_row.addWidget(vd_save_btn)
        layout.addLayout(vd_input_row)

        # Prompt chips (built-in + saved), horizontally scrollable
        self._prompt_chips_scroll = QScrollArea()
        self._prompt_chips_scroll.setFixedHeight(46)
        self._prompt_chips_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self._prompt_chips_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._prompt_chips_scroll.setWidgetResizable(True)
        self._prompt_chips_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        self._prompt_chips_inner = QWidget()
        self._prompt_chips_inner.setStyleSheet("background: transparent;")
        self._prompt_chips_row = QHBoxLayout(self._prompt_chips_inner)
        self._prompt_chips_row.setContentsMargins(0, 2, 0, 2)
        self._prompt_chips_row.setSpacing(6)
        self._prompt_chips_scroll.setWidget(self._prompt_chips_inner)

        self._active_chip: Optional[QPushButton] = None
        self._rebuild_prompt_chips()

        layout.addWidget(self._prompt_chips_scroll)

        # Voice name + gender row
        profile_row = QHBoxLayout()
        profile_row.setSpacing(12)
        name_lbl = QLabel("Voice Name:")
        name_lbl.setObjectName("fieldLabel")
        name_lbl.setFixedWidth(100)
        self.voice_name_edit = QLineEdit()
        self.voice_name_edit.setPlaceholderText("e.g. Khmer Male Hero")
        self.gender_select = self._make_select(["male", "female", "unknown"], "male", 150)
        profile_row.addWidget(name_lbl)
        profile_row.addWidget(self.voice_name_edit, 1)
        profile_row.addWidget(self.gender_select)
        layout.addLayout(profile_row)

        # Sample transcript
        tscript_lbl = QLabel("Sample Transcript:")
        tscript_lbl.setObjectName("fieldLabel")
        layout.addWidget(tscript_lbl)
        self.transcript_edit = QTextEdit()
        self.transcript_edit.setMinimumHeight(80)
        self.transcript_edit.setPlaceholderText("Exact words spoken in the selected sample audio…")
        layout.addWidget(self.transcript_edit)

        # Test text
        test_lbl = QLabel("Test Text:")
        test_lbl.setObjectName("fieldLabel")
        layout.addWidget(test_lbl)
        self.text_edit = QTextEdit()
        self.text_edit.setMinimumHeight(120)
        self.text_edit.setPlaceholderText("Enter Khmer text to hear in this voice…")
        layout.addWidget(self.text_edit)

        # Speed row
        speed_row = QHBoxLayout()
        speed_lbl = QLabel("Speed:")
        speed_lbl.setObjectName("fieldLabel")
        speed_lbl.setFixedWidth(100)
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 100)
        self.speed_spin.setValue(10)
        self.speed_spin.setSuffix(" %")
        self.speed_spin.setFixedWidth(120)
        speed_hint = QLabel("Kept for future post-processing (VoxCPM2 does not support speed natively).")
        speed_hint.setObjectName("subtitle")
        speed_row.addWidget(speed_lbl)
        speed_row.addWidget(self.speed_spin)
        speed_row.addWidget(speed_hint, 1)
        layout.addLayout(speed_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Output label
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Output:"))
        self.file_name_label = QLabel("No generated test yet")
        self.file_name_label.setObjectName("fileName")
        out_row.addWidget(self.file_name_label)
        out_row.addStretch()
        layout.addLayout(out_row)

        sep = QFrame()
        sep.setObjectName("separator")
        layout.addWidget(sep)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.generate_btn = QPushButton("Generate Test")
        self.generate_btn.setObjectName("primaryBtn")
        self.generate_btn.setFixedSize(150, 42)
        self.generate_btn.clicked.connect(self._on_generate_clicked)

        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setObjectName("secondaryBtn")
        self.play_btn.setFixedSize(100, 42)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._on_play_clicked)

        self.save_test_btn = QPushButton("Save Audio")
        self.save_test_btn.setObjectName("secondaryBtn")
        self.save_test_btn.setFixedSize(130, 42)
        self.save_test_btn.setEnabled(False)
        self.save_test_btn.clicked.connect(self._on_save_test_audio_clicked)

        self.save_voice_btn = QPushButton("Save Voice Clone")
        self.save_voice_btn.setObjectName("primaryBtn")
        self.save_voice_btn.setFixedSize(170, 42)
        self.save_voice_btn.setEnabled(False)
        self.save_voice_btn.clicked.connect(self._on_save_voice_clicked)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("secondaryBtn")
        close_btn.setFixedSize(100, 42)
        close_btn.clicked.connect(self._on_close_clicked)

        btn_row.addWidget(self.generate_btn)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.save_test_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_voice_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        return page

    # ── Prompt chip helpers ───────────────────────────────────────────────────

    def _rebuild_prompt_chips(self) -> None:
        """Repopulate the prompt chips row (built-ins + saved)."""
        # Clear existing widgets.
        while self._prompt_chips_row.count():
            item = self._prompt_chips_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._active_chip = None

        # Built-in chips.
        for p in BUILTIN_PROMPTS:
            self._add_chip(p["label"], p["text"], saved=False)

        # Separator label.
        if self._prompt_library.list_saved():
            sep = QLabel(" | Saved:")
            sep.setStyleSheet("color: #4b5563; font-size: 11px;")
            self._prompt_chips_row.addWidget(sep)

        # User-saved chips (with delete ×).
        for p in self._prompt_library.list_saved():
            self._add_chip(p["label"], p["text"], saved=True)

        self._prompt_chips_row.addStretch()

    def _add_chip(self, label: str, text: str, *, saved: bool) -> None:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(1)

        chip = QPushButton(label)
        chip.setObjectName("promptChipSaved" if saved else "promptChip")
        chip.setCheckable(True)
        chip.setFont(get_google_sans(size=10))
        chip.clicked.connect(lambda _=False, t=text, c=chip: self._on_chip_clicked(t, c))
        row.addWidget(chip)

        if saved:
            del_btn = QPushButton("×")
            del_btn.setObjectName("promptChipDel")
            del_btn.setFont(get_google_sans(size=11))
            del_btn.setFixedWidth(16)
            del_btn.clicked.connect(lambda _=False, lbl=label: self._on_delete_prompt(lbl))
            row.addWidget(del_btn)

        self._prompt_chips_row.addWidget(container)

    def _on_chip_clicked(self, text: str, chip: QPushButton) -> None:
        if self._active_chip and self._active_chip is not chip:
            self._active_chip.setChecked(False)
        chip.setChecked(True)
        self._active_chip = chip
        self.voice_design_edit.setText(text)

    def _on_save_prompt(self) -> None:
        text = self.voice_design_edit.text().strip()
        if not text:
            return
        from PySide6.QtWidgets import QInputDialog
        label, ok = QInputDialog.getText(
            self, "Save Prompt", "Name for this prompt:", text=text[:40]
        )
        if not ok or not label.strip():
            return
        self._prompt_library.save_prompt(label.strip(), text)
        self._rebuild_prompt_chips()

    def _on_delete_prompt(self, label: str) -> None:
        self._prompt_library.delete_prompt(label)
        self._rebuild_prompt_chips()

    # ── Tab 2: Hardware Check ─────────────────────────────────────────────────

    def _build_hardware_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        hw_title = QLabel("Device Info")
        hw_title.setObjectName("fieldLabel")
        layout.addWidget(hw_title)

        # Info card
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #12151f; border: 1px solid #2d3748; border-radius: 8px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        self._hw_rows: dict[str, QLabel] = {}
        for key in ("Device", "Physical GPU", "Torch GPU", "VRAM", "CUDA", "Status"):
            row = QHBoxLayout()
            lbl = QLabel(f"{key}:")
            lbl.setObjectName("hwLabel")
            lbl.setFixedWidth(100)
            val = QLabel("—")
            val.setObjectName("hwValue")
            val.setWordWrap(True)
            self._hw_rows[key] = val
            row.addWidget(lbl)
            row.addWidget(val, 1)
            card_layout.addLayout(row)

        # Warning box (shown only when GPU is detected but torch can't use it)
        self._hw_warning_box = QFrame()
        self._hw_warning_box.setStyleSheet(
            "QFrame { background: #3b1f00; border: 1px solid #d97706; border-radius: 6px; }"
        )
        hw_warn_layout = QVBoxLayout(self._hw_warning_box)
        hw_warn_layout.setContentsMargins(12, 10, 12, 10)
        self._hw_warning_lbl = QLabel()
        self._hw_warning_lbl.setWordWrap(True)
        self._hw_warning_lbl.setStyleSheet("color: #fcd34d; font-size: 12px; border: none;")
        self._hw_warning_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        hw_warn_layout.addWidget(self._hw_warning_lbl)
        self._hw_warning_box.hide()
        card_layout.addWidget(self._hw_warning_box)

        layout.addWidget(card)

        # Quick test
        test_title = QLabel("Quick Test")
        test_title.setObjectName("fieldLabel")
        layout.addWidget(test_title)

        test_desc = QLabel(
            "Synthesizes a short Khmer phrase and measures Real-Time Factor (RTF).\n"
            "RTF < 1.0 means faster-than-real-time; lower is better."
        )
        test_desc.setObjectName("subtitle")
        test_desc.setWordWrap(True)
        layout.addWidget(test_desc)

        self.hw_progress = QProgressBar()
        self.hw_progress.setRange(0, 100)
        self.hw_progress.setValue(0)
        self.hw_progress.setFixedHeight(8)
        self.hw_progress.setTextVisible(False)
        self.hw_progress.hide()
        layout.addWidget(self.hw_progress)

        self.hw_result_label = QLabel("")
        self.hw_result_label.setObjectName("hwValue")
        self.hw_result_label.setWordWrap(True)
        layout.addWidget(self.hw_result_label)

        hw_btn_row = QHBoxLayout()
        self.hw_run_btn = QPushButton("Run Quick Test")
        self.hw_run_btn.setObjectName("primaryBtn")
        self.hw_run_btn.setFixedSize(160, 42)
        self.hw_run_btn.clicked.connect(self._on_hw_test_clicked)

        self.hw_play_btn = QPushButton("▶ Play Test Audio")
        self.hw_play_btn.setObjectName("secondaryBtn")
        self.hw_play_btn.setFixedSize(160, 42)
        self.hw_play_btn.setEnabled(False)
        self.hw_play_btn.clicked.connect(self._on_hw_play_clicked)

        hw_btn_row.addWidget(self.hw_run_btn)
        hw_btn_row.addWidget(self.hw_play_btn)
        hw_btn_row.addStretch()
        layout.addLayout(hw_btn_row)

        layout.addStretch()

        # Populate hardware info now (no model load, fast).
        QTimer.singleShot(0, self._refresh_hardware_info)

        self._hw_test_output: Path | None = None
        self._hw_thread: QThread | None = None
        self._hw_worker: VoxCpmWorker | None = None

        return page

    # ── built-in voice helpers ────────────────────────────────────────────────

    @staticmethod
    def _load_builtin_manifest() -> list[dict]:
        manifest = DEFAULT_VOICES_DIR / "manifest.json"
        if not manifest.exists():
            return []
        try:
            return json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _on_builtin_card_clicked(self, voice: dict, btn: QPushButton) -> None:
        """Select a built-in voice card and pre-fill transcript."""
        # Deselect previous card.
        if self._selected_card and self._selected_card is not btn:
            self._selected_card.setChecked(False)

        btn.setChecked(True)
        self._selected_card = btn

        # Clear custom audio input — built-in card takes priority.
        self._sample_wav_path = None
        self.sample_file_edit.clear()

        # Clear Voice Design prompt — cloning takes priority.
        if self._active_chip:
            self._active_chip.setChecked(False)
            self._active_chip = None
        self.voice_design_edit.clear()

        wav_path = DEFAULT_VOICES_DIR / voice["wav"]
        self._sample_wav_path = wav_path
        self.sample_file_edit.setText(f"{voice['name']}  [{wav_path.name}]")

        # Pre-fill transcript (read-only for built-ins, user can still edit).
        self.transcript_edit.setPlainText(voice.get("transcript", ""))

        # Pre-fill voice name + gender.
        self.voice_name_edit.setText(voice["name"])
        gender = voice.get("gender", "male")
        self.gender_select.set_value(gender)

        # Reset output state.
        self._output_path = None
        self.file_name_label.setText("No generated test yet")
        self.play_btn.setEnabled(False)
        self.save_test_btn.setEnabled(False)
        self.save_voice_btn.setEnabled(False)

    # ── Hardware info ─────────────────────────────────────────────────────────

    def _refresh_hardware_info(self) -> None:
        try:
            from services.voxcpm_service import VoxCpmService
            info = VoxCpmService.get_device_info()
        except Exception as exc:
            logger.warning("Could not read device info: %s", exc)
            info = {
                "device": "unknown", "gpu_name": "N/A", "vram_gb": 0.0,
                "cuda_version": "N/A", "torch_cuda_built": False,
                "nvidia_smi_gpu": "N/A", "warning": "",
            }

        device = info.get("device", "cpu")
        self._hw_rows["Device"].setText(device.upper())

        # Physical GPU row — from nvidia-smi if torch can't see it, else from torch
        smi_gpu = info.get("nvidia_smi_gpu", "N/A")
        torch_gpu = info.get("gpu_name", "N/A")
        if device == "cuda":
            self._hw_rows["Physical GPU"].setText(torch_gpu)
            self._hw_rows["Torch GPU"].setText(f"{torch_gpu}  ✓ active")
            self._hw_rows["Torch GPU"].setStyleSheet("color: #22c55e;")
        else:
            phys = smi_gpu if smi_gpu != "N/A" else "Not detected"
            self._hw_rows["Physical GPU"].setText(phys)
            torch_built = info.get("torch_cuda_built", False)
            if smi_gpu != "N/A":
                self._hw_rows["Torch GPU"].setText("✗ GPU found but PyTorch cannot use it")
                self._hw_rows["Torch GPU"].setStyleSheet("color: #ef4444; font-weight: 700;")
            else:
                self._hw_rows["Torch GPU"].setText("No GPU" if not torch_built else "N/A")
                self._hw_rows["Torch GPU"].setStyleSheet("")

        vram = info.get("vram_gb", 0.0)
        if isinstance(vram, float):
            self._hw_rows["VRAM"].setText(f"{vram:.1f} GB" if vram else "N/A")
        else:
            self._hw_rows["VRAM"].setText(str(vram))

        self._hw_rows["CUDA"].setText(info.get("cuda_version", "N/A"))

        if device == "cuda":
            status = "✓ Good — VoxCPM2 will run on your GPU."
            self._hw_rows["Status"].setStyleSheet("color: #22c55e; font-weight: 700;")
        elif device == "mps":
            status = "✓ Apple Silicon MPS detected — decent performance expected."
            self._hw_rows["Status"].setStyleSheet("color: #22c55e; font-weight: 700;")
        else:
            status = "⚠ CPU only — inference will be very slow (5–15 min per segment)."
            self._hw_rows["Status"].setStyleSheet("color: #f59e0b; font-weight: 700;")

        self._hw_rows["Status"].setText(status)

        # Show/hide the fix warning box
        warning = info.get("warning", "")
        if warning:
            self._hw_warning_lbl.setText(f"⚠  {warning}")
            self._hw_warning_box.show()
        else:
            self._hw_warning_box.hide()

    def _on_hw_test_clicked(self) -> None:
        ok = ModelDownloadDialog.ensure(
            provider="local_voxcpm",
            model_name="openbmb/VoxCPM2",
            parent=self,
        )
        if not ok:
            return

        self.hw_run_btn.setEnabled(False)
        self.hw_result_label.setText("Running quick test…")
        self.hw_progress.show()
        self.hw_progress.setValue(0)
        self._hw_test_output = None
        self.hw_play_btn.setEnabled(False)

        test_text = "ខ្ញុំកំពុងសាកល្បងម៉ូដែលសំលេង"

        from services.voxcpm_service import VoxCpmService
        dummy_voice = self._builtin_voices[0] if self._builtin_voices else None
        prompt_wav = (DEFAULT_VOICES_DIR / dummy_voice["wav"]) if dummy_voice else None
        prompt_text = dummy_voice.get("transcript", "") if dummy_voice else ""

        self._start_time = time.time()

        self._hw_thread = QThread(self)
        self._hw_worker = VoxCpmWorker(
            text=test_text,
            prompt_wav=prompt_wav,
            prompt_text=prompt_text,
            speed_percent=10,
        )
        self._hw_worker.moveToThread(self._hw_thread)
        self._hw_thread.started.connect(self._hw_worker.run)
        self._hw_worker.progress_changed.connect(
            lambda p, _: self.hw_progress.setValue(p)
        )
        self._hw_worker.finished.connect(self._on_hw_test_finished)
        self._hw_worker.failed.connect(self._on_hw_test_failed)
        self._hw_worker.finished.connect(self._hw_thread.quit)
        self._hw_worker.failed.connect(self._hw_thread.quit)
        self._hw_worker.finished.connect(self._hw_worker.deleteLater)
        self._hw_worker.failed.connect(self._hw_worker.deleteLater)
        self._hw_thread.finished.connect(self._hw_thread.deleteLater)
        self._hw_thread.finished.connect(self._hw_cleanup)
        self._hw_thread.start()

    def _on_hw_test_finished(self, output_path: str) -> None:
        elapsed = time.time() - self._start_time
        # Approximate audio duration from a 5-word Khmer phrase (~2.5 s).
        audio_duration = 2.5
        rtf = elapsed / audio_duration
        self._hw_test_output = Path(output_path)

        verdict = "PASS ✓" if rtf < 2.0 else "SLOW ⚠"
        color = "#22c55e" if rtf < 2.0 else "#f59e0b"
        self.hw_result_label.setText(
            f"RTF {rtf:.2f} — {verdict}   ({elapsed:.1f} s wall-clock)"
        )
        self.hw_result_label.setStyleSheet(f"color: {color}; font-weight: 700;")
        self.hw_progress.setValue(100)
        self.hw_play_btn.setEnabled(True)
        self.hw_run_btn.setEnabled(True)

    def _on_hw_test_failed(self, error: str) -> None:
        self.hw_result_label.setText(f"FAIL ✗  {error}")
        self.hw_result_label.setStyleSheet("color: #ef4444; font-weight: 700;")
        self.hw_run_btn.setEnabled(True)

    def _on_hw_play_clicked(self) -> None:
        if self._hw_test_output and self._hw_test_output.exists():
            QDesktopServices.openUrl(self._hw_test_output.as_uri())

    def _hw_cleanup(self) -> None:
        self._hw_worker = None
        self._hw_thread = None

    # ── Clone Voice actions ───────────────────────────────────────────────────

    def _on_choose_sample_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Choose Voice Sample", "",
            "Audio Files (*.wav *.mp3 *.m4a *.flac);;All Files (*)",
        )
        if not file_path:
            return

        # Deselect any active built-in card.
        if self._selected_card:
            self._selected_card.setChecked(False)
            self._selected_card = None

        self._sample_wav_path = Path(file_path)
        self.sample_file_edit.setText(str(self._sample_wav_path))
        self.transcript_edit.setPlainText("")
        self._output_path = None
        self.file_name_label.setText("No generated test yet")
        self.play_btn.setEnabled(False)
        self.save_test_btn.setEnabled(False)
        self.save_voice_btn.setEnabled(False)

    def _on_generate_clicked(self) -> None:
        text = self.get_text()
        sample_text = self.get_sample_text()
        voice_design = self.voice_design_edit.text().strip()

        # Must have either a reference sample OR a Voice Design description.
        if not self._sample_wav_path and not voice_design:
            QMessageBox.warning(
                self, "Nothing to Clone",
                "Either select a voice sample card or enter a Voice Design description.",
            )
            return
        # If a sample is chosen, its transcript is required for Ultimate Cloning.
        if self._sample_wav_path and not sample_text:
            QMessageBox.warning(self, "Missing Transcript",
                                "Please enter the exact transcript of the sample audio.")
            return
        if not text:
            QMessageBox.warning(self, "Missing Test Text",
                                "Please enter test text to generate.")
            return

        ok = ModelDownloadDialog.ensure(
            provider="local_voxcpm", model_name="openbmb/VoxCPM2", parent=self,
        )
        if not ok:
            return

        self._set_generating_state(True)

        self._thread = QThread(self)
        self._worker = VoxCpmWorker(
            text=text,
            prompt_wav=self._sample_wav_path,
            prompt_text=sample_text,
            voice_design=voice_design or None,
            speed_percent=self.get_speed_percent(),
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress_changed.connect(self._on_generation_progress)
        self._worker.finished.connect(self._on_generation_finished)
        self._worker.failed.connect(self._on_generation_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.failed.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup_worker)
        self._thread.start()

    def _on_generation_progress(self, value: int, message: str) -> None:
        self.progress_bar.show()
        self.progress_bar.setValue(value)
        logger.info("VoxCPM progress: %s%% - %s", value, message)

    def _on_generation_finished(self, output_path: str) -> None:
        self._output_path = Path(output_path)
        self.file_name_label.setText(self._output_path.name)
        self.play_btn.setEnabled(True)
        self.save_test_btn.setEnabled(True)
        self.save_voice_btn.setEnabled(True)
        self._set_generating_state(False)

        self._result = VoxCPMResult(
            voice_name=self.voice_name_edit.text().strip(),
            gender=self.gender_select.value,
            sample_wav=str(self._sample_wav_path or ""),
            sample_text=self.get_sample_text(),
            test_text=self.get_text(),
            output_file=str(self._output_path),
            progress=100,
            status="completed",
            error="",
            success=True,
            message="Test voice generated successfully.",
            timestamp=datetime.datetime.now(),
            version="1.0",
            model="openbmb/VoxCPM2",
            provider="voxcpm",
        )
        QMessageBox.information(
            self, "Success",
            "Test voice generated. You can now play it or save this voice clone.",
        )

    def _on_generation_failed(self, error: str) -> None:
        self._set_generating_state(False)
        self._result = VoxCPMResult(
            voice_name=self.voice_name_edit.text().strip(),
            gender=self.gender_select.value,
            sample_wav=str(self._sample_wav_path or ""),
            sample_text=self.get_sample_text(),
            test_text=self.get_text(),
            output_file="",
            progress=self.progress_bar.value(),
            status="failed",
            error=error,
            success=False,
            message="Voice generation failed.",
            timestamp=datetime.datetime.now(),
            version="1.0",
            model="openbmb/VoxCPM2",
            provider="voxcpm",
        )
        QMessageBox.critical(self, "VoxCPM Error", error)

    def _on_play_clicked(self) -> None:
        if not self._output_path or not self._output_path.exists():
            QMessageBox.warning(self, "No Audio", "Please generate test voice first.")
            return
        QDesktopServices.openUrl(self._output_path.as_uri())

    def _on_save_test_audio_clicked(self) -> None:
        if not self._output_path or not self._output_path.exists():
            QMessageBox.warning(self, "No Audio", "Please generate test voice first.")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Test Audio", self._output_path.name,
            "WAV Audio (*.wav);;All Files (*)",
        )
        if not save_path:
            return
        try:
            shutil.copy2(self._output_path, Path(save_path))
            QMessageBox.information(self, "Saved", f"Test audio saved to:\n{save_path}")
        except Exception as err:
            logger.exception("Failed to save VoxCPM test audio.")
            QMessageBox.critical(self, "Save Failed", str(err))

    def _on_save_voice_clicked(self) -> None:
        if not self._sample_wav_path or not self._sample_wav_path.exists():
            QMessageBox.warning(self, "Missing Sample", "Please choose a voice sample first.")
            return
        sample_text = self.get_sample_text()
        if not sample_text:
            QMessageBox.warning(self, "Missing Transcript", "Please enter the sample transcript.")
            return
        voice_name = self.voice_name_edit.text().strip()
        if not voice_name:
            QMessageBox.warning(self, "Missing Voice Name", "Please enter a name for this clone.")
            return
        try:
            entry = self._voice_library.add_sample(
                name=voice_name,
                gender=self.gender_select.value,
                src_wav=self._sample_wav_path,
                sample_text=sample_text,
            )
            QMessageBox.information(self, "Saved", f"Voice clone saved:\n{entry.name}")
        except Exception as err:
            logger.exception("Failed to save voice clone.")
            QMessageBox.critical(self, "Save Failed", str(err))

    def _on_close_clicked(self) -> None:
        if self._thread and self._thread.isRunning():
            QMessageBox.warning(self, "Generating",
                                "Voice is still generating. Please wait.")
            return
        self.close()

    def closeEvent(self, event) -> None:
        """Disconnect worker signals before widgets are destroyed to prevent crashes."""
        for worker, thread in [
            (self._worker, self._thread),
            (getattr(self, "_hw_worker", None), getattr(self, "_hw_thread", None)),
        ]:
            if worker is not None:
                try:
                    worker.finished.disconnect()
                    worker.failed.disconnect()
                    worker.progress_changed.disconnect()
                except Exception:
                    pass
            if thread is not None and thread.isRunning():
                thread.quit()
                thread.wait(3000)
        super().closeEvent(event)

    def _cleanup_worker(self) -> None:
        self._worker = None
        self._thread = None

    def _set_generating_state(self, generating: bool) -> None:
        self.generate_btn.setEnabled(not generating)
        self.save_voice_btn.setEnabled(
            False if generating else self._output_path is not None
        )
        self.play_btn.setEnabled(False if generating else self._output_path is not None)
        self.save_test_btn.setEnabled(
            False if generating else self._output_path is not None
        )
        if generating:
            self.generate_btn.setText("Generating…")
            self.progress_bar.show()
            self.progress_bar.setValue(0)
        else:
            self.generate_btn.setText("Generate Test")

    # ── accessors ─────────────────────────────────────────────────────────────

    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def get_sample_text(self) -> str:
        return self.transcript_edit.toPlainText().strip()

    def get_speed_percent(self) -> int:
        return self.speed_spin.value()

    def get_result(self) -> Optional[VoxCPMResult]:
        return self._result

    # ── AppSelect helper ──────────────────────────────────────────────────────

    def _make_select(
        self,
        labels: list[str],
        current: str,
        width: int = 320,
        height: int = 34,
        on_change=None,
    ) -> AppSelect:
        sel = AppSelect(
            items=labels, value=current, width=width, height=height, on_change=on_change,
        )
        sel.setStyleSheet(self._DARK_BUTTON_QSS)
        original_rebuild = sel.rebuild_menu

        def _patched_rebuild():
            original_rebuild()
            sel.menu.setStyleSheet(self._DARK_MENU_QSS)

        sel.rebuild_menu = _patched_rebuild
        sel.menu.setStyleSheet(self._DARK_MENU_QSS)
        return sel

    _DARK_MENU_QSS = """
        QMenu { background-color: #2d3748; color: #e2e8f0;
                border: 1px solid #4a5568; border-radius: 6px;
                padding: 4px 0; font-size: 13px; }
        QMenu::item { color: #e2e8f0; padding: 8px 16px;
                      border-radius: 4px; margin: 2px 4px; }
        QMenu::item:selected { background-color: #3b82f6; color: #fff; }
        QMenu::item:checked  { background-color: #1e3a5f; color: #93c5fd; font-weight: 600; }
        QMenu::separator { height: 1px; background: #4a5568; margin: 4px 8px; }
    """

    _DARK_BUTTON_QSS = """
        QPushButton#appSelect {
            background-color: #2d3748; color: #e2e8f0;
            border: 1px solid #4a5568; border-radius: 7px;
            padding: 0px 12px; text-align: left;
            font-size: 13px; font-weight: 500;
        }
        QPushButton#appSelect:hover   { border-color: #3b82f6; background-color: #374151; }
        QPushButton#appSelect:pressed { background-color: #1e3a5f; border-color: #3b82f6; }
    """
