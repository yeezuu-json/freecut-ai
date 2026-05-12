from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QLabel, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ui.components.app_button import AppButton
from ui.components.icons import app_icon
from utils.font_manager import get_google_sans


class VideoPreviewPanel(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Video Preview")
        title.setObjectName("sectionTitle")
        title.setFont(get_google_sans(size=11, weight="Bold"))

        self.preview_box = QFrame()
        self.preview_box.setObjectName("videoPreviewBox")
        self.preview_box.setMinimumHeight(520)

        preview_layout = QVBoxLayout(self.preview_box)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.setSpacing(10)

        empty_icon = QLabel()
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon.setPixmap(
            app_icon(
                "video-off",
                fallback="fa6s.video-slash",
                color="#c4c9d1",
                size=34,
            ).pixmap(QSize(34, 34))
        )

        empty_label = QLabel("No Video\nLoaded")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setObjectName("emptyVideoText")
        empty_label.setFont(get_google_sans(size=15, weight="Bold"))

        preview_layout.addStretch()
        preview_layout.addWidget(empty_icon)
        preview_layout.addWidget(empty_label)
        preview_layout.addStretch()

        controls = QHBoxLayout()
        controls.setSpacing(6)

        play_button = AppButton(
            text="Play",
            icon=app_icon("player-play", fallback="fa6s.play", color="#ffffff"),
            variant="success",
            button_size="sm",
        )

        stop_button = AppButton(
            text="Stop",
            icon=app_icon("player-stop", fallback="fa6s.stop", color="#ffffff"),
            variant="danger",
            button_size="sm",
        )

        time_label = QLabel("00:00 / 00:00")
        time_label.setObjectName("mutedText")
        time_label.setFont(get_google_sans(size=9))

        controls.addWidget(play_button)
        controls.addWidget(stop_button)
        controls.addWidget(time_label)
        controls.addStretch()

        tools_title = QLabel("Tools")
        tools_title.setObjectName("sectionTitle")
        tools_title.setFont(get_google_sans(size=10, weight="Bold"))

        auto_sync = AppButton(
            text="Auto-Sync",
            icon=app_icon("wand", fallback="fa6s.wand-magic-sparkles", color="#ffffff"),
            variant="danger",
            button_size="md",
            full_width=True,
        )

        auto_speed = AppButton(
            text="Auto-Speed",
            icon=app_icon("gauge", fallback="fa6s.gauge-high", color="#ffffff"),
            variant="warning",
            button_size="md",
            full_width=True,
        )

        cutter = AppButton(
            text="Video Cutter",
            icon=app_icon("scissors", fallback="fa6s.scissors", color="#ffffff"),
            variant="purple",
            button_size="md",
            full_width=True,
        )

        license_label = QLabel("License: Lifetime")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_label.setObjectName("licenseText")
        license_label.setFont(get_google_sans(size=9, weight="Bold"))

        layout.addWidget(title)
        layout.addWidget(self.preview_box, 1)
        layout.addLayout(controls)
        layout.addWidget(tools_title)
        layout.addWidget(auto_sync)
        layout.addWidget(auto_speed)
        layout.addWidget(cutter)
        layout.addWidget(license_label)