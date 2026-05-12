from dataclasses import dataclass
from pathlib import Path

@dataclass
class Project:
    video_path: Path

    @property
    def video_name(self) -> str:
        return self.video_path.name

    @property
    def video_folder(self) -> Path:
        return self.video_path.parent

    @property
    def video_stem(self) -> str:
        return self.video_path.stem