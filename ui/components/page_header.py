from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from utils.font_manager import get_google_sans


class PageHeader(QWidget):
    def __init__(self, title: str, description: str = ""):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 20)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setFont(get_google_sans(size=24, weight="Bold"))
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        description_label = QLabel(description)
        description_label.setFont(get_google_sans(size=11, weight="Regular"))
        description_label.setObjectName("mutedText")

        layout.addWidget(title_label)

        if description:
            layout.addWidget(description_label)