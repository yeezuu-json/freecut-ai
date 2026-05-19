"""Infer speaker gender per subtitle line using Gemini."""
from __future__ import annotations

import os
import re
import time
from typing import Callable

from app.logger import get_logger
from models.subtitle_segment import SpeakerGender

logger = get_logger(__name__)

ProgressCallback = Callable[[int, str], None]

_BATCH_SIZE = 25
_FALLBACK_CHAIN = ["gemini-2.5-flash", "gemini-2.0-flash"]
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0

_VALID: set[str] = {"male", "female", "unknown"}


class GenderDetectionService:
    """Classify each subtitle line as male / female / unknown via Gemini."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        source_language: str = "Chinese",
        api_key: str | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.model_name = model_name
        self.source_language = source_language
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.progress_callback = progress_callback

        if not self.api_key:
            raise ValueError(
                "Gemini API key not found. Add it in Settings or set GEMINI_API_KEY."
            )

    def detect_genders(self, texts: list[str]) -> list[SpeakerGender]:
        from google import genai

        client = genai.Client(api_key=self.api_key)
        results: list[SpeakerGender] = []
        batches = [
            texts[i : i + _BATCH_SIZE] for i in range(0, len(texts), _BATCH_SIZE)
        ]

        for batch_idx, batch in enumerate(batches):
            base_pct = int(batch_idx / len(batches) * 90)
            self._emit(base_pct, f"Detecting gender… batch {batch_idx + 1}/{len(batches)}")

            labels = self._detect_batch_with_retry(client, batch)
            male_c = sum(1 for g in labels if g == "male")
            female_c = sum(1 for g in labels if g == "female")
            unknown_c = sum(1 for g in labels if g == "unknown")
            logger.debug(
                "Gender batch %d: %d lines → male:%d female:%d unknown:%d",
                batch_idx + 1,
                len(batch),
                male_c,
                female_c,
                unknown_c,
            )
            results.extend(labels)

            if batch_idx < len(batches) - 1:
                time.sleep(0.3)

        self._emit(100, "Gender detection complete")
        return results

    def _detect_batch_with_retry(self, client, texts: list[str]) -> list[SpeakerGender]:
        models_to_try = [self.model_name] + [
            m for m in _FALLBACK_CHAIN if m != self.model_name
        ]
        last_error: Exception | None = None

        for model in models_to_try:
            delay = _RETRY_BASE_DELAY
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    return self._detect_batch(client, texts, model=model)
                except Exception as exc:
                    last_error = exc
                    status = self._http_status(exc)
                    if status not in (429, 500, 503) or attempt >= _MAX_RETRIES:
                        break
                    time.sleep(delay)
                    delay = min(delay * 2, 20.0)

        raise RuntimeError(f"Gender detection failed. Last error: {last_error}")

    def _detect_batch(
        self, client, texts: list[str], model: str | None = None
    ) -> list[SpeakerGender]:
        model = model or self.model_name
        numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(texts))

        lang_hint = self._language_hint()
        prompt = (
            "You are analyzing subtitle dialogue from a film or drama.\n"
            f"{lang_hint}\n"
            "Each numbered line may show source dialogue, optionally followed by ' | ' "
            "and a Khmer translation. Use the SOURCE dialogue (before ' | ') for gender "
            "clues when present.\n"
            "For each line, infer the most likely SPEAKER gender.\n"
            "Use clues: pronouns (he/she, 他/她, គាត់, etc.), honorifics, names, "
            "how others address the speaker, and tone.\n"
            "Rules:\n"
            "- Reply with EXACTLY one word per line: male, female, or unknown\n"
            "- Use the same line numbers as the input (format: '1. male')\n"
            "- Prefer male or female when there is a reasonable clue; reserve unknown "
            "only for narration, crowd, sfx, or truly ambiguous lines\n"
            "- No explanations\n\n"
            f"{numbered}"
        )

        response = client.models.generate_content(model=model, contents=prompt)
        raw = self._response_text(response)
        if not raw:
            raise RuntimeError("Gemini returned an empty gender-detection response.")
        logger.debug("Gender detection raw response:\n%s", raw[:400])
        return self._parse_response(raw, expected_count=len(texts))

    @staticmethod
    def _response_text(response) -> str:
        """Extract text from a google-genai response safely."""
        text = getattr(response, "text", None)
        if text:
            return str(text).strip()
        try:
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                content = getattr(candidates[0], "content", None)
                parts = getattr(content, "parts", None) or []
                if parts:
                    part_text = getattr(parts[0], "text", None)
                    if part_text:
                        return str(part_text).strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _parse_response(raw: str, expected_count: int) -> list[SpeakerGender]:
        # Strip optional markdown fences from Gemini.
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```\w*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw.strip())

        labels: list[SpeakerGender] = []

        for line in raw.splitlines():
            stripped = line.strip().lower()
            if not stripped:
                continue
            # Strip leading "1. male" / "1) female"
            for sep in (". ", ") ", "、"):
                if stripped[0].isdigit():
                    parts = stripped.split(sep, 1)
                    if len(parts) == 2 and parts[0].isdigit():
                        stripped = parts[1].strip()
                        break
            # Take first token that looks like a label
            token = re.split(r"[\s,;]+", stripped)[0]
            if token in _VALID:
                labels.append(token)  # type: ignore[arg-type]
            elif "male" in stripped and "female" not in stripped:
                labels.append("male")
            elif "female" in stripped:
                labels.append("female")
            else:
                labels.append("unknown")

        if len(labels) != expected_count:
            logger.warning(
                "Gender parse mismatch: expected %d, got %d. Padding with unknown.",
                expected_count,
                len(labels),
            )
            while len(labels) < expected_count:
                labels.append("unknown")
            labels = labels[:expected_count]

        return labels

    @staticmethod
    def _http_status(exc: Exception) -> int | None:
        if hasattr(exc, "status_code"):
            return exc.status_code
        try:
            return int(exc.args[0].split()[0])
        except (IndexError, ValueError, AttributeError):
            pass
        msg = str(exc)
        for code in (429, 500, 503, 502):
            if str(code) in msg:
                return code
        return None

    def _language_hint(self) -> str:
        lang = (self.source_language or "").strip()
        if not lang or lang.lower() in {
            "auto", "auto (any language)", "any", "mixed", "multilingual",
        }:
            return (
                "Dialogue may be in Chinese, English, Khmer, or other languages "
                "(possibly mixed). Infer gender from each line's actual language."
            )
        return f"Dialogue is primarily in {lang}."

    def _emit(self, pct: int, msg: str) -> None:
        if self.progress_callback:
            self.progress_callback(pct, msg)
