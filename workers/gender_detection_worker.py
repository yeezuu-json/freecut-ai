from PySide6.QtCore import QObject, Signal, Slot

from app.config import AppConfig
from app.logger import get_logger
from models.subtitle_segment import SubtitleSegment
from services.gender_detection_service import GenderDetectionService

logger = get_logger(__name__)


class GenderDetectionWorker(QObject):
    progress_changed = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        segments: list[SubtitleSegment],
        dialogue_language: str | None = None,
        api_key: str | None = None,
    ):
        super().__init__()
        self.config = config
        self.segments = segments
        self.dialogue_language = dialogue_language
        self.api_key = api_key

    @Slot()
    def run(self) -> None:
        try:
            self.progress_changed.emit(5, "Preparing gender detection…")

            source_lang = (
                self.dialogue_language
                or self.config.translation_source_language
            )
            service = GenderDetectionService(
                model_name=self.config.translation_model,
                source_language=source_lang,
                api_key=self.api_key or self.config.gemini_api_key,
                progress_callback=self._on_progress,
            )

            texts = [_dialogue_text_for_gender(s) for s in self.segments]

            genders = service.detect_genders(texts)

            for seg, gender in zip(self.segments, genders):
                seg.gender = gender

            self.progress_changed.emit(100, "Gender detection complete")
            logger.info("Gender detection finished for %d segments.", len(self.segments))
            self.finished.emit(self.segments)

        except Exception as exc:
            logger.exception("Gender detection failed.")
            self.failed.emit(str(exc))

    def _on_progress(self, value: int, message: str) -> None:
        self.progress_changed.emit(value, message)


def _dialogue_text_for_gender(seg: SubtitleSegment) -> str:
    """Build the best text for gender inference (original language preferred)."""
    original = (seg.original_text or "").strip()
    khmer = (seg.khmer_text or "").strip()
    if original and khmer and original != khmer:
        return f"{original}  |  {khmer}"
    return original or khmer
