"""Gender Assignment Dialog.

Shows a mini NLE-style timeline (vocals track + segment clips) and a table where
the user can preview each segment and assign Male / Female before TTS.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPen,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from models.subtitle_segment import SubtitleSegment
from utils.font_manager import get_google_sans


# ── voice mapping ────────────────────────────────────────────────────────────

VOICE_FOR_GENDER: dict[str, str] = {
    "male":    "Piseth (Male)",
    "female":  "Sreymom (Female)",
    "unknown": "Default",
}

GENDER_COLORS: dict[str, str] = {
    "male":    "#3b82f6",   # blue
    "female":  "#ec4899",   # pink
    "unknown": "#6b7280",   # grey
}


def _srt_to_ms(t: str) -> int:
    try:
        h, m, rest = t.split(":")
        s, ms = rest.replace(".", ",").split(",")
        return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1_000 + int(ms)
    except Exception:
        return 0


# ── mini-timeline widget ─────────────────────────────────────────────────────

class _MiniTimeline(QWidget):
    """Paints a ruler, a vocals bar, and per-segment clip blocks.

    Emits ``segment_clicked(index)`` when the user clicks a clip.
    """

    segment_clicked = Signal(int)

    PPS       = 50           # pixels per second (zoom)
    RULER_H   = 22
    TRACK_H   = 34
    LABEL_W   = 90
    PADDING   = 8

    _BG       = QColor("#1a1d2e")
    _LABEL_BG = QColor("#141624")
    _RULER_BG = QColor("#12131f")
    _RULER_FG = QColor("#8892a4")
    _VOCALS_GRAD_TOP    = QColor("#3b5998")
    _VOCALS_GRAD_BOTTOM = QColor("#1e3a6e")
    _PLAYHEAD = QColor("#ef4444")

    def __init__(
        self,
        segments: list[SubtitleSegment],
        duration_ms: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._segments  = segments
        self._duration_ms = duration_ms
        self._selected  = -1
        self._playhead_ms = -1

        total_w = self.LABEL_W + max(
            int(duration_ms / 1000 * self.PPS) + self.PADDING * 2, 400
        )
        total_h = self.RULER_H + self.TRACK_H * 2
        self.setMinimumSize(total_w, total_h)
        self.setFixedHeight(total_h)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ── public ───────────────────────────────────────────────────────────────

    def set_selected(self, idx: int) -> None:
        self._selected = idx
        self.update()

    def set_playhead(self, ms: int) -> None:
        self._playhead_ms = ms
        self.update()

    # ── paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = self.width()
        lane_top   = self.RULER_H
        clips_top  = lane_top + self.TRACK_H
        label_w    = self.LABEL_W
        content_x  = label_w
        content_w  = W - label_w

        # ── background ────────────────────────────────────────────────────
        p.fillRect(0, 0, W, self.height(), self._BG)
        p.fillRect(0, 0, label_w, self.height(), self._LABEL_BG)

        # ── ruler ─────────────────────────────────────────────────────────
        p.fillRect(0, 0, W, self.RULER_H, self._RULER_BG)
        p.setPen(QPen(self._RULER_FG, 1))
        p.setFont(QFont("Helvetica", 8))

        step_s = self._ruler_step()
        t = 0.0
        while t <= self._duration_ms / 1000 + step_s:
            x = content_x + int(t * self.PPS)
            if x > W:
                break
            p.drawLine(x, self.RULER_H - 6, x, self.RULER_H)
            if t == int(t):
                mins, secs = divmod(int(t), 60)
                label = f"{mins:02d}:{secs:02d}"
                p.drawText(x + 2, 0, 50, self.RULER_H - 2, Qt.AlignmentFlag.AlignVCenter, label)
            t += step_s

        # ── vocals track ──────────────────────────────────────────────────
        self._draw_track_label(p, lane_top, "Vocals", "#3b82f6")
        lane_rect_x = content_x + self.PADDING
        lane_rect_w = content_w - self.PADDING * 2
        grad = QLinearGradient(0, lane_top + 4, 0, lane_top + self.TRACK_H - 4)
        grad.setColorAt(0, self._VOCALS_GRAD_TOP)
        grad.setColorAt(1, self._VOCALS_GRAD_BOTTOM)
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(lane_rect_x, lane_top + 4, lane_rect_w, self.TRACK_H - 8, 3, 3)
        self._draw_fake_waveform(p, lane_rect_x, lane_top + 4, lane_rect_w, self.TRACK_H - 8)

        # ── clips track ───────────────────────────────────────────────────
        self._draw_track_label(p, clips_top, "Clips", "#8b5cf6")
        p.fillRect(content_x, clips_top, content_w, self.TRACK_H, QColor("#0d0f1a"))

        for i, seg in enumerate(self._segments):
            start_ms = _srt_to_ms(seg.start_time)
            end_ms   = _srt_to_ms(seg.end_time)
            x  = content_x + self.PADDING + int(start_ms / 1000 * self.PPS)
            x2 = content_x + self.PADDING + int(end_ms   / 1000 * self.PPS)
            w  = max(x2 - x, 4)

            gender  = getattr(seg, "gender", "unknown") or "unknown"
            color   = QColor(GENDER_COLORS.get(gender, "#6b7280"))
            selected = (i == self._selected)

            cy = clips_top + 5
            ch = self.TRACK_H - 10

            if selected:
                p.setPen(QPen(QColor("#ffffff"), 1.5))
                brighter = color.lighter(150)
                p.setBrush(brighter)
            else:
                p.setPen(QPen(color.darker(130), 1))
                p.setBrush(color.darker(160))
            p.drawRoundedRect(x, cy, w, ch, 3, 3)

            # Index label
            if w > 14:
                p.setPen(QColor("#ffffff") if selected else QColor("#c0c8d4"))
                p.setFont(QFont("Helvetica", 7))
                p.drawText(x + 3, cy, w - 4, ch, Qt.AlignmentFlag.AlignVCenter, str(i + 1))

        # ── playhead ──────────────────────────────────────────────────────
        if self._playhead_ms >= 0:
            ph_x = content_x + self.PADDING + int(self._playhead_ms / 1000 * self.PPS)
            p.setPen(QPen(self._PLAYHEAD, 2))
            p.drawLine(ph_x, 0, ph_x, self.height())

        p.end()

    # ── mouse ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:  # noqa: N802
        mx = event.position().x()
        for i, seg in enumerate(self._segments):
            start_ms = _srt_to_ms(seg.start_time)
            end_ms   = _srt_to_ms(seg.end_time)
            x  = self.LABEL_W + self.PADDING + int(start_ms / 1000 * self.PPS)
            x2 = self.LABEL_W + self.PADDING + int(end_ms   / 1000 * self.PPS)
            clips_top = self.RULER_H + self.TRACK_H
            cy = clips_top + 5
            ch = self.TRACK_H - 10
            if x <= mx <= max(x2, x + 4) and cy <= event.position().y() <= cy + ch:
                self.segment_clicked.emit(i)
                return

    # ── helpers ───────────────────────────────────────────────────────────────

    def _draw_track_label(self, p: QPainter, y: int, name: str, accent: str) -> None:
        p.fillRect(0, y, self.LABEL_W, self.TRACK_H, self._LABEL_BG)
        p.setPen(QColor(accent))
        p.setFont(QFont("Helvetica", 8))
        p.drawText(8, y, self.LABEL_W - 10, self.TRACK_H, Qt.AlignmentFlag.AlignVCenter, name)

    @staticmethod
    def _draw_fake_waveform(p: QPainter, rx: int, ry: int, rw: int, rh: int) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 40))
        bar_w, gap = 2, 2
        seed = 0xDEADBEEF
        cx = rx + 4
        cy = ry + rh // 2
        mh = rh // 2 - 2
        while cx + bar_w <= rx + rw - 4:
            seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF
            h = max(2, int((seed & 0xFF) / 255 * mh))
            p.drawRoundedRect(cx, cy - h, bar_w, h * 2, 1, 1)
            cx += bar_w + gap

    def _ruler_step(self) -> float:
        total_s = self._duration_ms / 1000
        for step in (1, 2, 5, 10, 30, 60, 120, 300):
            if total_s / step < 40:
                return float(step)
        return 60.0


# ── main dialog ──────────────────────────────────────────────────────────────

class GenderAssignDialog(QDialog):
    """Assign Male / Female to each subtitle segment before TTS generation."""

    _COL_IDX    = 0
    _COL_START  = 1
    _COL_END    = 2
    _COL_TEXT   = 3
    _COL_GENDER = 4
    _COL_PLAY   = 5

    def __init__(
        self,
        segments: list[SubtitleSegment],
        vocals_path: str | None,
        duration_ms: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._segments    = [self._copy_seg(s) for s in segments]
        self._vocals_path = vocals_path
        self._duration_ms = duration_ms
        self._current_preview: int = -1   # index of segment being previewed

        # Audio player for segment preview.
        self._audio_out = QAudioOutput(self)
        self._player    = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_out)
        self._audio_out.setVolume(1.0)
        self._preview_end_ms = 0
        self._player.positionChanged.connect(self._on_player_position)
        self._player.playbackStateChanged.connect(self._on_playback_changed)

        if vocals_path:
            self._player.setSource(QUrl.fromLocalFile(vocals_path))

        self._setup_ui()

    # ── public ───────────────────────────────────────────────────────────────

    def get_segments(self) -> list[SubtitleSegment]:
        return self._segments

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setWindowTitle("Gender Assignment")
        self.setModal(True)
        self.resize(1100, 620)
        self.setStyleSheet("""
            QDialog { background: #1a1d2e; color: #c4c9d1; }
            QLabel  { color: #c4c9d1; }
            QTableWidget { background: #12131f; color: #c4c9d1;
                           gridline-color: #252840; border: none; }
            QHeaderView::section { background: #1e2235; color: #8892a4;
                                   padding: 4px; border: none;
                                   border-right: 1px solid #252840; }
            QTableWidget::item { padding: 4px; }
            QTableWidget::item:selected { background: #2a3050; }
            QScrollBar:horizontal, QScrollBar:vertical {
                background: #12131f; border: none; }
            QScrollBar::handle:horizontal, QScrollBar::handle:vertical {
                background: #2e3250; border-radius: 3px; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Title
        title = QLabel("Gender Assignment")
        title.setFont(get_google_sans(size=14, weight="Bold"))
        title.setStyleSheet("color: #e2e8f0;")
        root.addWidget(title)

        # Mini-timeline in a scroll area.
        self._timeline = _MiniTimeline(self._segments, self._duration_ms, self)
        self._timeline.segment_clicked.connect(self._on_timeline_click)

        scroll = QScrollArea()
        scroll.setWidget(self._timeline)
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(self._timeline.height() + 16)
        scroll.setStyleSheet("QScrollArea { background: #1a1d2e; border: 1px solid #252840; border-radius: 6px; }")
        root.addWidget(scroll)

        # Legend
        legend = QHBoxLayout()
        legend.setSpacing(16)
        for label, color in (("● Male", "#3b82f6"), ("● Female", "#ec4899"), ("● Unknown", "#6b7280")):
            lbl = QLabel(label)
            lbl.setFont(get_google_sans(size=9))
            lbl.setStyleSheet(f"color: {color};")
            legend.addWidget(lbl)
        legend.addStretch()
        root.addLayout(legend)

        # Segment table.
        self._table = QTableWidget(len(self._segments), 6)
        self._table.setHorizontalHeaderLabels(["#", "Start", "End", "Text", "Gender", "Preview"])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setColumnWidth(self._COL_IDX,    36)
        self._table.setColumnWidth(self._COL_START,  90)
        self._table.setColumnWidth(self._COL_END,    90)
        self._table.setColumnWidth(self._COL_TEXT,   360)
        self._table.setColumnWidth(self._COL_GENDER, 140)
        self._table.setColumnWidth(self._COL_PLAY,   90)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setFont(get_google_sans(size=10))
        self._table.setAlternatingRowColors(True)

        for i, seg in enumerate(self._segments):
            self._table.setRowHeight(i, 38)
            self._fill_row(i, seg)

        root.addWidget(self._table, 1)

        # Bottom buttons.
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        assign_male_all = QPushButton("All Male")
        assign_male_all.clicked.connect(lambda: self._assign_all("male"))
        assign_male_all.setStyleSheet(self._btn_style("#3b82f6"))

        assign_female_all = QPushButton("All Female")
        assign_female_all.clicked.connect(lambda: self._assign_all("female"))
        assign_female_all.setStyleSheet(self._btn_style("#ec4899"))

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(self._btn_style("#374151"))

        apply_btn = QPushButton("Apply & Generate Voice")
        apply_btn.clicked.connect(self.accept)
        apply_btn.setStyleSheet(self._btn_style("#22c55e"))

        btn_row.addWidget(assign_male_all)
        btn_row.addWidget(assign_female_all)
        btn_row.addSpacing(20)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(apply_btn)
        root.addLayout(btn_row)

    def _fill_row(self, row: int, seg: SubtitleSegment) -> None:
        gender  = getattr(seg, "gender", "unknown") or "unknown"

        self._set_cell(row, self._COL_IDX,   str(seg.index))
        self._set_cell(row, self._COL_START,  seg.start_time)
        self._set_cell(row, self._COL_END,    seg.end_time)
        text = (seg.khmer_text or seg.original_text or "").strip()
        self._set_cell(row, self._COL_TEXT,   text)

        # Gender toggle buttons.
        gender_widget = QWidget()
        gender_widget.setStyleSheet("background: transparent;")
        gl = QHBoxLayout(gender_widget)
        gl.setContentsMargins(4, 2, 4, 2)
        gl.setSpacing(4)

        male_btn   = QPushButton("♂ Male")
        female_btn = QPushButton("♀ Female")

        male_btn.setCheckable(True)
        female_btn.setCheckable(True)
        male_btn.setChecked(gender == "male")
        female_btn.setChecked(gender == "female")

        male_btn.setStyleSheet(self._toggle_style("#3b82f6", checked=(gender == "male")))
        female_btn.setStyleSheet(self._toggle_style("#ec4899", checked=(gender == "female")))

        def _on_male(checked, r=row):
            self._assign_gender(r, "male" if checked else "unknown")

        def _on_female(checked, r=row):
            self._assign_gender(r, "female" if checked else "unknown")

        male_btn.clicked.connect(_on_male)
        female_btn.clicked.connect(_on_female)

        gl.addWidget(male_btn)
        gl.addWidget(female_btn)
        self._table.setCellWidget(row, self._COL_GENDER, gender_widget)

        # Play button.
        play_btn = QPushButton("▶ Play")
        play_btn.setStyleSheet(self._btn_style("#4b5563", height=26))
        play_btn.setFont(get_google_sans(size=9))
        play_btn.clicked.connect(lambda _=False, r=row: self._toggle_preview(r))
        self._table.setCellWidget(row, self._COL_PLAY, play_btn)

    def _set_cell(self, row: int, col: int, value: str) -> None:
        item = QTableWidgetItem(value)
        item.setForeground(QColor("#c4c9d1"))
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._table.setItem(row, col, item)

    # ── interactions ─────────────────────────────────────────────────────────

    def _on_timeline_click(self, idx: int) -> None:
        self._table.selectRow(idx)
        self._timeline.set_selected(idx)
        self._start_preview(idx)

    def _toggle_preview(self, idx: int) -> None:
        if self._current_preview == idx and \
                self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
            self._current_preview = -1
            self._update_play_btn(idx, playing=False)
        else:
            self._start_preview(idx)

    def _start_preview(self, idx: int) -> None:
        if not self._vocals_path:
            return

        seg = self._segments[idx]
        start_ms = _srt_to_ms(seg.start_time)
        end_ms   = _srt_to_ms(seg.end_time)
        self._preview_end_ms = end_ms

        # Stop previous preview.
        if self._current_preview >= 0 and self._current_preview != idx:
            self._update_play_btn(self._current_preview, playing=False)

        self._current_preview = idx
        self._timeline.set_selected(idx)
        self._table.selectRow(idx)

        # Scroll timeline to show this segment.
        seg_x = _MiniTimeline.LABEL_W + _MiniTimeline.PADDING + int(start_ms / 1000 * _MiniTimeline.PPS)
        scroll = self.findChild(QScrollArea)
        if scroll:
            scroll.horizontalScrollBar().setValue(max(0, seg_x - 100))

        self._player.setPosition(start_ms)
        self._player.play()
        self._update_play_btn(idx, playing=True)

    def _on_player_position(self, pos_ms: int) -> None:
        if self._current_preview >= 0:
            self._timeline.set_playhead(pos_ms)
            if pos_ms >= self._preview_end_ms:
                self._player.pause()
                self._update_play_btn(self._current_preview, playing=False)
                self._current_preview = -1

    def _on_playback_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        if state != QMediaPlayer.PlaybackState.PlayingState and self._current_preview >= 0:
            self._update_play_btn(self._current_preview, playing=False)

    def _update_play_btn(self, idx: int, *, playing: bool) -> None:
        w = self._table.cellWidget(idx, self._COL_PLAY)
        if w:
            btn = w if isinstance(w, QPushButton) else w.findChild(QPushButton)
            if btn:
                btn.setText("⏸ Stop" if playing else "▶ Play")
                btn.setStyleSheet(self._btn_style("#ef4444" if playing else "#4b5563", height=26))

    def _assign_gender(self, idx: int, gender: str) -> None:
        seg = self._segments[idx]
        seg.gender = gender
        seg.voice  = VOICE_FOR_GENDER.get(gender, "Default")

        # Refresh the gender buttons for this row.
        self._refresh_gender_buttons(idx)
        self._timeline.set_selected(idx)
        self._timeline.update()

    def _assign_all(self, gender: str) -> None:
        for i in range(len(self._segments)):
            self._assign_gender(i, gender)

    def _refresh_gender_buttons(self, idx: int) -> None:
        gender = self._segments[idx].gender or "unknown"
        w = self._table.cellWidget(idx, self._COL_GENDER)
        if not w:
            return
        buttons = w.findChildren(QPushButton)
        if len(buttons) >= 2:
            male_btn, female_btn = buttons[0], buttons[1]
            male_btn.setChecked(gender == "male")
            female_btn.setChecked(gender == "female")
            male_btn.setStyleSheet(self._toggle_style("#3b82f6",   checked=(gender == "male")))
            female_btn.setStyleSheet(self._toggle_style("#ec4899", checked=(gender == "female")))

    # ── closeEvent ────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._player.stop()
        super().closeEvent(event)

    def reject(self) -> None:
        self._player.stop()
        super().reject()

    # ── style helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _btn_style(color: str, height: int = 30) -> str:
        return (
            f"QPushButton {{ background: {color}; color: #fff; border: none; "
            f"border-radius: 4px; padding: 0 10px; min-height: {height}px; font-size: 10px; }}"
            f"QPushButton:hover {{ background: {color}dd; }}"
            f"QPushButton:pressed {{ background: {color}aa; }}"
        )

    @staticmethod
    def _toggle_style(color: str, *, checked: bool) -> str:
        bg   = color if checked else "#1e2235"
        text = "#ffffff" if checked else "#8892a4"
        border = color if checked else "#374151"
        return (
            f"QPushButton {{ background: {bg}; color: {text}; "
            f"border: 1px solid {border}; border-radius: 4px; "
            f"padding: 0 8px; min-height: 26px; font-size: 10px; }}"
            f"QPushButton:hover {{ border-color: {color}; color: #fff; }}"
        )

    @staticmethod
    def _copy_seg(seg: SubtitleSegment) -> SubtitleSegment:
        import copy
        return copy.copy(seg)
