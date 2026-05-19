from typing import Callable, Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QPushButton, QMenu, QSizePolicy

from ui.components.icons import app_icon
from utils.font_manager import get_google_sans


class AppSelect(QPushButton):
    def __init__(
        self,
        items: list,           # list[str] OR list[tuple[str, str]] = (label, value)
        value: Optional[str] = None,
        width: int = 220,
        height: int = 38,
        on_change: Optional[Callable[[str], None]] = None,
    ):
        super().__init__()

        # Normalise to (label, value) pairs.
        self._pairs: list[tuple[str, str]] = [
            (item if isinstance(item, str) else item[0],
             item if isinstance(item, str) else item[1])
            for item in items
        ]
        self.items = [p[1] for p in self._pairs]   # values list (backward-compat)
        self.value = value or self.items[0]
        self.on_change = on_change

        self.setObjectName("appSelect")
        self.setFixedWidth(width)
        self.setFixedHeight(height)
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

    def _label_for(self, value: str) -> str:
        """Return the display label for a given value."""
        for label, val in self._pairs:
            if val == value:
                return label
        return value

    def update_text(self):
        self.setText(self._label_for(self.value))

    def rebuild_menu(self):
        self.menu.clear()

        for label, value in self._pairs:
            action = QAction(label, self)
            action.setCheckable(True)
            action.setChecked(value == self.value)
            action.triggered.connect(lambda checked=False, v=value: self.set_value(v))
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