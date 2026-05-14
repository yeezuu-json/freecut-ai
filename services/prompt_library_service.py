"""Voice Design Prompt Library.

Stores user-saved voice design prompts alongside the built-in defaults.
Saved prompts are persisted to ~/.freecut-ai/voice_design_prompts.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.logger import get_logger

logger = get_logger(__name__)

_STORE_PATH = Path.home() / ".freecut-ai" / "voice_design_prompts.json"

# ── Built-in prompts ──────────────────────────────────────────────────────────
BUILTIN_PROMPTS: list[dict] = [
    # Male
    {"label": "♂ Young Male, Calm",     "text": "young man, calm and deep voice",            "gender": "male"},
    {"label": "♂ Young Male, Energetic", "text": "young man, energetic and cheerful",          "gender": "male"},
    {"label": "♂ Male, Angry",           "text": "man, angry and tense voice",                 "gender": "male"},
    {"label": "♂ Male, Authoritative",   "text": "middle-aged man, serious and authoritative", "gender": "male"},
    {"label": "♂ Old Male, Wise",        "text": "old man, gentle and wise voice",              "gender": "male"},
    # Female
    {"label": "♀ Young Female, Sweet",  "text": "young woman, gentle and sweet voice",         "gender": "female"},
    {"label": "♀ Young Female, Bright", "text": "young woman, cheerful and bright",            "gender": "female"},
    {"label": "♀ Female, Dramatic",     "text": "woman, emotional and dramatic voice",         "gender": "female"},
    {"label": "♀ Female, Warm",         "text": "middle-aged woman, warm and caring voice",    "gender": "female"},
    {"label": "♀ Old Female, Calm",     "text": "old woman, calm and wise voice",              "gender": "female"},
    # Neutral
    {"label": "🎙 Narrator, Neutral",   "text": "neutral narrator, clear and steady voice",   "gender": "neutral"},
    {"label": "👦 Child, Playful",      "text": "child, curious and playful voice",            "gender": "neutral"},
]


class PromptLibraryService:
    """CRUD for user-saved voice design prompts."""

    def __init__(self) -> None:
        _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ── public ───────────────────────────────────────────────────────────────

    def list_saved(self) -> list[dict]:
        """Return user-saved prompts (label + text)."""
        return self._load()

    def save_prompt(self, label: str, text: str) -> None:
        """Add or overwrite a saved prompt by label."""
        prompts = self._load()
        for p in prompts:
            if p["label"] == label:
                p["text"] = text
                self._write(prompts)
                return
        prompts.append({"label": label, "text": text})
        self._write(prompts)
        logger.info("Saved voice design prompt: %s", label)

    def delete_prompt(self, label: str) -> None:
        """Delete a saved prompt by label."""
        prompts = [p for p in self._load() if p["label"] != label]
        self._write(prompts)
        logger.info("Deleted voice design prompt: %s", label)

    # ── private ──────────────────────────────────────────────────────────────

    def _load(self) -> list[dict]:
        if not _STORE_PATH.exists():
            return []
        try:
            return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write(self, prompts: list[dict]) -> None:
        _STORE_PATH.write_text(
            json.dumps(prompts, ensure_ascii=False, indent=2), encoding="utf-8"
        )
