from __future__ import annotations

import datetime
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.logger import get_logger
from services.voice_library_service import VoiceLibraryService
from ui.components.app_select import AppSelect
from ui.components.model_download_dialog import ModelDownloadDialog
from utils.font_manager import get_google_sans
from workers.voxcpm_worker import VoxCpmWorker


logger = get_logger(__name__)


_QSS = """
QDialog {
    background-color: #1a1f2e;
    color: #e2e8f0;
}

QLabel {
    color: #cbd5e1;
    font-size: 13px;
}

QLabel#title {
    color: #f1f5f9;
    font-size: 16px;
    font-weight: 700;
}

QLabel#subtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#fieldLabel {
    color: #cbd5e1;
    font-size: 13px;
    font-weight: 600;
}

QLabel#fileLabel {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#fileName {
    color: #e2e8f0;
    font-size: 12px;
    font-weight: 700;
}

QLineEdit {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 7px;
    padding: 8px 10px;
    font-size: 13px;
    min-height: 22px;
}

QLineEdit:focus {
    border: 1px solid #3b82f6;
}

QTextEdit {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 7px;
    padding: 10px;
    font-size: 13px;
    selection-background-color: #3b82f6;
}

QTextEdit:focus {
    border: 1px solid #3b82f6;
}

QSpinBox {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 7px;
    padding: 7px 10px;
    font-size: 13px;
    min-width: 90px;
}

QSpinBox:focus {
    border-color: #3b82f6;
}

QProgressBar {
    background-color: #2d3748;
    border: 1px solid #374151;
    border-radius: 5px;
    height: 10px;
    text-align: center;
    color: #ffffff;
    font-size: 9px;
    font-weight: 700;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 4px;
}

QFrame#separator {
    background-color: #1f2937;
    min-height: 1px;
    max-height: 1px;
}

QPushButton#primaryBtn {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 0px 14px;
    font-size: 13px;
    font-weight: 700;
}

QPushButton#primaryBtn:hover {
    background-color: #2563eb;
}

QPushButton#primaryBtn:pressed {
    background-color: #1d4ed8;
}

QPushButton#primaryBtn:disabled {
    background-color: #1e3a5f;
    color: #4b6fa0;
}

QPushButton#secondaryBtn {
    background-color: transparent;
    color: #94a3b8;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 0px 14px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton#secondaryBtn:hover {
    background-color: #1f2937;
    color: #e2e8f0;
    border-color: #4b5563;
}

QPushButton#secondaryBtn:pressed {
    background-color: #374151;
}

QPushButton#secondaryBtn:disabled {
    color: #4b5563;
    border-color: #2d3748;
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
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        logger.info("VoxCPMDialog initialized.")

        self._result: Optional[VoxCPMResult] = None
        self._thread: QThread | None = None
        self._worker: VoxCpmWorker | None = None
        self._output_path: Path | None = None
        self._sample_wav_path: Path | None = None
        self._voice_library = VoiceLibraryService()

        self.setWindowTitle("AI VoxCPM2 Voice Clone Tester")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumWidth(820)
        self.setMaximumWidth(920)
        self.resize(860, 760)
        self.setStyleSheet(_QSS)

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)

        title = QLabel("AI VoxCPM2 Voice Clone Tester")
        title.setObjectName("title")
        title.setFont(get_google_sans(size=16, weight="Bold"))
        root.addWidget(title)

        subtitle = QLabel(
            "Choose a sample voice, enter its exact transcript, generate a test, then save it as a reusable voice clone."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # Sample audio row
        sample_row = QHBoxLayout()
        sample_row.setSpacing(12)

        sample_label = QLabel("Sample:")
        sample_label.setObjectName("fieldLabel")
        sample_label.setFixedWidth(100)

        self.sample_file_label = QLabel("No sample selected")
        self.sample_file_label.setObjectName("fileName")

        self.choose_sample_btn = QPushButton("Choose Sample")
        self.choose_sample_btn.setObjectName("secondaryBtn")
        self.choose_sample_btn.setFixedSize(150, 36)
        self.choose_sample_btn.clicked.connect(self._on_choose_sample_clicked)

        sample_row.addWidget(sample_label)
        sample_row.addWidget(self.sample_file_label, 1)
        sample_row.addWidget(self.choose_sample_btn)
        root.addLayout(sample_row)

        # Voice profile row
        profile_row = QHBoxLayout()
        profile_row.setSpacing(12)

        name_label = QLabel("Voice Name:")
        name_label.setObjectName("fieldLabel")
        name_label.setFixedWidth(100)

        self.voice_name_edit = QLineEdit()
        self.voice_name_edit.setPlaceholderText("Example: Khmer Male Hero")

        self.gender_select = self._make_select(
            labels=["male", "female", "unknown"],
            current="male",
            width=150,
            height=36,
        )

        profile_row.addWidget(name_label)
        profile_row.addWidget(self.voice_name_edit, 1)
        profile_row.addWidget(self.gender_select)
        root.addLayout(profile_row)

        # Sample transcript
        transcript_label = QLabel("Sample Transcript:")
        transcript_label.setObjectName("fieldLabel")
        root.addWidget(transcript_label)

        self.transcript_edit = QTextEdit()
        self.transcript_edit.setMinimumHeight(115)
        self.transcript_edit.setPlaceholderText(
            "Enter the exact words spoken in the selected sample audio..."
        )
        root.addWidget(self.transcript_edit)

        # Test text
        text_label = QLabel("Test Text:")
        text_label.setObjectName("fieldLabel")
        root.addWidget(text_label)

        self.text_edit = QTextEdit()
        self.text_edit.setMinimumHeight(190)
        self.text_edit.setPlaceholderText(
            "Enter Khmer text to test this voice clone..."
        )
        root.addWidget(self.text_edit)

        # Speed row
        speed_row = QHBoxLayout()
        speed_row.setSpacing(12)

        speed_label = QLabel("Speed:")
        speed_label.setObjectName("fieldLabel")
        speed_label.setFixedWidth(100)

        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 100)
        self.speed_spin.setValue(10)
        self.speed_spin.setSuffix(" %")
        self.speed_spin.setFixedWidth(120)

        speed_hint = QLabel("Currently kept for future post-processing. VoxCPM generate() does not support speed directly.")
        speed_hint.setObjectName("subtitle")

        speed_row.addWidget(speed_label)
        speed_row.addWidget(self.speed_spin)
        speed_row.addWidget(speed_hint, 1)
        root.addLayout(speed_row)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.hide()
        root.addWidget(self.progress_bar)

        # File row
        file_row = QHBoxLayout()
        file_row.setSpacing(6)

        file_label = QLabel("Output:")
        file_label.setObjectName("fileLabel")

        self.file_name_label = QLabel("No generated test yet")
        self.file_name_label.setObjectName("fileName")

        file_row.addWidget(file_label)
        file_row.addWidget(self.file_name_label)
        file_row.addStretch()
        root.addLayout(file_row)

        separator = QFrame()
        separator.setObjectName("separator")
        root.addWidget(separator)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setContentsMargins(0, 2, 0, 0)

        self.generate_btn = QPushButton("Generate Test")
        self.generate_btn.setObjectName("primaryBtn")
        self.generate_btn.setFixedSize(150, 42)
        self.generate_btn.clicked.connect(self._on_generate_clicked)

        self.play_btn = QPushButton("Play Test")
        self.play_btn.setObjectName("secondaryBtn")
        self.play_btn.setFixedSize(130, 42)
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._on_play_clicked)

        self.save_test_btn = QPushButton("Save Test Audio")
        self.save_test_btn.setObjectName("secondaryBtn")
        self.save_test_btn.setFixedSize(150, 42)
        self.save_test_btn.setEnabled(False)
        self.save_test_btn.clicked.connect(self._on_save_test_audio_clicked)

        self.save_voice_btn = QPushButton("Save Voice Clone")
        self.save_voice_btn.setObjectName("primaryBtn")
        self.save_voice_btn.setFixedSize(170, 42)
        self.save_voice_btn.setEnabled(False)
        self.save_voice_btn.clicked.connect(self._on_save_voice_clicked)

        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("secondaryBtn")
        self.close_btn.setFixedSize(110, 42)
        self.close_btn.clicked.connect(self._on_close_clicked)

        btn_row.addWidget(self.generate_btn)
        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.save_test_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_voice_btn)
        btn_row.addWidget(self.close_btn)

        root.addLayout(btn_row)

    def _on_choose_sample_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Voice Sample",
            "",
            "Audio Files (*.wav *.mp3 *.m4a *.flac);;All Files (*)",
        )

        if not file_path:
            return

        self._sample_wav_path = Path(file_path)
        self.sample_file_label.setText(self._sample_wav_path.name)

        self._output_path = None
        self.file_name_label.setText("No generated test yet")
        self.play_btn.setEnabled(False)
        self.save_test_btn.setEnabled(False)
        self.save_voice_btn.setEnabled(False)

    def _on_generate_clicked(self):
        text = self.get_text()
        sample_text = self.get_sample_text()

        if not self._sample_wav_path:
            QMessageBox.warning(
                self,
                "Missing Sample",
                "Please choose a voice sample audio file first.",
            )
            return

        if not sample_text:
            QMessageBox.warning(
                self,
                "Missing Transcript",
                "Please enter the exact transcript spoken in the sample audio.",
            )
            return

        if not text:
            QMessageBox.warning(
                self,
                "Missing Test Text",
                "Please enter test text to generate.",
            )
            return

        ok = ModelDownloadDialog.ensure(
            provider="local_voxcpm",
            model_name="openbmb/VoxCPM2",
            parent=self,
        )

        if not ok:
            return

        self._set_generating_state(True)

        self._thread = QThread(self)
        self._worker = VoxCpmWorker(
            text=text,
            prompt_wav=self._sample_wav_path,
            prompt_text=sample_text,
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

    def _on_generation_progress(self, value: int, message: str):
        self.progress_bar.show()
        self.progress_bar.setValue(value)
        logger.info("VoxCPM progress: %s%% - %s", value, message)

    def _on_generation_finished(self, output_path: str):
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
            self,
            "Success",
            "Test voice generated successfully. You can now play it or save this voice clone.",
        )

    def _on_generation_failed(self, error: str):
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

        QMessageBox.critical(
            self,
            "VoxCPM Error",
            error,
        )

    def _on_play_clicked(self):
        if not self._output_path or not self._output_path.exists():
            QMessageBox.warning(
                self,
                "No Audio",
                "Please generate test voice first.",
            )
            return

        QDesktopServices.openUrl(self._output_path.as_uri())

    def _on_save_test_audio_clicked(self):
        if not self._output_path or not self._output_path.exists():
            QMessageBox.warning(
                self,
                "No Audio",
                "Please generate test voice first.",
            )
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Test Audio",
            self._output_path.name,
            "WAV Audio (*.wav);;All Files (*)",
        )

        if not save_path:
            return

        target = Path(save_path)

        try:
            shutil.copy2(self._output_path, target)

            QMessageBox.information(
                self,
                "Saved",
                f"Test audio saved to:\n{target}",
            )

        except Exception as error:
            logger.exception("Failed to save VoxCPM test audio.")

            QMessageBox.critical(
                self,
                "Save Failed",
                str(error),
            )

    def _on_save_voice_clicked(self):
        if not self._sample_wav_path or not self._sample_wav_path.exists():
            QMessageBox.warning(
                self,
                "Missing Sample",
                "Please choose a voice sample first.",
            )
            return

        sample_text = self.get_sample_text()

        if not sample_text:
            QMessageBox.warning(
                self,
                "Missing Transcript",
                "Please enter the sample transcript.",
            )
            return

        voice_name = self.voice_name_edit.text().strip()

        if not voice_name:
            QMessageBox.warning(
                self,
                "Missing Voice Name",
                "Please enter a name for this voice clone.",
            )
            return

        try:
            entry = self._voice_library.add_sample(
                name=voice_name,
                gender=self.gender_select.value,
                src_wav=self._sample_wav_path,
                sample_text=sample_text,
            )

            QMessageBox.information(
                self,
                "Saved",
                f"Voice clone saved:\n{entry.name}",
            )

        except Exception as error:
            logger.exception("Failed to save voice clone.")

            QMessageBox.critical(
                self,
                "Save Failed",
                str(error),
            )

    def _on_close_clicked(self):
        if self._thread and self._thread.isRunning():
            QMessageBox.warning(
                self,
                "Generating",
                "Voice is still generating. Please wait until it finishes.",
            )
            return

        self.close()

    def _cleanup_worker(self):
        self._worker = None
        self._thread = None

    def _set_generating_state(self, generating: bool):
        self.generate_btn.setEnabled(not generating)
        self.choose_sample_btn.setEnabled(not generating)
        self.save_voice_btn.setEnabled(
            False if generating else self._output_path is not None
        )
        self.close_btn.setEnabled(not generating)

        self.play_btn.setEnabled(
            False if generating else self._output_path is not None
        )
        self.save_test_btn.setEnabled(
            False if generating else self._output_path is not None
        )

        if generating:
            self.generate_btn.setText("Generating...")
            self.progress_bar.show()
            self.progress_bar.setValue(0)
        else:
            self.generate_btn.setText("Generate Test")

    def get_text(self) -> str:
        return self.text_edit.toPlainText().strip()

    def get_sample_text(self) -> str:
        return self.transcript_edit.toPlainText().strip()

    def get_speed_percent(self) -> int:
        return self.speed_spin.value()

    def get_result(self) -> Optional[VoxCPMResult]:
        return self._result

    def _make_select(
        self,
        labels: list[str],
        current: str,
        width: int = 320,
        height: int = 34,
        on_change=None,
    ) -> AppSelect:
        sel = AppSelect(
            items=labels,
            value=current,
            width=width,
            height=height,
            on_change=on_change,
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