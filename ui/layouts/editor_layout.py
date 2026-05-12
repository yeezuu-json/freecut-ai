from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout
from ui.components.editor_toolbar import EditorToolbar
from ui.components.status_bar_panel import StatusBarPanel
from ui.components.timeline_editor import TimelineEditor
from ui.components.transcript_table_view import TranscriptTableView
from ui.components.video_effects_panel import VideoEffectsPanel
from ui.components.video_preview_panel import VideoPreviewPanel

class EditorLayout(QFrame):
    def __init__(self):
        super().__init__()

        self.setObjectName("editorRoot")

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 6)
        root_layout.setSpacing(10)

        self.left_panel = self.build_left_panel()
        self.right_panel = self.build_right_panel()

        root_layout.addWidget(self.left_panel, 0)
        root_layout.addWidget(self.right_panel, 1)

    def build_left_panel(self) -> QFrame:
        leftPanel = QFrame()
        leftPanel.setObjectName("editorLeftPanel")
        leftPanel.setFixedWidth(330)

        layout = QVBoxLayout(leftPanel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Video Preview Panel
        videoPreviewPanel = VideoPreviewPanel()
        layout.addWidget(videoPreviewPanel)

        return leftPanel
    
    def build_right_panel(self) -> QFrame:
        rightPanel = QFrame()
        rightPanel.setObjectName("editorRightPanel")

        rightPanelLayout = QVBoxLayout(rightPanel)
        rightPanelLayout.setContentsMargins(0, 0, 0, 0)
        rightPanelLayout.setSpacing(8)

        # Top Bar
        editorToolbar = EditorToolbar()
        rightPanelLayout.addWidget(editorToolbar)

        # Transcribe Table
        subtitleTable = TranscriptTableView()
        rightPanelLayout.addWidget(subtitleTable)

        # Timeline editor
        timelineEditor = TimelineEditor()
        rightPanelLayout.addWidget(timelineEditor)

        # Video effects
        videoEffectsPanel = VideoEffectsPanel()
        rightPanelLayout.addWidget(videoEffectsPanel)

        # Status Bar
        statusBarPanel = StatusBarPanel()
        rightPanelLayout.addWidget(statusBarPanel)

        return rightPanel