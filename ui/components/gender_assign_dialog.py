"""Gender Assignment Dialog.

Shows a mini NLE-style timeline (vocals track + segment clips) and a table where
the user can preview each segment and assign Male / Female before TTS.

Workflow
--------
1. Auto-assign gender (called by caller before opening the dialog).
2. User reviews / overrides per-row gender toggles.
3. Voice Assignment section: pick male voice + female voice from Edge TTS
   defaults or saved VoxCPM2 clones.
4. "Assign Voices" — bulk-writes ``seg.voice`` on every segment.
5. "Generate TTS" — validates assignments, checks VoxCPM model if needed,
   then accepts the dialog so the caller starts TtsWorker.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPen,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.config import AppConfig, load_config
from app.logger import get_logger
from models.subtitle_segment import SubtitleSegment

logger = get_logger(__name__)
from services.voice_library_service import VoiceLibraryService
from ui.components.app_select import AppSelect
from utils.font_manager import get_google_sans


# ── voice mapping ────────────────────────────────────────────────────────────

VOICE_FOR_GENDER: dict[str, str] = {
    "male":    "Piseth (Male)",
    "female":  "Sreymom (Female)",
    "unknown": "Default",
}

# Default Edge TTS options shown in the voice dropdowns.
_EDGE_MALE_OPTIONS: list[str] = ["edge:Piseth (Male)", "edge:Default"]
_EDGE_FEMALE_OPTIONS: list[str] = ["edge:Sreymom (Female)", "edge:Default"]

GENDER_COLORS: dict[str, str] = {
    "male":    "#3b82f6",   # blue
    "female":  "#ec4899",   # pink
    "unknown": "#6b7280",   # grey
}

# Dialogue language hint for AI gender detection (not the same as Whisper code).
_DIALOGUE_LANG_OPTIONS: list[str] = [
    "Auto (any language)",
    "Chinese",
    "English",
    "Khmer",
    "Japanese",
    "Korean",
    "Spanish",
    "French",
    "Thai",
    "Vietnamese",
]


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
    """Assign Male / Female to each subtitle segment and pick voices before TTS."""

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
        config: AppConfig | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._config      = config
        self._segments    = [self._copy_seg(s) for s in segments]
        self._vocals_path = vocals_path
        self._duration_ms = duration_ms
        self._current_preview: int = -1
        self._gender_thread: QThread | None = None
        self._gender_worker = None
        self._gender_btns: dict[int, tuple[QPushButton, QPushButton]] = {}

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
        self._update_auto_detect_button_state()

    # ── public ───────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802
        """Refresh API-key state when the dialog is shown (e.g. after Settings)."""
        super().showEvent(event)
        self._update_auto_detect_button_state()

    def get_segments(self) -> list[SubtitleSegment]:
        return self._segments

    def _effective_gemini_key(self) -> str:
        """Resolve Gemini key from dialog config, .env, or freshly loaded app.json."""
        if self._config and self._config.gemini_api_key.strip():
            return self._config.gemini_api_key.strip()
        env_key = os.getenv("GEMINI_API_KEY", "").strip()
        if env_key:
            return env_key
        try:
            return load_config().gemini_api_key.strip()
        except Exception:
            return ""

    def _update_auto_detect_button_state(self) -> None:
        has_key = bool(self._effective_gemini_key())
        busy = self._gender_thread is not None and self._gender_thread.isRunning()
        self._auto_detect_btn.setEnabled(has_key and not busy)
        if not has_key:
            self._auto_detect_btn.setToolTip(
                "Add a Gemini API key in Settings (or GEMINI_API_KEY in .env), then reopen this dialog."
            )

    # ── UI construction ───────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        self.setWindowTitle("Voice Assignment & Gender")
        self.setModal(True)
        self.resize(1100, 720)
        self.setStyleSheet("""
            QDialog { background: #1a1d2e; color: #e2e8f0; }
            QLabel  { color: #e2e8f0; }

            QTableWidget {
                background: #12131f;
                color: #e2e8f0;
                gridline-color: #2a2d45;
                border: 1px solid #2a2d45;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 4px 6px;
                color: #e2e8f0;
                background: #12131f;
            }
            QTableWidget::item:alternate {
                background: #1a1d2e;
            }
            QTableWidget::item:selected {
                background: #2a3258;
                color: #ffffff;
            }
            QHeaderView::section {
                background: #1e2235;
                color: #94a3b8;
                padding: 5px 6px;
                border: none;
                border-right: 1px solid #2a2d45;
                border-bottom: 1px solid #2a2d45;
                font-weight: bold;
            }
            QScrollBar:horizontal, QScrollBar:vertical {
                background: #12131f; border: none; width: 8px; height: 8px;
            }
            QScrollBar::handle:horizontal, QScrollBar::handle:vertical {
                background: #3b4268; border-radius: 4px; min-width: 30px; min-height: 30px;
            }
            QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
            QWidget#cellWidget { background: transparent; }
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

        # ── Voice Assignment section ──────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("QFrame { color: #2a2d45; }")
        root.addWidget(sep)

        va_title = QLabel("Voice Assignment")
        va_title.setFont(get_google_sans(size=11, weight="Bold"))
        va_title.setStyleSheet("color: #94a3b8; margin-top: 2px;")
        root.addWidget(va_title)

        self._voice_row = QHBoxLayout()
        voice_row = self._voice_row
        voice_row.setSpacing(16)

        # Male voice dropdown
        male_lbl = QLabel("♂ Male voice:")
        male_lbl.setStyleSheet("color: #93c5fd; font-size: 12px; font-weight: 600;")
        self._male_voice_select = self._build_voice_select("male")

        # Female voice dropdown
        female_lbl = QLabel("♀ Female voice:")
        female_lbl.setStyleSheet("color: #f9a8d4; font-size: 12px; font-weight: 600;")
        self._female_voice_select = self._build_voice_select("female")

        open_lib_btn = QPushButton("Open Voice Library…")
        open_lib_btn.setStyleSheet(self._btn_style("#4b5563", height=30))
        open_lib_btn.clicked.connect(self._on_open_voice_library)

        voice_row.addWidget(male_lbl)
        voice_row.addWidget(self._male_voice_select)
        voice_row.addSpacing(12)
        voice_row.addWidget(female_lbl)
        voice_row.addWidget(self._female_voice_select)
        voice_row.addSpacing(12)
        voice_row.addWidget(open_lib_btn)
        voice_row.addStretch()
        root.addLayout(voice_row)

        # Assignment status label
        self._assign_status = QLabel("")
        self._assign_status.setStyleSheet("color: #22c55e; font-size: 11px;")
        root.addWidget(self._assign_status)

        # ── AI gender detection options ───────────────────────────────────────
        ai_row = QHBoxLayout()
        ai_row.setSpacing(10)
        ai_lang_lbl = QLabel("Dialogue language (for AI):")
        ai_lang_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self._dialogue_lang_select = AppSelect(
            items=_DIALOGUE_LANG_OPTIONS,
            value=self._default_dialogue_language(),
            width=180,
            height=28,
        )
        self._dialogue_lang_select.setStyleSheet(self._DARK_SELECT_QSS)
        ai_hint = QLabel("Gender is still assigned by you — AI only suggests.")
        ai_hint.setStyleSheet("color: #64748b; font-size: 10px;")
        ai_row.addWidget(ai_lang_lbl)
        ai_row.addWidget(self._dialogue_lang_select)
        ai_row.addWidget(ai_hint, 1)
        root.addLayout(ai_row)

        # ── Bottom buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._auto_detect_btn = QPushButton("Auto-Detect (AI)")
        self._auto_detect_btn.setToolTip(
            "Use Google Gemini to guess speaker gender from dialogue text.\n"
            "Pick dialogue language above (or Auto for mixed EN/ZH/etc.).\n"
            "Review results before generating TTS — AI can be wrong."
        )
        self._auto_detect_btn.clicked.connect(self._on_auto_detect_gender)
        self._auto_detect_btn.setStyleSheet(self._btn_style("#7c3aed"))

        assign_male_all = QPushButton("All Male")
        assign_male_all.clicked.connect(lambda: self._assign_all("male"))
        assign_male_all.setStyleSheet(self._btn_style("#3b82f6"))

        assign_female_all = QPushButton("All Female")
        assign_female_all.clicked.connect(lambda: self._assign_all("female"))
        assign_female_all.setStyleSheet(self._btn_style("#ec4899"))

        btn_row.addWidget(self._auto_detect_btn)
        btn_row.addWidget(assign_male_all)
        btn_row.addWidget(assign_female_all)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(self._btn_style("#374151"))

        self._assign_voices_btn = QPushButton("Assign Voices")
        self._assign_voices_btn.clicked.connect(self._on_assign_voices)
        self._assign_voices_btn.setStyleSheet(self._btn_style("#6366f1"))

        self._generate_btn = QPushButton("Generate TTS")
        self._generate_btn.clicked.connect(self._on_generate_tts)
        self._generate_btn.setStyleSheet(self._btn_style("#22c55e"))

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._assign_voices_btn)
        btn_row.addWidget(self._generate_btn)
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
        gender_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
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
        self._gender_btns[row] = (male_btn, female_btn)
        self._table.setCellWidget(row, self._COL_GENDER, gender_widget)

        # Play button.
        play_btn = QPushButton("▶ Play")
        play_btn.setStyleSheet(self._btn_style("#4b5563", height=26))
        play_btn.setFont(get_google_sans(size=9))
        play_btn.clicked.connect(lambda _=False, r=row: self._toggle_preview(r))
        self._table.setCellWidget(row, self._COL_PLAY, play_btn)

    def _set_cell(self, row: int, col: int, value: str) -> None:
        item = QTableWidgetItem(value)
        item.setForeground(QColor("#e2e8f0"))
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

    def _default_dialogue_language(self) -> str:
        """Map Settings → translation source language to dialog options."""
        if not self._config:
            return "Auto (any language)"
        src = (self._config.translation_source_language or "").strip()
        if not src:
            return "Auto (any language)"
        for opt in _DIALOGUE_LANG_OPTIONS:
            if opt.lower() == src.lower():
                return opt
        # Fuzzy: "Chinese" in settings, "zh" in transcription, etc.
        aliases = {
            "zh": "Chinese", "cn": "Chinese", "chinese": "Chinese",
            "en": "English", "english": "English",
            "km": "Khmer", "khmer": "Khmer",
            "ja": "Japanese", "jp": "Japanese",
            "ko": "Korean", "kr": "Korean",
        }
        return aliases.get(src.lower(), src if src in _DIALOGUE_LANG_OPTIONS else "Auto (any language)")

    # ── voice assignment helpers ──────────────────────────────────────────────

    def _build_voice_select(self, gender: str) -> AppSelect:
        """Build a dark-styled AppSelect populated with Edge TTS + all cloned voices.

        Items are (display_label, stored_value) tuples so the dropdown shows a
        clean name while the internal value keeps the full prefix for routing.
        All saved voice library entries are shown in both male and female dropdowns
        so any cloned voice can be freely assigned to either gender role.
        """
        # Edge TTS options: label == value (legacy format, no tuple needed)
        raw_edge = _EDGE_MALE_OPTIONS[:] if gender == "male" else _EDGE_FEMALE_OPTIONS[:]
        options: list = list(raw_edge)   # plain strings → label == value

        try:
            entries = VoiceLibraryService().list_entries()
            for e in entries:
                icon = "♂" if e.gender == "male" else ("♀" if e.gender == "female" else "🎙")
                label = f"{icon} {e.name}"          # "♂ Man 01"
                value = f"clone:{e.id}"             # "clone:e5b82898ce54"
                options.append((label, value))       # (display, stored-value) tuple
        except Exception:
            pass

        sel = AppSelect(items=options, width=200, height=30)
        sel.setStyleSheet(self._DARK_SELECT_QSS)
        original_rebuild = sel.rebuild_menu

        def _patched_rebuild():
            original_rebuild()
            sel.menu.setStyleSheet(self._DARK_MENU_QSS)

        sel.rebuild_menu = _patched_rebuild
        sel.menu.setStyleSheet(self._DARK_MENU_QSS)
        return sel

    def _voice_value_from_select(self, sel: AppSelect) -> str:
        """Return the seg.voice string for the currently selected option.

        Options have the form:
          "edge:Piseth (Male)"       → stored as-is
          "clone:<id>:<name>"        → stored as "clone:<id>"
          "edge:Default"             → stored as "Default" (legacy)
        """
        val = sel.value or ""
        if val.startswith("clone:"):
            parts = val.split(":", 2)
            return f"clone:{parts[1]}" if len(parts) >= 2 else val
        return val

    def _on_assign_voices(self) -> None:
        male_voice   = self._voice_value_from_select(self._male_voice_select)
        female_voice = self._voice_value_from_select(self._female_voice_select)

        assigned = 0
        for seg in self._segments:
            gender = getattr(seg, "gender", "unknown") or "unknown"
            if gender == "male":
                seg.voice = male_voice
                assigned += 1
            elif gender == "female":
                seg.voice = female_voice
                assigned += 1
            else:
                seg.voice = "Default"

        self._assign_status.setText(f"✓ {assigned} segment(s) assigned.")

    def _on_generate_tts(self) -> None:
        # Step 1: ensure voices are assigned.
        voiced = [s for s in self._segments if getattr(s, "voice", "") not in ("", "Default")]
        if not voiced:
            QMessageBox.warning(
                self,
                "No Voices Assigned",
                "Click 'Assign Voices' first to map a voice to each segment.",
            )
            return

        # Step 2: if any clone: voices are used, ensure VoxCPM2 model is ready.
        has_clone = any(
            (getattr(s, "voice", "") or "").startswith("clone:")
            for s in self._segments
        )
        if has_clone:
            from ui.components.model_download_dialog import ModelDownloadDialog
            ok = ModelDownloadDialog.ensure(
                provider="local_voxcpm",
                model_name="openbmb/VoxCPM2",
                parent=self,
            )
            if not ok:
                return

        # Step 3: accept — caller reads get_segments() and starts TtsWorker.
        self.accept()

    def _on_open_voice_library(self) -> None:
        from ui.components.voxcpm_dialog import VoxCPMDialog
        dlg = VoxCPMDialog(parent=self)
        dlg.exec()
        # Reload dropdowns in case user saved a new voice clone.
        old_male   = self._male_voice_select
        old_female = self._female_voice_select
        self._male_voice_select   = self._build_voice_select("male")
        self._female_voice_select = self._build_voice_select("female")
        self._voice_row.replaceWidget(old_male,   self._male_voice_select)
        self._voice_row.replaceWidget(old_female, self._female_voice_select)
        old_male.deleteLater()
        old_female.deleteLater()

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

    def _on_auto_detect_gender(self) -> None:
        api_key = self._effective_gemini_key()
        if not api_key:
            QMessageBox.warning(
                self,
                "Gemini API Key Required",
                "Add your Gemini API key in Settings (or GEMINI_API_KEY in .env), "
                "then try again.",
            )
            return

        if not self._config:
            QMessageBox.warning(self, "Configuration Error", "App configuration is missing.")
            return

        if self._gender_thread and self._gender_thread.isRunning():
            return

        texts = [
            (s.original_text or s.khmer_text or "").strip()
            for s in self._segments
        ]
        if not any(texts):
            QMessageBox.warning(
                self,
                "No Dialogue Text",
                "Segments have no transcript text to analyze.\n"
                "Run transcribe / translate first.",
            )
            return

        logger.info("Starting AI gender detection for %d segments.", len(self._segments))

        self._set_busy(True)
        self._assign_status.setText("Detecting speaker gender with AI…")
        self._assign_status.setStyleSheet("color: #a78bfa; font-size: 11px;")

        from workers.gender_detection_worker import GenderDetectionWorker

        thread = QThread()
        worker = GenderDetectionWorker(
            self._config,
            self._segments,
            dialogue_language=self._dialogue_lang_select.value,
            api_key=api_key,
        )
        worker.moveToThread(thread)
        thread.worker = worker
        self._gender_thread = thread
        self._gender_worker = worker

        thread.started.connect(
            worker.run,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.progress_changed.connect(
            self._on_gender_detect_progress,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(
            self._on_gender_detect_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.failed.connect(
            self._on_gender_detect_failed,
            Qt.ConnectionType.QueuedConnection,
        )
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(self._on_gender_thread_finished)

        thread.start()

    def _on_gender_detect_progress(self, pct: int, msg: str) -> None:
        self._assign_status.setText(f"{msg} ({pct}%)")

    def _on_gender_detect_finished(self, _segments: object) -> None:
        self._set_busy(False)
        for i in range(len(self._segments)):
            self._refresh_gender_buttons(i)
        self._timeline.update()

        male = sum(1 for s in self._segments if s.gender == "male")
        female = sum(1 for s in self._segments if s.gender == "female")
        unknown = len(self._segments) - male - female
        self._assign_status.setText(
            f"AI assigned: {male} male, {female} female, {unknown} unknown — review and adjust."
        )
        self._assign_status.setStyleSheet("color: #22c55e; font-size: 11px;")

    def _on_gender_detect_failed(self, message: str) -> None:
        self._set_busy(False)
        self._assign_status.setText("")
        QMessageBox.critical(self, "Gender Detection Failed", message)

    def _set_busy(self, busy: bool) -> None:
        self._update_auto_detect_button_state()
        self._assign_voices_btn.setEnabled(not busy)
        self._generate_btn.setEnabled(not busy)

    def _on_gender_thread_finished(self) -> None:
        if self._gender_worker:
            try:
                self._gender_worker.progress_changed.disconnect()
                self._gender_worker.finished.disconnect()
                self._gender_worker.failed.disconnect()
            except Exception:
                pass
        self._gender_worker = None
        self._gender_thread = None
        self._update_auto_detect_button_state()

    def _refresh_gender_buttons(self, idx: int) -> None:
        gender = self._segments[idx].gender or "unknown"
        pair = self._gender_btns.get(idx)
        if not pair:
            return
        male_btn, female_btn = pair
        male_btn.blockSignals(True)
        female_btn.blockSignals(True)
        male_btn.setChecked(gender == "male")
        female_btn.setChecked(gender == "female")
        male_btn.setStyleSheet(self._toggle_style("#3b82f6",   checked=(gender == "male")))
        female_btn.setStyleSheet(self._toggle_style("#ec4899", checked=(gender == "female")))
        male_btn.blockSignals(False)
        female_btn.blockSignals(False)

    # ── closeEvent ────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._player.stop()
        if self._gender_thread and self._gender_thread.isRunning():
            self._gender_thread.quit()
            self._gender_thread.wait(3000)
        super().closeEvent(event)

    def reject(self) -> None:
        self._player.stop()
        if self._gender_thread and self._gender_thread.isRunning():
            self._gender_thread.quit()
            self._gender_thread.wait(3000)
        super().reject()

    # ── style helpers ─────────────────────────────────────────────────────────

    _DARK_MENU_QSS = """
        QMenu { background-color: #2d3748; color: #e2e8f0;
                border: 1px solid #4a5568; border-radius: 6px; padding: 4px 0; }
        QMenu::item { color: #e2e8f0; padding: 7px 14px; border-radius: 3px; margin: 2px 4px; }
        QMenu::item:selected { background-color: #3b82f6; color: #fff; }
        QMenu::item:checked  { background-color: #1e3a5f; color: #93c5fd; font-weight: 600; }
    """
    _DARK_SELECT_QSS = """
        QPushButton#appSelect { background-color: #1e2235; color: #e2e8f0;
            border: 1px solid #374151; border-radius: 6px;
            padding: 0 10px; text-align: left; font-size: 12px; }
        QPushButton#appSelect:hover { border-color: #3b82f6; background-color: #252840; }
    """

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
