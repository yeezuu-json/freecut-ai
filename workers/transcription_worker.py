from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from app.config import AppConfig
from app.logger import get_logger
from services.audio_service import AudioService
from services.transcription_service import TranscriptionService


logger = get_logger(__name__)


class TranscriptionWorker(QObject):
    progress_changed = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        video_path: Path,
        provider: str,
        model: str,
        language: str | None = "zh",
        vocals_path: Path | None = None,
    ):
        super().__init__()

        self.config = config
        self.video_path = video_path
        self.provider = provider
        self.model = model
        self.language = language
        self.vocals_path = vocals_path  # preferred source; falls back to video

        self.audio_service = AudioService()
        self.transcription_service = TranscriptionService(config)

    @Slot()
    def run(self):
        try:
            self.progress_changed.emit(5, "Checking video duration...")
            duration_seconds = self.audio_service.get_duration_seconds(self.video_path)

            if self.vocals_path and self.vocals_path.exists():
                self.progress_changed.emit(10, "Preparing vocals stem for transcription...")
                # Convert the Demucs vocals WAV to 16 kHz mono for Whisper.
                audio_path = self.audio_service.extract_audio_for_transcription(
                    self.vocals_path
                )
                self.progress_changed.emit(15, "Vocals stem ready (background noise removed)")
            else:
                self.progress_changed.emit(10, "Extracting audio from video...")
                audio_path = self.audio_service.extract_audio_for_transcription(self.video_path)
                self.progress_changed.emit(15, "Audio extracted")

            segments = self.transcription_service.transcribe_audio(
                audio_path=audio_path,
                provider=self.provider,
                model=self.model,
                language=self.language,
                duration_seconds=duration_seconds,
                progress_callback=self.emit_progress,
            )

            self.progress_changed.emit(100, "Transcription complete")

            logger.info(
                "Transcription finished. provider=%s model=%s segments=%s",
                self.provider,
                self.model,
                len(segments),
            )

            self.finished.emit(segments)

        except Exception as error:
            logger.exception("Transcription failed.")
            self.failed.emit(str(error))

    def emit_progress(self, value: int, message: str):
        self.progress_changed.emit(value, message)