import shutil
import time

from PySide6.QtCore import QObject, Signal, Slot

from app.config import AppConfig, load_config
from app.logger import setup_logger, get_logger
from app.paths import STORAGE_DIR, CACHE_DIR
from services.model_manager import ModelManager
from services.system_check_service import SystemCheckService
from utils.font_manager import load_fonts


class BootstrapWorker(QObject):
    progress_changed = Signal(int, str)
    status_changed   = Signal(str, str, object)   # key, message, ok(bool|None)
    finished         = Signal(object)              # AppConfig
    failed           = Signal(str)

    # ── entry point ──────────────────────────────────────────────────────────

    @Slot()
    def run(self):
        logger = None
        try:
            self._run_checks()
        except Exception as error:
            if logger:
                logger.exception("Bootstrap failed.")
            else:
                print("Bootstrap failed:", error)
            self.failed.emit(str(error))

    def _run_checks(self):
        # ── Config ──────────────────────────────────────────────────────────
        self.progress_changed.emit(8, "Loading configuration…")
        config = load_config()
        self.status_changed.emit("Config", "Loaded", True)
        time.sleep(0.1)

        # ── Logger ──────────────────────────────────────────────────────────
        self.progress_changed.emit(16, "Starting logger…")
        setup_logger(config.log_level)
        logger = get_logger(__name__)
        logger.info("Bootstrap started.")
        self.status_changed.emit("Logger", "Ready", True)
        time.sleep(0.1)

        # ── Fonts ────────────────────────────────────────────────────────────
        self.progress_changed.emit(24, "Loading fonts…")
        load_fonts(config.fonts_path)
        self.status_changed.emit("Fonts", "Loaded", True)
        time.sleep(0.1)

        # ── FFmpeg (required — raises on failure) ────────────────────────────
        self.progress_changed.emit(32, "Checking FFmpeg…")
        self._check_ffmpeg()
        time.sleep(0.1)

        # ── Storage directories ──────────────────────────────────────────────
        self.progress_changed.emit(42, "Preparing storage…")
        self._check_storage()
        time.sleep(0.1)

        # ── API keys (warn-only) ─────────────────────────────────────────────
        self.progress_changed.emit(52, "Checking API keys…")
        self._check_api_keys(config)
        time.sleep(0.1)

        # ── CapCut (warn-only) ───────────────────────────────────────────────
        self.progress_changed.emit(62, "Checking CapCut…")
        self._check_capcut(config)
        time.sleep(0.1)

        # ── AI Models (info-only — never blocks startup) ─────────────────────
        self.progress_changed.emit(74, "Checking AI models…")
        self._check_ai_models(config)
        time.sleep(0.1)

        # ── License (placeholder — future integration) ───────────────────────
        self.progress_changed.emit(88, "Checking license…")
        self.status_changed.emit("License", "Not required", None)
        time.sleep(0.05)

        # ── Done ─────────────────────────────────────────────────────────────
        self.progress_changed.emit(100, "Ready")
        logger.info("Bootstrap finished.")
        self.finished.emit(config)

    # ── individual checks ────────────────────────────────────────────────────

    def _check_ffmpeg(self):
        checker = SystemCheckService()
        ffmpeg_ok, ffmpeg_msg   = checker.check_ffmpeg()
        ffprobe_ok, ffprobe_msg = checker.check_ffprobe()

        if ffmpeg_ok and ffprobe_ok:
            self.status_changed.emit("FFmpeg", "Installed", True)
            return

        missing = ffmpeg_msg if not ffmpeg_ok else ffprobe_msg
        self.status_changed.emit("FFmpeg", missing, False)
        raise RuntimeError(
            "FFmpeg is required but was not found.\n\n"
            "Install it with:\n"
            "  macOS:   brew install ffmpeg\n"
            "  Windows: download from https://ffmpeg.org/download.html"
        )

    def _check_storage(self):
        try:
            STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            # Quick write-test
            test_file = STORAGE_DIR / ".boot_test"
            test_file.write_text("ok")
            test_file.unlink()
            self.status_changed.emit("Storage", "Ready", True)
        except Exception as exc:
            self.status_changed.emit("Storage", f"Error: {exc}", False)
            raise RuntimeError(f"Cannot write to storage directory: {exc}")

    def _check_api_keys(self, config: AppConfig):
        missing: list[str] = []

        needs_gemini = config.translation_provider in ("gemini",)
        needs_deepinfra = config.transcription_provider == "deepinfra"

        if needs_gemini and not config.gemini_api_key:
            missing.append("Gemini")
        if needs_deepinfra and not config.deepinfra_api_key:
            missing.append("DeepInfra")

        if missing:
            self.status_changed.emit(
                "API Keys",
                f"Missing: {', '.join(missing)}",
                False,   # show as warning (red) but don't raise
            )
        else:
            self.status_changed.emit("API Keys", "Configured", True)

    def _check_capcut(self, config: AppConfig):
        capcut_path = config.capcut_app_path

        if capcut_path and shutil.which(capcut_path):
            self.status_changed.emit("CapCut", "Found", True)
            return

        # Try the default macOS install location
        import sys
        from pathlib import Path
        if sys.platform == "darwin":
            default = Path("/Applications/CapCut.app")
            if default.exists():
                self.status_changed.emit("CapCut", "Found", True)
                return
        elif sys.platform == "win32":
            candidates = [
                Path(r"C:\Program Files\CapCut\CapCut.exe"),
                Path(r"C:\Program Files (x86)\CapCut\CapCut.exe"),
            ]
            if any(p.exists() for p in candidates):
                self.status_changed.emit("CapCut", "Found", True)
                return

        # Not found — warn but never block
        self.status_changed.emit("CapCut", "Not found", None)

    def _check_ai_models(self, config: AppConfig):
        manager = ModelManager()
        parts: list[str] = []

        if config.transcription_provider == "local":
            result = manager.check_local_whisper_model(config.transcription_model)
            parts.append("Whisper ✓" if result.is_ready else "Whisper ↓")

        if config.translation_provider == "local_nllb":
            result = manager.check_nllb_model(config.translation_model)
            parts.append("NLLB ✓" if result.is_ready else "NLLB ↓")

        if not parts:
            self.status_changed.emit("AI Models", "Cloud mode", True)
            return

        has_missing = any("↓" in p for p in parts)
        label = " | ".join(parts)
        if has_missing:
            label += "  (download when needed)"
        # ok=None → yellow — models missing is a soft warning, not an error
        self.status_changed.emit("AI Models", label, None if has_missing else True)
