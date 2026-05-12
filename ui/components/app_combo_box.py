from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QListView

from utils.font_manager import get_google_sans


class AppComboBox(QComboBox):
    def __init__(self, items: list[str] | None = None, width: int | None = None):
        super().__init__()

        self.setObjectName("cleanSelect")
        self.setFont(get_google_sans(size=10, weight="Medium"))

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMaxVisibleItems(8)

        if width is not None:
            self.setFixedWidth(width)

        view = QListView()
        view.setObjectName("cleanSelectPopup")
        view.setFont(get_google_sans(size=10, weight="Medium"))
        view.setMouseTracking(True)
        view.setSpacing(2)

        self.setView(view)

        if items:
            self.addItems(items)