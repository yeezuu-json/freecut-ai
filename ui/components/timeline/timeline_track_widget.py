from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from models.timeline_item import TimelineItem
from models.timeline_track import TimelineTrack
from ui.components.timeline.timeline_clip_widget import TimelineClipWidget
from ui.components.icons import app_icon
from utils.font_manager import get_google_sans


LABEL_WIDTH = 130  # px — must stay in sync with dubbing_timeline.TRACK_LABEL_WIDTH

_KIND_META: dict[str, tuple[str, str, str]] = {
    # kind → (tabler_icon, fa_fallback, accent_color)
    "video": ("movie",     "fa6s.film",        "#3b82f6"),
    "audio": ("music",     "fa6s.music",       "#10b981"),
    "voice": ("microphone","fa6s.microphone",  "#f472b6"),
}


class TimelineTrackWidget(QWidget):
    mute_toggled  = Signal(str, bool)   # track_id, muted
    clip_clicked  = Signal(object, int) # TimelineItem, frame_at_click
    drag_adjusted = Signal(str, int)    # item_id, delta_frames

    def __init__(
        self,
        track: TimelineTrack,
        items: list[TimelineItem],
        total_frames: int,
        ppf: float = 0.6,
    ):
        super().__init__()

        self.track        = track
        self.total_frames = max(total_frames, 1)
        self.ppf          = ppf
        self._clips: dict[str, TimelineClipWidget] = {}

        self.setObjectName("timelineTrack")
        self.setFixedHeight(48)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._label_area = self._build_label(track)

        self.lane = QFrame()
        self.lane.setObjectName("timelineLane")
        self.lane.setStyleSheet(
            "#timelineLane { background-color: #1c1f30;"
            " border-bottom: 1px solid #252840; }"
        )
        self.lane.setFixedHeight(40)

        root.addWidget(self._label_area)
        root.addWidget(self.lane, 1)

        for item in items:
            self._add_clip(item)

        self._apply_mute_visual(track.muted)

    # ---------------------------------------------------------------- label

    def _build_label(self, track: TimelineTrack) -> QWidget:
        icon_name, fallback, accent = _KIND_META.get(
            track.kind, ("music", "fa6s.music", "#6b7280")
        )

        area = QWidget()
        area.setObjectName("timelineTrackLabel")
        area.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Inline style wins over any descendant rule in external QSS
        area.setStyleSheet(
            "#timelineTrackLabel { background-color: #1e2235;"
            " border-right: 1px solid #2d3147; }"
        )
        area.setFixedWidth(LABEL_WIDTH)

        layout = QHBoxLayout(area)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(6)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            app_icon(icon_name, fallback=fallback, color=accent, size=12)
            .pixmap(QSize(12, 12))
        )
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        name_lbl = QLabel(track.name)
        name_lbl.setObjectName("timelineTrackName")
        name_lbl.setFont(get_google_sans(size=9, weight="Bold"))
        name_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.mute_btn = QPushButton()
        self.mute_btn.setObjectName("muteButton")
        self.mute_btn.setCheckable(True)
        self.mute_btn.setChecked(track.muted)
        self.mute_btn.setFixedSize(22, 22)
        self.mute_btn.setToolTip("Mute / unmute track")
        self.mute_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sync_mute_icon(track.muted)
        self.mute_btn.toggled.connect(self._on_mute_toggled)

        layout.addWidget(icon_lbl)
        layout.addWidget(name_lbl, 1)
        layout.addWidget(self.mute_btn)

        return area

    def _sync_mute_icon(self, muted: bool):
        if muted:
            pix = app_icon(
                "volume-off", fallback="fa6s.volume-xmark", color="#ef4444", size=12
            ).pixmap(QSize(12, 12))
        else:
            pix = app_icon(
                "volume", fallback="fa6s.volume-high", color="#6b7280", size=12
            ).pixmap(QSize(12, 12))
        self.mute_btn.setIcon(QIcon(pix))

    # ---------------------------------------------------------------- clips

    def _add_clip(self, item: TimelineItem):
        w = TimelineClipWidget(item, ppf=self.ppf)
        w.setParent(self.lane)
        w.clip_clicked.connect(self.clip_clicked)
        w.drag_adjusted.connect(self._on_drag_adjusted)
        self._clips[item.id] = w
        self._position_clip(w)
        w.show()

    def _position_clip(self, w: TimelineClipWidget):
        item = w.item
        x    = self._frames_to_x(item.from_frame)
        wid  = max(self._frames_to_x(item.duration_in_frames), 8)
        w.setGeometry(x, 6, wid, 28)

    def _frames_to_x(self, frames: int) -> int:
        return int(frames * self.ppf)

    # --------------------------------------------------------------- signals

    def _on_mute_toggled(self, checked: bool):
        self.track.muted = checked
        self._sync_mute_icon(checked)
        self._apply_mute_visual(checked)
        self.mute_toggled.emit(self.track.id, checked)

    def _on_drag_adjusted(self, item_id: str, delta_frames: int):
        w = self._clips.get(item_id)
        if w is None:
            return
        new_start       = max(0, w.item.from_frame + delta_frames)
        w.item.from_frame = new_start
        self._position_clip(w)
        self.drag_adjusted.emit(item_id, delta_frames)

    def _apply_mute_visual(self, muted: bool):
        if muted:
            fx = QGraphicsOpacityEffect(self.lane)
            fx.setOpacity(0.35)
            self.lane.setGraphicsEffect(fx)
        else:
            self.lane.setGraphicsEffect(None)

    # ---------------------------------------------------------------- public

    def rerender(self, ppf: float):
        """Reposition all clip widgets after a zoom change."""
        self.ppf = ppf
        for w in self._clips.values():
            w.set_ppf(ppf)
            self._position_clip(w)
