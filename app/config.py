import json
from dataclasses import dataclass
from pathlib import Path

from app.paths import CONFIG_FILE, CONFIG_DIR, BASE_DIR


@dataclass(frozen=True)
class AppConfig:
    app_name: str
    app_version: str
    debug: bool
    theme_path: Path
    fonts_path: Path
    log_level: str


DEFAULT_CONFIG = {
    "app_name": "FreeCut AI",
    "app_version": "1.0.0",
    "debug": True,
    "theme_path": "assets/styles/theme.qss",
    "fonts_path": "assets/fonts",
    "log_level": "DEBUG",
}


def create_default_config() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(DEFAULT_CONFIG, file, indent=4)


def load_config() -> AppConfig:
    if not CONFIG_FILE.exists():
        create_default_config()

    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    return AppConfig(
        app_name=data.get("app_name", DEFAULT_CONFIG["app_name"]),
        app_version=data.get("app_version", DEFAULT_CONFIG["app_version"]),
        debug=data.get("debug", DEFAULT_CONFIG["debug"]),
        theme_path=BASE_DIR / data.get("theme_path", DEFAULT_CONFIG["theme_path"]),
        fonts_path=BASE_DIR / data.get("fonts_path", DEFAULT_CONFIG["fonts_path"]),
        log_level=data.get("log_level", DEFAULT_CONFIG["log_level"]),
    )