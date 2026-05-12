from PySide6.QtCore import QObject, Signal, Slot

from app.config import AppConfig
from app.logger import get_logger
from models.subtitle_segment import SubtitleSegment
from services.translation_service import TranslationService


logger = get_logger(__name__)


class TranslationWorker(QObject):
    progress_changed = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        config: AppConfig,
        segments: list[SubtitleSegment],
        provider: str,
        model: str,
        source_language: str,
        target_language: str,
    ):
        super().__init__()

        self.config = config
        self.segments = segments
        self.provider = provider
        self.model = model
        self.source_language = source_language
        self.target_language = target_language
        self.translation_service = TranslationService(config)

    @Slot()
    def run(self):
        try:
            self.progress_changed.emit(5, "Preparing translation...")

            texts = [segment.original_text for segment in self.segments]

            translations = self.translation_service.translate_texts(
                texts=texts,
                provider=self.provider,
                model=self.model,
                source_language=self.source_language,
                target_language=self.target_language,
                progress_callback=self.emit_progress,
            )

            for segment, translated_text in zip(self.segments, translations):
                segment.khmer_text = translated_text

            self.progress_changed.emit(100, "Translation complete")

            logger.info("Translation finished. segments=%s", len(self.segments))

            self.finished.emit(self.segments)

        except Exception as error:
            logger.exception("Translation failed.")
            self.failed.emit(str(error))

    def emit_progress(self, value: int, message: str):
        self.progress_changed.emit(value, message)