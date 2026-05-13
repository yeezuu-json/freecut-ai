import json
import subprocess
from pathlib import Path

from models.subtitle_segment import SubtitleSegment
from models.timeline_cache import TimelineCache
from models.timeline_item import TimelineItem
from models.timeline_track import TimelineTrack


class TimelineBuilderService:
    def build_from_video(
        self,
        video_path: Path,
        duration_ms: int,
        fps: float = 30.0,
    ) -> TimelineCache:
        duration_frames = self.ms_to_frames(duration_ms, fps)

        video_track = TimelineTrack(
            id="track_video",
            name="Video",
            kind="video",
            order=0,
            locked=True,
            muted=False,
            visible=True,
        )

        raw_audio_track = TimelineTrack(
            id="track_raw_audio",
            name="Raw Audio",
            kind="audio",
            order=1,
            locked=False,
            muted=True,
            visible=True,
        )

        background_track = TimelineTrack(
            id="track_background",
            name="Background",
            kind="audio",
            order=2,
            locked=False,
            muted=False,
            visible=True,
        )

        vocal_track = TimelineTrack(
            id="track_vocal",
            name="Original Vocal",
            kind="audio",
            order=3,
            locked=False,
            muted=True,
            visible=True,
        )

        khmer_voice_track = TimelineTrack(
            id="track_khmer_voice",
            name="Khmer Voice",
            kind="voice",
            order=4,
            locked=False,
            muted=False,
            visible=True,
        )

        tracks = [
            video_track,
            raw_audio_track,
            background_track,
            vocal_track,
            khmer_voice_track,
        ]

        # All five tracks get a full-span item immediately so the timeline
        # renders clips for every row.  Audio/voice items start with no
        # source_path (placeholder); attach_audio_sources / attach_tts_segments
        # will update them with real paths when available.
        items = [
            TimelineItem(
                id="item_video",
                type="video",
                track_id=video_track.id,
                from_frame=0,
                duration_in_frames=duration_frames,
                source_path=str(video_path),
                label=video_path.name,
            ),
            TimelineItem(
                id="item_raw_audio",
                type="raw_audio",
                track_id=raw_audio_track.id,
                from_frame=0,
                duration_in_frames=duration_frames,
                label="Raw Audio",
                muted=True,
            ),
            TimelineItem(
                id="item_background",
                type="background",
                track_id=background_track.id,
                from_frame=0,
                duration_in_frames=duration_frames,
                label="Background",
            ),
            TimelineItem(
                id="item_vocal",
                type="vocal",
                track_id=vocal_track.id,
                from_frame=0,
                duration_in_frames=duration_frames,
                label="Original Vocal",
                muted=True,
            ),
        ]

        return TimelineCache(
            video_path=str(video_path),
            video_name=video_path.name,
            video_folder=str(video_path.parent),
            duration_ms=duration_ms,
            fps=fps,
            tracks=tracks,
            items=items,
        )

    def attach_audio_sources(
        self,
        cache: TimelineCache,
        raw_audio_path: Path | None = None,
        vocals_path: Path | None = None,
        background_path: Path | None = None,
    ) -> TimelineCache:
        cache.raw_audio_path = str(raw_audio_path) if raw_audio_path else cache.raw_audio_path
        cache.vocals_path    = str(vocals_path)    if vocals_path    else cache.vocals_path
        cache.background_path = str(background_path) if background_path else cache.background_path

        # Update placeholder items in-place; the full-span items already exist
        # from build_from_video — just patch the source_path.
        updates: dict[str, str] = {}
        if raw_audio_path:
            updates["item_raw_audio"] = str(raw_audio_path)
        if background_path:
            updates["item_background"] = str(background_path)
        if vocals_path:
            updates["item_vocal"] = str(vocals_path)

        for item in cache.items:
            if item.id in updates:
                item.source_path = updates[item.id]

        return cache

    def attach_tts_segments(
        self,
        cache: TimelineCache,
        segments: list[SubtitleSegment],
    ) -> TimelineCache:
        cache.segments = segments

        # Remove old dubbed voice items before re-adding.
        cache.items = [
            item
            for item in cache.items
            if item.type != "dubbed_voice"
        ]

        for segment in segments:
            if not segment.audio_path:
                continue

            start_ms = self.srt_time_to_ms(segment.start_time)
            end_ms   = self.srt_time_to_ms(segment.end_time)
            slot_ms  = max(1, end_ms - start_ms)

            # Use the actual trimmed audio file's duration so the segment fits
            # the speech exactly — not the subtitle slot which may be shorter
            # (cutting off the last word) or longer (leaving dead air).
            audio_ms = self._get_audio_duration_ms(segment.audio_path) or slot_ms

            cache.items.append(
                TimelineItem(
                    id=f"item_dub_{segment.index}",
                    type="dubbed_voice",
                    track_id="track_khmer_voice",
                    from_frame=self.ms_to_frames(start_ms, cache.fps),
                    duration_in_frames=self.ms_to_frames(audio_ms, cache.fps),
                    source_path=segment.audio_path,
                    label=f"Voice {segment.index}",
                    linked_segment_id=str(segment.index),
                )
            )

        return cache

    def ms_to_frames(self, ms: int, fps: float) -> int:
        return int((ms / 1000) * fps)

    def srt_time_to_ms(self, value: str) -> int:
        hours, minutes, rest = value.split(":")
        seconds, millis = rest.split(",")

        return (
            int(hours) * 3_600_000
            + int(minutes) * 60_000
            + int(seconds) * 1000
            + int(millis)
        )

    @staticmethod
    def _get_audio_duration_ms(audio_path: str) -> int | None:
        """Return the actual playback duration of an audio file in milliseconds
        using ffprobe, or None if the file cannot be probed."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "json",
                    audio_path,
                ],
                capture_output=True, text=True, check=True,
            )
            data = json.loads(result.stdout)
            return int(float(data["format"]["duration"]) * 1000)
        except Exception:
            return None