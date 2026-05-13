"""
dubbing_timeline.py
-------------------
Three-layer widget stack:

  DubbingTimeline            ← outer shell: header + scroll wrapper + public API
    └── QScrollArea
          └── TimelineCanvas ← scrollable content: ruler + tracks + playhead overlay
                ├── TimelineRuler   (custom-painted ticks; click to seek)
                └── TimelineTrackWidget × N
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from stores.timeline_store import TimelineStore
from ui.components.timeline.timeline_track_widget import (
    LABEL_WIDTH,
    TimelineTrackWidget,
)
from utils.font_manager import get_google_sans


DEFAULT_PPS = 18.0   # pixels per second at zoom = 1×


# ---------------------------------------------------------------------------
# TimelineRuler
# ---------------------------------------------------------------------------

class TimelineRuler(QWidget):
    """Custom-painted time ruler. Click anywhere to seek."""

    seek_requested = Signal(int)  # frame number

    def __init__(self):
        super().__init__()
        self.setObjectName("timelineRuler")
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.fps: float          = 30.0
        self.ppf: float          = DEFAULT_PPS / 30.0
        self.total_frames: int   = 1

        self._font = get_google_sans(size=8, weight="Medium")

    def configure(self, fps: float, ppf: float, total_frames: int):
        self.fps           = max(fps, 1.0)
        self.ppf           = max(ppf, 0.001)
        self.total_frames  = max(total_frames, 1)
        self.update()

    # ---------------------------------------------------------------- paint

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor("#13151e"))

        # Label-area separator
        painter.setPen(QPen(QColor("#2d3147"), 1))
        painter.drawLine(LABEL_WIDTH, 0, LABEL_WIDTH, h)

        # Bottom border
        painter.drawLine(0, h - 1, w, h - 1)

        if self.ppf <= 0:
            return

        pps = self.ppf * self.fps  # pixels per second

        # Pick a "nice" step (in seconds) so labels never overlap (≥ 50 px apart).
        raw_step_s = 50.0 / max(pps, 0.01)
        nice = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
        step_s  = next((s for s in nice if s >= raw_step_s), 600)
        step_f  = max(1, int(step_s * self.fps))
        sub_f   = max(1, step_f // 5)   # 5 minor ticks per major

        painter.setFont(self._font)

        frame = 0
        while True:
            x = LABEL_WIDTH + int(frame * self.ppf)
            if x > w:
                break

            is_major = (frame % step_f == 0)

            if is_major:
                painter.setPen(QPen(QColor("#4b5563"), 1))
                painter.drawLine(x, h - 12, x, h - 1)

                sec   = frame / self.fps
                label = self._fmt(sec)
                painter.setPen(QColor("#6b7280"))
                painter.drawText(x + 3, 0, 60, h - 12,
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                                 label)
            else:
                painter.setPen(QPen(QColor("#2d3147"), 1))
                painter.drawLine(x, h - 6, x, h - 1)

            frame += sub_f

    @staticmethod
    def _fmt(sec: float) -> str:
        t = int(sec)
        return f"{t // 60:02d}:{t % 60:02d}"

    # ---------------------------------------------------------------- mouse

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            lane_x = event.pos().x() - LABEL_WIDTH
            if lane_x >= 0 and self.ppf > 0:
                frame = max(0, min(int(lane_x / self.ppf), self.total_frames))
                self.seek_requested.emit(frame)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# TimelineCanvas
# ---------------------------------------------------------------------------

class TimelineCanvas(QWidget):
    """
    Scrollable content widget that lives inside the QScrollArea.
    Owns the ruler + track widgets and draws a playhead overlay.
    """

    seek_requested = Signal(int)         # frame
    clip_clicked   = Signal(object, int) # TimelineItem, frame_at_click
    drag_adjusted  = Signal(str, int)
    mute_toggled   = Signal(str, bool)

    def __init__(self):
        super().__init__()
        self.setObjectName("timelineCanvas")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.fps:           float = 30.0
        self.ppf:           float = DEFAULT_PPS / 30.0
        self.total_frames:  int   = 1
        self._store:        TimelineStore | None = None

        self._track_widgets: list[TimelineTrackWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.ruler = TimelineRuler()
        self.ruler.seek_requested.connect(self.seek_requested)
        layout.addWidget(self.ruler)
        layout.addStretch()     # keeps ruler pinned to the top when no tracks loaded

        self._layout = layout   # tracks inserted before the trailing stretch

        # Playhead — absolutely-positioned red line over all tracks.
        # Use inline stylesheet (highest specificity) so generic QSS descendant
        # rules like "#timelineScroll QWidget { background: transparent }" cannot
        # override the red color.
        self._playhead = QWidget(self)
        self._playhead.setObjectName("playheadLine")
        self._playhead.setFixedWidth(2)
        self._playhead.setStyleSheet("background-color: #ef4444;")
        self._playhead.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._playhead.hide()

        # Small square handle at the top of the playhead
        self._ph_handle = QWidget(self)
        self._ph_handle.setObjectName("playheadHandle")
        self._ph_handle.setFixedSize(10, 10)
        self._ph_handle.setStyleSheet(
            "background-color: #ef4444; border-radius: 2px;"
        )
        self._ph_handle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._ph_handle.hide()

    # ---------------------------------------------------------------- load

    def load_store(self, store: TimelineStore, duration_ms: int):
        self._store        = store
        self.fps           = max(store.fps, 1.0)
        self.total_frames  = self._get_total_frames(store)
        self.ppf           = DEFAULT_PPS / self.fps

        self._clear_tracks()
        self.ruler.configure(self.fps, self.ppf, self.total_frames)

        for track in store.get_sorted_tracks():
            if not track.visible:
                continue
            items = store.get_items_on_track(track.id)
            tw = TimelineTrackWidget(
                track=track,
                items=items,
                total_frames=self.total_frames,
                ppf=self.ppf,
            )
            tw.clip_clicked.connect(self.clip_clicked)
            tw.drag_adjusted.connect(self.drag_adjusted)
            tw.mute_toggled.connect(self.mute_toggled)
            self._track_widgets.append(tw)
            # Insert before the trailing stretch (last item in layout)
            self._layout.insertWidget(self._layout.count() - 1, tw)

        self._update_canvas_width()

    def _get_total_frames(self, store: TimelineStore) -> int:
        frames = 1
        for item in store.items:
            frames = max(frames, item.end_frame)
        return frames

    def _clear_tracks(self):
        for tw in self._track_widgets:
            self._layout.removeWidget(tw)
            tw.deleteLater()
        self._track_widgets.clear()
        # Ruler (index 0) and stretch (last index) are permanent; only track
        # widgets are removed above.

    def _update_canvas_width(self):
        width = LABEL_WIDTH + int(self.total_frames * self.ppf) + 40
        self.setMinimumWidth(width)

    # --------------------------------------------------------------- playhead

    def set_playhead(self, frame: int):
        self._playhead_frame = frame
        self._position_playhead(frame)

    def _position_playhead(self, frame: int):
        x = LABEL_WIDTH + int(frame * self.ppf)
        h = max(self.height(), 400)
        self._playhead.setGeometry(x, 0, 2, h)
        self._ph_handle.setGeometry(x - 4, 0, 10, 10)
        self._playhead.raise_()
        self._ph_handle.raise_()
        if self.total_frames > 1:
            self._playhead.show()
            self._ph_handle.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_playhead_frame"):
            self._position_playhead(self._playhead_frame)

    # ----------------------------------------------------------------- zoom

    def set_zoom(self, pps: float):
        """pps = pixels per second."""
        self.ppf = pps / self.fps
        self.ruler.configure(self.fps, self.ppf, self.total_frames)
        for tw in self._track_widgets:
            tw.rerender(self.ppf)
        self._update_canvas_width()
        if hasattr(self, "_playhead_frame"):
            self._position_playhead(self._playhead_frame)


# ---------------------------------------------------------------------------
# DubbingTimeline — public API
# ---------------------------------------------------------------------------

class DubbingTimeline(QWidget):
    """
    Timeline shell exposed to the rest of the app.

    Signals
    -------
    seek_requested(int)      frame number clicked on the ruler
    clip_clicked(object)     TimelineItem that was clicked
    drag_adjusted(str, int)  item_id, delta_frames
    mute_toggled(str, bool)  track_id, is_muted
    """

    seek_requested = Signal(int)
    clip_clicked   = Signal(object, int)  # TimelineItem, frame_at_click
    drag_adjusted  = Signal(str, int)
    mute_toggled   = Signal(str, bool)

    def __init__(self):
        super().__init__()
        self.setObjectName("dubbingTimeline")

        self._fps:         float = 30.0
        self._duration_ms: int   = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # Header row
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Dubbing Timeline")
        title.setObjectName("sectionTitle")
        title.setFont(get_google_sans(size=10, weight="Bold"))

        self._dur_label = QLabel("--:--")
        self._dur_label.setObjectName("timelineDurationLabel")
        self._dur_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._dur_label.setFont(get_google_sans(size=9, weight="Medium"))

        header.addWidget(title)
        header.addStretch()
        header.addWidget(self._dur_label)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setObjectName("timelineScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._canvas = TimelineCanvas()
        self._canvas.seek_requested.connect(self.seek_requested)
        self._canvas.clip_clicked.connect(self.clip_clicked)
        self._canvas.drag_adjusted.connect(self.drag_adjusted)
        self._canvas.mute_toggled.connect(self.mute_toggled)
        self._scroll.setWidget(self._canvas)

        root.addLayout(header)
        root.addWidget(self._scroll, 1)

    # ---------------------------------------------------------------- public

    def set_store(self, store: TimelineStore, duration_ms: int):
        self._fps         = max(store.fps, 1.0)
        self._duration_ms = duration_ms
        self._dur_label.setText(self._fmt_ms(duration_ms))
        self._canvas.load_store(store, duration_ms)

    def set_playhead(self, position_ms: int):
        """Convert milliseconds → frames and update the playhead."""
        frame = int((position_ms / 1000.0) * self._fps)
        self._canvas.set_playhead(frame)

    def set_zoom(self, pps: float):
        """pps = pixels per second from the zoom slider."""
        self._canvas.set_zoom(pps)

    @staticmethod
    def _fmt_ms(ms: int) -> str:
        s = ms // 1000
        return f"{s // 60:02d}:{s % 60:02d}"
