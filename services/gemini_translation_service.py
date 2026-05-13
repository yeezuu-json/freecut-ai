import os
import time
from typing import Callable

from app.logger import get_logger


logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]

# Max texts to translate in one API call.
_BATCH_SIZE = 20

# Models to try in order when the primary model is overloaded.
_FALLBACK_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]

_MAX_RETRIES = 4
_RETRY_BASE_DELAY = 3.0   # seconds; doubled on each retry


class GeminiTranslationService:
    """Translate subtitle texts using Google Gemini (gemini-2.5-flash or similar)."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        source_language: str = "Chinese",
        target_language: str = "Khmer",
        api_key: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.model_name = model_name
        self.source_language = source_language
        self.target_language = target_language
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.progress_callback = progress_callback

        if not self.api_key:
            raise ValueError(
                "Gemini API key not found. "
                "Set the GEMINI_API_KEY environment variable or add it to .env."
            )

    def translate_texts(self, texts: list[str]) -> list[str]:
        from google import genai

        client = genai.Client(api_key=self.api_key)

        results: list[str] = []
        total = len(texts)
        batches = [texts[i : i + _BATCH_SIZE] for i in range(0, total, _BATCH_SIZE)]

        for batch_idx, batch in enumerate(batches):
            base_pct = int(batch_idx / len(batches) * 90)
            self._emit(base_pct, f"Translating batch {batch_idx + 1}/{len(batches)}…")

            translated = self._translate_batch_with_retry(client, batch)
            results.extend(translated)

            if batch_idx < len(batches) - 1:
                time.sleep(0.5)

        self._emit(100, "Translation complete")
        return results

    # ── private ──────────────────────────────────────────────────────────────

    def _translate_batch_with_retry(self, client, texts: list[str]) -> list[str]:
        """Retry with exponential backoff, falling back through model chain on 503."""
        # Build list of (model, attempt) pairs to try.
        attempts = []
        for model in _FALLBACK_CHAIN:
            for _ in range(_MAX_RETRIES if model == self.model_name else 1):
                attempts.append(model)
            if model == self.model_name:
                continue  # already added retries above; don't add duplicates

        delay = _RETRY_BASE_DELAY
        last_error: Exception | None = None

        tried_models: set[str] = set()
        # Primary model retries first, then fallbacks.
        models_to_try = [self.model_name] + [
            m for m in _FALLBACK_CHAIN if m != self.model_name
        ]

        for model in models_to_try:
            retries = _MAX_RETRIES if model == self.model_name else 2
            delay = _RETRY_BASE_DELAY

            for attempt in range(1, retries + 1):
                try:
                    logger.debug(
                        "Gemini translate attempt %d/%d model=%s texts=%d",
                        attempt, retries, model, len(texts),
                    )
                    return self._translate_batch(client, texts, model=model)
                except Exception as exc:
                    last_error = exc
                    status = self._http_status(exc)
                    is_retryable = status in (429, 500, 503)

                    if not is_retryable:
                        raise

                    if attempt < retries:
                        self._emit(
                            0,
                            f"Model {model} busy (attempt {attempt}/{retries}), "
                            f"retrying in {int(delay)}s…",
                        )
                        logger.warning(
                            "Gemini %s: %s – retrying in %.0fs", model, exc, delay
                        )
                        time.sleep(delay)
                        delay = min(delay * 2, 30.0)
                    else:
                        logger.warning(
                            "Gemini %s exhausted retries, trying next model.", model
                        )

        raise RuntimeError(
            f"All Gemini models failed. Last error: {last_error}"
        )

    def _translate_batch(self, client, texts: list[str], model: str | None = None) -> list[str]:
        model = model or self.model_name
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))

        prompt = (
            f"You are a professional subtitle translator.\n"
            f"Translate the following {self.source_language} subtitles to {self.target_language}.\n"
            f"Rules:\n"
            f"- Return ONLY the translations, one per line, with the same numbering.\n"
            f"- Keep the translation natural and concise for subtitles.\n"
            f"- Do NOT add explanations, notes, or extra text.\n\n"
            f"{numbered}"
        )

        logger.debug("Gemini prompt model=%s (%d texts)", model, len(texts))

        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        raw = response.text.strip()
        logger.debug("Gemini raw response:\n%s", raw[:400])

        return self._parse_response(raw, expected_count=len(texts))

    @staticmethod
    def _http_status(exc: Exception) -> int | None:
        """Extract HTTP status code from a google-genai error, or None."""
        try:
            return int(exc.args[0].split()[0])
        except (IndexError, ValueError, AttributeError):
            pass
        # google.genai errors carry the status as the first positional arg sometimes
        if hasattr(exc, "status_code"):
            return exc.status_code
        msg = str(exc)
        for code in (429, 500, 503, 502):
            if str(code) in msg:
                return code
        return None

    @staticmethod
    def _parse_response(raw: str, expected_count: int) -> list[str]:
        """Extract the translation lines from the numbered response."""
        lines = raw.splitlines()
        translations: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            # Strip leading "1. " / "1) " etc.
            for sep in (". ", ") ", "、"):
                if stripped[0].isdigit():
                    parts = stripped.split(sep, 1)
                    if len(parts) == 2 and parts[0].isdigit():
                        stripped = parts[1].strip()
                        break
            translations.append(stripped)

        # If parsing produced the wrong number, fall back to raw lines.
        if len(translations) != expected_count:
            logger.warning(
                "Gemini parse mismatch: expected %d, got %d. Using raw lines.",
                expected_count,
                len(translations),
            )
            fallback = [l.strip() for l in raw.splitlines() if l.strip()]
            # Pad or trim to match expected count.
            while len(fallback) < expected_count:
                fallback.append("")
            return fallback[:expected_count]

        return translations

    def _emit(self, pct: int, msg: str) -> None:
        if self.progress_callback:
            self.progress_callback(pct, msg)
