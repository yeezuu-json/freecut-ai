from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.logger import get_logger
from services.audio_service import AudioService


logger = get_logger(__name__)


class VideoToMp3Worker(QObject):
    """Converts a video file to MP3 on a background QThread."""

    progress_changed = Signal(int, str)
    finished = Signal(str)   # output path as str
    failed = Signal(str)

    def __init__(self, video_path: Path, output_path: Path, bitrate: str = "320k") -> None:
        super().__init__()
        self.video_path = video_path
        self.output_path = output_path
        self.bitrate = bitrate
        self._service = AudioService()

    @Slot()
    def run(self) -> None:
        try:
            self.progress_changed.emit(0, "Starting MP3 export…")
            result = self._service.export_to_mp3(
                video_path=self.video_path,
                output_path=self.output_path,
                bitrate=self.bitrate,
                progress_callback=lambda p, m: self.progress_changed.emit(p, m),
            )
            logger.info("MP3 export finished: %s", result)
            self.finished.emit(str(result))
        except Exception as exc:
            logger.exception("MP3 export failed.")
            self.failed.emit(str(exc))
