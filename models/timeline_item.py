from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
import uuid

TimelineItemType = Literal[
    "video",
    "raw_audio",
    "background",
    "vocal",
    "dubbed_voice",
]

@dataclass
class TimelineItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    type: TimelineItemType = "dubbed_voice"

    track_id: str = ""

    # Timeline position
    from_frame: int = 0
    duration_in_frames: int = 0

    # Media source
    source_path: str = ""

    # UI label
    label: str = ""

    # Audio settings
    volume: float = 1.0
    muted: bool = False

    # Optional link back to subtitle/tts segment
    linked_segment_id: str | None = None

    @property
    def end_frame(self) -> int:
        return self.from_frame + self.duration_in_frames