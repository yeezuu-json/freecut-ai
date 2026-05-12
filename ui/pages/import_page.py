from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QLabel, QVBoxLayout, QWidget

from ui.components.app_button import AppButton
from ui.components.page_header import PageHeader
from utils.font_manager import get_google_sans


class ImportPage(QWidget):
    def __init__(self, router):
        super().__init__()

        self.router = router
        self.selected_video_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        header = PageHeader(
            title="Import Video",
            description="Choose a video file to start the dubbing workflow.",
        )

        self.video_label = QLabel("No video selected")
        self.video_label.setObjectName("card")
        self.video_label.setFont(get_google_sans(size=12, weight="Regular"))

        choose_button = AppButton(
            text="Choose Video",
            variant="primary",
            button_size="md",
            on_click=self.choose_video,
        )

        continue_button = AppButton(
            text="Continue to Editor",
            variant="success",
            button_size="md",
            on_click=self.continue_to_editor,
        )

        layout.addWidget(header)
        layout.addWidget(self.video_label)
        layout.addWidget(choose_button)
        layout.addWidget(continue_button)
        layout.addStretch()

    def choose_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Video",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi)",
        )

        if not file_path:
            return

        self.selected_video_path = Path(file_path)
        self.video_label.setText(f"Selected video:\n{self.selected_video_path}")

    def continue_to_editor(self):
        self.router.go_to("editor")