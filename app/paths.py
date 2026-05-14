import shutil
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

# When running as a PyInstaller bundle the app directory is read-only
# (macOS .app bundle, Windows Program Files, etc.).  User settings must be
# written to a writable location that survives app updates.
_USER_DATA_DIR = Path.home() / ".freecut-ai"

if getattr(sys, "frozen", False):
    # Bundled: store user config in ~/.freecut-ai/config/
    CONFIG_DIR  = _USER_DATA_DIR / "config"
    # Bundled default (read-only reference, never written to)
    _BUNDLED_CONFIG_DIR  = Path(sys._MEIPASS) / "config"  # type: ignore[attr-defined]
    BUNDLED_CONFIG_FILE  = _BUNDLED_CONFIG_DIR / "app.json"
else:
    # Dev: use the project config/ directory as usual
    CONFIG_DIR  = BASE_DIR / "config"
    BUNDLED_CONFIG_FILE = CONFIG_DIR / "app.json"  # same file in dev

CONFIG_FILE = CONFIG_DIR / "app.json"

ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
STYLES_DIR = ASSETS_DIR / "styles"
THEME_FILE = STYLES_DIR / "theme.qss"

# Built-in default voice samples for VoxCPM2 (read-only, shipped with the app).
DEFAULT_VOICES_DIR = ASSETS_DIR / "voices"

LOGS_DIR    = BASE_DIR / "logs"
LOG_FILE    = LOGS_DIR / "app.log"
STORAGE_DIR = BASE_DIR / "storage"

VOICE_LIBRARY_DIR = BASE_DIR / "voice_library"
VOICE_LIBRARY_INDEX = VOICE_LIBRARY_DIR / "index.json"

# ── FFmpeg / ffprobe resolution ───────────────────────────────────────────────
# When bundled with PyInstaller, ffmpeg/ffprobe live in a bin/ sub-directory
# next to the executable.  In dev they must be on PATH.

def _ffmpeg_bin_dir() -> Path:
    """Return the directory that contains the bundled ffmpeg/ffprobe binaries."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "bin"
    return BASE_DIR / "bin"


def find_ffmpeg() -> str:
    """Return the absolute path to ffmpeg, preferring the bundled copy."""
    ext = ".exe" if sys.platform == "win32" else ""
    bundled = _ffmpeg_bin_dir() / f"ffmpeg{ext}"
    if bundled.exists():
        return str(bundled)
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    raise FileNotFoundError(
        "ffmpeg not found. Add ffmpeg to PATH or place it in the bin/ folder."
    )


def find_ffprobe() -> str:
    """Return the absolute path to ffprobe, preferring the bundled copy."""
    ext = ".exe" if sys.platform == "win32" else ""
    bundled = _ffmpeg_bin_dir() / f"ffprobe{ext}"
    if bundled.exists():
        return str(bundled)
    on_path = shutil.which("ffprobe")
    if on_path:
        return on_path
    raise FileNotFoundError(
        "ffprobe not found. Add ffprobe to PATH or place it in the bin/ folder."
    )


# ── Persistent per-user cache ─────────────────────────────────────────────────
# These directories survive app restarts so expensive AI steps can be reused.
CACHE_DIR = Path.home() / ".freecut-ai" / "cache"
PROJECTS_CACHE_DIR = CACHE_DIR / "projects"   # timeline JSON files
TTS_CACHE_DIR      = CACHE_DIR / "tts"        # edge-tts MP3 output
STEMS_CACHE_DIR    = CACHE_DIR / "stems"      # Demucs WAV stems
MODEL_CACHE_DIR    = CACHE_DIR / "models"     # Model files