from pathlib import Path
from typing import Callable

from app.config import AppConfig
from app.logger import get_logger
from models.subtitle_segment import SubtitleSegment
from services.local_whisper_service import LocalWhisperService


logger = get_logger(__name__)


ProgressCallback = Callable[[int, str], None]


class TranscriptionService:
    def __init__(self, config: AppConfig):
        self.config = config

    def transcribe_audio(
        self,
        audio_path: Path,
        provider: str = "local",
        model: str = "small",
        language: str | None = "zh",
        duration_seconds: float = 0,
        progress_callback: ProgressCallback | None = None,
    ) -> list[SubtitleSegment]:
        logger.info(
            "Transcription request provider=%s model=%s language=%s",
            provider,
            model,
            language,
        )

        if provider == "local":
            service = LocalWhisperService(
                model_name=model,
                device="cpu",
                compute_type="int8",
                progress_callback=progress_callback,
            )

            return service.transcribe_audio(
                audio_path=audio_path,
                duration_seconds=duration_seconds,
                language=language,
            )

        if provider == "deepinfra":
            from services.deepinfra_transcription_service import DeepInfraTranscriptionService

            service = DeepInfraTranscriptionService(self.config)

            if progress_callback:
                progress_callback(35, "Uploading audio to DeepInfra...")

            segments = service.transcribe_audio(
                audio_path=audio_path,
                model=model,
                language=language,
            )

            if progress_callback:
                progress_callback(100, "Transcription complete")

            return segments

        raise ValueError(f"Unsupported transcription provider: {provider}")