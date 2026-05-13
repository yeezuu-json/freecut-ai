from dataclasses import dataclass, field

from models.subtitle_segment import SubtitleSegment
from models.timeline_item import TimelineItem
from models.timeline_track import TimelineTrack


@dataclass
class TimelineCache:
    cache_version: int = 1

    video_path: str = ""
    video_name: str = ""
    video_folder: str = ""

    duration_ms: int = 0
    fps: float = 30.0

    raw_audio_path: str | None = None
    vocals_path: str | None = None
    background_path: str | None = None

    tracks: list[TimelineTrack] = field(default_factory=list)
    items: list[TimelineItem] = field(default_factory=list)
    segments: list[SubtitleSegment] = field(default_factory=list)