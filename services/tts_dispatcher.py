"""TTS Dispatcher — routes each segment to Edge TTS or VoxCPM2 based on seg.voice prefix.

Voice prefix conventions
------------------------
  "edge:<label>"   → Microsoft Edge TTS, e.g. "edge:Piseth (Male)"
  "clone:<id>"     → VoxCPM2 voice clone, e.g. "clone:abc123def456"
  anything else    → Edge TTS with the raw value (legacy / no-prefix fallback)
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, TYPE_CHECKING

from app.logger import get_logger

if TYPE_CHECKING:
    from workers.cancel_token import CancelToken

logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]


class TtsDispatcher:
    """Synthesize all segments, routing each to the correct TTS backend."""

    def __init__(
        self,
        output_dir: Path | None = None,
        progress_callback: ProgressCallback | None = None,
        cancel_token: "CancelToken | None" = None,
    ) -> None:
        self.output_dir = output_dir
        self.progress_callback = progress_callback
        self._cancel = cancel_token

    def _check_cancel(self) -> None:
        if self._cancel:
            self._cancel.check()

    # ── public ───────────────────────────────────────────────────────────────

    def synthesize_segments(self, segments: list, video_stem: str) -> list:
        """Synthesize *segments* and return them with ``audio_path`` filled in."""
        if not segments:
            return segments

        edge_segs: list = []
        clone_segs: list = []

        for seg in segments:
            voice = getattr(seg, "voice", "") or ""
            if voice.startswith("clone:"):
                clone_segs.append(seg)
            else:
                edge_segs.append(seg)

        total = len(segments)
        results: dict = {}

        self._check_cancel()

        # ── Edge TTS ─────────────────────────────────────────────────────────
        if edge_segs:
            from services.edge_tts_service import EdgeTtsService

            edge_frac = len(edge_segs) / total

            def _edge_progress(pct: int, msg: str) -> None:
                if self.progress_callback:
                    self.progress_callback(int(pct * edge_frac), msg)

            service = EdgeTtsService(
                output_dir=self.output_dir,
                progress_callback=_edge_progress,
            )

            # Strip the "edge:" prefix so EdgeTtsService can look up the label
            # in its KHMER_VOICES dict.  Use a shallow copy per segment so we
            # never mutate the original segment objects (avoids corrupting the
            # results dict when segments are referenced from multiple lists).
            import copy
            edge_segs_copy = []
            for seg in edge_segs:
                seg_copy = copy.copy(seg)
                v = getattr(seg_copy, "voice", "") or ""
                if v.startswith("edge:"):
                    seg_copy.voice = v[len("edge:"):]
                edge_segs_copy.append(seg_copy)

            for seg in service.synthesize_segments(
                edge_segs_copy, video_stem, should_cancel=self._is_cancelled
            ):
                self._check_cancel()
                results[seg.index] = seg

        # ── VoxCPM2 clone ────────────────────────────────────────────────────
        self._check_cancel()
        if clone_segs:
            from services.voxcpm_service import VoxCpmService

            vox_service = VoxCpmService()
            clone_total = len(clone_segs)
            edge_done_pct = int(len(edge_segs) / total * 100)

            for ci, seg in enumerate(clone_segs):
                self._check_cancel()
                voice_id = (getattr(seg, "voice", "") or "").removeprefix("clone:")
                text = (
                    getattr(seg, "khmer_text", "") or
                    getattr(seg, "original_text", "") or ""
                ).strip()

                if not text:
                    logger.debug("Segment %d has no text — skipping VoxCPM.", seg.index)
                    results[seg.index] = seg
                    continue

                if self.progress_callback:
                    pct = edge_done_pct + int(
                        ci / clone_total * (100 - edge_done_pct) * 0.95
                    )
                    self.progress_callback(pct, f"VoxCPM generating {ci + 1}/{clone_total}…")

                out_path: Path | None = None
                if self.output_dir:
                    out_path = self.output_dir / f"{video_stem}_vox_{seg.index:04d}.wav"

                try:
                    out = vox_service.synthesize_with_voice_id(
                        text=text,
                        voice_id=voice_id,
                        output_path=out_path,
                        speed_percent=10,
                    )
                    seg.audio_path = str(out)
                    logger.debug("VoxCPM ok: seg=%d path=%s", seg.index, out)
                except Exception as exc:
                    from workers.cancel_token import WorkerCancelled
                    if isinstance(exc, WorkerCancelled):
                        raise
                    logger.exception("VoxCPM failed for segment %d.", seg.index)

                results[seg.index] = seg

        if self.progress_callback:
            self.progress_callback(100, "Voice generation complete")

        # Return in original order; fall back to unmodified seg for any missed.
        return [results.get(seg.index, seg) for seg in segments]

    def _is_cancelled(self) -> bool:
        return bool(self._cancel and self._cancel.is_cancelled)
