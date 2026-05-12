from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from ui.components.app_button import AppButton


class SettingsPage(QWidget):
    def __init__(self, router):
        super().__init__()

        self.router = router

        layout = QVBoxLayout(self)

        title = QLabel("Settings Page")

        back_button = AppButton(
            text="Back Home",
            variant="secondary",
            button_size="md",
            on_click=self.go_home,
        )

        layout.addWidget(title)
        layout.addWidget(back_button)

    def go_home(self):
        self.router.go_to("home")