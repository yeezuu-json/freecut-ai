from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from utils.font_manager import get_google_sans


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Loading")
        self.setFixedSize(480, 340)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.SplashScreen
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.container = QWidget()
        self.container.setObjectName("splashContainer")

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(34, 30, 34, 26)
        layout.setSpacing(14)

        self.title_label = QLabel("FreeCut AI")
        self.title_label.setObjectName("splashTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setFont(get_google_sans(size=24, weight="Bold"))

        self.subtitle_label = QLabel("AI Dubbing Studio")
        self.subtitle_label.setObjectName("splashSubtitle")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setFont(get_google_sans(size=11, weight="Medium"))

        self.message_label = QLabel("Starting...")
        self.message_label.setObjectName("splashMessage")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setFont(get_google_sans(size=10, weight="Medium"))

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("splashProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        self.status_box = QWidget()
        self.status_box.setObjectName("splashStatusBox")

        status_layout = QVBoxLayout(self.status_box)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(8)

        self.config_status = self.create_status_label("Config", "Waiting")
        self.logger_status = self.create_status_label("Logger", "Waiting")
        self.font_status = self.create_status_label("Fonts", "Waiting")
        self.ffmpeg_status = self.create_status_label("FFmpeg", "Waiting")
        self.model_status = self.create_status_label("AI Models", "Waiting")

        status_layout.addWidget(self.config_status)
        status_layout.addWidget(self.logger_status)
        status_layout.addWidget(self.font_status)
        status_layout.addWidget(self.ffmpeg_status)
        status_layout.addWidget(self.model_status)

        self.version_label = QLabel("v1.0.0")
        self.version_label.setObjectName("splashVersion")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setFont(get_google_sans(size=9, weight="Regular"))

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addSpacing(4)
        layout.addWidget(self.message_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_box)
        layout.addStretch()
        layout.addWidget(self.version_label)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.container)

        self.apply_style()

    def create_status_label(self, name: str, status: str) -> QLabel:
        label = QLabel(f"{name}: {status}")
        label.setObjectName("splashStatusItem")
        label.setFont(get_google_sans(size=9, weight="Medium"))
        return label

    def update_progress(self, value: int, message: str):
        self.progress_bar.setValue(value)
        self.message_label.setText(message)

    def set_version(self, version: str):
        self.version_label.setText(f"v{version}")

    def set_status(self, key: str, status: str, ok: bool | None = None):
        icon = "●"

        if ok is True:
            icon = "✓"
        elif ok is False:
            icon = "✕"

        text = f"{icon} {key}: {status}"

        if key == "Config":
            self.config_status.setText(text)
            self.set_status_property(self.config_status, ok)
        elif key == "Logger":
            self.logger_status.setText(text)
            self.set_status_property(self.logger_status, ok)
        elif key == "Fonts":
            self.font_status.setText(text)
            self.set_status_property(self.font_status, ok)
        elif key == "FFmpeg":
            self.ffmpeg_status.setText(text)
            self.set_status_property(self.ffmpeg_status, ok)
        elif key == "AI Models":
            self.model_status.setText(text)
            self.set_status_property(self.model_status, ok)

    def set_status_property(self, label: QLabel, ok: bool | None):
        if ok is True:
            label.setProperty("status", "success")
        elif ok is False:
            label.setProperty("status", "error")
        else:
            label.setProperty("status", "pending")

        label.style().unpolish(label)
        label.style().polish(label)

    def apply_style(self):
        self.setStyleSheet("""
            #splashContainer {
                background-color: #111827;
                border-radius: 20px;
            }

            #splashTitle {
                color: #ffffff;
                font-size: 24px;
                font-weight: 700;
            }

            #splashSubtitle {
                color: #93c5fd;
                font-size: 12px;
                font-weight: 600;
            }

            #splashMessage {
                color: #d1d5db;
                font-size: 13px;
            }

            #splashVersion {
                color: #9ca3af;
                font-size: 12px;
            }

            #splashProgress {
                height: 10px;
                border-radius: 5px;
                background-color: #374151;
                color: #ffffff;
                text-align: center;
                font-size: 9px;
                font-weight: 700;
            }

            #splashProgress::chunk {
                border-radius: 5px;
                background-color: #2563eb;
            }

            #splashStatusBox {
                background-color: #1f2937;
                border: 1px solid #374151;
                border-radius: 14px;
            }

            #splashStatusItem {
                color: #d1d5db;
                font-size: 12px;
            }

            #splashStatusItem[status="success"] {
                color: #86efac;
            }

            #splashStatusItem[status="error"] {
                color: #fca5a5;
            }

            #splashStatusItem[status="pending"] {
                color: #facc15;
            }
        """)