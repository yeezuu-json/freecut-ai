from pathlib import Path

from PySide6.QtCore import Qt, QSize, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QLabel, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from ui.components.app_button import AppButton
from ui.components.icons import app_icon
from utils.font_manager import get_google_sans


class VideoPreviewPanel(QWidget):
    def __init__(self):
        super().__init__()

        self.video_path: Path | None = None

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self.audio_output.setVolume(0.8)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Video Preview")
        title.setObjectName("sectionTitle")
        title.setFont(get_google_sans(size=11, weight="Bold"))

        self.preview_box = QFrame()
        self.preview_box.setObjectName("videoPreviewBox")
        self.preview_box.setMinimumHeight(520)

        self.preview_layout = QVBoxLayout(self.preview_box)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.setSpacing(0)

        self.video_widget = QVideoWidget()
        self.video_widget.setObjectName("videoWidget")
        self.video_widget.hide()

        self.empty_widget = QWidget()
        self.empty_widget.setObjectName("emptyVideoWidget")

        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(10)

        self.empty_icon = QLabel()
        self.empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_icon.setPixmap(
            app_icon(
                "video-off",
                fallback="fa6s.video-slash",
                color="#c4c9d1",
                size=34,
            ).pixmap(QSize(34, 34))
        )

        self.video_name_label = QLabel("No Video\nLoaded")
        self.video_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_name_label.setObjectName("emptyVideoText")
        self.video_name_label.setFont(get_google_sans(size=15, weight="Bold"))
        self.video_name_label.setWordWrap(True)

        self.video_path_label = QLabel("")
        self.video_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_path_label.setObjectName("videoPathText")
        self.video_path_label.setFont(get_google_sans(size=9, weight="Regular"))
        self.video_path_label.setWordWrap(True)

        empty_layout.addStretch()
        empty_layout.addWidget(self.empty_icon)
        empty_layout.addWidget(self.video_name_label)
        empty_layout.addWidget(self.video_path_label)
        empty_layout.addStretch()

        self.preview_layout.addWidget(self.video_widget)
        self.preview_layout.addWidget(self.empty_widget)

        self.player.setVideoOutput(self.video_widget)

        controls = QHBoxLayout()
        controls.setSpacing(6)

        self.play_button = AppButton(
            text="Play",
            icon=app_icon("player-play", fallback="fa6s.play", color="#ffffff"),
            variant="success",
            button_size="sm",
            disabled=True,
            on_click=self.toggle_play_pause,
        )

        self.stop_button = AppButton(
            text="Stop",
            icon=app_icon("player-stop", fallback="fa6s.stop", color="#ffffff"),
            variant="danger",
            button_size="sm",
            disabled=True,
            on_click=self.stop_video,
        )

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("mutedText")
        self.time_label.setFont(get_google_sans(size=9))

        controls.addWidget(self.play_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.time_label)
        controls.addStretch()

        tools_title = QLabel("Tools")
        tools_title.setObjectName("sectionTitle")
        tools_title.setFont(get_google_sans(size=10, weight="Bold"))

        auto_sync = AppButton(
            text="Auto-Sync",
            icon=app_icon("wand", fallback="fa6s.wand-magic-sparkles", color="#ffffff"),
            variant="danger",
            button_size="tool",
            full_width=True,
        )

        auto_speed = AppButton(
            text="Auto-Speed",
            icon=app_icon("gauge", fallback="fa6s.gauge-high", color="#ffffff"),
            variant="warning",
            button_size="tool",
            full_width=True,
        )

        cutter = AppButton(
            text="Video Cutter",
            icon=app_icon("scissors", fallback="fa6s.scissors", color="#ffffff"),
            variant="purple",
            button_size="tool",
            full_width=True,
        )

        license_label = QLabel("License: Lifetime")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_label.setObjectName("licenseText")
        license_label.setFont(get_google_sans(size=9, weight="Bold"))

        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)

        self.duration = 0

        layout.addWidget(title)
        layout.addWidget(self.preview_box, 1)
        layout.addLayout(controls)
        layout.addWidget(tools_title)
        layout.addWidget(auto_sync)
        layout.addWidget(auto_speed)
        layout.addWidget(cutter)
        layout.addWidget(license_label)

    def set_video(self, video_path: Path):
        self.video_path = video_path

        self.empty_widget.hide()
        self.video_widget.show()

        self.player.setSource(QUrl.fromLocalFile(str(video_path)))

        self.video_name_label.setText(video_path.name)
        self.video_path_label.setText(str(video_path.parent))

        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.time_label.setText("00:00 / --:--")

    def clear_video(self):
        self.video_path = None

        self.player.stop()
        self.player.setSource(QUrl())

        self.video_widget.hide()
        self.empty_widget.show()

        self.video_name_label.setText("No Video\nLoaded")
        self.video_path_label.setText("")

        self.play_button.setDisabled(True)
        self.stop_button.setDisabled(True)
        self.time_label.setText("00:00 / 00:00")

    def toggle_play_pause(self):
        if self.video_path is None:
            return

        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()


    def stop_video(self):
        self.player.stop()
        self.set_play_button_state(is_playing=False)


    def on_playback_state_changed(self, state):
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.set_play_button_state(is_playing)


    def set_play_button_state(self, is_playing: bool):
        if is_playing:
            self.play_button.setText("Pause")
            self.play_button.setIcon(
                app_icon("player-pause", fallback="fa6s.pause", color="#ffffff")
            )
            self.play_button.variant_name = "warning"
        else:
            self.play_button.setText("Play")
            self.play_button.setIcon(
                app_icon("player-play", fallback="fa6s.play", color="#ffffff")
            )
            self.play_button.variant_name = "success"

        self.play_button.apply_style()

    def stop_video(self):
        self.player.stop()

    def update_duration(self, duration: int):
        self.duration = duration
        self.update_time_label(self.player.position(), duration)

    def update_position(self, position: int):
        self.update_time_label(position, self.duration)

    def update_time_label(self, position: int, duration: int):
        current = self.format_time(position)
        total = self.format_time(duration)

        self.time_label.setText(f"{current} / {total}")

    def format_time(self, ms: int) -> str:
        seconds = ms // 1000
        minutes = seconds // 60
        seconds = seconds % 60

        return f"{minutes:02d}:{seconds:02d}"