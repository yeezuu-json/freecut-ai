from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_DIR = BASE_DIR / "config"
CONFIG_FILE = CONFIG_DIR / "app.json"

ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
STYLES_DIR = ASSETS_DIR / "styles"
THEME_FILE = STYLES_DIR / "theme.qss"

LOGS_DIR    = BASE_DIR / "logs"
LOG_FILE    = LOGS_DIR / "app.log"
STORAGE_DIR = BASE_DIR / "storage"

# ── Persistent per-user cache ─────────────────────────────────────────────────
# These directories survive app restarts so expensive AI steps can be reused.
CACHE_DIR = Path.home() / ".freecut-ai" / "cache"
PROJECTS_CACHE_DIR = CACHE_DIR / "projects"   # timeline JSON files
TTS_CACHE_DIR      = CACHE_DIR / "tts"        # edge-tts MP3 output
STEMS_CACHE_DIR    = CACHE_DIR / "stems"      # Demucs WAV stems