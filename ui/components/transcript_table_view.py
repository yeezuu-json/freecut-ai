from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from models.subtitle_segment import SubtitleSegment
from utils.font_manager import get_google_sans

class TranscriptTableView(QTableWidget):
    segments_edited = Signal(list[SubtitleSegment])

    def __init__(self):
        super().__init__()

        self.setObjectName("subtitleTable")

        self.setColumnCount(11)
        self.setRowCount(0)

        self.setHorizontalHeaderLabels([
            "Start",
            "End",
            "Editable Text",
            "Pitch",
            "Speed",
            "Vol(dB)",
            "Voice",
            "Play/Stop",
            "Audio",
            "Download",
            "ECC",
        ])

        self.verticalHeader().setVisible(False)

        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)

        self.setColumnWidth(0, 110)
        self.setColumnWidth(1, 110)
        self.setColumnWidth(2, 350)
        self.setColumnWidth(3, 60)
        self.setColumnWidth(4, 60)
        self.setColumnWidth(5, 70)
        self.setColumnWidth(6, 120)
        self.setColumnWidth(7, 90)
        self.setColumnWidth(8, 80)
        self.setColumnWidth(9, 90)
        self.setColumnWidth(10, 60)

        self.setFont(get_google_sans(size=10))
        self.setWordWrap(True)
        self.setAlternatingRowColors(True)

    def set_segments(self, segments: list[SubtitleSegment]):
        self.clearContents()
        self.setRowCount(len(segments))

        for row, segment in enumerate(segments):
            self.setRowHeight(row, 58)

            self.set_cell(row, 0, segment.start_time, editable=False)
            self.set_cell(row, 1, segment.end_time, editable=False)
            self.set_cell(row, 2, segment.khmer_text, editable=True)

            self.set_cell(row, 3, "0", editable=True)
            self.set_cell(row, 4, "1.0", editable=True)
            self.set_cell(row, 5, "0", editable=True)
            self.set_cell(row, 6, "Default", editable=True)
            self.set_cell(row, 7, "-", editable=False)
            self.set_cell(row, 8, "-", editable=False)
            self.set_cell(row, 9, "-", editable=False)
            self.set_cell(row, 10, "-", editable=False)

        self.resizeRowsToContents()
        self.viewport().update()

    def set_cell(self, row: int, column: int, value: str, editable: bool = False):
        item = QTableWidgetItem(value)

        item.setForeground(QColor("#111827"))
        item.setBackground(QColor("#ffffff"))
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.setItem(row, column, item)