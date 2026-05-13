from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui.components.app_select import AppSelect
from ui.components.app_button import AppButton
from ui.components.icons import app_icon
from stores.timeline_store import TimelineStore
from ui.components.timeline.dubbing_timeline import DubbingTimeline
from utils.font_manager import get_google_sans


class IconLabel(QWidget):
    def __init__(
        self,
        text: str,
        icon_name: str,
        fallback: str,
        color: str = "#374151",
        icon_size: int = 14,
    ):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        icon = QLabel()
        icon.setPixmap(
            app_icon(icon_name, fallback=fallback, color=color, size=icon_size)
            .pixmap(QSize(icon_size, icon_size))
        )

        label = QLabel(text)
        label.setFont(get_google_sans(size=9, weight="Medium"))
        label.setObjectName("controlLabel")

        layout.addWidget(icon)
        layout.addWidget(label)


class TimelineEditor(QWidget):
    # Forwarded signals from DubbingTimeline
    seek_requested = Signal(int)          # frame number
    clip_clicked   = Signal(object, int)  # TimelineItem, frame_at_click
    drag_adjusted  = Signal(str, int)
    mute_toggled   = Signal(str, bool)

    def __init__(self):
        super().__init__()

        self.setObjectName("timelinePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Timeline Editor — Fine Timing")
        title.setObjectName("sectionTitle")
        title.setFont(get_google_sans(size=10, weight="Bold"))

        controls_frame = QFrame()
        controls_frame.setObjectName("timelineControls")

        controls = QHBoxLayout(controls_frame)
        controls.setContentsMargins(10, 8, 10, 8)
        controls.setSpacing(10)

        # ── Zoom ────────────────────────────────────────────────────────
        zoom_label = IconLabel(
            text="Zoom",
            icon_name="zoom-in",
            fallback="fa6s.magnifying-glass-plus",
            color="#374151",
        )

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setObjectName("compactSlider")
        self.zoom_slider.setFixedWidth(100)
        self.zoom_slider.setRange(6, 120)
        self.zoom_slider.setValue(18)
        self.zoom_slider.setToolTip("Timeline zoom (pixels per second)")

        self.zoom_value_label = QLabel("1×")
        self.zoom_value_label.setObjectName("controlLabel")
        self.zoom_value_label.setFont(get_google_sans(size=9, weight="Bold"))
        self.zoom_value_label.setFixedWidth(28)

        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)

        # ── Voice ────────────────────────────────────────────────────────
        voice_label = IconLabel(
            text="Voice",
            icon_name="microphone",
            fallback="fa6s.microphone",
            color="#374151",
        )

        voice_select = self._combo(["Srey Mom", "Male Khmer", "Female Khmer"], 150)

        apply_all = AppButton(
            text="Apply to All",
            icon=app_icon("check", fallback="fa6s.check", color="#ffffff"),
            variant="purple",
            button_size="sm",
        )

        divider_1 = self._divider()

        # ── Window Size ──────────────────────────────────────────────────
        window_label = IconLabel(
            text="Window Size",
            icon_name="alert-triangle",
            fallback="fa6s.triangle-exclamation",
            color="#ef4444",
        )

        size_select = self._combo(
            ["Large (1400x900)", "Medium (1280x720)", "Small (960x540)"], 175
        )

        apply = AppButton(
            text="Apply",
            icon=app_icon("check", fallback="fa6s.check", color="#ffffff"),
            variant="danger",
            button_size="sm",
        )

        divider_2 = self._divider()

        # ── Echo ─────────────────────────────────────────────────────────
        echo_label = IconLabel(
            text="Echo",
            icon_name="volume",
            fallback="fa6s.volume-high",
            color="#374151",
        )

        echo_slider = QSlider(Qt.Orientation.Horizontal)
        echo_slider.setObjectName("compactSlider")
        echo_slider.setFixedWidth(120)
        echo_slider.setRange(0, 100)
        echo_slider.setValue(50)

        self.echo_pct = QLabel("50%")
        self.echo_pct.setObjectName("purpleText")
        self.echo_pct.setFont(get_google_sans(size=10, weight="Bold"))
        self.echo_pct.setFixedWidth(36)
        echo_slider.valueChanged.connect(lambda v: self.echo_pct.setText(f"{v}%"))

        echo_all = AppButton(
            text="Echo All Row",
            icon=app_icon("sparkles", fallback="fa6s.sparkles", color="#ffffff"),
            variant="purple",
            button_size="sm",
        )

        # ── Assemble controls ─────────────────────────────────────────────
        controls.addWidget(zoom_label)
        controls.addWidget(self.zoom_slider)
        controls.addWidget(self.zoom_value_label)

        controls.addWidget(voice_label)
        controls.addWidget(voice_select)
        controls.addWidget(apply_all)

        controls.addWidget(divider_1)

        controls.addWidget(window_label)
        controls.addWidget(size_select)
        controls.addWidget(apply)

        controls.addWidget(divider_2)

        controls.addWidget(echo_label)
        controls.addWidget(echo_slider)
        controls.addWidget(self.echo_pct)
        controls.addWidget(echo_all)

        controls.addStretch()

        # ── Timeline widget ───────────────────────────────────────────────
        self.timeline = DubbingTimeline()
        self.timeline.setMinimumHeight(220)

        # Forward timeline signals upward
        self.timeline.seek_requested.connect(self.seek_requested)
        self.timeline.clip_clicked.connect(self.clip_clicked)
        self.timeline.drag_adjusted.connect(self.drag_adjusted)
        self.timeline.mute_toggled.connect(self.mute_toggled)

        layout.addWidget(title)
        layout.addWidget(controls_frame)
        layout.addWidget(self.timeline, 1)

    # ---------------------------------------------------------------- zoom

    def _on_zoom_changed(self, value: int):
        ratio = round(value / 18.0, 1)
        self.zoom_value_label.setText(f"{ratio}×")
        self.timeline.set_zoom(float(value))

    # --------------------------------------------------------------- public

    def set_timeline_store(self, store: TimelineStore, duration_ms: int):
        self.timeline.set_store(store, duration_ms)

    def set_playhead(self, position_ms: int):
        self.timeline.set_playhead(position_ms)

    # ------------------------------------------------------------ helpers

    @staticmethod
    def _divider() -> QFrame:
        d = QFrame()
        d.setObjectName("verticalDivider")
        d.setFrameShape(QFrame.Shape.VLine)
        d.setFixedHeight(28)
        return d

    @staticmethod
    def _combo(items: list[str], width: int) -> AppSelect:
        return AppSelect(items, width=width)
