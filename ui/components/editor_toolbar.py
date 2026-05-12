from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from ui.components.app_button import AppButton
from utils.font_manager import get_google_sans
from ui.components.icons import app_icon

class EditorToolbar(QWidget):
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

        buttons = [
            {
                "text": "Load Video",
                "icon": app_icon("folder-open", "fa6s.folder-open", color="#ffffff"),
                "variant": "primary",
            },
            {
                "text": "Import SRT",
                "icon": app_icon("file-import", "fa6s.file-import", color="#ffffff"),
                "variant": "purple",
            },
            {
                "text": "Auto Transcribe",
                "icon": app_icon("microphone", "fa6s.microphone", color="#ffffff"),
                "variant": "danger",
            },
            {
                "text": "Export SRT",
                "icon": app_icon("file-export", "fa6s.file-export", color="#ffffff"),
                "variant": "teal",
            },
            {
                "text": "Video → MP3",
                "icon": app_icon("music", "fa6s.music", color="#ffffff"),
                "variant": "purple",
            },
            {
                "text": "Detect Gender",
                "icon": app_icon("gender-bigender", "fa6s.venus-mars", color="#ffffff"),
                "variant": "primary",
            },
            {
                "text": "Translate SRT",
                "icon": app_icon("language", "fa6s.language", color="#ffffff"),
                "variant": "warning",
            },
            {
                "text": "Settings",
                "icon": app_icon("settings", "fa6s.gear", color="#ffffff"),
                "variant": "dark",
            },
            {
                "text": "Update",
                "icon": app_icon("upload", "fa6s.upload", color="#ffffff"),
                "variant": "teal",
            },
        ]

        for item in buttons:
            button_row.addWidget(
                AppButton(
                    text=item["text"],
                    icon=item["icon"],
                    variant=item["variant"],
                    button_size="sm",
                )
            )

        button_row.addStretch()

        root.addWidget(title)
        root.addLayout(button_row)