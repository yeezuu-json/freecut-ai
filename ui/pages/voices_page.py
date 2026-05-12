from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from ui.components.app_button import AppButton
from ui.components.page_header import PageHeader
from utils.font_manager import get_google_sans


class VoicesPage(QWidget):
    def __init__(self, router):
        super().__init__()

        self.router = router

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        header = PageHeader(
            title="Voices",
            description="Assign male and female Khmer voices for each speaker.",
        )

        voice_panels = QHBoxLayout()
        voice_panels.setSpacing(16)

        male_panel = QLabel("Male Voice\n\nDefault Khmer Male\nPreview voice\nAssign to selected segments")
        male_panel.setObjectName("largePanel")
        male_panel.setFont(get_google_sans(size=12, weight="Regular"))

        female_panel = QLabel("Female Voice\n\nDefault Khmer Female\nPreview voice\nAssign to selected segments")
        female_panel.setObjectName("largePanel")
        female_panel.setFont(get_google_sans(size=12, weight="Regular"))

        voice_panels.addWidget(male_panel)
        voice_panels.addWidget(female_panel)

        actions = QHBoxLayout()

        back_button = AppButton(
            text="Back to Editor",
            variant="secondary",
            button_size="md",
            on_click=lambda: self.router.go_to("editor"),
        )

        export_button = AppButton(
            text="Continue to Export",
            variant="success",
            button_size="md",
            on_click=lambda: self.router.go_to("export"),
        )

        actions.addWidget(back_button)
        actions.addStretch()
        actions.addWidget(export_button)

        layout.addWidget(header)
        layout.addLayout(voice_panels, 1)
        layout.addLayout(actions)