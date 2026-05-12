from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from ui.components.app_button import AppButton
from ui.components.icons import app_icon
from utils.font_manager import get_google_sans


class EditorToolbar(QWidget):
    load_video_requested = Signal()

    def __init__(self):
        super().__init__()

        self.setObjectName("toolbar")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        title = QLabel("FreeCut AI - AI Dubbing Studio")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("mainTitle")
        title.setFont(get_google_sans(size=16, weight="Bold"))

        button_row = QHBoxLayout()
        button_row.setSpacing(8)

        load_video_button = AppButton(
            text="Load Video",
            icon=app_icon("folder-open", "fa6s.folder-open", color="#ffffff"),
            variant="primary",
            button_size="sm",
            on_click=self.load_video_requested.emit,
        )

        import_srt_button = AppButton(
            text="Import SRT",
            icon=app_icon("file-import", "fa6s.file-import", color="#ffffff"),
            variant="purple",
            button_size="sm",
        )

        auto_transcribe_button = AppButton(
            text="Auto Transcribe",
            icon=app_icon("microphone", "fa6s.microphone", color="#ffffff"),
            variant="danger",
            button_size="sm",
        )

        export_srt_button = AppButton(
            text="Export SRT",
            icon=app_icon("file-export", "fa6s.file-export", color="#ffffff"),
            variant="teal",
            button_size="sm",
        )

        video_mp3_button = AppButton(
            text="Video → MP3",
            icon=app_icon("music", "fa6s.music", color="#ffffff"),
            variant="purple",
            button_size="sm",
        )

        detect_gender_button = AppButton(
            text="Detect Gender",
            icon=app_icon("gender-bigender", "fa6s.venus-mars", color="#ffffff"),
            variant="primary",
            button_size="sm",
        )

        translate_button = AppButton(
            text="Translate SRT",
            icon=app_icon("language", "fa6s.language", color="#ffffff"),
            variant="warning",
            button_size="sm",
        )

        settings_button = AppButton(
            text="Settings",
            icon=app_icon("settings", "fa6s.gear", color="#ffffff"),
            variant="dark",
            button_size="sm",
        )

        update_button = AppButton(
            text="Update",
            icon=app_icon("upload", "fa6s.upload", color="#ffffff"),
            variant="teal",
            button_size="sm",
        )

        button_row.addWidget(load_video_button)
        button_row.addWidget(import_srt_button)
        button_row.addWidget(auto_transcribe_button)
        button_row.addWidget(export_srt_button)
        button_row.addWidget(video_mp3_button)
        button_row.addWidget(detect_gender_button)
        button_row.addWidget(translate_button)
        button_row.addWidget(settings_button)
        button_row.addWidget(update_button)
        button_row.addStretch()

        root.addWidget(title)
        root.addLayout(button_row)