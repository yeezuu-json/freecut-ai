from typing import Callable, Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QPushButton, QMenu, QSizePolicy

from ui.components.icons import app_icon
from utils.font_manager import get_google_sans


class AppSelect(QPushButton):
    def __init__(
        self,
        items: list[str],
        value: Optional[str] = None,
        width: int = 220,
        on_change: Optional[Callable[[str], None]] = None,
    ):
        super().__init__()

        self.items = items
        self.value = value or items[0]
        self.on_change = on_change

        self.setObjectName("appSelect")
        self.setFixedWidth(width)
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(get_google_sans(size=10, weight="Medium"))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.setIcon(
            app_icon(
                "chevron-down",
                fallback="fa6s.chevron-down",
                color="#374151",
                size=14,
            )
        )
        self.setIconSize(QSize(14, 14))
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.menu = QMenu(self)
        self.menu.setObjectName("appSelectMenu")
        self.menu.setFont(get_google_sans(size=10, weight="Medium"))

        self.clicked.connect(self.show_menu)

        self.rebuild_menu()
        self.update_text()

    def update_text(self):
        self.setText(self.value)

    def rebuild_menu(self):
        self.menu.clear()

        for item in self.items:
            action = QAction(item, self)
            action.setCheckable(True)
            action.setChecked(item == self.value)
            action.triggered.connect(lambda checked=False, value=item: self.set_value(value))
            self.menu.addAction(action)

    def set_value(self, value: str):
        self.value = value
        self.update_text()
        self.rebuild_menu()

        if self.on_change:
            self.on_change(value)

    def show_menu(self):
        self.menu.setMinimumWidth(self.width())
        self.menu.exec(self.mapToGlobal(self.rect().bottomLeft()))