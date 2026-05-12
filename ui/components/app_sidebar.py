from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from utils.font_manager import get_google_sans


class SidebarButton(QPushButton):
    def __init__(self, text: str, route: str, on_click: Callable[[str], None]):
        super().__init__(text)

        self.route = route
        self.on_click = on_click

        self.setFixedHeight(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(get_google_sans(size=11, weight="Medium"))
        self.setObjectName("sidebarButton")

        self.clicked.connect(self.handle_click)

    def handle_click(self):
        self.on_click(self.route)


class AppSidebar(QWidget):
    def __init__(self, on_navigate: Callable[[str], None]):
        super().__init__()

        self.on_navigate = on_navigate
        self.buttons: dict[str, SidebarButton] = {}

        self.setFixedWidth(240)
        self.setObjectName("sidebar")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(8)

        brand = QLabel("FreeCut AI")
        brand.setFont(get_google_sans(size=20, weight="Bold"))
        brand.setObjectName("sidebarBrand")

        subtitle = QLabel("Dubbing Studio")
        subtitle.setFont(get_google_sans(size=10, weight="Regular"))
        subtitle.setObjectName("sidebarSubtitle")

        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addSpacing(24)

        self.add_nav_button(layout, "Home", "home")
        self.add_nav_button(layout, "Import Video", "import")
        self.add_nav_button(layout, "Editor", "editor")
        self.add_nav_button(layout, "Voices", "voices")
        self.add_nav_button(layout, "Export", "export")

        layout.addStretch()

        version = QLabel("v1.0.0")
        version.setObjectName("sidebarVersion")
        version.setFont(get_google_sans(size=9, weight="Regular"))

        layout.addWidget(version)

    def add_nav_button(self, layout: QVBoxLayout, text: str, route: str):
        button = SidebarButton(text, route, self.on_navigate)
        self.buttons[route] = button
        layout.addWidget(button)

    def set_active(self, route: str):
        for button_route, button in self.buttons.items():
            button.setProperty("active", button_route == route)
            button.style().unpolish(button)
            button.style().polish(button)