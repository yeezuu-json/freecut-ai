from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "app.json"

ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
STYLES_DIR = ASSETS_DIR / "styles"
THEME_FILE = STYLES_DIR / "theme.qss"

LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "app.log"