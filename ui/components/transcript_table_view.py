from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from models.subtitle_segment import SubtitleSegment
from utils.font_manager import get_google_sans


class TranscriptTableView(QTableWidget):
    segments_edited = Signal(list)

    _COL_START   = 0
    _COL_END     = 1
    _COL_TEXT    = 2   # editable original / translated text
    _COL_PITCH   = 3
    _COL_SPEED   = 4
    _COL_VOL     = 5
    _COL_VOICE   = 6
    _COL_PLAY    = 7
    _COL_AUDIO   = 8
    _COL_DL      = 9
    _COL_ECC     = 10

    def __init__(self):
        super().__init__()

        self._segments: list[SubtitleSegment] = []
        self._updating = False          # guard against recursive cellChanged

        self.setObjectName("subtitleTable")
        self.setColumnCount(11)
        self.setRowCount(0)

        self.setHorizontalHeaderLabels([
            "Start", "End", "Editable Text",
            "Pitch", "Speed", "Vol(dB)",
            "Voice", "Play/Stop", "Audio", "Download", "ECC",
        ])

        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.horizontalHeader().setStretchLastSection(True)

        self.setColumnWidth(self._COL_START,  110)
        self.setColumnWidth(self._COL_END,    110)
        self.setColumnWidth(self._COL_TEXT,   380)
        self.setColumnWidth(self._COL_PITCH,   60)
        self.setColumnWidth(self._COL_SPEED,   60)
        self.setColumnWidth(self._COL_VOL,     70)
        self.setColumnWidth(self._COL_VOICE,  120)
        self.setColumnWidth(self._COL_PLAY,    90)
        self.setColumnWidth(self._COL_AUDIO,   80)
        self.setColumnWidth(self._COL_DL,      90)
        self.setColumnWidth(self._COL_ECC,     60)

        self.setFont(get_google_sans(size=10))
        self.setWordWrap(True)
        self.setAlternatingRowColors(True)

        self.cellChanged.connect(self._on_cell_changed)

    # ── public API ───────────────────────────────────────────────────────────

    def set_segments(self, segments: list[SubtitleSegment]) -> None:
        self._updating = True
        try:
            self._segments = list(segments)
            self.clearContents()
            self.setRowCount(len(segments))

            for row, seg in enumerate(segments):
                self.setRowHeight(row, 58)

                self._set_cell(row, self._COL_START, seg.start_time,  editable=False)
                self._set_cell(row, self._COL_END,   seg.end_time,    editable=False)

                # Show transcribed text; if translation exists, show that instead.
                display = seg.khmer_text.strip() or seg.original_text.strip()
                self._set_cell(row, self._COL_TEXT, display, editable=True)

                self._set_cell(row, self._COL_PITCH, seg.pitch,  editable=True)
                self._set_cell(row, self._COL_SPEED, seg.speed,  editable=True)
                self._set_cell(row, self._COL_VOL,   seg.volume, editable=True)
                self._set_cell(row, self._COL_VOICE, seg.voice,  editable=True)
                self._set_cell(row, self._COL_PLAY,  "-",        editable=False)
                self._set_cell(row, self._COL_AUDIO, "-",        editable=False)
                self._set_cell(row, self._COL_DL,    "-",        editable=False)
                self._set_cell(row, self._COL_ECC,   "-",        editable=False)

            self.resizeRowsToContents()
            self.viewport().update()
        finally:
            self._updating = False

    # ── private helpers ──────────────────────────────────────────────────────

    def _set_cell(self, row: int, col: int, value: str, *, editable: bool) -> None:
        item = QTableWidgetItem(value or "")
        item.setForeground(QColor("#111827"))
        item.setBackground(QColor("#ffffff"))
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, col, item)

    def _on_cell_changed(self, row: int, col: int) -> None:
        if self._updating:
            return
        if row >= len(self._segments):
            return

        item = self.item(row, col)
        if item is None:
            return
        value = item.text()
        seg = self._segments[row]

        if col == self._COL_TEXT:
            # Write back to whichever text field is active.
            if seg.khmer_text.strip():
                seg.khmer_text = value
            else:
                seg.original_text = value
        elif col == self._COL_PITCH:
            seg.pitch = value
        elif col == self._COL_SPEED:
            seg.speed = value
        elif col == self._COL_VOL:
            seg.volume = value
        elif col == self._COL_VOICE:
            seg.voice = value

        self.segments_edited.emit(list(self._segments))
