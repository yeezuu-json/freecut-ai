from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from ui.components.app_button import AppButton
from ui.components.page_header import PageHeader
from utils.font_manager import get_google_sans


class ExportPage(QWidget):
    def __init__(self, router):
        super().__init__()

        self.router = router

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        header = PageHeader(
            title="Export",
            description="Generate the final dubbed video and subtitle files.",
        )

        summary = QLabel(
            "Export Settings\n\n"
            "Output: MP4 Video\n"
            "Audio: Khmer Dubbed Voice\n"
            "Subtitles: Khmer SRT\n"
            "Quality: High"
        )
        summary.setObjectName("card")
        summary.setFont(get_google_sans(size=12, weight="Regular"))

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        export_button = AppButton(
            text="Export Video",
            variant="primary",
            button_size="lg",
            on_click=self.export_video,
        )

        layout.addWidget(header)
        layout.addWidget(summary)
        layout.addWidget(self.progress_bar)
        layout.addWidget(export_button)
        layout.addStretch()

    def export_video(self):
        self.progress_bar.setValue(20)
        print("Export video clicked")