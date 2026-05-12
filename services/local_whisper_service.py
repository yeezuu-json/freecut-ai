from pathlib import Path
from typing import Callable

from faster_whisper import WhisperModel

from app.logger import get_logger
from models.subtitle_segment import SubtitleSegment


logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]

class LocalWhisperService:
    def __init__(
        self,
        model_name: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        progress_callback: ProgressCallback | None = None,
    ):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.progress_callback = progress_callback

        self.emit_progress(18, f"Loading local Whisper model: {model_name}")
        
        logger.info(
            "Loading local Whisper model=%s device=%s compute_type=%s",
            model_name,
            device,
            compute_type,
        )

        self.model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
        )

    def emit_progress(self, value: int, message: str):
        if self.progress_callback:
            self.progress_callback(value, message)
        else:
            logger.warning("No progress callback provided. Progress not emitted.")
            return

    def transcribe_audio(
        self,
        audio_path: Path,
        duration_seconds: float,
        language: str | None = "zh",
    ) -> list[SubtitleSegment]:
        logger.info("Local transcription started: %s", audio_path)

        self.emit_progress(35, "Transcribing audio...")

        segments_iter, info = self.model.transcribe(
            str(audio_path),
            language=language or None,
            beam_size=5,
            vad_filter=True,
        )

        logger.info(
            "Detected language=%s probability=%.2f",
            info.language,
            info.language_probability,
        )

        segments: list[SubtitleSegment] = []

        for index, segment in enumerate(segments_iter, start=1):
            segments.append(
                SubtitleSegment(
                    index=index,
                    start_time=self.seconds_to_srt_time(segment.start),
                    end_time=self.seconds_to_srt_time(segment.end),
                    original_text=segment.text.strip(),
                    khmer_text="",
                )
            )

            if duration_seconds > 0:
                transcribe_percent = min(segment.end / duration_seconds, 1.0)
                progress = 35 + int(transcribe_percent * 60)

                self.emit_progress(
                    progress,
                    f"Transcribing... {progress}%",
                )

        self.emit_progress(100, "Transcription complete")

        logger.info("Local transcription finished. segments=%s", len(segments))

        return segments

    def seconds_to_srt_time(self, seconds: float) -> str:
        milliseconds_total = int(seconds * 1000)

        hours = milliseconds_total // 3_600_000
        milliseconds_total %= 3_600_000

        minutes = milliseconds_total // 60_000
        milliseconds_total %= 60_000

        secs = milliseconds_total // 1000
        millis = milliseconds_total % 1000

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"