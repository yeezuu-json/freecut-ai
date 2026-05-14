from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

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

    # Emitted when the user clicks the Voice Library / AI Voice button
    voice_library_requested = Signal()

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

        # ── Voice Library button ──────────────────────────────────────────
        voxcpm_label = IconLabel(
            text="Voice Clone",
            icon_name="robot",
            fallback="fa6s.robot",
            color="#374151",
        )

        voxcpm_button = AppButton(
            text="Voice Library",
            icon=app_icon("microphone", fallback="fa6s.microphone", color="#ffffff"),
            variant="purple",
            button_size="sm",
            on_click=lambda: self.voice_library_requested.emit(),
        )

        # ── Assemble controls ─────────────────────────────────────────────
        controls.addWidget(zoom_label)
        controls.addWidget(self.zoom_slider)
        controls.addWidget(self.zoom_value_label)

        controls.addWidget(self._divider())

        controls.addWidget(voxcpm_label)
        controls.addWidget(voxcpm_button)

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
