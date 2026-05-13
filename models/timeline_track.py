from dataclasses import dataclass, field
from typing import Literal
import uuid


TrackKind = Literal[
    "video",
    "audio",
    "voice",
]


@dataclass
class TimelineTrack:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    kind: TrackKind = "audio"

    order: int = 0

    locked: bool = False
    muted: bool = False
    visible: bool = True