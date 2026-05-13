import asyncio
import subprocess
import tempfile
import threading
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
        # Create ONE event loop for the entire session and run it on a
        # dedicated thread so it never conflicts with Qt's event loop.
        loop = asyncio.new_event_loop()
        loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
        loop_thread.start()

        total = len(segments)
        results = []

        try:
            for idx, seg in enumerate(segments):
                pct = int(idx / total * 95)
                self._emit(pct, f"Generating voice {idx + 1}/{total}…")

                text = seg.khmer_text.strip() or seg.original_text.strip()
                if not text:
                    logger.debug("Segment %d has no text – skipping TTS.", seg.index)
                    results.append(seg)
                    continue

                voice  = KHMER_VOICES.get(seg.voice, KHMER_VOICES["Default"])
                pitch  = self._to_hz_offset(seg.pitch)
                rate   = self._to_rate_str(seg.speed)
                volume = self._to_volume_str(seg.volume)

                out_path = self.output_dir / f"{video_stem}_seg{seg.index:04d}.mp3"

                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self._synthesize_one(text, voice, pitch, rate, volume, out_path),
                        loop,
                    )
                    future.result(timeout=30)
                    # Strip leading and trailing silence so voices sit flush on
                    # the timeline without dead air before/after the speech.
                    self._trim_silence(out_path)
                    seg.audio_path = str(out_path)
                    logger.debug("TTS ok: seg=%d path=%s", seg.index, out_path)
                except Exception:
                    logger.exception("TTS failed for segment %d.", seg.index)

                results.append(seg)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            loop_thread.join(timeout=5)
            loop.close()

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

    @staticmethod
    def _trim_silence(path: Path, threshold_db: int = -40) -> None:
        """
        Use ffmpeg silenceremove to strip leading and trailing silence from the
        TTS MP3 file in-place.

        Strategy: two-pass via areverse so the same silenceremove filter handles
        both ends reliably:
          1. Strip leading silence.
          2. Reverse audio → strip new leading silence (= original trailing) → reverse back.

        A small tail buffer (0.05 s) is kept at the end so the very last phoneme
        is not clipped by encoder look-ahead.
        """
        tmp = path.with_suffix(".trim_tmp.mp3")
        silence_filter = (
            f"silenceremove=start_periods=1:start_silence=0.03:start_threshold={threshold_db}dB,"
            f"areverse,"
            f"silenceremove=start_periods=1:start_silence=0.05:start_threshold={threshold_db}dB,"
            f"areverse"
        )
        cmd = [
            "ffmpeg", "-loglevel", "error", "-y",
            "-i", str(path),
            "-af", silence_filter,
            "-c:a", "libmp3lame", "-q:a", "4",
            str(tmp),
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            if tmp.exists() and tmp.stat().st_size > 0:
                tmp.replace(path)
            else:
                tmp.unlink(missing_ok=True)
        except Exception:
            logger.warning("Silence trim failed for %s – keeping original.", path)
            tmp.unlink(missing_ok=True)

    def _emit(self, pct: int, msg: str) -> None:
        if self.progress_callback:
            self.progress_callback(pct, msg)
