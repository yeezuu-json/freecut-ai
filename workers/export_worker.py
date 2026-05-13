from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot

from app.logger import get_logger
from models.subtitle_segment import SubtitleSegment
from services.audio_service import AudioService


logger = get_logger(__name__)


class ExportWorker(QObject):
    """Exports a dubbed video (video + TTS voice + optional background stem) on a QThread."""

    progress_changed = Signal(int, str)
    finished = Signal(str)   # output path as str
    failed = Signal(str)

    def __init__(
        self,
        video_path: Path,
        segments: list[SubtitleSegment],
        output_path: Path,
        background_path: Optional[Path] = None,
        background_volume: float = 0.8,
        dubbed_volume: float = 1.0,
    ) -> None:
        super().__init__()
        self.video_path = video_path
        self.segments = segments
        self.output_path = output_path
        self.background_path = background_path
        self.background_volume = background_volume
        self.dubbed_volume = dubbed_volume
        self._service = AudioService()

    @Slot()
    def run(self) -> None:
        try:
            self.progress_changed.emit(0, "Starting export…")
            result = self._service.export_dubbed_video(
                video_path=self.video_path,
                segments=self.segments,
                output_path=self.output_path,
                background_path=self.background_path,
                background_volume=self.background_volume,
                dubbed_volume=self.dubbed_volume,
                progress_callback=lambda p, m: self.progress_changed.emit(p, m),
            )
            logger.info("Dubbed video export finished: %s", result)
            self.finished.emit(str(result))
        except Exception as exc:
            logger.exception("Dubbed video export failed.")
            self.failed.emit(str(exc))
