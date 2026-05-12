from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget

from utils.font_manager import get_google_sans


class AppTopBar(QWidget):
    def __init__(self):
        super().__init__()

        self.setFixedHeight(64)
        self.setObjectName("topBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)

        title = QLabel("FreeCut AI")
        title.setFont(get_google_sans(size=16, weight="Bold"))

        status = QLabel("AI Dubbing Studio")
        status.setFont(get_google_sans(size=10, weight="Regular"))
        status.setObjectName("mutedText")
        status.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(status)