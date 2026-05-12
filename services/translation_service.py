from typing import Callable

from app.config import AppConfig
from app.logger import get_logger
from services.local_nllb_translation_service import LocalNllbTranslationService


logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]


class TranslationService:
    def __init__(self, config: AppConfig):
        self.config = config

    def translate_texts(
        self,
        texts: list[str],
        provider: str,
        model: str,
        source_language: str,
        target_language: str,
        progress_callback: ProgressCallback | None = None,
    ) -> list[str]:
        logger.info(
            "Translation request provider=%s model=%s source=%s target=%s count=%s",
            provider,
            model,
            source_language,
            target_language,
            len(texts),
        )

        if provider == "local_nllb":
            service = LocalNllbTranslationService(
                model_name=model,
                source_language=source_language,
                target_language=target_language,
                progress_callback=progress_callback,
            )

            return service.translate_texts(texts)

        raise ValueError(f"Unsupported translation provider: {provider}")