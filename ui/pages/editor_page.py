from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from ui.components.app_button import AppButton
from ui.components.page_header import PageHeader
from utils.font_manager import get_google_sans


class EditorPage(QWidget):
    def __init__(self, router):
        super().__init__()

        self.router = router

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        header = PageHeader(
            title="Editor",
            description="Preview video, manage transcript segments, and assign voices.",
        )

        body = QHBoxLayout()
        body.setSpacing(16)

        preview_panel = QLabel("Video Preview")
        preview_panel.setObjectName("largePanel")
        preview_panel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_panel.setFont(get_google_sans(size=14, weight="Medium"))

        segments_panel = QLabel(
            "Segments List\n\n"
            "00:00 - 00:04  Speaker: Unknown\n"
            "Original: ...\n"
            "Khmer: ...\n\n"
            "00:04 - 00:08  Speaker: Unknown\n"
            "Original: ...\n"
            "Khmer: ..."
        )
        segments_panel.setObjectName("largePanel")
        segments_panel.setAlignment(Qt.AlignmentFlag.AlignTop)
        segments_panel.setFont(get_google_sans(size=11, weight="Regular"))

        body.addWidget(preview_panel, 2)
        body.addWidget(segments_panel, 1)

        actions = QHBoxLayout()

        transcribe_button = AppButton(
            text="Transcribe",
            variant="primary",
            button_size="md",
            on_click=self.transcribe,
        )

        translate_button = AppButton(
            text="Translate to Khmer",
            variant="secondary",
            button_size="md",
            on_click=self.translate,
        )

        next_button = AppButton(
            text="Choose Voices",
            variant="success",
            button_size="md",
            on_click=self.open_voices,
        )

        actions.addWidget(transcribe_button)
        actions.addWidget(translate_button)
        actions.addStretch()
        actions.addWidget(next_button)

        layout.addWidget(header)
        layout.addLayout(body, 1)
        layout.addLayout(actions)

    def transcribe(self):
        print("Transcribe clicked")

    def translate(self):
        print("Translate clicked")

    def open_voices(self):
        self.router.go_to("voices")