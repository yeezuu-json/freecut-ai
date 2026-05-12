from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from models.project import Project

class AppState(QObject):
    video_changed = Signal(object)

    def __init__(self):
        super().__init__()

        self.current_project: Optional[Project] = None

    def set_video(self, video_path: Path):
        self.current_project = Project(video_path=video_path)
        self.video_changed.emit(self.current_project)

    def has_video(self) -> bool:
        return self.current_project is not None

    def get_video_path(self) -> Optional[Path]:
        if self.current_project is None:
            return None

        return self.current_project.video_path