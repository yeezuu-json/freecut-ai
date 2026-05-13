from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from models.project import Project
from models.subtitle_segment import SubtitleSegment


class AppState(QObject):
    video_changed = Signal(object)
    transcript_changed = Signal(object)
    translation_changed = Signal(object)

    def __init__(self):
        super().__init__()

        self.current_project: Optional[Project] = None
        self.segments: list[SubtitleSegment] = []

        self.has_transcript = False
        self.has_khmer_translation = False

    def set_video(self, video_path: Path):
        self.current_project = Project(video_path=video_path)
        self.video_changed.emit(self.current_project)

    def has_video(self) -> bool:
        return self.current_project is not None

    def get_video_path(self) -> Optional[Path]:
        if self.current_project is None:
            return None

        return self.current_project.video_path

    def get_transcript(self) -> list[SubtitleSegment]:
        return self.segments

    def set_transcript(self, segments: list[SubtitleSegment]):
        self.segments = segments
        self.has_transcript = True
        self.has_khmer_translation = False
        self.transcript_changed.emit(segments)

    def set_translation(self, segments: list[SubtitleSegment]):
        self.segments = segments
        self.has_khmer_translation = True
        self.translation_changed.emit(segments)

    def update_segments_from_table(self, segments: list[SubtitleSegment]):
        self.segments = segments