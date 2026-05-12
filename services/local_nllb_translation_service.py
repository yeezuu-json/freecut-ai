from typing import Callable

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from app.logger import get_logger


logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]


class LocalNllbTranslationService:
    def __init__(
        self,
        model_name: str = "facebook/nllb-200-distilled-600M",
        source_language: str = "zho_Hans",
        target_language: str = "khm_Khmr",
        progress_callback: ProgressCallback | None = None,
    ):
        self.model_name = model_name
        self.source_language = source_language
        self.target_language = target_language
        self.progress_callback = progress_callback

        self.device = self.detect_device()

        self.emit_progress(10, f"Loading translation model: {model_name}")

        logger.info(
            "Loading NLLB translation model=%s device=%s source=%s target=%s",
            model_name,
            self.device,
            source_language,
            target_language,
        )

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

        self.model.to(self.device)
        self.model.eval()

        self.emit_progress(25, "Translation model loaded")

    def detect_device(self) -> str:
        if torch.backends.mps.is_available():
            return "mps"

        if torch.cuda.is_available():
            return "cuda"

        return "cpu"

    def emit_progress(self, value: int, message: str):
        if self.progress_callback:
            self.progress_callback(value, message)

    def translate_texts(self, texts: list[str]) -> list[str]:
        if not texts:
            return []

        translations: list[str] = []
        total = len(texts)

        self.tokenizer.src_lang = self.source_language

        forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(
            self.target_language
        )

        for index, text in enumerate(texts, start=1):
            clean_text = text.strip()

            if not clean_text:
                translations.append("")
                continue

            inputs = self.tokenizer(
                clean_text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
            ).to(self.device)

            with torch.no_grad():
                generated_tokens = self.model.generate(
                    **inputs,
                    forced_bos_token_id=forced_bos_token_id,
                    max_length=512,
                    num_beams=4,
                )

            translated = self.tokenizer.batch_decode(
                generated_tokens,
                skip_special_tokens=True,
            )[0]

            translations.append(translated.strip())

            progress = 25 + int((index / total) * 70)
            self.emit_progress(
                progress,
                f"Translating {index}/{total} segments...",
            )

        self.emit_progress(100, "Translation complete")

        return translations