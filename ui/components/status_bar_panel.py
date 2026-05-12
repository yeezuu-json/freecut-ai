from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from ui.components.app_button import AppButton
from ui.components.icons import app_icon
from utils.font_manager import get_google_sans


class StatusBarPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("statusBarPanel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        timing_group = self.build_timing_group()
        export_group = self.build_export_group()

        status = QLabel("Ready | FreeCut AI Dubbing Studio")
        status.setObjectName("statusText")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setFont(get_google_sans(size=10, weight="Bold"))

        layout.addWidget(timing_group)
        layout.addStretch()
        layout.addWidget(status)
        layout.addStretch()
        layout.addWidget(export_group)

    def build_timing_group(self) -> QWidget:
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        minus = self.create_button(
            text="-0.2s",
            icon_name="arrow-left",
            fallback="fa6s.arrow-left",
            variant="danger",
            size="sm",
        )

        plus = self.create_button(
            text="+0.2s",
            icon_name="arrow-right",
            fallback="fa6s.arrow-right",
            variant="primary",
            size="sm",
        )

        smart_sync = self.create_button(
            text="Smart Sync",
            icon_name="refresh",
            fallback="fa6s.rotate",
            variant="success",
            size="sm",
        )

        preview = self.create_button(
            text="Preview",
            icon_name="player-play",
            fallback="fa6s.play",
            variant="warning",
            size="sm",
        )

        layout.addWidget(minus)
        layout.addWidget(plus)
        layout.addWidget(smart_sync)
        layout.addWidget(preview)

        return group

    def build_export_group(self) -> QWidget:
        group = QWidget()
        layout = QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        remove_vocal = self.create_button(
            text="Remove Original Vocal",
            icon_name="microphone-off",
            fallback="fa6s.microphone-slash",
            variant="ghost",
            size="sm",
            icon_color="#111827",
        )

        export_mp3 = self.create_button(
            text="Export MP3",
            icon_name="music",
            fallback="fa6s.music",
            variant="warning",
            size="md",
        )

        export_video = self.create_button(
            text="Export Video",
            icon_name="device-floppy",
            fallback="fa6s.floppy-disk",
            variant="success",
            size="md",
        )

        export_capcut = self.create_button(
            text="Export to CapCut",
            icon_name="upload",
            fallback="fa6s.upload",
            variant="purple",
            size="md",
        )

        layout.addWidget(remove_vocal)
        layout.addWidget(export_mp3)
        layout.addWidget(export_video)
        layout.addWidget(export_capcut)

        return group

    def create_button(
        self,
        text: str,
        icon_name: str,
        fallback: str,
        variant: str,
        size: str = "sm",
        icon_color: str = "#ffffff",
    ) -> AppButton:
        return AppButton(
            text=text,
            icon=app_icon(
                icon_name,
                fallback=fallback,
                color=icon_color,
                size=16,
            ),
            variant=variant,
            button_size=size,
        )