import asyncio
import tempfile
from pathlib import Path
from typing import Callable

from app.logger import get_logger


logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]

# Available Khmer neural voices from Microsoft Edge TTS.
KHMER_VOICES: dict[str, str] = {
    "Default":        "km-KH-PisethNeural",   # male
    "Piseth (Male)":  "km-KH-PisethNeural",
    "Sreymom (Female)": "km-KH-SreymomNeural",
}


def list_khmer_voice_labels() -> list[str]:
    return list(KHMER_VOICES.keys())


class EdgeTtsService:
    """Generate per-segment audio using Microsoft Edge TTS (free, online)."""

    def __init__(
        self,
        output_dir: Path | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        if output_dir is None:
            output_dir = Path(tempfile.gettempdir()) / "freecut_ai" / "tts"
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.progress_callback = progress_callback

    # ── public ───────────────────────────────────────────────────────────────

    def synthesize_segments(
        self,
        segments,           # list[SubtitleSegment]
        video_stem: str,
    ) -> list:              # returns the same list with audio_path filled in
        total = len(segments)
        results = []

        for idx, seg in enumerate(segments):
            pct = int(idx / total * 95)
            self._emit(pct, f"Generating voice {idx + 1}/{total}…")

            text = seg.khmer_text.strip() or seg.original_text.strip()
            if not text:
                logger.debug("Segment %d has no text – skipping TTS.", seg.index)
                results.append(seg)
                continue

            voice   = KHMER_VOICES.get(seg.voice, KHMER_VOICES["Default"])
            pitch   = self._to_hz_offset(seg.pitch)
            rate    = self._to_rate_str(seg.speed)
            volume  = self._to_volume_str(seg.volume)

            out_path = self.output_dir / f"{video_stem}_seg{seg.index:04d}.mp3"

            try:
                asyncio.run(
                    self._synthesize_one(text, voice, pitch, rate, volume, out_path)
                )
                seg.audio_path = str(out_path)
                logger.debug("TTS ok: seg=%d path=%s", seg.index, out_path)
            except Exception:
                logger.exception("TTS failed for segment %d.", seg.index)

            results.append(seg)

        self._emit(100, "Voice generation complete")
        return results

    # ── private ──────────────────────────────────────────────────────────────

    @staticmethod
    async def _synthesize_one(
        text: str,
        voice: str,
        pitch: str,
        rate: str,
        volume: str,
        out_path: Path,
    ) -> None:
        import edge_tts
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            pitch=pitch,
            rate=rate,
            volume=volume,
        )
        await communicate.save(str(out_path))

    @staticmethod
    def _to_hz_offset(pitch_str: str) -> str:
        """Convert semitone integer string to Edge TTS Hz offset string."""
        try:
            semitones = int(pitch_str)
            hz = int(semitones * 10)          # rough: 1 semitone ≈ 10 Hz offset
            sign = "+" if hz >= 0 else ""
            return f"{sign}{hz}Hz"
        except (ValueError, TypeError):
            return "+0Hz"

    @staticmethod
    def _to_rate_str(speed_str: str) -> str:
        """Convert speed multiplier to Edge TTS rate percentage string."""
        try:
            rate = float(speed_str)
            pct = int((rate - 1.0) * 100)
            sign = "+" if pct >= 0 else ""
            return f"{sign}{pct}%"
        except (ValueError, TypeError):
            return "+0%"

    @staticmethod
    def _to_volume_str(volume_str: str) -> str:
        """Convert dB volume adjustment to Edge TTS volume percentage string."""
        try:
            db = float(volume_str)
            pct = int(db * 2)                 # rough: 0 dB = +0%, +6 dB ≈ +12%
            pct = max(-100, min(100, pct))
            sign = "+" if pct >= 0 else ""
            return f"{sign}{pct}%"
        except (ValueError, TypeError):
            return "+0%"

    def _emit(self, pct: int, msg: str) -> None:
        if self.progress_callback:
            self.progress_callback(pct, msg)
