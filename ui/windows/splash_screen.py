from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Loading")
        self.setFixedSize(420, 260)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.SplashScreen
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.container = QWidget()
        self.container.setObjectName("splashContainer")

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(16)

        self.title_label = QLabel("My PySide6 App")
        self.title_label.setObjectName("splashTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.message_label = QLabel("Starting...")
        self.message_label.setObjectName("splashMessage")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.version_label = QLabel("Version 1.0.0")
        self.version_label.setObjectName("splashVersion")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch()
        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.version_label)
        layout.addStretch()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self.container)

        self.apply_style()

    def update_progress(self, value: int, message: str):
        self.progress_bar.setValue(value)
        self.message_label.setText(message)

    def apply_style(self):
        self.setStyleSheet("""
            #splashContainer {
                background-color: #111827;
                border-radius: 18px;
            }

            #splashTitle {
                color: white;
                font-size: 24px;
                font-weight: 700;
            }

            #splashMessage {
                color: #d1d5db;
                font-size: 14px;
            }

            #splashVersion {
                color: #9ca3af;
                font-size: 12px;
            }

            QProgressBar {
                height: 8px;
                border-radius: 4px;
                background-color: #374151;
            }

            QProgressBar::chunk {
                border-radius: 4px;
                background-color: #2563eb;
            }
        """)