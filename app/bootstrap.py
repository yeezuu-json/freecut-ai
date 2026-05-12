import time

from PySide6.QtCore import QObject, Signal, Slot

from app.config import AppConfig, load_config
from app.logger import setup_logger, get_logger
from services.model_manager import ModelManager
from services.system_check_service import SystemCheckService
from utils.font_manager import load_fonts


class BootstrapWorker(QObject):
    progress_changed = Signal(int, str)
    status_changed = Signal(str, str, object)
    finished = Signal(object)
    failed = Signal(str)

    @Slot()
    def run(self):
        logger = None

        try:
            self.progress_changed.emit(10, "Loading configuration...")
            config = load_config()
            self.status_changed.emit("Config", "Loaded", True)
            time.sleep(0.15)

            self.progress_changed.emit(20, "Starting logger...")
            setup_logger(config.log_level)
            logger = get_logger(__name__)
            logger.info("Application bootstrap started.")
            self.status_changed.emit("Logger", "Ready", True)
            time.sleep(0.15)

            self.progress_changed.emit(35, "Loading fonts...")
            load_fonts(config.fonts_path)
            self.status_changed.emit("Fonts", "Loaded", True)
            time.sleep(0.15)

            self.progress_changed.emit(50, "Checking FFmpeg...")
            self.check_ffmpeg()
            time.sleep(0.15)

            self.progress_changed.emit(70, "Checking AI models...")
            self.check_ai_models(config)
            time.sleep(0.15)

            self.progress_changed.emit(90, "Preparing window...")
            self.load_services(config)
            time.sleep(0.15)

            self.progress_changed.emit(100, "Ready")
            logger.info("Application bootstrap finished.")

            self.finished.emit(config)

        except Exception as error:
            if logger:
                logger.exception("Bootstrap failed.")
            else:
                print("Bootstrap failed:", error)

            self.failed.emit(str(error))

    def check_ffmpeg(self):
        checker = SystemCheckService()

        ffmpeg_ok, ffmpeg_message = checker.check_ffmpeg()
        ffprobe_ok, ffprobe_message = checker.check_ffprobe()

        if ffmpeg_ok and ffprobe_ok:
            self.status_changed.emit("FFmpeg", "Installed", True)
            return

        if not ffmpeg_ok:
            self.status_changed.emit("FFmpeg", ffmpeg_message, False)
            raise RuntimeError(
                "FFmpeg is required but was not found.\n\n"
                "Install it with:\n"
                "brew install ffmpeg"
            )

        if not ffprobe_ok:
            self.status_changed.emit("FFmpeg", ffprobe_message, False)
            raise RuntimeError(
                "FFprobe is required but was not found.\n\n"
                "Install FFmpeg with:\n"
                "brew install ffmpeg"
            )

    def check_ai_models(self, config: AppConfig):
        logger = get_logger(__name__)

        model_manager = ModelManager()

        messages: list[str] = []

        if config.transcription_provider == "local":
            whisper_status = model_manager.check_local_whisper_model(
                config.transcription_model
            )

            logger.info("Whisper model status: %s", whisper_status)

            if whisper_status.is_ready:
                messages.append("Whisper ready")
            else:
                messages.append("Whisper missing")

        if config.translation_provider == "local_nllb":
            translation_status = model_manager.check_nllb_model(
                config.translation_model
            )

            logger.info("Translation model status: %s", translation_status)

            if translation_status.is_ready:
                messages.append("Translation ready")
            else:
                messages.append("Translation missing")

        if not messages:
            self.status_changed.emit("AI Models", "Cloud/remote mode", True)
            return

        has_missing = any("missing" in message for message in messages)

        self.status_changed.emit(
            "AI Models",
            " | ".join(messages),
            not has_missing,
        )

    def load_services(self, config: AppConfig):
        logger = get_logger(__name__)

        # logger.info("API token mode: %s", config.api_token_mode)
        logger.info("Transcription provider: %s", config.transcription_provider)
        logger.info("Translation provider: %s", config.translation_provider)