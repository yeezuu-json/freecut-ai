from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from app.logger import get_logger
from app.state import AppState
from ui.components.editor_toolbar import EditorToolbar
from ui.components.status_bar_panel import StatusBarPanel
from ui.components.transcript_table_view import TranscriptTableView
from ui.components.timeline_editor import TimelineEditor
from ui.components.video_effects_panel import VideoEffectsPanel
from ui.components.video_preview_panel import VideoPreviewPanel


logger = get_logger(__name__)


class EditorLayout(QWidget):
    def __init__(self):
        super().__init__()

        self.state = AppState()

        self.setObjectName("editorRoot")

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 6)
        root_layout.setSpacing(10)

        self.left_panel = self.build_left_panel()
        self.right_panel = self.build_right_panel()

        root_layout.addWidget(self.left_panel, 0)
        root_layout.addWidget(self.right_panel, 1)

        self.connect_signals()

    def build_left_panel(self):
        panel = QFrame()
        panel.setObjectName("leftPanel")
        panel.setFixedWidth(330)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.video_preview = VideoPreviewPanel()

        layout.addWidget(self.video_preview, 1)

        return panel

    def build_right_panel(self):
        panel = QFrame()
        panel.setObjectName("rightPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.toolbar = EditorToolbar()
        self.transcript_table = TranscriptTableView()
        self.timeline_editor = TimelineEditor()
        self.effects_panel = VideoEffectsPanel()
        self.status_bar = StatusBarPanel()

        layout.addWidget(self.toolbar)
        layout.addWidget(self.transcript_table, 2)
        layout.addWidget(self.timeline_editor, 2)
        layout.addWidget(self.effects_panel)
        layout.addWidget(self.status_bar)

        return panel

    def connect_signals(self):
        self.toolbar.load_video_requested.connect(self.select_video)
        self.state.video_changed.connect(self.on_video_changed)

    def select_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video",
            str(Path.home() / "Desktop"),
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)",
        )

        if not file_path:
            logger.info("Video selection cancelled.")
            return

        video_path = Path(file_path)

        if not video_path.exists():
            logger.warning("Selected video does not exist: %s", video_path)
            return

        logger.info("Selected video: %s", video_path)

        self.state.set_video(video_path)

    def on_video_changed(self, project):
        logger.info("Current project video: %s", project.video_path)

        self.video_preview.set_video(project.video_path)