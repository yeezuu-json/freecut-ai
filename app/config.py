import os
import json
from dataclasses import dataclass
from pathlib import Path

from app.paths import BASE_DIR, BUNDLED_CONFIG_FILE, CONFIG_DIR, CONFIG_FILE

@dataclass(frozen=True)
class TranscriptionModelConfig:
    label: str
    provider: str
    value: str

@dataclass(frozen=True)
class TranslationModelConfig:
    label: str
    provider: str
    value: str

@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_version: str
    debug: bool
    theme_path: Path
    fonts_path: Path
    log_level: str
    capcut_app_path: str

    deepinfra_api_key: str
    gemini_api_key: str
    transcription_provider: str
    transcription_model: str
    transcription_language: str

    transcription_models: list[TranscriptionModelConfig]

    translation_provider: str
    translation_model: str
    translation_source_language: str
    translation_target_language: str
    translation_models: list[TranslationModelConfig]


DEFAULT_CONFIG = {
    "app_name": "FreeCut AI",
    "app_version": "1.0.0",
    "debug": True,
    "theme_path": "assets/styles/theme.qss",
    "fonts_path": "assets/fonts",
    "log_level": "DEBUG",
    "capcut_app_path": "",

    "deepinfra_api_key": "",
    "gemini_api_key": "",
    "transcription_provider": "local",
    "transcription_model": "small",
    "transcription_language": "zh",
    "transcription_models": [
        {
            "label": "Local Tiny - Free",
            "provider": "local",
            "value": "tiny"
        },
        {
            "label": "Local Base - Free",
            "provider": "local",
            "value": "base"
        },
        {
            "label": "Local Small - Free",
            "provider": "local",
            "value": "small"
        },
        {
            "label": "Local Medium - Free",
            "provider": "local",
            "value": "medium"
        },
        {
            "label": "Local Large V3 - Free",
            "provider": "local",
            "value": "large-v3"
        },
        {
            "label": "DeepInfra Large V3 - Paid",
            "provider": "deepinfra",
            "value": "openai/whisper-large-v3"
        }
    ],

    "translation_provider": "gemini",
    "translation_model": "gemini-2.5-flash",
    "translation_source_language": "Chinese",
    "translation_target_language": "Khmer",
    "translation_models": [
        {
            "label": "Gemini 2.5 Flash - Best",
            "provider": "gemini",
            "value": "gemini-2.5-flash",
        },
        {
            "label": "Gemini 2.0 Flash - Fast",
            "provider": "gemini",
            "value": "gemini-2.0-flash",
        },
        {
            "label": "Local NLLB 600M - Free",
            "provider": "local_nllb",
            "value": "facebook/nllb-200-distilled-600M",
        },
        {
            "label": "Local NLLB 1.3B - Free Better",
            "provider": "local_nllb",
            "value": "facebook/nllb-200-distilled-1.3B",
        },
    ],
}


def create_default_config() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(DEFAULT_CONFIG, file, indent=4)


def load_config() -> AppConfig:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        # Seed user config from the bundled defaults (strips any API keys
        # that may have been accidentally left in the shipped config).
        if BUNDLED_CONFIG_FILE.exists() and BUNDLED_CONFIG_FILE != CONFIG_FILE:
            import shutil
            shutil.copy2(BUNDLED_CONFIG_FILE, CONFIG_FILE)
            # Strip any accidentally-shipped API keys from the seeded copy.
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    seed = json.load(f)
                seed["gemini_api_key"] = ""
                seed["deepinfra_api_key"] = ""
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(seed, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        else:
            create_default_config()

    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    api_key = (
        os.getenv("DEEPINFRA_API_KEY")
        or data.get("deepinfra_api_key", DEFAULT_CONFIG["deepinfra_api_key"])
    )

    gemini_api_key = (
        os.getenv("GEMINI_API_KEY")
        or data.get("gemini_api_key", DEFAULT_CONFIG["gemini_api_key"])
    )

    raw_models = data.get(
        "transcription_models",
        DEFAULT_CONFIG["transcription_models"],
    )

    transcription_models = [
        TranscriptionModelConfig(
            label=item.get("label", item.get("value", "Unknown")),
            provider=item.get("provider", "local"),
            value=item.get("value", ""),
        )
        for item in raw_models
        if item.get("value") and item.get("provider") and item.get("label")
    ]

    raw_translation_models = data.get(
        "translation_models",
        DEFAULT_CONFIG["translation_models"],
    )

    translation_models = [
        TranslationModelConfig(
            label=item.get("label", item.get("value", "Unknown")),
            provider=item.get("provider", "local_nllb"),
            value=item.get("value", ""),
        )
        for item in raw_translation_models
        if item.get("value")
    ]

    return AppConfig(
        app_name=data.get("app_name", DEFAULT_CONFIG["app_name"]),
        app_version=data.get("app_version", DEFAULT_CONFIG["app_version"]),
        debug=data.get("debug", DEFAULT_CONFIG["debug"]),
        theme_path=BASE_DIR / data.get("theme_path", DEFAULT_CONFIG["theme_path"]),
        fonts_path=BASE_DIR / data.get("fonts_path", DEFAULT_CONFIG["fonts_path"]),
        log_level=data.get("log_level", DEFAULT_CONFIG["log_level"]),
        capcut_app_path=data.get("capcut_app_path", DEFAULT_CONFIG["capcut_app_path"]),
        deepinfra_api_key=api_key,
        gemini_api_key=gemini_api_key,
        transcription_provider=data.get("transcription_provider", DEFAULT_CONFIG["transcription_provider"]),
        transcription_model=data.get("transcription_model", DEFAULT_CONFIG["transcription_model"]),
        transcription_language=data.get("transcription_language", DEFAULT_CONFIG["transcription_language"]),
        transcription_models=transcription_models,
        translation_provider=data.get("translation_provider", DEFAULT_CONFIG["translation_provider"]),
        translation_model=data.get("translation_model", DEFAULT_CONFIG["translation_model"]),
        translation_source_language=data.get("translation_source_language", DEFAULT_CONFIG["translation_source_language"]),
        translation_target_language=data.get("translation_target_language", DEFAULT_CONFIG["translation_target_language"]),
        translation_models=translation_models,
    )