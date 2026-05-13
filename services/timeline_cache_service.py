import json
import hashlib
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from app.logger import get_logger
from app.paths import PROJECTS_CACHE_DIR
from models.subtitle_segment import SubtitleSegment
from models.timeline_cache import TimelineCache
from models.timeline_item import TimelineItem
from models.timeline_track import TimelineTrack


logger = get_logger(__name__)


class TimelineCacheService:
    def __init__(self):
        self.cache_dir = PROJECTS_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cache_path(self, video_path: Path) -> Path:
        key = hashlib.sha1(str(video_path).encode("utf-8")).hexdigest()[:10]
        safe_name = video_path.stem.replace(" ", "_")

        return self.cache_dir / f"{safe_name}_{key}.timeline.json"

    def exists(self, video_path: Path) -> bool:
        return self.get_cache_path(video_path).exists()

    def save(self, cache: TimelineCache) -> Path:
        video_path = Path(cache.video_path)
        cache_path = self.get_cache_path(video_path)

        with open(cache_path, "w", encoding="utf-8") as file:
            json.dump(
                self.to_json(cache),
                file,
                ensure_ascii=False,
                indent=2,
            )

        logger.info("Timeline cache saved: %s", cache_path)

        return cache_path

    def load(self, video_path: Path) -> TimelineCache | None:
        cache_path = self.get_cache_path(video_path)

        if not cache_path.exists():
            return None

        with open(cache_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        cache = TimelineCache(
            cache_version=data.get("cache_version", 1),
            video_path=data.get("video_path", ""),
            video_name=data.get("video_name", ""),
            video_folder=data.get("video_folder", ""),
            duration_ms=data.get("duration_ms", 0),
            fps=data.get("fps", 30.0),
            raw_audio_path=data.get("raw_audio_path"),
            vocals_path=data.get("vocals_path"),
            background_path=data.get("background_path"),
            tracks=[
                TimelineTrack(**track)
                for track in data.get("tracks", [])
            ],
            items=[
                TimelineItem(**item)
                for item in data.get("items", [])
            ],
            segments=[
                SubtitleSegment(**segment)
                for segment in data.get("segments", [])
            ],
        )

        logger.info("Timeline cache loaded: %s", cache_path)

        return cache

    def delete(self, video_path: Path) -> None:
        cache_path = self.get_cache_path(video_path)
        if cache_path.exists():
            cache_path.unlink()
            logger.info("Timeline cache deleted: %s", cache_path)

    def delete_all(self) -> None:
        deleted = 0
        for f in self.cache_dir.glob("*.timeline.json"):
            try:
                f.unlink()
                deleted += 1
            except OSError:
                logger.warning("Could not delete cache file: %s", f)
        logger.info("Deleted %d timeline cache file(s).", deleted)

    def to_json(self, value: Any):
        if is_dataclass(value):
            return asdict(value)

        return value