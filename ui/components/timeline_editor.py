from PySide6.QtCore import Qt, QSize
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
            app_icon(
                icon_name,
                fallback=fallback,
                color=color,
                size=icon_size,
            ).pixmap(QSize(icon_size, icon_size))
        )

        label = QLabel(text)
        label.setFont(get_google_sans(size=9, weight="Medium"))
        label.setObjectName("controlLabel")

        layout.addWidget(icon)
        layout.addWidget(label)


class TimelineEditor(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("timelinePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Timeline Editor - Fine Timing")
        title.setObjectName("sectionTitle")
        title.setFont(get_google_sans(size=10, weight="Bold"))

        controls_frame = QFrame()
        controls_frame.setObjectName("timelineControls")

        controls = QHBoxLayout(controls_frame)
        controls.setContentsMargins(10, 8, 10, 8)
        controls.setSpacing(10)

        zoom_label = IconLabel(
            text="Zoom",
            icon_name="zoom-in",
            fallback="fa6s.magnifying-glass-plus",
            color="#374151",
        )

        zoom_slider = QSlider(Qt.Orientation.Horizontal)
        zoom_slider.setObjectName("compactSlider")
        zoom_slider.setFixedWidth(80)
        zoom_slider.setValue(20)

        voice_label = IconLabel(
            text="Voice",
            icon_name="microphone",
            fallback="fa6s.microphone",
            color="#374151",
        )

        voice_select = self.create_combo_box(["Srey Mom", "Male Khmer", "Female Khmer"], 150)

        apply_all = AppButton(
            text="Apply to All",
            icon=app_icon("check", fallback="fa6s.check", color="#ffffff"),
            variant="purple",
            button_size="sm",
        )

        divider_1 = self.create_divider()

        window_label = IconLabel(
            text="Window Size",
            icon_name="alert-triangle",
            fallback="fa6s.triangle-exclamation",
            color="#ef4444",
        )

        size_select = self.create_combo_box([
            "Large (1400x900)",
            "Medium (1280x720)",
            "Small (960x540)"
        ], 170)

        apply = AppButton(
            text="Apply",
            icon=app_icon("check", fallback="fa6s.check", color="#ffffff"),
            variant="danger",
            button_size="sm",
        )

        divider_2 = self.create_divider()

        echo_label = IconLabel(
            text="Echo",
            icon_name="volume",
            fallback="fa6s.volume-high",
            color="#374151",
        )

        echo_slider = QSlider(Qt.Orientation.Horizontal)
        echo_slider.setObjectName("compactSlider")
        echo_slider.setFixedWidth(120)
        echo_slider.setValue(50)

        echo_percent = QLabel("50%")
        echo_percent.setObjectName("purpleText")
        echo_percent.setFont(get_google_sans(size=10, weight="Bold"))
        echo_percent.setFixedWidth(36)

        echo_all = AppButton(
            text="Echo All Row",
            icon=app_icon("sparkles", fallback="fa6s.sparkles", color="#ffffff"),
            variant="purple",
            button_size="sm",
        )

        controls.addWidget(zoom_label)
        controls.addWidget(zoom_slider)

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
        controls.addWidget(echo_percent)
        controls.addWidget(echo_all)

        controls.addStretch()

        timeline_area = QFrame()
        timeline_area.setObjectName("timelineArea")
        timeline_area.setMinimumHeight(170)

        layout.addWidget(title)
        layout.addWidget(controls_frame)
        layout.addWidget(timeline_area, 1)

    def create_divider(self):
        divider = QFrame()
        divider.setObjectName("verticalDivider")
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setFixedHeight(28)
        return divider
    
    def create_combo_box(self, items: list[str], width: int):
        combo_box = AppSelect(items, width=width)
        return combo_box