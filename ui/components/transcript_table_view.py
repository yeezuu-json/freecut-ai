from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from utils.font_manager import get_google_sans


class TranscriptTableView(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("transcriptTableView")
        self.setColumnCount(11)
        self.setRowCount(0)

        self.setHorizontalHeaderLabels([
            "Start",
            "End",
            "Text (Editable)",
            "Pitch",
            "Speed",
            "Vol(dB)",
            "Voice",
            "Play/Stop",
            "Audio",
            "Download",
            "ECC",
        ])

        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setVisible(False)

        self.setColumnWidth(0, 70)
        self.setColumnWidth(1, 70)
        self.setColumnWidth(2, 260)
        self.setColumnWidth(3, 60)
        self.setColumnWidth(4, 60)
        self.setColumnWidth(5, 70)
        self.setColumnWidth(6, 90)
        self.setColumnWidth(7, 90)
        self.setColumnWidth(8, 80)
        self.setColumnWidth(9, 90)
        self.setColumnWidth(10, 60)

        self.setFont(get_google_sans(size=10))