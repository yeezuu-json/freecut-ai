from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.logger import get_logger
from services.tts_dispatcher import TtsDispatcher


logger = get_logger(__name__)


class TtsWorker(QObject):
    """Generates per-segment TTS audio on a background QThread.

    Routes each segment to Edge TTS or VoxCPM2 based on ``seg.voice`` prefix:
      "edge:<label>"  → Microsoft Edge TTS
      "clone:<id>"    → VoxCPM2 voice clone
      anything else   → Edge TTS (legacy / fallback)

    Signals:
        progress_changed(int, str)  – 0-100 percentage + status message.
        finished(list)              – list[SubtitleSegment] with audio_path filled.
        failed(str)                 – error message.
    """

    progress_changed = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        segments: list,
        video_stem: str,
        output_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.segments = segments
        self.video_stem = video_stem
        self.output_dir = output_dir

    @Slot()
    def run(self) -> None:
        try:
            self.progress_changed.emit(0, "Starting voice generation…")

            dispatcher = TtsDispatcher(
                output_dir=self.output_dir,
                progress_callback=lambda p, m: self.progress_changed.emit(int(p), m),
            )

            result = dispatcher.synthesize_segments(
                segments=self.segments,
                video_stem=self.video_stem,
            )

            logger.info(
                "TTS finished. %d/%d segments have audio.",
                sum(1 for s in result if s.audio_path),
                len(result),
            )
            self.finished.emit(result)

        except Exception as exc:
            logger.exception("TTS failed.")
            self.failed.emit(str(exc))
