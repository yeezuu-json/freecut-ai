from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui.components.app_button import AppButton
from ui.components.page_header import PageHeader
from utils.font_manager import get_google_sans


class HomePage(QWidget):
    def __init__(self, router):
        super().__init__()

        self.router = router

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        header = PageHeader(
            title="Welcome to FreeCut AI",
            description="Create Khmer dubbed videos from Chinese clips with AI-assisted workflow.",
        )

        card = QLabel(
            "Workflow:\n\n"
            "1. Import your video\n"
            "2. Extract and transcribe audio\n"
            "3. Translate to Khmer\n"
            "4. Choose male/female voices\n"
            "5. Export dubbed video"
        )
        card.setObjectName("card")
        card.setFont(get_google_sans(size=12, weight="Regular"))
        card.setAlignment(Qt.AlignmentFlag.AlignTop)

        start_button = AppButton(
            text="Start New Project",
            variant="primary",
            button_size="lg",
            on_click=self.open_import,
        )

        layout.addWidget(header)
        layout.addWidget(card)
        layout.addWidget(start_button)
        layout.addStretch()

    def open_import(self):
        self.router.go_to("import")